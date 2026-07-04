"""Module for tracking, calculating, and presenting market price momentum indicators."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, cast

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, model_validator

from src.analysis.base import BaseAnalyzer
from src.config import settings
from src.core.constants import ConfigKeys, DataColumns, TrendStatus
from src.data.base_client import BaseDataClient
from src.data.yfinance_client import YFinanceClient
from src.utils.logger_util import setup_logger


@dataclass(frozen=True)
class MomentumMetrics:
    """Read-only container for finalized computation metrics."""

    ticker: str
    status: TrendStatus
    current_price: float
    short_sma_val: float
    long_sma_val: float
    crossover_signal: float
    timestamp: datetime


def _get_default_short_window() -> int:
    """Helper factory function to read short window default from settings."""
    return int(settings.get_momentum_analysis()[ConfigKeys.WINDOW_SIZES][ConfigKeys.SHORT_WINDOW])


def _get_default_long_window() -> int:
    """Helper factory function to read long window default from settings."""
    return int(settings.get_momentum_analysis()[ConfigKeys.WINDOW_SIZES][ConfigKeys.LONG_WINDOW])


class MomentumConfig(BaseModel):
    """Parameter tracking definitions specific to SMA Momentum Indicators.

    Defaults are evaluated dynamically from the configuration TOML settings.
    """

    short_window: int = Field(default_factory=_get_default_short_window)
    long_window: int = Field(default_factory=_get_default_long_window)

    @model_validator(mode="after")
    def validate_windows(self) -> "MomentumConfig":
        """Verify boundaries ensuring short window properties do not eclipse long windows."""
        if self.short_window >= self.long_window:
            raise ValueError(f"Short window ({self.short_window}) cannot be >= Long window ({self.long_window})")
        return self


class MomentumAnalyzer(BaseAnalyzer[MomentumConfig]):
    """Executes vectorized financial momentum analysis over historical market metrics."""

    def __init__(self, default_ticker: str | None = None, data_client: BaseDataClient | None = None) -> None:
        """Initialize analyzer with custom dependency injections and fallback policies."""
        super().__init__(default_ticker=default_ticker)
        analysis_settings = settings.get_analysis_settings()

        default_section = analysis_settings[ConfigKeys.DEFAULT_SECTION]
        self._fallback_ticker: Final[str] = default_ticker or default_section[ConfigKeys.TICKER]
        self._start_date: Final[str] = default_section[ConfigKeys.START_DATE]

        # Decoupled Dependency Injection
        self.data_client: Final[BaseDataClient] = data_client or YFinanceClient()

    def run_analysis(
        self, config: MomentumConfig, ticker: str | None = None, df: pd.DataFrame | None = None
    ) -> MomentumMetrics:
        """Calculate Simple Moving Average (SMA) crossover indicators using a verified configuration schema.

        Supports fully stateless execution by accepting a pre-loaded DataFrame, or uses its
        injected data client to dynamically download data if omitted.
        """
        target_ticker: str = ticker or self._fallback_ticker
        s_win: int = config.short_window
        l_win: int = config.long_window

        # Fetch market data using the decoupled engine only if a pre-loaded df is not passed
        if df is None:
            df = self.data_client.fetch_data(target_ticker, self._start_date)

        with setup_logger(__name__) as logger:
            logger.debug(f"Executing vectorized metrics matrix: SMA({s_win}), SMA({l_win}) on {target_ticker}")

        # Explicit typing casts to satisfy static analysis checkers
        close_series = cast(pd.Series, df.loc[:, DataColumns.CLOSE])
        sma_short = cast(pd.Series, close_series.rolling(window=s_win).mean().astype(float))
        sma_long = cast(pd.Series, close_series.rolling(window=l_win).mean().astype(float))

        signal_vector = np.where(sma_short > sma_long, 1, 0)
        crossover_vector = np.diff(signal_vector, prepend=0)

        try:
            current_price = float(close_series.iloc[-1])
            last_short_val = float(sma_short.iloc[-1])
            last_long_val = float(sma_long.iloc[-1])
            last_crossover = float(crossover_vector[-1])
            is_bullish = bool(signal_vector[-1] == 1)
        except IndexError as err:
            raise ValueError(
                "Insufficient historical data points to populate calculation range matrix window."
            ) from err

        status: TrendStatus = TrendStatus.BULLISH if is_bullish else TrendStatus.BEARISH
        if np.isnan(last_short_val) or np.isnan(last_long_val):
            status = TrendStatus.UNKNOWN

        return MomentumMetrics(
            ticker=target_ticker,
            status=status,
            current_price=current_price,
            short_sma_val=last_short_val,
            long_sma_val=last_long_val,
            crossover_signal=last_crossover,
            timestamp=datetime.now(UTC),
        )


if __name__ == "__main__":
    analyzer = MomentumAnalyzer()
    try:
        # Self-test harness instantiates empty config, automatically loading defaults via factory methods
        default_config = MomentumConfig()
        metrics = analyzer.run_analysis(config=default_config)

        display_en = metrics.status.display_name(locale="en")
        display_fr = metrics.status.display_name(locale="fr")

        with setup_logger(__name__) as main_logger:
            main_logger.info(f"Local Runtime Test Execution Successful for {metrics.ticker}")
            main_logger.info(f"Trend Status (EN): {display_en}")
            main_logger.info(f"Trend Status (FR): {display_fr}")
            main_logger.info(f"Last Price: ${metrics.current_price:,.2f}")
            main_logger.info(f"Signal Flag: {metrics.crossover_signal} (Generated at {metrics.timestamp})")
    except Exception as e:
        with setup_logger(__name__) as main_logger:
            main_logger.critical(f"Self-test harness faulted: {e}", exc_info=True)
