"""Module for tracking, calculating, and presenting market price momentum indicators."""

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, model_validator

from src.analysis.base_analyzer import BaseAnalyzer
from src.config import settings
from src.core.constants import ConfigKeys, DataColumns, TrendStatus
from src.data.base_client import BaseDataClient
from src.data.market_data import MarketDataContext
from src.data.yfinance import YFinanceClient
from src.utils.logger_util import setup_logger


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


@dataclass(frozen=True)
class MomentumRun:
    """One Momentum calculation paired with retained market-data context."""

    metrics: MomentumMetrics
    market_data: MarketDataContext


def _get_default_short_window() -> int:
    """Read the configured default short SMA window."""
    return int(settings.get_momentum_analysis()[ConfigKeys.WINDOW_SIZES][ConfigKeys.SHORT_WINDOW])


def _get_default_long_window() -> int:
    """Read the configured default long SMA window."""
    return int(settings.get_momentum_analysis()[ConfigKeys.WINDOW_SIZES][ConfigKeys.LONG_WINDOW])


class MomentumConfig(BaseModel):
    """Parameter definitions specific to SMA momentum indicators.

    Defaults are evaluated dynamically from the configuration TOML settings.
    """

    short_window: int = Field(default_factory=_get_default_short_window, gt=0)
    long_window: int = Field(default_factory=_get_default_long_window, gt=0)

    @model_validator(mode="after")
    def validate_windows(self) -> "MomentumConfig":
        """Require a positive short window that is smaller than the long window."""
        if self.short_window >= self.long_window:
            raise ValueError(
                f"Short window ({self.short_window}) must be smaller than Long window ({self.long_window})."
            )
        return self


class MomentumAnalyzer(BaseAnalyzer[MomentumConfig]):
    """Execute vectorized financial momentum analysis over historical market metrics."""

    def __init__(self, default_ticker: str | None = None, data_client: BaseDataClient | None = None) -> None:
        """Initialize analyzer with custom dependency injections and fallback policies."""
        super().__init__(default_ticker=default_ticker)
        analysis_settings = settings.get_analysis_settings()

        default_section = analysis_settings[ConfigKeys.DEFAULT_SECTION]
        self._fallback_ticker: Final[str] = default_ticker or default_section[ConfigKeys.TICKER]
        self._start_date: Final[str] = default_section[ConfigKeys.START_DATE]

        self.data_client: Final[BaseDataClient] = data_client or YFinanceClient()

    def run_with_context(self, config: MomentumConfig, ticker: str | None = None) -> MomentumRun:
        """Fetch market data once, calculate metrics, and retain retrieval context."""
        target_ticker = ticker or self._fallback_ticker
        market_data = self.data_client.fetch_data_with_context(target_ticker, self._start_date)
        metrics = self.run_analysis(config=config, ticker=target_ticker, df=market_data.frame)
        return MomentumRun(metrics=metrics, market_data=market_data.context)

    def run_analysis(
        self,
        config: MomentumConfig,
        ticker: str | None = None,
        df: pd.DataFrame | None = None,
    ) -> MomentumMetrics:
        """Calculate Simple Moving Average crossover indicators for one price series.

        A pre-loaded frame keeps the calculation layer stateless. When a frame
        is not supplied, the injected client provides historical market data.
        """
        target_ticker = ticker or self._fallback_ticker
        s_win = config.short_window
        l_win = config.long_window

        if df is None:
            df = self.data_client.fetch_data(target_ticker, self._start_date)

        with setup_logger(__name__) as logger:
            logger.debug(f"Executing vectorized metrics matrix: SMA({s_win}), SMA({l_win}) on {target_ticker}")

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
            raise ValueError(
                "Insufficient historical data points to populate calculation range matrix window."
            ) from err

        if not math.isfinite(current_price):
            raise ValueError(f"Momentum latest close must be finite (received {current_price!r}).")

        short_sma_val = _finite_or_none(raw_short_sma)
        long_sma_val = _finite_or_none(raw_long_sma)

        if short_sma_val is None or long_sma_val is None:
            status = TrendStatus.UNKNOWN
            crossover_signal = None
        else:
            status = TrendStatus.BULLISH if short_sma_val > long_sma_val else TrendStatus.BEARISH
            crossover_signal = _finite_or_none(raw_crossover)

        return MomentumMetrics(
            ticker=target_ticker,
            status=status,
            current_price=current_price,
            short_sma_val=short_sma_val,
            long_sma_val=long_sma_val,
            crossover_signal=crossover_signal,
            timestamp=datetime.now(UTC),
        )


def _finite_or_none(value: float) -> float | None:
    """Return a finite value or explicit unavailability for a non-finite calculation."""
    return value if math.isfinite(value) else None


if __name__ == "__main__":
    analyzer = MomentumAnalyzer()
    try:
        default_config = MomentumConfig()
        metrics = analyzer.run_analysis(config=default_config)

        display_en = metrics.status.display_name(locale="en")
        display_fr = metrics.status.display_name(locale="fr")

        with setup_logger(__name__) as main_logger:
            main_logger.info(f"Local Runtime Test Execution Successful for {metrics.ticker}")
            main_logger.info(f"Trend Status (EN): {display_en}")
            main_logger.info(f"Trend Status (FR): {display_fr}")
            main_logger.info(f"Last Close: ${metrics.current_price:,.2f}")
            main_logger.info(
                "Signal Flag: %s (Generated at %s)",
                metrics.crossover_signal if metrics.crossover_signal is not None else "unavailable",
                metrics.timestamp,
            )
    except Exception as exc:
        with setup_logger(__name__) as main_logger:
            main_logger.critical(f"Self-test harness faulted: {exc}", exc_info=True)
