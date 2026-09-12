"""Reusable historical market-data payloads and retained observation context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol, runtime_checkable

import pandas as pd

from src.data.financial.provenance import SourceKind


@dataclass(frozen=True)
class HistoricalDataResolution:
    """Transient retrieval evidence reconstructed from the source or cache entry."""

    source_kind: SourceKind
    retrieved_at: datetime | None
    cached_at: datetime | None
    resolved_at: datetime
    cache_schema_version: int | None = None

    def __post_init__(self) -> None:
        """Reject ambiguous source and timestamp evidence."""
        if self.source_kind not in (SourceKind.PROVIDER, SourceKind.CACHE):
            raise ValueError("Historical resolution requires provider or cache origin.")
        for stamp in (self.retrieved_at, self.cached_at, self.resolved_at):
            if stamp is not None and stamp.utcoffset() is None:
                raise ValueError("Historical resolution timestamps must be timezone-aware.")
        if self.source_kind is SourceKind.CACHE and self.cache_schema_version is None:
            raise ValueError("Cached historical resolution requires a schema version.")


@runtime_checkable
class MarketDataProvider(Protocol):
    """Provider-neutral historical price boundary used by Momentum."""

    @property
    def provider_id(self) -> str | None:
        """Return the stable provider identifier when known."""
        ...

    def fetch_historical_data(self, ticker: str, start_date: str, end_date: str | None = None) -> HistoricalMarketData:
        """Return historical observations and retained retrieval context."""
        ...


@dataclass(frozen=True)
class MarketDataContext:
    """Metadata retained alongside a historical market-data frame."""

    provider_id: str | None = None
    observation_interval: str | None = None
    data_as_of: date | None = None
    currency: str | None = None
    observation_count: int | None = None
    price_adjustment: str | None = None

    def __post_init__(self) -> None:
        """Normalize short identifiers and reject impossible observation counts."""
        if self.provider_id is not None:
            provider_id = self.provider_id.strip()
            if not provider_id:
                raise ValueError("provider_id must be non-empty when supplied.")
            object.__setattr__(self, "provider_id", provider_id)

        if self.observation_interval is not None:
            interval = self.observation_interval.strip()
            if not interval:
                raise ValueError("observation_interval must be non-empty when supplied.")
            object.__setattr__(self, "observation_interval", interval)

        if self.currency is not None:
            currency = self.currency.strip().upper()
            if not currency:
                raise ValueError("currency must be non-empty when supplied.")
            object.__setattr__(self, "currency", currency)

        if self.price_adjustment is not None:
            price_adjustment = self.price_adjustment.strip().lower()
            if not price_adjustment:
                raise ValueError("price_adjustment must be non-empty when supplied.")
            object.__setattr__(self, "price_adjustment", price_adjustment)

        if self.observation_count is not None and self.observation_count < 0:
            raise ValueError("observation_count must be non-negative when supplied.")


@dataclass(frozen=True)
class HistoricalMarketData:
    """Historical price frame paired with the context known at retrieval time."""

    frame: pd.DataFrame
    context: MarketDataContext
    resolution: HistoricalDataResolution | None = None


def latest_observation_date(frame: pd.DataFrame) -> date | None:
    """Return the date represented by the final frame index when it is date-like."""
    if frame.empty:
        return None

    value = frame.index[-1]
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None
