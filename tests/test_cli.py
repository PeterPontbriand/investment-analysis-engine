"""Unit tests for validating the Typer CLI controller commands and option routing."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.analysis.momentum.momentum_analyzer import MomentumMetrics, TrendStatus
from src.cli import app
from src.data.base_client import DataFetchError

runner = CliRunner()


@pytest.fixture
def mock_metrics() -> MomentumMetrics:
    """Generate static mock momentum results."""
    return MomentumMetrics(
        ticker="BTC-USD",
        status=TrendStatus.BULLISH,
        current_price=100.0,
        short_sma_val=98.0,
        long_sma_val=95.0,
        crossover_signal=1.0,
        timestamp=datetime.now(UTC),
    )


def test_cli_help() -> None:
    """Verify the main entry point help command outputs help text."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "momentum" in result.output.lower()
    assert "financial" in result.output.lower()


def test_cli_main_callback() -> None:
    """Verify invoking the root CLI callback returns successfully or exits with usage help."""
    result = runner.invoke(app, [])
    assert result.exit_code in (0, 2)


@patch("src.cli.MomentumAnalyzer.run_analysis")
def test_cli_momentum_success(
    mock_run: MagicMock, mock_metrics: MomentumMetrics, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify executing the momentum command with default arguments operates cleanly."""
    mock_run.return_value = mock_metrics
    with caplog.at_level("INFO"):
        result = runner.invoke(app, ["momentum"])
    assert result.exit_code == 0

    log_messages = [record.message for record in caplog.records]
    assert any("Analysis Complete for BTC-USD" in msg for msg in log_messages)
    assert any("Trend Status: BULLISH" in msg for msg in log_messages)


@patch("src.cli.MomentumAnalyzer.run_analysis")
def test_cli_momentum_unknown_never_logs_nan(mock_run: MagicMock, caplog: pytest.LogCaptureFixture) -> None:
    """Render unavailable Momentum metrics explicitly instead of exposing NaN."""
    mock_run.return_value = MomentumMetrics(
        ticker="SHORT",
        status=TrendStatus.UNKNOWN,
        current_price=12.0,
        short_sma_val=None,
        long_sma_val=None,
        crossover_signal=None,
        timestamp=datetime.now(UTC),
    )

    with caplog.at_level("INFO"):
        result = runner.invoke(app, ["momentum", "--ticker", "SHORT"])

    assert result.exit_code == 0
    log_text = "\n".join(record.message for record in caplog.records)
    assert "nan" not in log_text.lower()
    assert "SMA(50): unavailable" in log_text
    assert "SMA(200): unavailable" in log_text
    assert "Crossover Signal: unavailable" in log_text


@patch("src.cli.MomentumAnalyzer.run_analysis")
def test_cli_momentum_with_options(mock_run: MagicMock, mock_metrics: MomentumMetrics) -> None:
    """Verify CLI successfully routes custom override options to the analyzer configurations."""
    mock_run.return_value = mock_metrics
    result = runner.invoke(app, ["momentum", "--ticker", "AAPL", "-s", "10", "-l", "30"])
    assert result.exit_code == 0
    mock_run.assert_called_once()
    config_passed = mock_run.call_args[1]["config"]
    assert config_passed.short_window == 10
    assert config_passed.long_window == 30


@patch("src.cli.MomentumAnalyzer.run_analysis")
def test_cli_momentum_data_fetch_failure(mock_run: MagicMock, caplog: pytest.LogCaptureFixture) -> None:
    """Verify CLI gracefully isolates and prettifies DataFetchError exceptions."""
    mock_run.side_effect = DataFetchError("No market data was returned for ticker 'FCIM'.")

    with caplog.at_level("ERROR"):
        result = runner.invoke(app, ["momentum", "--ticker", "FCIM"])

    assert result.exit_code == 1
    log_messages = [record.message for record in caplog.records]
    assert any("Market data retrieval failed" in msg for msg in log_messages)
    assert any("FCIM" in msg for msg in log_messages)
    assert any("verify the ticker symbol" in msg.lower() for msg in log_messages)
    assert not any("resolved to empty" in msg.lower() for msg in log_messages)


@patch("src.cli.MomentumAnalyzer.run_analysis")
def test_cli_momentum_validation_failure(mock_run: MagicMock, caplog: pytest.LogCaptureFixture) -> None:
    """Verify CLI catches configuration ValueError constraints and exits with code 1."""
    mock_run.side_effect = ValueError("Short window cannot be >= Long window")
    with caplog.at_level("ERROR"):
        result = runner.invoke(app, ["momentum"])
    assert result.exit_code == 1

    log_messages = [record.message for record in caplog.records]
    assert any("Validation constraints breached" in msg for msg in log_messages)


@patch("src.cli.MomentumAnalyzer.run_analysis")
def test_cli_momentum_unexpected_failure(mock_run: MagicMock, caplog: pytest.LogCaptureFixture) -> None:
    """Verify CLI handles unhandled exceptions safely with code 1."""
    mock_run.side_effect = RuntimeError("Disk full")
    with caplog.at_level("ERROR"):
        result = runner.invoke(app, ["momentum"])
    assert result.exit_code == 1

    log_messages = [record.message for record in caplog.records]
    assert any("An unexpected error occurred" in msg for msg in log_messages)
