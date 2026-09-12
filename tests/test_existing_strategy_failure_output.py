"""Execution failures remain nonzero and machine-readable without leaking exceptions."""

import json
from datetime import UTC, datetime
from unittest.mock import patch

import pandas as pd
import pytest
from typer.testing import CliRunner

from src.cli import app
from src.data.market_data import HistoricalMarketData, MarketDataContext
from src.data.quality import HistoricalDataQualityError, QualityContext, evaluate_historical_quality


@pytest.mark.parametrize("command", ["momentum", "graham-number", "graham-growth", "fcf-growth"])
def test_execution_failure_json_is_sanitized(command: str) -> None:
    """All command resource boundaries translate unexpected failures consistently."""
    arguments = [command, "ACME", "--json"]
    if command == "graham-growth":
        arguments += ["--expected-growth", "5", "--aaa-yield", "4.4"]
    target = "src.cli._production_historical_client" if command == "momentum" else "src.cli._production_financial_cache"
    with patch(target, side_effect=RuntimeError("secret-token-and-private-path")):
        result = CliRunner().invoke(app, arguments)
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["result"] is None
    assert payload["reason_code"] == "execution_error"
    assert "secret-token" not in result.output
    assert "Traceback" not in result.output


def test_missing_ohlc_error_retains_field_and_date() -> None:
    """The invalid date is actionable without exposing raw provider data."""
    frame = pd.DataFrame({"Close": [1.0, float("nan")]}, index=pd.date_range("2026-09-09", periods=2))
    decisions = evaluate_historical_quality(
        HistoricalMarketData(frame, MarketDataContext()),
        context=QualityContext("ACME", datetime(2026, 9, 11, tzinfo=UTC)),
    )
    error = HistoricalDataQualityError(decisions, frame)
    with patch("src.cli._production_historical_client", side_effect=error):
        result = CliRunner().invoke(app, ["momentum", "ACME", "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert "Close at 2026-09-10" in payload["reason"]
    assert payload["diagnostics"][0]["rule"] == "historical.numeric"
