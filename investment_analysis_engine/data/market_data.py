"""Reusable historical market-data payloads and retained observation context."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, ClassVar, Final, Literal, Protocol, runtime_checkable

import numpy as np
import pandas as pd

from investment_analysis_engine.core.failure_codes import FailureReasonCode
from investment_analysis_engine.data.financial.provenance import SourceKind

HistoricalIndexKind = Literal["datetime", "date"]


def historical_index_kind(index: pd.Index[Any]) -> HistoricalIndexKind | None:
    """Classify a historical frame index against the one allowlist of date-like index kinds.

    The allowlist is exactly what providers return and the historical cache stores and restores:
    a ``DatetimeIndex`` (naive or timezone-aware, any resolution) and an index of Python ``date``
    values. Anything else, including values that merely parse as dates, is not date-like.
    """
    if isinstance(index, pd.DatetimeIndex):
        return "datetime"
    if len(index) > 0 and all(type(value) is date for value in index):
        return "date"
    return None


class SplitHistoryEndsBeforeRequestError(ValueError):
    """The requested day is later than the day the split-adjusted response was adjusted to."""


class NoEligibleObservationsError(ValueError):
    """No observation exists at or before the requested point-in-time boundary."""

    reason_code: ClassVar[FailureReasonCode] = FailureReasonCode.NO_ELIGIBLE_OBSERVATIONS


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

    def fetch_historical_data(
        self, ticker: str, start_date: str, end_date: str | None = None, *, use_cache: bool
    ) -> HistoricalMarketData:
        """Return historical observations and retained retrieval context.

        ``end_date`` is exclusive: an observation dated on it is not returned, matching yfinance's
        ``end``. ``None`` requests everything through the latest observation.
        """
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


SPLIT_ADJUSTED_PRICE: Final = "split_adjusted"
"""The ``price_adjustment`` of a close adjusted for splits and for nothing else (no dividend adjustment)."""


@dataclass(frozen=True)
class SplitEvent:
    """One split of the provider's history, dated at its ex-date.

    ``ratio`` is new shares per old share. A stock dividend appears as a fractional ratio (1.05) and cannot be told from
    a small split; it scales a share count exactly as a split does and is not issuance.
    """

    ex_date: date
    ratio: float

    def __post_init__(self) -> None:
        """Require a calendar date and a finite, positive ratio."""
        if type(self.ex_date) is not date:
            raise ValueError("A split's ex-date must be a calendar date.")
        if isinstance(self.ratio, bool) or not math.isfinite(self.ratio) or self.ratio <= 0:
            raise ValueError(f"A split ratio must be finite and positive (received {self.ratio!r}).")


@dataclass(frozen=True)
class SplitAdjustedHistory:
    """The split-adjusted close and the split history of one response.

    Both come from one response, so the adjustment date of the closes is the adjustment date of the events by
    construction, and a cached response stays consistent however old it is.

    Attributes:
        close: A frame with the single column ``Close``: split-adjusted, not dividend-adjusted, one row per session in
            ascending date order.
        events: The splits of the response ordered by ex-date, one per date.
        context: Retained context; ``price_adjustment`` names the split-only basis.
        adjustment_date: The date of the response: every split up to it is in the closes and in ``events``.
        resolution: Retrieval evidence when the response came through a client.
    """

    close: pd.DataFrame
    events: tuple[SplitEvent, ...]
    context: MarketDataContext
    adjustment_date: date
    resolution: HistoricalDataResolution | None = None

    def __post_init__(self) -> None:
        """Require the one-column frame, ordered unique events and the split-only basis."""
        if list(self.close.columns) != ["Close"] or self.close.empty:
            raise ValueError("A split-adjusted history holds a non-empty frame with the single column Close.")
        if not np.isfinite(self.close["Close"].to_numpy(dtype="float64")).all():
            raise ValueError("Split-adjusted closes must be finite.")
        if historical_index_kind(self.close.index) is None or not self.close.index.is_monotonic_increasing:
            raise ValueError("Split-adjusted closes need an ascending date-like index.")
        if self.context.price_adjustment != SPLIT_ADJUSTED_PRICE:
            raise ValueError("A split-adjusted history names the split-only price basis.")
        if type(self.adjustment_date) is not date:
            raise ValueError("The adjustment date must be a calendar date.")
        dates = [event.ex_date for event in self.events]
        if dates != sorted(set(dates)):
            raise ValueError("Split events must be ordered by ex-date, one per date.")
        if dates and dates[-1] > self.adjustment_date:
            raise ValueError("A split cannot follow the adjustment date.")


@runtime_checkable
class SplitAdjustedHistoryProvider(Protocol):
    """Provider-neutral boundary for the split-adjusted close and the split history."""

    def fetch_split_adjusted_history(self, ticker: str, start_date: str, *, use_cache: bool) -> SplitAdjustedHistory:
        """Return the closes from ``start_date`` through the latest session and every split in that range."""
        ...


def split_adjusted_close_on_or_before(history: SplitAdjustedHistory, as_of: date) -> tuple[date, float]:
    """Return the date and split-adjusted close of the last session on or before ``as_of``.

    Raises:
        SplitHistoryEndsBeforeRequestError: If ``as_of`` is later than the response's adjustment date: the response has
            no session on that day, and the last session before it would be silently an older one.
        NoEligibleObservationsError: If no session exists on or before ``as_of``.
    """
    if as_of > history.adjustment_date:
        raise SplitHistoryEndsBeforeRequestError(
            f"The split-adjusted history ends at its adjustment date {history.adjustment_date}, "
            f"before the requested {as_of}."
        )
    sessions = [
        value.date() if isinstance(value, datetime) else value  # pd.Timestamp is a datetime
        for value in history.close.index
    ]
    eligible = [position for position, session in enumerate(sessions) if session <= as_of]
    if not eligible:
        raise NoEligibleObservationsError(f"No close exists on or before {as_of}.")
    position = eligible[-1]
    return sessions[position], float(history.close["Close"].iloc[position])
