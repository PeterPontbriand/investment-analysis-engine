"""Exact-request historical caching with an independent live quote boundary."""

import logging
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pandas as pd

from src.data.base_client import BaseDataClient, DataFetchError
from src.data.financial.provenance import SourceKind
from src.data.market_data import HistoricalDataResolution, HistoricalMarketData
from src.data.quality import (
    FreshnessPolicy,
    HistoricalDataQualityError,
    HistoricalQualityPolicy,
    QualityContext,
    QualityOutcome,
    evaluate_freshness,
    evaluate_historical_quality,
)
from src.data.quality_reporting import publish_quality
from src.data.repositories.market_data import (
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
        clock: Callable[[], datetime] | None = None,
        quality_policy: HistoricalQualityPolicy | None = None,
    ) -> None:
        """Inject historical storage, explicit reuse policy, and an aware clock."""
        if ttl is not None and ttl < timedelta(0):
            raise ValueError("Historical cache TTL must be non-negative.")
        self._provider = provider
        self._repository = repository
        self._variant = request_variant
        self._ttl = ttl
        self._clock = clock or (lambda: datetime.now(UTC))
        self._quality_policy = quality_policy or HistoricalQualityPolicy()

    def _quality_error(
        self, data: HistoricalMarketData, input_id: str, *, cached_at: datetime | None = None
    ) -> str | None:
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
        """Return historical observations through the context-preserving cache."""
        return self.fetch_data_with_context(ticker, start_date, end_date).frame

    def fetch_data_with_context(
        self, ticker: str, start_date: str, end_date: str | None = None
    ) -> HistoricalMarketData:
        """Reuse an eligible exact snapshot or fetch and validate a full request."""
        provider_id = self.provider_id
        input_id = f"{ticker}:{provider_id}:{start_date}:{end_date}:{self._variant}"
        if not provider_id or not provider_id.strip() or not self._variant or not self._variant.strip():
            logger.debug("Historical cache bypassed: provider or request variant is unavailable.")
            data = self._provider.fetch_historical_data(ticker, start_date, end_date)
            error = self._quality_error(data, input_id)
            if error is not None:
                raise DataFetchError(error)
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
        data = self._provider.fetch_historical_data(ticker, start_date, end_date)
        completed_at = self._now()
        error = self._quality_error(data, input_id)
        if error is not None:
            raise DataFetchError(error)
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

    def fetch_current_price(self, ticker: str) -> float:
        """Delegate every current quote to the provider's real quote boundary."""
        return self._provider.fetch_current_price(ticker)
