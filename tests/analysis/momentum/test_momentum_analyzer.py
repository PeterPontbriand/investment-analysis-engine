"""Unit tests for validating the stateless MomentumAnalyzer indicator logic."""

from collections.abc import Generator
from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.analysis.base_analyzer import AnalysisContext
from src.analysis.strategy.momentum.momentum_analyzer import MomentumAnalyzer, MomentumConfig, compute_momentum_metrics
from src.core.constants import TrendStatus
from src.data.base_client import DataFetchError
from src.data.market_data import HistoricalMarketData, MarketDataContext

_CONTEXT = AnalysisContext(as_of=None, executed_at=datetime(2026, 1, 20, tzinfo=UTC), use_cache=True)


@pytest.fixture(autouse=True)
def mock_settings_config() -> Generator[None, None, None]:
    """Stub out external TOML file reads by patching the ProjectSettings class methods."""
    mock_analysis = {
        "default": {
            "default_ticker": "BTC-USD",
            "data_start_date": "2026-01-01",
        }
    }
    mock_momentum = {
        "window_sizes": {
            "short_window": 2,
            "long_window": 5,
        }
    }
    with (
        patch("src.config.ProjectSettings.get_analysis_settings", return_value=mock_analysis),
        patch("src.config.ProjectSettings.get_momentum_analysis", return_value=mock_momentum),
    ):
        yield


@pytest.fixture
def sample_ohlcv_data() -> pd.DataFrame:
    """Generate basic base DataFrame structure mimicking standard yfinance layouts."""
    dates = pd.date_range(start="2026-01-01", periods=20, freq="D")
    data = {
        "Open": [100.0] * 20,
        "High": [102.0] * 20,
        "Low": [98.0] * 20,
        "Close": [100.0 + (i * 0.5) for i in range(20)],
        "Volume": [1000000] * 20,
    }
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def bullish_dataframe() -> pd.DataFrame:
    """Generate a mock DataFrame representing a golden cross (short SMA > long SMA)."""
    dates = pd.date_range(start="2026-01-01", periods=10, freq="D")
    data = {"Close": [10.0, 11.0, 12.0, 13.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0]}
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def bearish_dataframe() -> pd.DataFrame:
    """Generate a mock DataFrame representing a death cross (short SMA < long SMA)."""
    dates = pd.date_range(start="2026-01-01", periods=10, freq="D")
    data = {"Close": [40.0, 38.0, 35.0, 30.0, 25.0, 20.0, 15.0, 12.0, 10.0, 8.0]}
    return pd.DataFrame(data, index=dates)


def test_momentum_config_dynamic_factory_defaults() -> None:
    config = MomentumConfig()
    assert config.short_window == 2
    assert config.long_window == 5


def test_momentum_config_rejects_non_positive_windows() -> None:
    with pytest.raises(ValueError, match="greater than 0"):
        MomentumConfig(short_window=0, long_window=5)


def test_momentum_analyzer_fallback_ticker_assignment() -> None:
    analyzer = MomentumAnalyzer()
    assert analyzer._fallback_ticker == "BTC-USD"


@patch("src.data.yfinance.client.yf.download")
def test_fetch_market_data_handles_multiindex_flattening(mock_download: MagicMock) -> None:
    multi_cols = pd.MultiIndex.from_product([["Close", "Volume"], ["BTC-USD"]])
    multi_df = pd.DataFrame(np.random.randn(5, 2), columns=multi_cols)
    mock_download.return_value = multi_df

    analyzer = MomentumAnalyzer()
    df = analyzer.data_client.fetch_data("BTC-USD", start_date="2026-01-01")

    assert not isinstance(df.columns, pd.MultiIndex)
    assert "Close" in df.columns


def test_analyze_momentum_bullish(bullish_dataframe: pd.DataFrame) -> None:
    metrics = compute_momentum_metrics(
        df=bullish_dataframe,
        config=MomentumConfig(short_window=2, long_window=5),
        ticker="BTC-USD",
        timestamp=datetime(2026, 1, 20, tzinfo=UTC),
    )

    assert metrics.ticker == "BTC-USD"
    assert metrics.status == TrendStatus.BULLISH
    assert metrics.current_price == 40.0
    assert metrics.short_sma_val is not None
    assert metrics.long_sma_val is not None
    assert metrics.short_sma_val > metrics.long_sma_val
    assert isinstance(metrics.timestamp, datetime)


def test_analyze_momentum_bearish(bearish_dataframe: pd.DataFrame) -> None:
    metrics = compute_momentum_metrics(
        df=bearish_dataframe,
        config=MomentumConfig(short_window=2, long_window=5),
        ticker="BTC-USD",
        timestamp=datetime(2026, 1, 20, tzinfo=UTC),
    )

    assert metrics.status == TrendStatus.BEARISH
    assert metrics.current_price == 8.0
    assert metrics.short_sma_val is not None
    assert metrics.long_sma_val is not None
    assert metrics.short_sma_val < metrics.long_sma_val


def test_run_analysis_retains_market_metadata(bullish_dataframe: pd.DataFrame) -> None:
    market_data = HistoricalMarketData(
        frame=bullish_dataframe,
        context=MarketDataContext(
            provider_id="fixture-market",
            observation_interval="1d",
            data_as_of=date(2026, 1, 10),
            currency="USD",
            observation_count=10,
        ),
    )
    client = MagicMock()
    client.fetch_data_with_context.return_value = market_data
    analyzer = MomentumAnalyzer(data_client=client)

    run = analyzer.run_analysis(
        ticker="BTC-USD",
        config=MomentumConfig(short_window=2, long_window=5),
        context=_CONTEXT,
    )

    assert run.metrics.status is TrendStatus.BULLISH
    assert run.market_data == market_data.context
    client.fetch_data_with_context.assert_called_once_with("BTC-USD", "2026-01-01")


def test_insufficient_window_history_returns_unknown_without_nan() -> None:
    df = pd.DataFrame({"Close": [10.0, 11.0, 12.0]})

    metrics = compute_momentum_metrics(
        df=df,
        config=MomentumConfig(short_window=2, long_window=5),
        ticker="SHORT",
        timestamp=datetime(2026, 1, 20, tzinfo=UTC),
    )

    assert metrics.status is TrendStatus.UNKNOWN
    assert metrics.current_price == 12.0
    assert metrics.short_sma_val == pytest.approx(11.5)
    assert metrics.long_sma_val is None
    assert metrics.crossover_signal is None


def test_non_finite_latest_price_is_rejected() -> None:
    df = pd.DataFrame({"Close": [10.0, 11.0, float("nan")]})

    with pytest.raises(ValueError, match="Momentum latest close must be finite"):
        compute_momentum_metrics(
            df=df,
            config=MomentumConfig(short_window=2, long_window=3),
            ticker="BAD",
            timestamp=datetime(2026, 1, 20, tzinfo=UTC),
        )


def test_analyze_momentum_ticker_override_invariant(sample_ohlcv_data: pd.DataFrame) -> None:
    metrics = compute_momentum_metrics(
        df=sample_ohlcv_data,
        config=MomentumConfig(short_window=3, long_window=7),
        ticker="ETH-USD",
        timestamp=datetime(2026, 1, 20, tzinfo=UTC),
    )

    assert metrics.ticker == "ETH-USD"


def test_analyze_momentum_window_validation() -> None:
    with pytest.raises(ValueError, match="must be smaller than Long window"):
        MomentumConfig(short_window=20, long_window=10)


@patch("src.data.yfinance.client.YFinanceClient.fetch_data_with_context")
def test_analyze_momentum_empty_dataset_fault(mock_fetch: MagicMock) -> None:
    mock_fetch.side_effect = DataFetchError("No market data was returned for ticker 'XYZ'.")

    analyzer = MomentumAnalyzer()
    with pytest.raises(DataFetchError, match="No market data was returned"):
        analyzer.run_analysis(ticker="XYZ", config=MomentumConfig(), context=_CONTEXT)
