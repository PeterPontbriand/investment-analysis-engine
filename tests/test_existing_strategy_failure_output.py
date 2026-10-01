"""Execution failures remain nonzero and machine-readable without leaking exceptions."""

import json
from datetime import UTC, datetime
from unittest.mock import patch

import pandas as pd
import pytest
from typer.testing import CliRunner

from src.cli import app
from src.data.market_data import HistoricalMarketData, MarketDataContext, NoEligibleObservationsError
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


_NO_HISTORY_REASON = "No price history is available at or before the requested --as-of boundary."


def test_momentum_boundary_before_the_first_observation_is_input_unavailable_in_json() -> None:
    """ESC-24: an unavailable boundary is reported like Graham and FCF report unavailable inputs."""
    with patch("src.cli._production_historical_client", side_effect=NoEligibleObservationsError(_NO_HISTORY_REASON)):
        result = CliRunner().invoke(app, ["momentum", "ACME", "--as-of", "1990-01-01", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "input_unavailable"
    assert payload["reason_code"] == "no_eligible_observations"
    assert payload["reason"] == _NO_HISTORY_REASON
    assert payload["result"] is None
    assert payload["schema_version"] == 5


def test_momentum_boundary_before_the_first_observation_is_explained_in_text() -> None:
    with patch("src.cli._production_historical_client", side_effect=NoEligibleObservationsError(_NO_HISTORY_REASON)):
        result = CliRunner().invoke(app, ["momentum", "ACME", "--as-of", "1990-01-01"])

    assert result.exit_code == 1
    assert _NO_HISTORY_REASON in result.output
    assert "could not be analyzed" not in result.output
