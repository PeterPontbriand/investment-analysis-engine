"""Unit tests for validating the stateless MomentumAnalyzer indicator logic."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.analysis.momentum.momentum_analyzer import MomentumAnalyzer, MomentumConfig
from src.core.constants import TrendStatus
from src.data.base_client import DataFetchError


@pytest.fixture(autouse=True)
def mock_settings_config():
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
    # Patch the class methods rather than the instantiated instance proxy
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
    """Verify that MomentumConfig automatically populates its fields from TOML settings when empty."""
    # When initialized with no arguments, fields trigger their default_factory methods
    config = MomentumConfig()

    # Assert values match mock_settings_config values (2 and 5)
    assert config.short_window == 2
    assert config.long_window == 5


def test_momentum_analyzer_fallback_ticker_assignment() -> None:
    """Verify that MomentumAnalyzer assigns its default fallback ticker if initialized without one."""
    analyzer = MomentumAnalyzer()
    # Confirm it correctly extracted the default from configuration block
    assert analyzer._fallback_ticker == "BTC-USD"


@patch("src.data.yfinance_client.yf.download")
def test_fetch_market_data_handles_multiindex_flattening(
    mock_download: MagicMock,
) -> None:
    """Verify MultiIndex columns are properly handled and flattened by the data layer."""
    multi_cols = pd.MultiIndex.from_product([["Close", "Volume"], ["BTC-USD"]])
    multi_df = pd.DataFrame(np.random.randn(5, 2), columns=multi_cols)
    mock_download.return_value = multi_df

    analyzer = MomentumAnalyzer()
    df = analyzer.data_client.fetch_data("BTC-USD", start_date="2026-01-01")

    assert not isinstance(df.columns, pd.MultiIndex)
    assert "Close" in df.columns


@patch("src.data.yfinance_client.YFinanceClient.fetch_data")
def test_analyze_momentum_bullish(mock_fetch: MagicMock, bullish_dataframe: pd.DataFrame) -> None:
    """Verify that a sustained upward price trend correctly returns a BULLISH variant."""
    mock_fetch.return_value = bullish_dataframe

    analyzer = MomentumAnalyzer()
    metrics = analyzer.run_analysis(ticker="BTC-USD", config=MomentumConfig(short_window=2, long_window=5))

    assert metrics.ticker == "BTC-USD"
    assert metrics.status == TrendStatus.BULLISH
    assert metrics.current_price == 40.0
    assert metrics.short_sma_val > metrics.long_sma_val
    assert isinstance(metrics.timestamp, datetime)


@patch("src.data.yfinance_client.YFinanceClient.fetch_data")
def test_analyze_momentum_bearish(mock_fetch: MagicMock, bearish_dataframe: pd.DataFrame) -> None:
    """Verify that a sustained downward price trend correctly returns a BEARISH variant."""
    mock_fetch.return_value = bearish_dataframe

    analyzer = MomentumAnalyzer()
    metrics = analyzer.run_analysis(ticker="BTC-USD", config=MomentumConfig(short_window=2, long_window=5))

    assert metrics.status == TrendStatus.BEARISH
    assert metrics.current_price == 8.0
    assert metrics.short_sma_val < metrics.long_sma_val


@patch("src.data.yfinance_client.YFinanceClient.fetch_data")
def test_analyze_momentum_ticker_override_invariant(mock_fetch: MagicMock, sample_ohlcv_data: pd.DataFrame) -> None:
    """Verify custom ticker overrides default settings."""
    mock_fetch.return_value = sample_ohlcv_data

    analyzer = MomentumAnalyzer()
    metrics = analyzer.run_analysis(ticker="ETH-USD", config=MomentumConfig(short_window=3, long_window=7))

    assert metrics.ticker == "ETH-USD"


def test_analyze_momentum_window_validation() -> None:
    """Ensure a ValueError is safely raised if window constraints are broken."""
    analyzer = MomentumAnalyzer()

    with pytest.raises(ValueError, match="Short window.*cannot be >= Long window"):
        analyzer.run_analysis(config=MomentumConfig(short_window=20, long_window=10))


@patch("src.data.yfinance_client.YFinanceClient.fetch_data")
def test_analyze_momentum_empty_dataset_fault(mock_fetch: MagicMock) -> None:
    """Verify that completely empty datasets instantly trigger explicit validation failures."""
    mock_fetch.side_effect = DataFetchError("Target market ticker data resolved to empty: 'XYZ'")

    analyzer = MomentumAnalyzer()
    with pytest.raises(ValueError, match="Target market ticker data resolved to empty"):
        analyzer.run_analysis(ticker="XYZ", config=MomentumConfig())
