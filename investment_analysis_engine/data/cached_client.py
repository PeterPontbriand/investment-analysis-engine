"""Exact-request historical caching with an independent live quote boundary."""

import logging
from collections.abc import Callable
from dataclasses import replace
from datetime import date, datetime, timedelta

import pandas as pd

from investment_analysis_engine.data.base_client import BaseDataClient
from investment_analysis_engine.data.financial.provenance import SourceKind
from investment_analysis_engine.data.market_data import (
    SPLIT_ADJUSTED_PRICE,
    HistoricalDataResolution,
    HistoricalMarketData,
    SplitAdjustedHistory,
    SplitAdjustedHistoryProvider,
)
from investment_analysis_engine.data.quality import (
    FreshnessPolicy,
    HistoricalDataQualityError,
    HistoricalQualityPolicy,
    QualityContext,
    QualityOutcome,
    evaluate_freshness,
    evaluate_historical_quality,
)
from investment_analysis_engine.data.quality_reporting import publish_quality
from investment_analysis_engine.data.repositories.market_data import (
    MarketDataCacheKey,
    SQLiteMarketDataRepository,
    UnsupportedHistoricalDataError,
)

logger = logging.getLogger(__name__)


class CachedHistoricalDataClient(BaseDataClient):
    """Cache exact historical requests while borrowing the provider and repository.

    The caller supplies the provider configuration variant and TTL. None disables
    expiry; zero permits reuse only when cache age is non-positive. Unknown
    provider or variant identities and unsupported valid frames bypass storage.
    Other ranges are fetched in full, without stitching or stale error fallback.
    Production composition owns resource lifetime and selection of TTL defaults.
    """

    def __init__(  # noqa: PLR0913
        self,
        provider: BaseDataClient,
        repository: SQLiteMarketDataRepository,
        *,
        request_variant: str | None,
        ttl: timedelta | None,
        clock: Callable[[], datetime],
        quality_policy: HistoricalQualityPolicy | None = None,
        split_request_variant: str | None = None,
    ) -> None:
        """Inject historical storage, explicit reuse policy, and a required aware clock."""
        if ttl is not None and ttl < timedelta(0):
            raise ValueError("Historical cache TTL must be non-negative.")
        self._provider = provider
        self._repository = repository
        self._variant = request_variant
        self._ttl = ttl
        self._clock = clock
        self._quality_policy = quality_policy or HistoricalQualityPolicy()
        self._split_variant = split_request_variant

    def _quality_error(
        self, data: HistoricalMarketData, input_id: str, *, cached_at: datetime | None = None
    ) -> str | None:
        """Raise for fresh data that fails a rule; for a cached entry, return the failure reason or ``None``."""
        context = QualityContext(input_id, self._now())
        decisions = evaluate_historical_quality(data, context=context, policy=self._quality_policy)
        # Historical series have date labels, not publication timestamps. Only
        # cache residence age is evaluated here; fact availability is separate.
        decisions += evaluate_freshness(
            context=context, policy=FreshnessPolicy(cache_ttl=self._ttl), cached_at=cached_at
        )
        publish_quality(decisions)
        if cached_at is None and any(item.outcome is QualityOutcome.FAIL for item in decisions):
            raise HistoricalDataQualityError(decisions, data.frame)
        return next((item.reason for item in decisions if item.outcome is QualityOutcome.FAIL), None)

    @property
    def provider_id(self) -> str | None:
        """Retain the injected provider identity without relabeling cache hits."""
        return self._provider.provider_id

    def _now(self) -> datetime:
        now = self._clock()
        if now.utcoffset() is None:
            raise ValueError("Historical cache clock must be timezone-aware.")
        return now

    def fetch_data(self, ticker: str, start_date: str, end_date: str | None = None) -> pd.DataFrame:
        """Return historical observations through the context-preserving cache.

        This legacy entry point has no ``use_cache`` parameter of its own to forward; it always
        behaves as if caching were requested, matching this method's historical contract.
        """
        return self.fetch_data_with_context(ticker, start_date, end_date, use_cache=True).frame

    def fetch_data_with_context(
        self, ticker: str, start_date: str, end_date: str | None = None, *, use_cache: bool
    ) -> HistoricalMarketData:
        """Reuse an eligible exact snapshot or fetch and validate a full request.

        ``use_cache=False`` always fetches live and never reads or writes the repository. The
        wrapped raw provider's own ``fetch_historical_data`` call always forwards this same
        ``use_cache`` value unchanged: it has nothing of its own to skip today, but an outer
        caller's explicit "do not use any cache" must never be silently overridden by an inner
        layer, including a future one.
        """
        provider_id = self.provider_id
        input_id = f"{ticker}:{provider_id}:{start_date}:{end_date}:{self._variant}"
        if not use_cache:
            logger.debug("Historical cache bypassed: use_cache is False for this call.")
            data = self._provider.fetch_historical_data(ticker, start_date, end_date, use_cache=use_cache)
            self._quality_error(data, input_id)
            return self._provider_resolution(data)
        if not provider_id or not provider_id.strip() or not self._variant or not self._variant.strip():
            logger.debug("Historical cache bypassed: provider or request variant is unavailable.")
            data = self._provider.fetch_historical_data(ticker, start_date, end_date, use_cache=use_cache)
            self._quality_error(data, input_id)
            return self._provider_resolution(data)
        key = MarketDataCacheKey(
            ticker,
            provider_id,
            date.fromisoformat(start_date),
            None if end_date is None else date.fromisoformat(end_date),
            self._variant,
        )
        entry = self._repository.get(key)
        if entry is not None and self._quality_error(entry.data, input_id, cached_at=entry.cached_at) is None:
            return replace(
                entry.data,
                resolution=HistoricalDataResolution(
                    SourceKind.CACHE, entry.fetch_completed_at, entry.cached_at, self._now(), key.schema_version
                ),
            )
        data = self._provider.fetch_historical_data(ticker, start_date, end_date, use_cache=use_cache)
        completed_at = self._now()
        self._quality_error(data, input_id)
        try:
            original_retrieval = data.resolution.retrieved_at if data.resolution is not None else completed_at
            self._repository.put(key, data, fetch_completed_at=original_retrieval)
        except UnsupportedHistoricalDataError:
            logger.debug("Historical cache bypassed: frame representation is unsupported.")
        return self._provider_resolution(data, completed_at)

    def _provider_resolution(
        self, data: HistoricalMarketData, completed_at: datetime | None = None
    ) -> HistoricalMarketData:
        """Retain actual fetch completion without replacing original provider timing."""
        completed = completed_at or self._now()
        return replace(
            data,
            resolution=HistoricalDataResolution(
                SourceKind.PROVIDER,
                data.resolution.retrieved_at if data.resolution is not None else completed,
                None,
                completed,
            ),
        )

    def fetch_split_adjusted_history(
        self, ticker: str, start_date: str, *, use_cache: bool, adjusted_on: date | None = None
    ) -> SplitAdjustedHistory:
        """Return the split-adjusted close and split history from ``start_date``, reusing an eligible stored response.

        The response is stored as an entry of its own request variant, so it never shares an entry with the
        dividend-adjusted series, and carries its own adjustment date. A stored response is returned with its original
        adjustment date, however old: the closes and the splits of one response agree by construction.

        Args:
            ticker: The instrument.
            start_date: First calendar day requested (``YYYY-MM-DD``); the response runs through the latest session.
            use_cache: ``False`` always fetches and neither reads nor writes storage.
            adjusted_on: For the live path, the day the share count must be scaled to. A stored response adjusted on
                another day is refused and fetched again, because a split since then is in neither its closes nor its
                events.
        """
        provider = self._provider
        if not isinstance(provider, SplitAdjustedHistoryProvider):
            raise TypeError("The wrapped provider offers no split-adjusted history.")
        provider_id = self.provider_id
        variant = self._split_variant
        if not use_cache or not provider_id or not provider_id.strip() or not variant or not variant.strip():
            logger.debug("Split-history cache bypassed: caching is off or the provider or variant is unavailable.")
            return self._split_provider_resolution(
                provider.fetch_split_adjusted_history(ticker, start_date, use_cache=use_cache)
            )
        key = MarketDataCacheKey(ticker, provider_id, date.fromisoformat(start_date), None, variant)
        entry = self._repository.get(key)
        if (
            entry is not None
            and entry.split_history is not None
            and entry.data.context.price_adjustment == SPLIT_ADJUSTED_PRICE
            and (adjusted_on is None or entry.split_history.adjustment_date == adjusted_on)
            and not self._expired(entry.cached_at, f"{ticker}:{provider_id}:{start_date}:{variant}")
        ):
            return SplitAdjustedHistory(
                close=entry.data.frame,
                events=entry.split_history.events,
                context=entry.data.context,
                adjustment_date=entry.split_history.adjustment_date,
                resolution=HistoricalDataResolution(
                    SourceKind.CACHE, entry.fetch_completed_at, entry.cached_at, self._now(), key.schema_version
                ),
            )
        history = provider.fetch_split_adjusted_history(ticker, start_date, use_cache=use_cache)
        completed = self._now()
        try:
            retrieved = history.resolution.retrieved_at if history.resolution is not None else completed
            self._repository.put_split_history(key, history, fetch_completed_at=retrieved)
        except UnsupportedHistoricalDataError:
            logger.debug("Split-history cache bypassed: frame representation is unsupported.")
        return self._split_provider_resolution(history, completed)

    def _expired(self, cached_at: datetime, input_id: str) -> bool:
        """Return whether a stored response has outlived the cache TTL."""
        decisions = evaluate_freshness(
            context=QualityContext(input_id, self._now()),
            policy=FreshnessPolicy(cache_ttl=self._ttl),
            cached_at=cached_at,
        )
        publish_quality(decisions)
        return any(item.outcome is QualityOutcome.FAIL for item in decisions)

    def _split_provider_resolution(
        self, history: SplitAdjustedHistory, completed_at: datetime | None = None
    ) -> SplitAdjustedHistory:
        """Retain actual fetch completion without replacing original provider timing."""
        completed = completed_at or self._now()
        return replace(
            history,
            resolution=HistoricalDataResolution(
                SourceKind.PROVIDER,
                history.resolution.retrieved_at if history.resolution is not None else completed,
                None,
                completed,
            ),
        )

    def fetch_current_price(self, ticker: str) -> float:
        """Delegate every current quote to the provider's real quote boundary."""
        return self._provider.fetch_current_price(ticker)
