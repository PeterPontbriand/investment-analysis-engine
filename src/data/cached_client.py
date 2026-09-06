"""Exact-request historical caching with an independent live quote boundary."""

import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import numpy as np
import pandas as pd

from src.data.base_client import BaseDataClient, DataFetchError
from src.data.market_data import HistoricalMarketData
from src.data.repositories.market_data import (
    MarketDataCacheKey,
    SQLiteMarketDataRepository,
    UnsupportedHistoricalDataError,
)

logger = logging.getLogger(__name__)


def _validate_data(data: HistoricalMarketData) -> None:
    """Reject missing or non-finite observations even when storage is bypassed."""
    frame = data.frame
    if frame.empty or "Close" not in frame.columns:
        raise DataFetchError("Historical data must be non-empty and contain Close.")
    for column in ("Open", "High", "Low", "Close", "Adj Close", "Volume"):
        if column not in frame.columns:
            continue
        try:
            values = frame[column].to_numpy(dtype=float)
        except (TypeError, ValueError) as exc:
            raise DataFetchError("Historical observations must be numeric and finite.") from exc
        if not np.isfinite(values).all():
            raise DataFetchError("Historical observations must be numeric and finite.")


class CachedHistoricalDataClient(BaseDataClient):
    """Cache exact historical requests while borrowing the provider and repository.

    The caller supplies the provider configuration variant and TTL. None disables
    expiry; zero permits reuse only when cache age is non-positive. Unknown
    provider or variant identities and unsupported valid frames bypass storage.
    Other ranges are fetched in full, without stitching or stale error fallback.
    Production composition owns resource lifetime and selection of TTL defaults.
    """

    def __init__(
        self,
        provider: BaseDataClient,
        repository: SQLiteMarketDataRepository,
        *,
        request_variant: str | None,
        ttl: timedelta | None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Inject historical storage, explicit reuse policy, and an aware clock."""
        if ttl is not None and ttl < timedelta(0):
            raise ValueError("Historical cache TTL must be non-negative.")
        self._provider = provider
        self._repository = repository
        self._variant = request_variant
        self._ttl = ttl
        self._clock = clock or (lambda: datetime.now(UTC))

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
        if not provider_id or not provider_id.strip() or not self._variant or not self._variant.strip():
            logger.debug("Historical cache bypassed: provider or request variant is unavailable.")
            data = self._provider.fetch_historical_data(ticker, start_date, end_date)
            _validate_data(data)
            return data
        key = MarketDataCacheKey(
            ticker,
            provider_id,
            date.fromisoformat(start_date),
            None if end_date is None else date.fromisoformat(end_date),
            self._variant,
        )
        now = self._now()
        entry = self._repository.get(key)
        if entry is not None and (self._ttl is None or now - entry.cached_at <= self._ttl):
            return entry.data
        data = self._provider.fetch_historical_data(ticker, start_date, end_date)
        completed_at = self._now()
        _validate_data(data)
        try:
            self._repository.put(key, data, fetch_completed_at=completed_at)
        except UnsupportedHistoricalDataError:
            logger.debug("Historical cache bypassed: frame representation is unsupported.")
        return data

    def fetch_current_price(self, ticker: str) -> float:
        """Delegate every current quote to the provider's real quote boundary."""
        return self._provider.fetch_current_price(ticker)
