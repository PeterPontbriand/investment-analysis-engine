"""Focused tests for the watchlist (F1) and Analysis Run browsing (F2) CLI commands."""

import importlib
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest
import typer
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import update
from typer.testing import CliRunner

import investment_analysis_engine.cli_workspace
from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.cli import app
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.data.repositories.schema import analysis_runs
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.evaluation.fixtures.market_data import FixtureDataClient
from investment_analysis_engine.strategies.momentum.execution import run_momentum
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.strategy_wiring import STRATEGIES, run_spec_for
from investment_analysis_engine.workspace.capture import ExecutionCapture
from investment_analysis_engine.workspace.execution import execute
from investment_analysis_engine.workspace.repositories.analysis_runs import SQLiteAnalysisRunRepository
from investment_analysis_engine.workspace.repositories.watchlists import SQLiteWatchlistRepository
from investment_analysis_engine.workspace.requests import AnalysisRequest
from investment_analysis_engine.workspace.runs import AnalysisRun, RunQuery
from investment_analysis_engine.workspace.watchlists import WatchlistNotFoundError
from scripts.repository_root import REPOSITORY_ROOT
from tests._cli_helpers import isolated_cli_database, normalize_cli_output  # noqa: F401
from tests._wiring import encode_native

runner = CliRunner()


def _create(name: str) -> None:
    result = runner.invoke(app, ["watchlist", "create", name])
    assert result.exit_code == 0, result.output


def test_watchlist_create_starts_with_no_entries() -> None:
    """Amendment A1 (§12): creation no longer materializes any default selection."""
    result = runner.invoke(app, ["watchlist", "create", "My Watch"])
    assert result.exit_code == 0
    output = normalize_cli_output(result.output)
    assert "My Watch" in output
    assert "Entries (0):" in output
    assert "(none)" in output


def test_watchlist_create_duplicate_name_exits_1() -> None:
    _create("My Watch")
    result = runner.invoke(app, ["watchlist", "create", "My Watch"])
    assert result.exit_code == 1
    assert "already exists" in normalize_cli_output(result.output)


def test_watchlist_create_blank_name_is_a_usage_error() -> None:
    result = runner.invoke(app, ["watchlist", "create", "   "])
    assert result.exit_code == 1


def test_watchlist_list_reports_no_watchlists_then_summaries() -> None:
    result = runner.invoke(app, ["watchlist", "list"])
    assert result.exit_code == 0
    assert "No watchlists" in result.output

    _create("Alpha")
    _create("Beta")
    result = runner.invoke(app, ["watchlist", "list"])
    assert result.exit_code == 0
    assert "Alpha" in result.output
    assert "Beta" in result.output


def test_watchlist_show_empty_text_and_json() -> None:
    """Amendment A1's I1 checkpoint has no add/configure command yet; that is I2's job."""
    _create("My Watch")

    result = runner.invoke(app, ["watchlist", "show", "My Watch"])
    assert result.exit_code == 0
    assert "Entries (0):" in normalize_cli_output(result.output)

    result = runner.invoke(app, ["watchlist", "show", "My Watch", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["display_name"] == "My Watch"
    assert payload["entries"] == []


def test_watchlist_show_missing_exits_1() -> None:
    result = runner.invoke(app, ["watchlist", "show", "Nonexistent"])
    assert result.exit_code == 1
    assert "No watchlist named" in normalize_cli_output(result.output)


def test_watchlist_create_seeds_one_method_across_multiple_tickers() -> None:
    """Amendment A1 (§12): one command seeds a fresh watchlist with one method, many tickers."""
    result = runner.invoke(app, ["watchlist", "create", "Momentum Watch", "--analysis", "momentum", "AAPL", "MSFT"])
    assert result.exit_code == 0, result.output
    output = normalize_cli_output(result.output)
    assert "Entries (2):" in output
    assert "AAPL" in output
    assert "MSFT" in output
    assert "momentum:" in output
    assert "sma_crossover" not in output


def test_watchlist_create_seeding_requires_analysis_with_tickers() -> None:
    result = runner.invoke(app, ["watchlist", "create", "Bad", "AAPL"])
    assert result.exit_code == 1
    assert "--analysis is required" in normalize_cli_output(result.output)


def test_watchlist_create_seeding_requires_tickers_with_analysis() -> None:
    result = runner.invoke(app, ["watchlist", "create", "Bad", "--analysis", "momentum"])
    assert result.exit_code == 1
    assert "At least one TICKER is required" in normalize_cli_output(result.output)


def test_watchlist_create_rejects_an_unknown_analysis_alias() -> None:
    result = runner.invoke(app, ["watchlist", "create", "Bad", "--analysis", "bogus", "AAPL"])
    assert result.exit_code == 1
    assert "--analysis must be one of" in normalize_cli_output(result.output)


def test_watchlist_create_graham_growth_requires_its_assumptions() -> None:
    """Amendment A1 (§12): a method missing a required flag is a usage error, as the direct command produces."""
    result = runner.invoke(app, ["watchlist", "create", "Bad", "--analysis", "graham-growth", "AAPL"])
    assert result.exit_code == 1
    assert "--expected-growth" in normalize_cli_output(result.output)

    result = runner.invoke(
        app, ["watchlist", "create", "Bad", "--analysis", "graham-growth", "--expected-growth", "6.0", "AAPL"]
    )
    assert result.exit_code == 1
    assert "--aaa-yield" in normalize_cli_output(result.output)


def test_watchlist_create_graham_growth_seeds_with_its_assumptions() -> None:
    result = runner.invoke(
        app,
        [
            "watchlist",
            "create",
            "Growth Watch",
            "--analysis",
            "graham-growth",
            "--expected-growth",
            "6.0",
            "--aaa-yield",
            "4.4",
            "AAPL",
        ],
    )
    assert result.exit_code == 0, result.output
    output = normalize_cli_output(result.output)
    assert "graham-growth:" in output
    assert "graham_growth_value" not in output
    assert "expected_growth=6.0" in output
    assert "aaa_yield_override=4.4" in output


def test_watchlist_create_momentum_persists_as_of_and_no_cache() -> None:
    result = runner.invoke(
        app,
        [
            "watchlist",
            "create",
            "Point In Time",
            "--analysis",
            "momentum",
            "--as-of",
            "2026-08-01",
            "--no-cache",
            "AAPL",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(runner.invoke(app, ["watchlist", "show", "Point In Time", "--json"]).output)
    selection = payload["entries"][0]["selection"]
    assert selection["as_of"] == "2026-08-01T23:59:59.999999+00:00"
    assert selection["use_cache"] is False
    assert selection["config_schema_version"] == 2


def test_watchlist_create_rejects_invalid_momentum_windows() -> None:
    """Mirrors the direct ``momentum`` command's own window/RSI validation exactly."""
    cases = [
        (["--short-window", "0"], "--short-window must be positive"),
        (["--long-window", "0"], "--long-window must be positive"),
        (["--rsi-period", "0"], "--rsi-period must be positive"),
        (["--short-window", "30", "--long-window", "10"], "must be smaller than --long-window"),
    ]
    for flags, expected_message in cases:
        result = runner.invoke(app, ["watchlist", "create", "Bad Windows", "--analysis", "momentum", *flags, "AAPL"])
        assert result.exit_code == 1, result.output
        assert expected_message in normalize_cli_output(result.output)


def test_watchlist_create_fcf_growth_seeds_with_flags() -> None:
    result = runner.invoke(
        app,
        [
            "watchlist",
            "create",
            "FCF Watch",
            "--analysis",
            "fcf-growth",
            "--growth-years",
            "5",
            "--forward-policy",
            "hard-gate",
            "--classification-basis",
            "fcf-per-share",
            "--currency",
            "eur",
            "AAPL",
        ],
    )
    assert result.exit_code == 0, result.output
    output = normalize_cli_output(result.output)
    assert "fcf-growth:" in output
    assert "reported_fcf_eps_cagr" not in output
    assert "currency=EUR" in output


def test_watchlist_create_fcf_growth_rejects_an_invalid_growth_years() -> None:
    result = runner.invoke(
        app, ["watchlist", "create", "Bad FCF", "--analysis", "fcf-growth", "--growth-years", "7", "AAPL"]
    )
    assert result.exit_code == 1
    assert "--growth-years must be 3, 4, or 5" in normalize_cli_output(result.output)


def test_watchlist_create_fcf_growth_rejects_an_invalid_forward_policy() -> None:
    result = runner.invoke(
        app, ["watchlist", "create", "Bad FCF", "--analysis", "fcf-growth", "--forward-policy", "bogus", "AAPL"]
    )
    assert result.exit_code == 1
    assert "--forward-policy must be" in normalize_cli_output(result.output)


def test_watchlist_create_fcf_growth_rejects_an_invalid_classification_basis() -> None:
    result = runner.invoke(
        app,
        ["watchlist", "create", "Bad FCF", "--analysis", "fcf-growth", "--classification-basis", "bogus", "AAPL"],
    )
    assert result.exit_code == 1
    assert "--classification-basis must be" in normalize_cli_output(result.output)


def test_watchlist_create_fcf_growth_rejects_an_invalid_currency() -> None:
    result = runner.invoke(
        app, ["watchlist", "create", "Bad FCF", "--analysis", "fcf-growth", "--currency", "US", "AAPL"]
    )
    assert result.exit_code == 1
    assert "--currency must be a three-letter ISO 4217 code" in normalize_cli_output(result.output)


def test_watchlist_create_rejects_a_blank_seed_ticker() -> None:
    result = runner.invoke(app, ["watchlist", "create", "Blank Ticker", "--analysis", "momentum", "  "])
    assert result.exit_code == 1


def test_watchlist_add_selection_appends_and_allows_the_same_method_twice() -> None:
    """The amendment's headline capability: comparing one method under two configurations on one ticker."""
    _create("Compare")
    result = runner.invoke(app, ["watchlist", "add-selection", "Compare", "AAPL", "--analysis", "graham-number"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(
        app,
        [
            "watchlist",
            "add-selection",
            "Compare",
            "AAPL",
            "--analysis",
            "graham-number",
            "--bvps",
            "12.5",
        ],
    )
    assert result.exit_code == 0, result.output
    output = normalize_cli_output(result.output)
    assert "Entries (2):" in output
    assert "bvps_override=12.5" in output


def test_watchlist_add_selection_missing_watchlist_exits_1() -> None:
    result = runner.invoke(app, ["watchlist", "add-selection", "Nonexistent", "AAPL", "--analysis", "momentum"])
    assert result.exit_code == 1
    assert "No watchlist named" in normalize_cli_output(result.output)


def test_watchlist_add_selection_requires_at_least_one_ticker() -> None:
    _create("Empty Tickers")
    result = runner.invoke(app, ["watchlist", "add-selection", "Empty Tickers", "--analysis", "momentum"])
    assert result.exit_code == 2
    assert "Missing argument" in normalize_cli_output(result.output)


def test_watchlist_add_selection_rejects_a_blank_ticker() -> None:
    _create("Blank Ticker Add")
    result = runner.invoke(app, ["watchlist", "add-selection", "Blank Ticker Add", "  ", "--analysis", "momentum"])
    assert result.exit_code == 1


def test_watchlist_remove_entry_by_1_based_index_and_renumbers_survivors() -> None:
    _create("Trimmed")
    runner.invoke(app, ["watchlist", "add-selection", "Trimmed", "AAPL", "MSFT", "GOOG", "--analysis", "momentum"])

    result = runner.invoke(app, ["watchlist", "remove-entry", "Trimmed", "1"])
    assert result.exit_code == 0, result.output
    output = normalize_cli_output(result.output)
    assert output.startswith("Removed 1 entry from watchlist 'Trimmed'.")
    assert "Entries (2):" in output
    assert "[1] " in output  # MSFT renumbered down to display index 1
    assert "[2] " in output


def test_watchlist_remove_entry_out_of_range_exits_1() -> None:
    _create("Short List")
    runner.invoke(app, ["watchlist", "add-selection", "Short List", "AAPL", "--analysis", "momentum"])
    result = runner.invoke(app, ["watchlist", "remove-entry", "Short List", "5"])
    assert result.exit_code == 1
    assert "No entry at position" in normalize_cli_output(result.output)


def test_watchlist_remove_entry_rejects_an_index_below_1() -> None:
    _create("Zero Index")
    result = runner.invoke(app, ["watchlist", "remove-entry", "Zero Index", "0"])
    assert result.exit_code == 1
    assert "INDEX must be 1 or greater" in normalize_cli_output(result.output)


def test_watchlist_remove_entry_missing_watchlist_exits_1() -> None:
    result = runner.invoke(app, ["watchlist", "remove-entry", "Nonexistent", "1"])
    assert result.exit_code == 1
    assert "No watchlist named" in normalize_cli_output(result.output)


def test_watchlist_remove_rejects_a_blank_ticker() -> None:
    _create("Blank Ticker Remove")
    result = runner.invoke(app, ["watchlist", "remove-ticker", "Blank Ticker Remove", "  "])
    assert result.exit_code == 1


def test_watchlist_remove_removes_every_entry_for_a_ticker_across_methods() -> None:
    _create("Bulk By Ticker")
    runner.invoke(app, ["watchlist", "add-selection", "Bulk By Ticker", "AAPL", "MSFT", "--analysis", "momentum"])
    runner.invoke(app, ["watchlist", "add-selection", "Bulk By Ticker", "AAPL", "--analysis", "graham-number"])

    result = runner.invoke(app, ["watchlist", "remove-ticker", "Bulk By Ticker", "AAPL"])
    assert result.exit_code == 0, result.output
    confirmation, *listing_lines = result.output.splitlines()
    listing = " ".join(listing_lines)
    assert confirmation == "Removed 2 entries for AAPL from watchlist 'Bulk By Ticker'."
    assert "Entries (1):" in listing
    assert "MSFT" in listing
    assert "AAPL" not in listing


def test_watchlist_remove_of_an_absent_ticker_says_so_and_exits_0() -> None:
    _create("Nothing To Remove")
    runner.invoke(app, ["watchlist", "add-selection", "Nothing To Remove", "MSFT", "--analysis", "momentum"])

    result = runner.invoke(app, ["watchlist", "remove-ticker", "Nothing To Remove", "AAPL"])

    assert result.exit_code == 0, result.output
    output = normalize_cli_output(result.output)
    assert output.startswith("No entries for AAPL in watchlist 'Nothing To Remove'.")
    assert "Entries (1):" in output


def test_watchlist_remove_missing_watchlist_exits_1() -> None:
    result = runner.invoke(app, ["watchlist", "remove-ticker", "Nonexistent", "AAPL"])
    assert result.exit_code == 1
    assert "No watchlist named" in normalize_cli_output(result.output)


def test_watchlist_remove_requires_at_least_one_ticker() -> None:
    _create("No Tickers To Remove")
    result = runner.invoke(app, ["watchlist", "remove-ticker", "No Tickers To Remove"])
    assert result.exit_code == 2
    assert "Missing argument" in normalize_cli_output(result.output)


def test_watchlist_disable_removes_every_entry_for_a_method_across_tickers() -> None:
    _create("Bulk By Method")
    runner.invoke(app, ["watchlist", "add-selection", "Bulk By Method", "AAPL", "MSFT", "--analysis", "momentum"])
    runner.invoke(app, ["watchlist", "add-selection", "Bulk By Method", "AAPL", "--analysis", "graham-number"])

    result = runner.invoke(app, ["watchlist", "remove-method", "Bulk By Method", "--analysis", "momentum"])
    assert result.exit_code == 0, result.output
    output = normalize_cli_output(result.output)
    assert output.startswith("Removed 2 entries for momentum from watchlist 'Bulk By Method'.")
    assert "Entries (1):" in output
    assert "graham-number:" in output
    assert "momentum:" not in output
    assert "sma_crossover" not in output


def test_watchlist_disable_of_an_absent_method_says_so_and_exits_0() -> None:
    _create("No Such Method")
    runner.invoke(app, ["watchlist", "add-selection", "No Such Method", "MSFT", "--analysis", "momentum"])

    result = runner.invoke(app, ["watchlist", "remove-method", "No Such Method", "--analysis", "graham-number"])

    assert result.exit_code == 0, result.output
    assert normalize_cli_output(result.output).startswith("No entries for graham-number in watchlist 'No Such Method'.")


def test_watchlist_disable_missing_watchlist_exits_1() -> None:
    result = runner.invoke(app, ["watchlist", "remove-method", "Nonexistent", "--analysis", "momentum"])
    assert result.exit_code == 1
    assert "No watchlist named" in normalize_cli_output(result.output)


def test_watchlist_show_groups_by_ticker_by_default_and_by_method_on_request() -> None:
    _create("Grouped")
    runner.invoke(app, ["watchlist", "add-selection", "Grouped", "AAPL", "MSFT", "--analysis", "momentum"])
    runner.invoke(app, ["watchlist", "add-selection", "Grouped", "AAPL", "--analysis", "graham-number"])

    by_ticker = normalize_cli_output(runner.invoke(app, ["watchlist", "show", "Grouped"]).output)
    assert by_ticker.index("AAPL") < by_ticker.index("momentum") < by_ticker.index("graham-number")
    assert by_ticker.index("MSFT") > by_ticker.index("graham-number")  # MSFT is its own later group

    by_method = normalize_cli_output(
        runner.invoke(app, ["watchlist", "show", "Grouped", "--group-by", "method"]).output
    )
    assert by_method.index("momentum") < by_method.index("AAPL") < by_method.index("graham-number")


def test_watchlist_show_rejects_an_invalid_group_by() -> None:
    _create("Bad Group By")
    result = runner.invoke(app, ["watchlist", "show", "Bad Group By", "--group-by", "bogus"])
    assert result.exit_code == 1
    assert "--group-by must be" in normalize_cli_output(result.output)


def test_watchlist_show_json_uses_the_same_1_based_index_as_text_and_remove_entry() -> None:
    _create("Indexed")
    runner.invoke(app, ["watchlist", "add-selection", "Indexed", "AAPL", "MSFT", "--analysis", "momentum"])

    result = runner.invoke(app, ["watchlist", "show", "Indexed", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert [item["index"] for item in payload["entries"]] == [1, 2]
    assert "position" not in payload["entries"][0]


def test_watchlist_commands_have_no_config_file_flag() -> None:
    """Amendment A1 (§12) retires file-based --config entirely; it must not resurface."""
    for command_name in ("create", "add-selection"):
        result = runner.invoke(app, ["watchlist", command_name, "--help"])
        assert result.exit_code == 0
        assert "--config" not in result.output


def test_runs_list_reports_no_matches_then_summaries() -> None:
    result = runner.invoke(app, ["runs", "list"])
    assert result.exit_code == 0
    assert "No matching runs" in result.output


def test_runs_list_rejects_an_invalid_status_as_a_usage_error() -> None:
    result = runner.invoke(app, ["runs", "list", "--status", "bogus"])
    assert result.exit_code == 1


def test_runs_list_rejects_the_removed_cancelled_status_as_a_usage_error() -> None:
    result = runner.invoke(app, ["runs", "list", "--status", "cancelled"])
    assert result.exit_code == 1
    assert "cancelled" not in normalize_cli_output(result.output).split("must be one of:")[-1]


def test_runs_show_missing_id_exits_1() -> None:
    result = runner.invoke(app, ["runs", "show", "11111111-1111-4111-8111-111111111111"])
    assert result.exit_code == 1
    assert "No Analysis Run" in normalize_cli_output(result.output)


def test_runs_show_invalid_id_is_a_usage_error() -> None:
    result = runner.invoke(app, ["runs", "show", "not-a-uuid"])
    assert result.exit_code == 1
    output = normalize_cli_output(result.output)
    assert "not a shortened or partial value" in output
    assert "RUN_ID" in output


def test_runs_show_rejects_conflicting_view_flags() -> None:
    run_id = "11111111-1111-4111-8111-111111111111"
    result = runner.invoke(app, ["runs", "show", run_id, "--details", "--json"])
    assert result.exit_code == 1


class _FixtureClient(FixtureDataClient):
    """FixtureDataClient with a stable provider identity for the full resolver path."""

    @property
    def provider_id(self) -> str:
        return "fixture"


_DEFAULT_RUN_ID = UUID("33333333-3333-4333-8333-333333333333")


def _insert_momentum_run(
    settings: ProjectSettings,
    ticker: str = "AAPL",
    *,
    run_id: UUID | None = None,
    outcome: RunOutcome = RunOutcome.COMPLETED,
) -> AnalysisRun:
    """Insert one real, genuinely-executed Momentum run through the isolated database."""
    resolved_run_id = run_id if run_id is not None else _DEFAULT_RUN_ID
    database = SQLiteDatabase(settings)
    try:
        repository = SQLiteAnalysisRunRepository(database)
        selection = MomentumSelection(short_window=2, long_window=3, rsi_period=14)
        request = AnalysisRequest(ticker=ticker, selection=selection)

        def capture() -> ExecutionCapture:
            native = run_momentum(
                selection,
                ticker,
                _FixtureClient(),
                start_date="2026-01-01",
                executed_at=datetime.now(UTC),
                instrument_profile=None,
            )
            return ExecutionCapture(
                native_evidence=native,
                profile=None,
                outcome=outcome,
                failure_reason_code="execution_error" if outcome is RunOutcome.FAILED else None,
            )

        return execute(
            request,
            capture=capture,
            repository=repository,
            id_factory=lambda: resolved_run_id,
            clock=lambda: datetime(2026, 9, 19, 12, tzinfo=UTC),
            spec=run_spec_for(request.selection),
        )
    finally:
        database.close()


def test_runs_show_replays_a_real_persisted_run_and_exits_0_even_when_failed(
    isolated_cli_settings: ProjectSettings,
) -> None:
    """A pure successful read exits 0 even when it shows a failed historical run.

    A genuine execution failure is simulated here purely to exercise the "pure read
    exits 0 even for a failed historical run" contract rule; Momentum itself has no
    native failure status (see D1).
    """
    run = _insert_momentum_run(isolated_cli_settings, outcome=RunOutcome.FAILED)
    result = runner.invoke(app, ["runs", "show", str(run.analysis_run_id)])
    assert result.exit_code == 0
    assert "AAPL" in normalize_cli_output(result.output)


def _unreadable_run_message(run_id: UUID) -> str:
    return f"Analysis Run {run_id} could not be read: its stored record is malformed or does not match its summary."


_LIBRARY_TEXT = ("input_value", "validation error for", "errors.pydantic.dev", "Malformed or inconsistent")


def test_runs_show_reports_an_envelope_that_fails_validation_in_one_message(
    caplog: pytest.LogCaptureFixture,
    isolated_cli_settings: ProjectSettings,
) -> None:
    """Issue 113: the validation library's text goes to the log, never to the user."""
    run = _insert_momentum_run(isolated_cli_settings)
    database = SQLiteDatabase(isolated_cli_settings)
    try:
        with database.transaction() as connection:
            connection.execute(
                update(analysis_runs)
                .where(analysis_runs.c.analysis_run_id == str(run.analysis_run_id))
                .values(envelope_json='{"requested_config": {}}')
            )
    finally:
        database.close()
    message = _unreadable_run_message(run.analysis_run_id)

    text = runner.invoke(app, ["runs", "show", str(run.analysis_run_id)])
    as_json = runner.invoke(app, ["runs", "show", str(run.analysis_run_id), "--json"])

    assert text.exit_code == as_json.exit_code == 1
    assert text.stdout == ""
    assert as_json.stderr == ""
    assert text.stderr.strip() == message
    document = json.loads(as_json.stdout)
    assert (document["reason_code"], document["reason"]) == ("invalid_stored_run", message)
    for output in (text.stderr, as_json.stdout):
        assert not any(token in output for token in _LIBRARY_TEXT)
    assert any(record.exc_info and "validation error" in str(record.exc_info[1]) for record in caplog.records)


def test_runs_show_rejects_a_corrupted_stored_envelope_without_a_raw_traceback(
    isolated_cli_settings: ProjectSettings,
) -> None:
    """A row whose relational columns disagree with its own envelope is a sanitized exit 1.

    ``SQLiteAnalysisRunRepository.get`` raises a plain ``ValueError`` for this case
    (documented on the repository itself), distinct from the codec's typed
    `UnsupportedRunVersionError`/`InvalidStoredRunError` — `runs show` must catch
    both classes, or a corrupted row would print a raw Python traceback instead of
    the sanitized message the contract requires.
    """
    run = _insert_momentum_run(isolated_cli_settings)
    database = SQLiteDatabase(isolated_cli_settings)
    try:
        with database.transaction() as connection:
            connection.execute(
                update(analysis_runs)
                .where(analysis_runs.c.analysis_run_id == str(run.analysis_run_id))
                .values(method_version=99)
            )
    finally:
        database.close()

    result = runner.invoke(app, ["runs", "show", str(run.analysis_run_id)])
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)  # a deliberate typer.Exit, not an unhandled traceback
    assert "Traceback" not in result.output
    assert normalize_cli_output(result.output) == _unreadable_run_message(run.analysis_run_id)
    as_json = runner.invoke(app, ["runs", "show", str(run.analysis_run_id), "--json"])
    document = json.loads(as_json.stdout)
    assert (document["reason_code"], document["reason"]) == (
        "invalid_stored_run",
        _unreadable_run_message(run.analysis_run_id),
    )
    assert not any(token in as_json.stdout + result.output for token in _LIBRARY_TEXT)


def test_runs_show_rejects_an_unsupported_stored_method_version(isolated_cli_settings: ProjectSettings) -> None:
    """A self-consistent but unsupported stored method_version raises from the evidence codec.

    Unlike `projection_version` (a pydantic `Literal[1]`, so an unsupported value can
    never even round-trip through the repository), `method_version` is a plain
    `int`, so a genuinely stored, self-consistent row with an unsupported value is
    possible — and must surface as the same sanitized exit 1, not a raw traceback.
    """
    selection = MomentumSelection(short_window=2, long_window=3, rsi_period=14)
    native = run_momentum(
        selection,
        "AAPL",
        _FixtureClient(),
        start_date="2026-01-01",
        executed_at=datetime.now(UTC),
        instrument_profile=None,
    )
    run = AnalysisRun(
        analysis_run_id=UUID("66666666-6666-4666-8666-666666666666"),
        ticker="AAPL",
        analysis_id="momentum",
        method_id="sma_crossover",
        config_schema_version=2,
        requested_config=selection,
        started_at=datetime(2026, 9, 19, 12, tzinfo=UTC),
        completed_at=datetime(2026, 9, 19, 12, tzinfo=UTC),
        method_version=99,
        result_schema_version=1,
        evidence_codec_version=1,
        status=RunOutcome.COMPLETED,
        result_evidence=encode_native(native),
    )
    database = SQLiteDatabase(isolated_cli_settings)
    try:
        SQLiteAnalysisRunRepository(database).insert(run)
    finally:
        database.close()

    result = runner.invoke(app, ["runs", "show", str(run.analysis_run_id)])
    assert result.exit_code == 1
    assert "Unsupported Analysis Run method or version" in normalize_cli_output(result.output)


def test_runs_list_rejects_an_invalid_ticker_or_refresh_id_as_a_usage_error() -> None:
    result = runner.invoke(app, ["runs", "list", "--ticker", "   "])
    assert result.exit_code == 1

    result = runner.invoke(app, ["runs", "list", "--refresh-id", "not-a-uuid"])
    assert result.exit_code == 1
    output = normalize_cli_output(result.output)
    assert "not a shortened or partial value" in output
    assert "--refresh-id" in output


def test_runs_list_json_and_text_render_real_persisted_summaries(isolated_cli_settings: ProjectSettings) -> None:
    run = _insert_momentum_run(isolated_cli_settings)

    result = runner.invoke(app, ["runs", "list"])
    assert result.exit_code == 0
    assert str(run.analysis_run_id) in result.output
    assert "AAPL" in result.output

    result = runner.invoke(app, ["runs", "list", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload) == 1
    assert payload[0]["analysis_run_id"] == str(run.analysis_run_id)
    assert payload[0]["ticker"] == "AAPL"


def test_workspace_commands_report_a_sanitized_readiness_error(tmp_path: Path) -> None:
    """An un-migrated database is a sanitized exit 1, not a raw traceback."""
    url = f"sqlite:///{(tmp_path / 'stale.sqlite3').as_posix()}"
    config = Config(str(REPOSITORY_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "0001_persistence")  # older head: newer workspace tables never created

    with patch("investment_analysis_engine.cli_workspace.settings", ProjectSettings(database_url=url)):
        result = runner.invoke(app, ["watchlist", "list"])
    assert result.exit_code == 1
    assert "Traceback" not in result.output


def test_watchlist_help_and_runs_help_have_no_storage_side_effects() -> None:
    with patch.object(SQLiteDatabase, "__init__", side_effect=AssertionError("must not open a database for --help")):
        assert runner.invoke(app, ["watchlist", "--help"]).exit_code == 0
        assert runner.invoke(app, ["runs", "--help"]).exit_code == 0
        assert runner.invoke(app, ["watchlist", "show", "--help"]).exit_code == 0
        assert runner.invoke(app, ["watchlist", "create", "--help"]).exit_code == 0
        assert runner.invoke(app, ["watchlist", "add-selection", "--help"]).exit_code == 0
        assert runner.invoke(app, ["watchlist", "remove-entry", "--help"]).exit_code == 0
        assert runner.invoke(app, ["watchlist", "remove-ticker", "--help"]).exit_code == 0
        assert runner.invoke(app, ["watchlist", "remove-method", "--help"]).exit_code == 0
        assert runner.invoke(app, ["runs", "show", "--help"]).exit_code == 0


def test_module_import_has_no_storage_side_effects() -> None:
    with patch.object(SQLiteDatabase, "__init__", side_effect=AssertionError("import must not open a database")):
        importlib.reload(investment_analysis_engine.cli_workspace)


def test_the_retired_watchlist_command_names_are_rejected() -> None:
    """IR.6.1 (D1): `remove` and `disable` are gone outright, with no aliases or shims."""
    _create("Old Names")
    for arguments in (
        ["watchlist", "remove", "Old Names", "AAPL"],
        ["watchlist", "disable", "Old Names", "--analysis", "momentum"],
    ):
        result = runner.invoke(app, arguments)
        assert result.exit_code == 2, arguments
        assert "No such command" in normalize_cli_output(result.output)


def test_runs_list_method_option_is_rejected() -> None:
    """IR.6.1 (D4): `runs list --method` is replaced by `--analysis`, with no shim."""
    result = runner.invoke(app, ["runs", "list", "--method", "sma_crossover"])
    assert result.exit_code == 2
    assert "No such option" in normalize_cli_output(result.output)


def test_runs_list_filters_by_analysis_alias(isolated_cli_settings: ProjectSettings) -> None:
    run = _insert_momentum_run(isolated_cli_settings)

    for flag in ("--analysis", "-a"):
        result = runner.invoke(app, ["runs", "list", flag, "momentum"])
        assert result.exit_code == 0, result.output
        assert str(run.analysis_run_id) in result.output

    result = runner.invoke(app, ["runs", "list", "--analysis", "  Momentum "])
    assert result.exit_code == 0, result.output
    assert str(run.analysis_run_id) in result.output

    result = runner.invoke(app, ["runs", "list", "--analysis", "graham-number"])
    assert result.exit_code == 0, result.output
    assert "No matching runs." in result.output


_ALIASES = [item.alias for item in STRATEGIES]
_ALIAS_VOCABULARY = ", ".join(_ALIASES[:-1]) + ", or " + _ALIASES[-1]
_ALIAS_ERROR = f"--analysis must be one of: {', '.join(_ALIASES)}."


def test_runs_list_rejects_a_canonical_method_id_or_unknown_alias_as_a_usage_error() -> None:
    for value in ("sma_crossover", "bogus"):
        result = runner.invoke(app, ["runs", "list", "--analysis", value])
        assert result.exit_code == 1, value
        assert _ALIAS_ERROR in normalize_cli_output(result.output)


_ANALYSIS_HELP = [
    (["watchlist", "create", "--help"], "Method to seed: {}."),
    (["watchlist", "add-selection", "--help"], "Method: {}."),
    (["runs", "list", "--help"], "Filter by method: {}."),
]


@pytest.mark.parametrize(("args", "help_template"), _ANALYSIS_HELP)
def test_the_analysis_help_text_names_every_declared_alias_as_before(args: list[str], help_template: str) -> None:
    """The ``--analysis`` help is generated from the CLI tier and lists the declared aliases in declaration order."""
    result = runner.invoke(app, args, env={"COLUMNS": "200"})
    assert result.exit_code == 0, result.output
    assert help_template.format(_ALIAS_VOCABULARY) in normalize_cli_output(result.output)


@pytest.mark.parametrize(
    "args",
    [
        ["watchlist", "create", "W", "AAPL", "--analysis", "bogus"],
        ["watchlist", "add-selection", "W", "AAPL", "--analysis", "bogus"],
        ["watchlist", "remove-method", "W", "--analysis", "bogus"],
        ["runs", "list", "--analysis", "bogus"],
    ],
)
def test_every_analysis_option_rejects_an_unknown_alias_with_the_same_usage_error(args: list[str]) -> None:
    """The validation error lists the declared aliases, in declaration order, with no ``or``."""
    result = runner.invoke(app, args, env={"COLUMNS": "200"})
    assert result.exit_code == 1, result.output
    assert _ALIAS_ERROR in normalize_cli_output(result.output)


@pytest.mark.parametrize("alias", _ALIASES)
def test_every_declared_alias_is_a_choice_of_the_analysis_option(alias: str) -> None:
    """Each strategy's alias is in the help of every ``--analysis`` option and in the unknown-alias error."""
    for args, help_template in _ANALYSIS_HELP:
        result = runner.invoke(app, args, env={"COLUMNS": "200"})
        assert result.exit_code == 0, result.output
        text = normalize_cli_output(result.output)
        prefix = help_template.split("{}")[0]
        assert alias in text.split(prefix)[1].split(".")[0]
    rejected = runner.invoke(app, ["runs", "list", "--analysis", "bogus"], env={"COLUMNS": "200"})
    assert alias in normalize_cli_output(rejected.output).split("must be one of:")[1]


def test_the_alias_choices_are_formatted_as_a_comma_list_with_a_final_or(monkeypatch: pytest.MonkeyPatch) -> None:
    """On a fixed, hand-written vocabulary the help text and the error read as the documented message."""
    cli_workspace = importlib.import_module("investment_analysis_engine.cli_workspace")
    monkeypatch.setattr(cli_workspace, "CLI_BUILDERS", {"alpha": None, "beta-two": None, "gamma": None})

    assert cli_workspace._alias_choices() == "alpha, beta-two, or gamma"  # noqa: SLF001 - the formatter under test
    with pytest.raises(cli_workspace.InvalidParameterError) as raised:
        cli_workspace._parse_analysis("bogus")  # noqa: SLF001 - the validator under test
    assert str(raised.value) == "--analysis must be one of: alpha, beta-two, gamma."


def test_runs_list_text_shows_the_alias_and_json_keeps_the_canonical_method_id(
    isolated_cli_settings: ProjectSettings,
) -> None:
    _insert_momentum_run(isolated_cli_settings)

    text = runner.invoke(app, ["runs", "list"])
    assert text.exit_code == 0, text.output
    assert "momentum" in text.output
    assert "sma_crossover" not in text.output

    payload = json.loads(runner.invoke(app, ["runs", "list", "--json"]).output)
    assert payload[0]["method_id"] == "sma_crossover"


def test_watchlist_show_json_keeps_the_canonical_method_id() -> None:
    _create("Canonical Json")
    runner.invoke(app, ["watchlist", "add-selection", "Canonical Json", "AAPL", "--analysis", "graham-number"])

    text = normalize_cli_output(runner.invoke(app, ["watchlist", "show", "Canonical Json"]).output)
    assert "graham-number:" in text
    assert "graham_number" not in text

    payload = json.loads(runner.invoke(app, ["watchlist", "show", "Canonical Json", "--json"]).output)
    assert payload["entries"][0]["selection"]["method_id"] == "graham_number"


def test_removal_confirmation_lines_name_the_alias_never_the_canonical_id() -> None:
    _create("Confirm Lines")
    runner.invoke(
        app,
        [
            "watchlist",
            "add-selection",
            "Confirm Lines",
            "AAPL",
            "MSFT",
            "--analysis",
            "graham-growth",
            "--expected-growth",
            "6.0",
            "--aaa-yield",
            "4.4",
        ],
    )

    absent = runner.invoke(app, ["watchlist", "remove-method", "Confirm Lines", "--analysis", "fcf-growth"])
    assert absent.output.splitlines()[0] == "No entries for fcf-growth in watchlist 'Confirm Lines'."

    removed = runner.invoke(app, ["watchlist", "remove-method", "Confirm Lines", "--analysis", "graham-growth"])
    assert removed.output.splitlines()[0] == "Removed 2 entries for graham-growth from watchlist 'Confirm Lines'."
    assert "graham_growth_value" not in removed.output


def _database_path(settings: ProjectSettings) -> Path:
    return Path(settings.database_url.removeprefix("sqlite:///"))


def _seed_for_delete(name: str = "Scratch") -> None:
    _create(name)
    runner.invoke(app, ["watchlist", "add-selection", name, "AAPL", "MSFT", "--analysis", "momentum"])


def _listed_names() -> str:
    return normalize_cli_output(runner.invoke(app, ["watchlist", "list"]).output)


def test_watchlist_delete_with_yes_deletes_and_says_runs_are_kept() -> None:
    _seed_for_delete()

    result = runner.invoke(app, ["watchlist", "delete", "scratch", "--yes"])

    assert result.exit_code == 0, result.output
    output = normalize_cli_output(result.output)
    assert output.startswith("Deleted watchlist 'Scratch' (ID ")
    assert "2 entries" in output
    assert "Saved Analysis Runs are kept." in output
    assert "No watchlists exist yet." in _listed_names()


def test_watchlist_delete_json_carries_the_watchlist_show_document() -> None:
    _seed_for_delete()
    shown = json.loads(runner.invoke(app, ["watchlist", "show", "Scratch", "--json"]).output)

    result = runner.invoke(app, ["watchlist", "delete", "Scratch", "--yes", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"requested_name": "Scratch", "deleted": True, "watchlist": shown}


def test_watchlist_delete_non_interactive_without_yes_is_a_usage_error_and_changes_nothing(
    isolated_cli_settings: ProjectSettings,
) -> None:
    _seed_for_delete()
    before = _database_path(isolated_cli_settings).read_bytes()

    with patch("investment_analysis_engine.cli_workspace._stdin_is_interactive", return_value=False):
        result = runner.invoke(app, ["watchlist", "delete", "Scratch"])

    assert result.exit_code == 1
    assert "--yes" in normalize_cli_output(result.output)
    assert _database_path(isolated_cli_settings).read_bytes() == before


def test_watchlist_delete_non_interactive_check_happens_before_the_database_is_opened() -> None:
    with (
        patch("investment_analysis_engine.cli_workspace._stdin_is_interactive", return_value=False),
        patch.object(SQLiteDatabase, "__init__", side_effect=AssertionError("must not open a database")),
    ):
        result = runner.invoke(app, ["watchlist", "delete", "Scratch"])

    assert result.exit_code == 1


def test_watchlist_delete_interactive_confirm_shows_name_id_and_count_then_deletes() -> None:
    _seed_for_delete()

    with patch("investment_analysis_engine.cli_workspace._stdin_is_interactive", return_value=True):
        result = runner.invoke(app, ["watchlist", "delete", "Scratch"], input="y\n")

    assert result.exit_code == 0, result.output
    output = normalize_cli_output(result.output)
    assert "Scratch" in output
    assert "2 entries" in output
    assert "Deleted watchlist 'Scratch'" in output
    assert "No watchlists exist yet." in _listed_names()


def test_watchlist_delete_interactive_decline_exits_1_and_deletes_nothing() -> None:
    _seed_for_delete()

    with patch("investment_analysis_engine.cli_workspace._stdin_is_interactive", return_value=True):
        result = runner.invoke(app, ["watchlist", "delete", "Scratch"], input="n\n")

    assert result.exit_code == 1
    assert "Nothing was deleted." in normalize_cli_output(result.output)
    assert "Scratch" in _listed_names()


def test_watchlist_delete_interactive_unknown_name_exits_1_before_prompting() -> None:
    with patch("investment_analysis_engine.cli_workspace._stdin_is_interactive", return_value=True):
        result = runner.invoke(app, ["watchlist", "delete", "Nonexistent"])

    assert result.exit_code == 1
    assert "No watchlist named 'Nonexistent' exists." in normalize_cli_output(result.output)


def test_watchlist_delete_unknown_name_exits_1() -> None:
    result = runner.invoke(app, ["watchlist", "delete", "Nonexistent", "--yes"])

    assert result.exit_code == 1
    assert "No watchlist named 'Nonexistent' exists." in normalize_cli_output(result.output)


def test_watchlist_delete_missing_ok_on_an_unknown_name_exits_0_in_text_and_json() -> None:
    text_result = runner.invoke(app, ["watchlist", "delete", "Nonexistent", "--yes", "--missing-ok"])
    assert text_result.exit_code == 0, text_result.output
    assert "Nothing was deleted." in normalize_cli_output(text_result.output)

    json_result = runner.invoke(app, ["watchlist", "delete", "Nonexistent", "--yes", "--missing-ok", "--json"])
    assert json_result.exit_code == 0, json_result.output
    assert json.loads(json_result.stdout) == {"requested_name": "Nonexistent", "deleted": False, "watchlist": None}


def test_watchlist_delete_missing_ok_on_an_existing_watchlist_deletes_normally() -> None:
    _seed_for_delete()

    result = runner.invoke(app, ["watchlist", "delete", "Scratch", "--yes", "--missing-ok"])

    assert result.exit_code == 0, result.output
    assert "Deleted watchlist 'Scratch'" in normalize_cli_output(result.output)
    assert "No watchlists exist yet." in _listed_names()


def test_watchlist_delete_leaves_other_watchlists_in_the_list() -> None:
    _seed_for_delete("Scratch")
    _create("Keeper")

    runner.invoke(app, ["watchlist", "delete", "Scratch", "--yes"])

    listed = _listed_names()
    assert "Keeper" in listed
    assert "Scratch" not in listed


def test_watchlist_delete_help_has_no_storage_side_effects() -> None:
    with patch.object(SQLiteDatabase, "__init__", side_effect=AssertionError("must not open a database for --help")):
        assert runner.invoke(app, ["watchlist", "delete", "--help"]).exit_code == 0


def test_watchlist_rename_prints_the_confirmation_then_the_renamed_watchlist() -> None:
    _seed_for_delete("Old Name")

    result = runner.invoke(app, ["watchlist", "rename", "old name", "New Name"])

    assert result.exit_code == 0, result.output
    confirmation, *listing = result.output.splitlines()
    assert confirmation == "Renamed watchlist 'old name' to 'New Name'."
    shown = runner.invoke(app, ["watchlist", "show", "New Name"])
    assert "\n".join(listing).strip() == shown.output.strip()
    assert "Watchlist: New Name" in shown.output
    assert runner.invoke(app, ["watchlist", "show", "Old Name"]).exit_code == 1


def test_watchlist_rename_json_prints_only_the_watchlist_document() -> None:
    _seed_for_delete("Old Name")
    before = json.loads(runner.invoke(app, ["watchlist", "show", "Old Name", "--json"]).output)

    result = runner.invoke(app, ["watchlist", "rename", "Old Name", "New Name", "--json"])

    assert result.exit_code == 0, result.output
    document = json.loads(result.stdout)
    assert document["display_name"] == "New Name"
    assert document["watchlist_id"] == before["watchlist_id"]
    assert document["entries"] == before["entries"]


def test_watchlist_rename_case_only_and_identical_names_succeed() -> None:
    _create("core holdings")

    case_only = runner.invoke(app, ["watchlist", "rename", "core holdings", "Core Holdings"])
    identical = runner.invoke(app, ["watchlist", "rename", "Core Holdings", "Core Holdings"])

    assert case_only.exit_code == 0, case_only.output
    assert identical.exit_code == 0, identical.output
    assert "Watchlist: Core Holdings" in case_only.output


def test_watchlist_rename_to_another_watchlists_name_exits_1() -> None:
    _create("First")
    _create("Second")

    result = runner.invoke(app, ["watchlist", "rename", "First", "second"])

    assert result.exit_code == 1
    assert "already exists" in normalize_cli_output(result.output)
    assert "First" in _listed_names()


def test_watchlist_rename_to_a_blank_name_is_a_usage_error() -> None:
    _create("Keep")

    result = runner.invoke(app, ["watchlist", "rename", "Keep", "   "])

    assert result.exit_code == 1
    assert "Keep" in _listed_names()


def test_watchlist_rename_of_an_unknown_name_exits_1() -> None:
    result = runner.invoke(app, ["watchlist", "rename", "Nonexistent", "Anything"])

    assert result.exit_code == 1
    assert "No watchlist named 'Nonexistent' exists." in normalize_cli_output(result.output)


def test_watchlist_rename_help_has_no_storage_side_effects() -> None:
    with patch.object(SQLiteDatabase, "__init__", side_effect=AssertionError("must not open a database for --help")):
        assert runner.invoke(app, ["watchlist", "rename", "--help"]).exit_code == 0


class _FakeStdin:
    def __init__(self, *, tty: bool) -> None:
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


def test_stdin_is_not_interactive_when_it_is_not_a_terminal() -> None:
    with patch("investment_analysis_engine.cli_workspace.sys.stdin", _FakeStdin(tty=False)):
        assert investment_analysis_engine.cli_workspace._stdin_is_interactive() is False


def test_stdin_is_interactive_for_a_terminal_off_windows() -> None:
    with (
        patch("investment_analysis_engine.cli_workspace.sys.stdin", _FakeStdin(tty=True)),
        patch("investment_analysis_engine.cli_workspace.is_windows", return_value=False),
    ):
        assert investment_analysis_engine.cli_workspace._stdin_is_interactive() is True


@pytest.mark.parametrize("console_attached", [True, False])
def test_on_windows_a_terminal_report_must_be_confirmed_as_a_real_console(console_attached: bool) -> None:
    """Windows reports the NUL device as a terminal, so isatty() alone would let a script reach the prompt."""
    with (
        patch("investment_analysis_engine.cli_workspace.sys.stdin", _FakeStdin(tty=True)),
        patch("investment_analysis_engine.cli_workspace.is_windows", return_value=True),
        patch("investment_analysis_engine.cli_workspace._windows_console_attached", return_value=console_attached),
    ):
        assert investment_analysis_engine.cli_workspace._stdin_is_interactive() is console_attached


# --- the catch-all in _workspace_database ---------------------------------------------------------------------


def _a_real_validation_error() -> ValidationError:
    try:
        RunQuery(limit=0)
    except ValidationError as error:
        return error
    raise AssertionError("RunQuery accepted limit 0")


_UNEXPECTED = [
    pytest.param(_a_real_validation_error(), id="validation-error"),
    pytest.param(ValueError("plain detail"), id="value-error"),
    pytest.param(RuntimeError("runtime detail"), id="runtime-error"),
]


@pytest.mark.parametrize("error", _UNEXPECTED)
@pytest.mark.parametrize(
    ("typed", "target", "json_flag"),
    [
        ("watchlist show", (SQLiteWatchlistRepository, "get"), True),
        ("watchlist list", (SQLiteWatchlistRepository, "list"), False),
        ("runs list", (SQLiteAnalysisRunRepository, "list"), True),
    ],
)
def test_an_exception_without_its_own_code_is_an_unexpected_failure_with_one_fixed_message(
    error: Exception, typed: str, target: tuple[type, str], json_flag: bool, caplog: pytest.LogCaptureFixture
) -> None:
    _create("Core")
    arguments = [*typed.split(), *(["Core"] if typed == "watchlist show" else [])]
    message = f"{typed} failed unexpectedly."
    owner, attribute = target
    with patch.object(owner, attribute, side_effect=error):
        text = runner.invoke(app, arguments)
        as_json = runner.invoke(app, [*arguments, "--json"]) if json_flag else None

    assert text.exit_code == 1
    assert text.stdout == ""
    assert text.stderr.strip() == message
    outputs = [text.stderr]
    if as_json is not None:
        assert as_json.exit_code == 1
        assert as_json.stderr == ""
        document = json.loads(as_json.stdout)
        assert (document["reason_code"], document["reason"]) == ("execution_error", message)
        outputs.append(as_json.stdout)
    for output in outputs:
        assert not any(token in output for token in _LIBRARY_TEXT)
        assert str(error).splitlines()[0] not in output
    assert any(record.exc_info and record.exc_info[1] is error for record in caplog.records)


def test_an_exception_that_declares_its_own_code_keeps_its_own_message() -> None:
    _create("Core")
    with patch(
        "investment_analysis_engine.cli_workspace.SQLiteWatchlistRepository.get",
        side_effect=WatchlistNotFoundError("own message"),
    ):
        result = runner.invoke(app, ["watchlist", "show", "Core", "--json"])
    document = json.loads(result.stdout)
    assert result.exit_code == 1
    assert (document["reason_code"], document["reason"]) == ("watchlist_not_found", "own message")


def test_a_deliberate_exit_passes_through_the_catch_all() -> None:
    _create("Core")
    with patch("investment_analysis_engine.cli_workspace.SQLiteWatchlistRepository.get", side_effect=typer.Exit(7)):
        result = runner.invoke(app, ["watchlist", "show", "Core"])
    assert result.exit_code == 7
