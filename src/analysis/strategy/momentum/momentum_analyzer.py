"""Module for tracking, calculating, and presenting market price momentum indicators."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Final

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, model_validator

from src.analysis.base_analyzer import AnalysisContext, BaseAnalyzer, require_ticker
from src.config import settings
from src.core.constants import ConfigKeys, DataColumns, TrendStatus
from src.core.metric_result import MetricResult, MetricStatus, ReasonCode
from src.data.base_client import BaseDataClient
from src.data.financial.provenance import ResolvedInput, SourceKind
from src.data.financial.resolution_trace import ResolutionEvent, ResolutionOutcome, ResolutionStage, ResolutionTrace
from src.data.instrument_profile import InstrumentProfile
from src.data.market_data import HistoricalDataResolution, HistoricalMarketData, MarketDataContext, MarketDataProvider
from src.data.quality import HistoricalDataQualityError, QualityContext, QualityOutcome, evaluate_historical_quality
from src.data.quality_reporting import publish_quality
from src.data.yfinance import YFinanceClient


@dataclass(frozen=True)
class MomentumMetrics:
    """Read-only container for finalized computation metrics.

    Moving-average and crossover values are ``None`` when the available
    historical series cannot support the configured windows. Non-finite
    numeric sentinels are never exposed as valid result values.
    """

    ticker: str
    status: TrendStatus
    current_price: float
    short_sma_val: float | None
    long_sma_val: float | None
    crossover_signal: float | None
    timestamp: datetime
    rsi_result: MetricResult | None = None
    crossover_result: MetricResult | None = None

    @property
    def sma_50(self) -> MetricResult:
        """Standard result for the configured short SMA."""
        return _legacy_metric_result(self.short_sma_val, "Short SMA is unavailable.")

    @property
    def sma_200(self) -> MetricResult:
        """Standard result for the configured long SMA."""
        return _legacy_metric_result(self.long_sma_val, "Long SMA is unavailable.")

    @property
    def rsi_14(self) -> MetricResult:
        """Standard result for the configured RSI period."""
        return self.rsi_result or MetricResult.failure(
            MetricStatus.UNAVAILABLE, ReasonCode.INSUFFICIENT_HISTORY, "RSI was not retained."
        )


@dataclass(frozen=True)
class MomentumRun:
    """One Momentum calculation paired with retained market-data context."""

    metrics: MomentumMetrics
    market_data: MarketDataContext
    price_inputs: tuple[ResolvedInput, ...] = ()
    resolution_trace: ResolutionTrace = ResolutionTrace()
    instrument_profile: InstrumentProfile | None = None
    data_resolution: HistoricalDataResolution | None = None


def _get_default_short_window() -> int:
    """Read the configured default short SMA window."""
    return int(settings.get_momentum_analysis()[ConfigKeys.WINDOW_SIZES][ConfigKeys.SHORT_WINDOW])


def _get_default_long_window() -> int:
    """Read the configured default long SMA window."""
    return int(settings.get_momentum_analysis()[ConfigKeys.WINDOW_SIZES][ConfigKeys.LONG_WINDOW])


@dataclass(frozen=True)
class MomentumPolicy:
    """Typed home for Momentum calculation-window defaults."""

    short_window: int = _get_default_short_window()
    long_window: int = _get_default_long_window()
    rsi_period: int = 14

    def __post_init__(self) -> None:
        """Reject invalid window combinations."""
        if self.short_window <= 0 or self.long_window <= 0 or self.rsi_period <= 0:
            raise ValueError("Momentum windows and RSI period must be positive.")
        if self.short_window >= self.long_window:
            raise ValueError("Momentum short_window must be smaller than long_window.")


class MomentumConfig(BaseModel):
    """Parameter definitions specific to SMA momentum indicators.

    Defaults are evaluated dynamically from the configuration TOML settings.
    """

    short_window: int = Field(default_factory=_get_default_short_window, gt=0)
    long_window: int = Field(default_factory=_get_default_long_window, gt=0)
    rsi_period: int = Field(default=14, gt=0)

    @model_validator(mode="after")
    def validate_windows(self) -> MomentumConfig:
        """Require a positive short window that is smaller than the long window."""
        if self.short_window >= self.long_window:
            raise ValueError(
                f"Short window ({self.short_window}) must be smaller than Long window ({self.long_window})."
            )
        return self


class MomentumAnalyzer(BaseAnalyzer[MomentumConfig, MomentumRun]):
    """Execute vectorized financial momentum analysis over historical market metrics."""

    def __init__(
        self,
        default_ticker: str | None = None,
        data_client: BaseDataClient | None = None,
        market_data_provider: MarketDataProvider | None = None,
    ) -> None:
        """Initialize analyzer with custom dependency injections and fallback policies."""
        analysis_settings = settings.get_analysis_settings()

        default_section = analysis_settings[ConfigKeys.DEFAULT_SECTION]
        self._fallback_ticker: Final[str] = default_ticker or default_section[ConfigKeys.TICKER]
        self._start_date: Final[str] = default_section[ConfigKeys.START_DATE]

        client = data_client or YFinanceClient()
        self.data_client: Final[BaseDataClient] = client
        self.market_data_provider: Final[MarketDataProvider] = market_data_provider or _ClientProviderAdapter(client)

    def resolve_ticker(self, ticker: str | None) -> str:
        """Return the explicit ticker or this analyzer's configured fallback.

        A later change relocates this TOML-fallback lookup to the CLI layer and removes it
        from the analyzer entirely.
        """
        return ticker or self._fallback_ticker

    def run_analysis(self, ticker: str, config: MomentumConfig, context: AnalysisContext) -> MomentumRun:
        """Fetch market data once, calculate metrics, and retain retrieval context.

        The resolver checks and publishes data quality once, against the raw
        provider fetch. This method independently re-checks the same rules
        against the (possibly ``as_of``-truncated) frame actually handed to
        calculation, without publishing again — a fail-safe on the exact
        input, not a second independent telemetry event.
        """
        normalized_ticker = require_ticker(ticker)
        resolver = MomentumInputResolver(self.market_data_provider, clock=lambda: context.executed_at)
        resolved = resolver.resolve(
            ticker=normalized_ticker,
            start_date=self._start_date,
            as_of=context.as_of,
            effective_as_of=context.effective_as_of,
        )
        df = resolved.market_data.frame
        decisions = evaluate_historical_quality(
            HistoricalMarketData(df, MarketDataContext()),
            context=QualityContext(
                f"{normalized_ticker}:historical_close", context.executed_at, context.effective_as_of
            ),
        )
        failure = next((item for item in decisions if item.outcome is QualityOutcome.FAIL), None)
        if failure is not None:
            raise HistoricalDataQualityError(decisions, df)
        metrics = compute_momentum_metrics(
            df=df, config=config, ticker=normalized_ticker, timestamp=context.effective_as_of
        )
        trace = resolved.resolution_trace.append(
            ResolutionEvent(
                "momentum",
                ResolutionStage.DERIVATION,
                ResolutionOutcome.SUCCESS,
                "Calculated Momentum metrics from the point-in-time price series.",
            )
        )
        return MomentumRun(
            metrics=metrics,
            market_data=resolved.market_data.context,
            price_inputs=resolved.price_inputs,
            resolution_trace=trace,
            data_resolution=resolved.market_data.resolution,
        )


def compute_momentum_metrics(
    df: pd.DataFrame, config: MomentumConfig, ticker: str, timestamp: datetime
) -> MomentumMetrics:
    """Calculate Simple Moving Average crossover indicators for one price series.

    Genuinely pure: no quality check, no telemetry, no clock read, no
    logger. Takes a pre-loaded frame and the caller-sourced point-in-time
    ``timestamp`` this result describes.
    """
    s_win = config.short_window
    l_win = config.long_window

    close_series = df.loc[:, DataColumns.CLOSE]
    sma_short = close_series.rolling(window=s_win).mean().astype(float)
    sma_long = close_series.rolling(window=l_win).mean().astype(float)

    signal_vector = np.where(sma_short > sma_long, 1, 0)
    crossover_vector = np.diff(signal_vector, prepend=0)

    try:
        current_price = float(close_series.iloc[-1])
        raw_short_sma = float(sma_short.iloc[-1])
        raw_long_sma = float(sma_long.iloc[-1])
        raw_crossover = float(crossover_vector[-1])
    except IndexError as err:
        raise ValueError("Insufficient historical data points to populate calculation range matrix window.") from err

    if not math.isfinite(current_price):
        raise ValueError(f"Momentum latest close must be finite (received {current_price!r}).")

    short_sma_val = _metric_or_unavailable(raw_short_sma, s_win, len(close_series), "short SMA")
    long_sma_val = _metric_or_unavailable(raw_long_sma, l_win, len(close_series), "long SMA")
    rsi = _calculate_rsi(close_series, config.rsi_period)

    if short_sma_val.value is None or long_sma_val.value is None:
        status = TrendStatus.UNKNOWN
        crossover_signal = MetricResult.failure(
            MetricStatus.UNAVAILABLE,
            ReasonCode.INSUFFICIENT_HISTORY,
            "A crossover requires both configured moving averages.",
        )
    else:
        status = TrendStatus.BULLISH if short_sma_val.value > long_sma_val.value else TrendStatus.BEARISH
        crossover_signal = (
            MetricResult.ok(raw_crossover)
            if len(close_series) > l_win
            else MetricResult.failure(
                MetricStatus.UNAVAILABLE,
                ReasonCode.INSUFFICIENT_HISTORY,
                "A crossover requires both moving averages at two consecutive observations.",
            )
        )

    return MomentumMetrics(
        ticker=ticker,
        status=status,
        current_price=current_price,
        short_sma_val=short_sma_val.value,
        long_sma_val=long_sma_val.value,
        crossover_signal=crossover_signal.value,
        timestamp=timestamp,
        rsi_result=rsi,
        crossover_result=crossover_signal,
    )


def _metric_or_unavailable(value: float, required: int, actual: int, label: str) -> MetricResult:
    """Return a standard metric result without non-finite sentinels."""
    if math.isfinite(value):
        return MetricResult.ok(value)
    return MetricResult.failure(
        MetricStatus.UNAVAILABLE,
        ReasonCode.INSUFFICIENT_HISTORY,
        f"{label} requires {required} observations; {actual} were available.",
    )


def _legacy_metric_result(value: float | None, reason: str) -> MetricResult:
    """Expose legacy optional metrics through the standard result contract."""
    if value is not None:
        return MetricResult.ok(value)
    return MetricResult.failure(MetricStatus.UNAVAILABLE, ReasonCode.INSUFFICIENT_HISTORY, reason)


def _calculate_rsi(close: pd.Series[float], period: int) -> MetricResult:
    """Calculate a deterministic trailing RSI metric."""
    if len(close) <= period:
        return MetricResult.failure(
            MetricStatus.UNAVAILABLE,
            ReasonCode.INSUFFICIENT_HISTORY,
            f"RSI requires at least {period + 1} observations; {len(close)} were available.",
        )
    changes = close.diff()
    gains = float(changes.clip(lower=0).rolling(period).mean().iloc[-1])
    losses = float((-changes.clip(upper=0)).rolling(period).mean().iloc[-1])
    if not math.isfinite(gains) or not math.isfinite(losses):
        return MetricResult.failure(
            MetricStatus.UNAVAILABLE,
            ReasonCode.INSUFFICIENT_HISTORY,
            "RSI could not be calculated from the available history.",
        )
    if losses == 0.0:
        return MetricResult.ok(100.0 if gains > 0.0 else 50.0)
    return MetricResult.ok(100.0 - (100.0 / (1.0 + (gains / losses))))


@dataclass(frozen=True)
class MomentumResolution:
    """Point-in-time historical inputs prepared for pure Momentum calculation."""

    market_data: HistoricalMarketData
    price_inputs: tuple[ResolvedInput, ...]
    resolution_trace: ResolutionTrace


class MomentumInputResolver:
    """Resolve and strictly truncate historical prices before calculation."""

    def __init__(self, provider: MarketDataProvider, *, clock: Callable[[], datetime]) -> None:
        """Initialize with an injected provider and retrieval clock.

        ``clock`` must resolve to the caller's own ``executed_at`` — the
        sole source for this resolver's retrieval timestamp and quality
        check. It is never fed a point-in-time boundary.
        """
        self._provider = provider
        self._clock = clock

    def resolve(
        self, *, ticker: str, start_date: str, effective_as_of: datetime, as_of: datetime | None = None
    ) -> MomentumResolution:
        """Fetch prices and retain only observations at or before ``as_of``."""
        trace = ResolutionTrace().append(
            ResolutionEvent(
                "historical_close",
                ResolutionStage.PROVIDER,
                ResolutionOutcome.ATTEMPTED,
                "Requested historical market observations from the configured provider.",
            )
        )
        data = self._provider.fetch_historical_data(ticker, start_date)
        decisions = evaluate_historical_quality(
            data, context=QualityContext(f"{ticker}:historical_close", self._clock(), analysis_as_of=effective_as_of)
        )
        publish_quality(decisions)
        failure = next((item for item in decisions if item.outcome is QualityOutcome.FAIL), None)
        if failure is not None:
            raise HistoricalDataQualityError(decisions, data.frame)
        frame = data.frame
        if as_of is not None:
            if as_of.tzinfo is None or as_of.tzinfo.utcoffset(as_of) is None:
                raise ValueError("Momentum as_of must be timezone-aware.")
            timestamps = pd.to_datetime(frame.index, utc=True)
            frame = frame.loc[timestamps <= pd.Timestamp(as_of)]
        if frame.empty:
            raise ValueError("No historical observations are eligible at the requested as_of boundary.")

        retrieved_at = self._clock()
        resolution = data.resolution
        provider_id = data.context.provider_id or self._provider.provider_id
        if provider_id is None:
            raise ValueError("Momentum market-data provider identity is required.")
        timestamps = pd.to_datetime(frame.index, utc=True)
        prices = tuple(
            ResolvedInput(
                field_name="historical_close",
                value=float(value),
                source_kind=resolution.source_kind if resolution is not None else SourceKind.PROVIDER,
                origin_source_kind=SourceKind.PROVIDER
                if resolution is not None and resolution.source_kind is SourceKind.CACHE
                else None,
                cache_schema_version=resolution.cache_schema_version if resolution is not None else None,
                resolved_at=retrieved_at,
                units="currency_per_share",
                currency=data.context.currency,
                provider_id=provider_id,
                provider_field="Close",
                observed_at=timestamp.to_pydatetime(),
                as_of=as_of,
                retrieved_at=resolution.retrieved_at if resolution is not None else None,
            )
            for timestamp, value in zip(timestamps, frame.loc[:, DataColumns.CLOSE], strict=True)
        )
        context = MarketDataContext(
            provider_id=provider_id,
            observation_interval=data.context.observation_interval,
            data_as_of=prices[-1].observed_at.date() if prices[-1].observed_at is not None else None,
            currency=data.context.currency,
            observation_count=len(frame),
            price_adjustment=data.context.price_adjustment,
        )
        trace = trace.append(
            ResolutionEvent(
                "historical_close",
                ResolutionStage.CACHE
                if resolution is not None and resolution.source_kind is SourceKind.CACHE
                else ResolutionStage.PROVIDER,
                ResolutionOutcome.SUCCESS,
                f"Resolved {len(frame)} historical observations with retained source provenance.",
            )
        ).append(
            ResolutionEvent(
                "historical_close",
                ResolutionStage.VALIDATION,
                ResolutionOutcome.SUCCESS,
                "Applied the requested point-in-time boundary before calculation.",
            )
        )
        return MomentumResolution(
            market_data=HistoricalMarketData(frame=frame, context=context, resolution=resolution),
            price_inputs=prices,
            resolution_trace=trace,
        )


class _ClientProviderAdapter:
    """Compatibility adapter from the legacy client to ``MarketDataProvider``."""

    def __init__(self, client: BaseDataClient) -> None:
        self._client = client

    @property
    def provider_id(self) -> str | None:
        """Return the legacy client's retained provider identity."""
        return self._client.provider_id

    def fetch_historical_data(self, ticker: str, start_date: str, end_date: str | None = None) -> HistoricalMarketData:
        """Delegate through the existing context-retaining call."""
        if end_date is None:
            return self._client.fetch_data_with_context(ticker, start_date)
        return self._client.fetch_data_with_context(ticker, start_date, end_date)
