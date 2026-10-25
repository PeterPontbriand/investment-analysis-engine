"""Momentum's result-level status through the commands: exit codes, streams, saved runs and refresh.

Each test drives the real command over a patched Yahoo history fetch, so the whole path from the provider call to the
stored run is the production one.
"""

import json
from datetime import UTC, date, datetime
from unittest.mock import patch

import pandas as pd
import pytest
from typer.testing import CliRunner

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.cli import app
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.data.market_data import HistoricalMarketData, MarketDataContext
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.workspace.repositories.analysis_runs import SQLiteAnalysisRunRepository
from investment_analysis_engine.workspace.repositories.watchlists import SQLiteWatchlistRepository
from investment_analysis_engine.workspace.runs import RunQuery
from tests._wiring import alias_for

pytestmark = pytest.mark.usefixtures("isolated_cli_settings", "stub_yahoo_identity_metadata")

runner = CliRunner()
FETCH = "investment_analysis_engine.data.yfinance.client.YFinanceClient.fetch_data_with_context"
FIXED_REASON = "Historical prices could not be retrieved from the market-data provider."
WINDOWS = ("--short-window", "2", "--long-window", "5", "--rsi-period", "2")


def _history(closes: list[float]) -> HistoricalMarketData:
    index = pd.date_range("2026-01-01", periods=len(closes), tz=UTC)
    return HistoricalMarketData(
        pd.DataFrame({"Close": closes}, index=index),
        MarketDataContext(
            provider_id="yfinance",
            observation_interval="1d",
            data_as_of=date(2026, 1, len(closes)),
            currency="USD",
            observation_count=len(closes),
        ),
    )


def _failure(kind: ProviderFailureKind | None = ProviderFailureKind.RATE_LIMITED) -> DataFetchError:
    return DataFetchError("secret library text", kind=kind, provider_id="yfinance" if kind else None)


# The direct command ----------------------------------------------------------------------------------------------


def test_a_known_trend_completes_with_exit_0_and_writes_to_standard_output() -> None:
    with patch(FETCH, return_value=_history([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])):
        result = runner.invoke(app, ["momentum", "ACME", "--no-cache", *WINDOWS])

    assert result.exit_code == 0
    assert result.stderr == ""
    assert "Bullish Trend" in result.stdout


def test_a_history_too_short_for_the_long_average_exits_1_and_writes_the_text_to_standard_error() -> None:
    with patch(FETCH, return_value=_history([1.0, 2.0, 3.0, 4.0])):
        concise = runner.invoke(app, ["momentum", "ACME", "--no-cache", *WINDOWS])
        details = runner.invoke(app, ["momentum", "ACME", "--no-cache", "--details", *WINDOWS])
        diagnostics = runner.invoke(app, ["momentum", "ACME", "--no-cache", "--diagnostics", *WINDOWS])

    assert (concise.exit_code, details.exit_code, diagnostics.exit_code) == (1, 1, 1)
    assert concise.stdout == details.stdout == ""
    assert "Unknown State" in concise.stderr
    assert "RSI (2 observations): 100.00" in concise.stderr, "RSI is still shown when it was computed."
    assert "Calculation and evidence" in details.stderr
    assert diagnostics.stderr == ""
    assert "Diagnostics" in diagnostics.stdout


def test_a_provider_failure_exits_1_and_names_no_provider_text() -> None:
    with patch(FETCH, side_effect=_failure()):
        concise = runner.invoke(app, ["momentum", "ACME", "--no-cache", *WINDOWS])
        as_json = runner.invoke(app, ["momentum", "ACME", "--no-cache", "--json", *WINDOWS])

    assert concise.exit_code == as_json.exit_code == 1
    assert concise.stdout == ""
    assert f"Reason: {FIXED_REASON}" in concise.stderr
    assert "secret library text" not in concise.stderr + as_json.stdout
    document = json.loads(as_json.stdout)
    assert document["status"] == "provider_error"
    assert document["result"] is None
    assert document["provider_failure"]["reason_code"] == "provider_rate_limited"


def test_no_data_before_the_boundary_is_unavailable_with_its_code() -> None:
    with patch(FETCH, return_value=_history([1.0])) as fetch:
        result = runner.invoke(app, ["momentum", "ACME", "--no-cache", "--json", "--as-of", "2019-06-01", *WINDOWS])

    document = json.loads(result.stdout)
    assert result.exit_code == 1
    assert (document["status"], document["reason_code"], document["result"]) == (
        "input_unavailable",
        "not_available_as_of",
        None,
    )
    fetch.assert_not_called()


def test_a_failed_quality_check_is_unavailable_with_a_text_reason_and_no_code() -> None:
    with patch(FETCH, return_value=_history([1.0, 2.0, float("nan"), 4.0, 5.0, 6.0])):
        result = runner.invoke(app, ["momentum", "ACME", "--no-cache", "--json", *WINDOWS])

    document = json.loads(result.stdout)
    assert result.exit_code == 1
    assert document["status"] == "input_unavailable"
    assert document["reason_code"] is None
    assert "finite" in document["reason"]


# --save-run ------------------------------------------------------------------------------------------------------


def _stored(settings: ProjectSettings) -> list[RunOutcome]:
    database = SQLiteDatabase(settings)
    try:
        return [item.status for item in SQLiteAnalysisRunRepository(database).list(RunQuery())]
    finally:
        database.close()


def test_save_run_stores_a_provider_failure_as_a_failed_run_with_its_code(
    isolated_cli_settings: ProjectSettings,
) -> None:
    with patch(FETCH, side_effect=_failure()):
        result = runner.invoke(app, ["momentum", "ACME", "--no-cache", "--save-run", *WINDOWS])

    assert result.exit_code == 1
    assert "Saved Analysis Run:" in result.stderr
    database = SQLiteDatabase(isolated_cli_settings)
    try:
        (summary,) = SQLiteAnalysisRunRepository(database).list(RunQuery())
        run = SQLiteAnalysisRunRepository(database).get(summary.analysis_run_id)
    finally:
        database.close()
    assert run is not None
    assert run.status is RunOutcome.FAILED
    assert run.failure_reason_code == "provider_rate_limited"
    assert run.result_evidence is not None


def test_save_run_stores_an_unavailable_run_for_a_short_history(isolated_cli_settings: ProjectSettings) -> None:
    with patch(FETCH, return_value=_history([1.0, 2.0, 3.0, 4.0])):
        result = runner.invoke(app, ["momentum", "ACME", "--no-cache", "--save-run", *WINDOWS])

    assert result.exit_code == 1
    assert _stored(isolated_cli_settings) == [RunOutcome.UNAVAILABLE]


# refresh ---------------------------------------------------------------------------------------------------------


def _seed(settings: ProjectSettings, name: str, tickers: list[str]) -> None:
    created = runner.invoke(app, ["watchlist", "create", name])
    assert created.exit_code == 0, created.output
    selection = MomentumSelection(short_window=2, long_window=5, rsi_period=2)
    database = SQLiteDatabase(settings)
    try:
        SQLiteWatchlistRepository(database, alias_for=alias_for).add_entries(
            name, [(ticker, selection) for ticker in tickers]
        )
    finally:
        database.close()


def _fetch_by_ticker(ticker: str, *_args: object, **_kwargs: object) -> HistoricalMarketData:
    if ticker == "BAD":
        raise _failure()
    if ticker == "SHORT":
        return _history([1.0, 2.0, 3.0, 4.0])
    return _history([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])


def test_refresh_stores_a_failed_run_with_its_batch_context_and_counts_every_outcome(
    isolated_cli_settings: ProjectSettings,
) -> None:
    _seed(isolated_cli_settings, "Mixed", ["GOOD", "BAD", "SHORT"])

    with patch(FETCH, side_effect=_fetch_by_ticker):
        result = runner.invoke(app, ["refresh", "Mixed", "--workers", "1", "--json"])

    document = json.loads(result.stdout)
    assert result.exit_code == 1
    assert document["counts"] == {"completed": 1, "failed": 1, "unavailable": 1}
    by_ticker = {item["ticker"]: item for item in document["results"]}
    assert by_ticker["BAD"]["status"] == "failed"
    assert by_ticker["BAD"]["reason_code"] == "provider_rate_limited"
    assert by_ticker["BAD"]["error"] is None
    assert by_ticker["BAD"]["saved"] is True
    assert by_ticker["SHORT"]["status"] == "unavailable"
    assert by_ticker["GOOD"]["status"] == "completed"

    database = SQLiteDatabase(isolated_cli_settings)
    try:
        repository = SQLiteAnalysisRunRepository(database)
        runs = {summary.ticker: repository.get(summary.analysis_run_id) for summary in repository.list(RunQuery())}
    finally:
        database.close()
    failed = runs["BAD"]
    assert failed is not None
    assert str(failed.refresh_id) == document["refresh_id"]
    assert failed.batch_position == 1
    assert failed.watchlist_id is not None
    assert failed.status is RunOutcome.FAILED


def test_refresh_no_save_reports_the_failed_outcome_with_its_code_and_stores_nothing(
    isolated_cli_settings: ProjectSettings,
) -> None:
    _seed(isolated_cli_settings, "Unsaved", ["BAD"])

    with patch(FETCH, side_effect=_failure(ProviderFailureKind.UNREACHABLE)):
        result = runner.invoke(app, ["refresh", "Unsaved", "--workers", "1", "--no-save", "--json"])

    document = json.loads(result.stdout)
    (job,) = document["results"]
    assert result.exit_code == 1
    assert (job["saved"], job["analysis_run_id"], job["status"]) == (False, None, "failed")
    assert job["reason_code"] == "provider_unreachable"
    assert job["error"] is None
    assert _stored(isolated_cli_settings) == []


def test_a_refresh_with_an_unavailable_short_history_exits_1_and_stores_the_run(
    isolated_cli_settings: ProjectSettings,
) -> None:
    _seed(isolated_cli_settings, "Short", ["SHORT"])

    with patch(FETCH, side_effect=_fetch_by_ticker):
        result = runner.invoke(app, ["refresh", "Short", "--workers", "1"])

    assert result.exit_code == 1
    assert "Counts: unavailable=1" in result.stdout
    assert _stored(isolated_cli_settings) == [RunOutcome.UNAVAILABLE]


def test_the_clock_is_not_consulted_for_the_stored_effective_time() -> None:
    """A run without metrics still carries the time it was evaluated at, which is its execution time."""
    before = datetime.now(UTC)
    with patch(FETCH, side_effect=_failure()):
        result = runner.invoke(app, ["momentum", "ACME", "--no-cache", "--json", *WINDOWS])

    effective = datetime.fromisoformat(json.loads(result.stdout)["effective_as_of"])
    assert before <= effective <= datetime.now(UTC)
