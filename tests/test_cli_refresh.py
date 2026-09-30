"""Refresh CLI (G3) tests: multi-ticker execution, exit codes, and graceful interruption.

Every test here that actually executes a job passes `--workers 1`, keeping
`refresh_watchlist` on its sequential path. Real bounded-concurrent
execution (`workers>1`, a genuine `ThreadPoolExecutor`) is already
exhaustively proven directly against `refresh_watchlist` in
`tests/workspace/test_refresh.py` (G2/G3). Exercising it a second time
*through* Click's `CliRunner` was found to trigger a rare ("I/O operation on
closed file", roughly 1 in 8 runs), Windows-specific race in the test
harness's own stdio-capture teardown when the invoked command has spawned
real background threads — not a defect in refresh itself. Sticking to
`--workers 1` at this layer avoids that harness flake entirely while still
proving the CLI's own wiring (argument parsing, exit codes, output
rendering, interruption).
"""

import json
import re
import signal
import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import replace
from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

import src.cli_workspace
from src.analysis.strategy.graham_growth.calculation import GrahamGrowthInputResolver
from src.analysis.strategy.graham_number.calculation import GrahamNumberInputResolver
from src.analysis.strategy.momentum.momentum_analyzer import MomentumMetrics, MomentumRun
from src.cli import app
from src.core.constants import TrendStatus
from src.data.financial.facts import FinancialFactRequest, ProviderFact
from src.data.financial.production import ProductionFinancialFactsProvider
from src.data.market_data import MarketDataContext
from src.data.repositories.analysis_runs import AnalysisRunConflictError, SQLiteAnalysisRunRepository
from src.data.repositories.sqlite import SQLiteDatabase
from src.data.repositories.watchlists import SQLiteWatchlistRepository
from src.data.sec_edgar import SEC_PROVIDER_ID
from src.evaluation.fixtures.fcf_earnings_growth import FixtureAnnualFinancialFactsProvider, annual_series
from src.evaluation.fixtures.graham import NOW, SUBJECT_MISSING, FixtureFinancialFactsProvider
from src.evaluation.fixtures.instrument_profiles import fixture_known_etf_profile
from src.workspace.requests import (
    AnalysisSelection,
    FCFGrowthSelection,
    GrahamGrowthSelection,
    GrahamNumberSelection,
    MomentumSelection,
)
from tests._cli_helpers import isolated_cli_database, normalize_cli_output  # noqa: F401

runner = CliRunner()


def _create(name: str) -> None:
    result = runner.invoke(app, ["watchlist", "create", name])
    assert result.exit_code == 0, result.output


def _seed(name: str, entries: list[tuple[str, AnalysisSelection]]) -> None:
    """Create a watchlist and add entries directly via the repository.

    Amendment A1's I1 checkpoint removed the CLI's add/configure/disable
    commands (they had no coherent meaning once a ticker only exists as
    part of an entry); I2 restores equivalent capability under new command
    names. Until then, tests seed entries directly against the same
    isolated database `isolated_cli_database` already points the CLI at.
    """
    _create(name)
    if entries:
        database = SQLiteDatabase(src.cli_workspace.settings)
        try:
            SQLiteWatchlistRepository(database).add_entries(name, entries)
        finally:
            database.close()


def _create_momentum_only(name: str, members: list[str]) -> None:
    """A watchlist with only a Momentum entry for each given ticker."""
    momentum = MomentumSelection(short_window=2, long_window=3)
    _seed(name, [(ticker, momentum) for ticker in members])


def _mock_momentum_run(ticker: str = "BTC-USD") -> MomentumRun:
    return MomentumRun(
        metrics=MomentumMetrics(
            ticker=ticker,
            status=TrendStatus.BULLISH,
            current_price=100.0,
            short_sma_val=98.0,
            long_sma_val=95.0,
            crossover_signal=1.0,
            timestamp=datetime(2026, 8, 22, 12, 0, tzinfo=UTC),
        ),
        market_data=MarketDataContext(
            provider_id="fixture-market-source",
            observation_interval="1d",
            data_as_of=date(2026, 8, 21),
            currency="USD",
            observation_count=500,
        ),
    )


class _SecLabeledGrahamProvider:
    """Wraps the Graham fixture provider, relabeling facts as `sec_edgar` (matches B1's restriction)."""

    def __init__(self) -> None:
        self._delegate = FixtureFinancialFactsProvider()

    def fetch_facts(self, request: FinancialFactRequest, *, effective_as_of: datetime) -> tuple[ProviderFact, ...]:
        return tuple(
            replace(fact, provider_id="sec_edgar")
            for fact in self._delegate.fetch_facts(request, effective_as_of=effective_as_of)
        )


def _graham_resolver() -> GrahamNumberInputResolver:
    return GrahamNumberInputResolver(_SecLabeledGrahamProvider(), clock=lambda: NOW)


def _graham_growth_resolver() -> GrahamGrowthInputResolver:
    return GrahamGrowthInputResolver(_SecLabeledGrahamProvider(), clock=lambda: NOW)


def _fcf_provider() -> ProductionFinancialFactsProvider:
    facts = tuple(
        replace(fact, provider_id=SEC_PROVIDER_ID, provider_fact_id=f"fy-{fact.fiscal_year}:{fact.field_name.value}")
        for fact in annual_series(range(2020, 2026))
    )
    return ProductionFinancialFactsProvider(sec_edgar=FixtureAnnualFinancialFactsProvider(facts))


def test_refresh_missing_watchlist_exits_1() -> None:
    result = runner.invoke(app, ["refresh", "Nonexistent"])
    assert result.exit_code == 1
    assert "No watchlist named" in normalize_cli_output(result.output)


def test_refresh_empty_target_is_a_usage_error() -> None:
    _create("My Watch")

    result = runner.invoke(app, ["refresh", "My Watch"])
    assert result.exit_code == 2
    assert "nothing to refresh" in normalize_cli_output(result.output)


def test_refresh_rejects_an_out_of_range_worker_count() -> None:
    _create_momentum_only("My Watch", ["BTC-USD"])
    result = runner.invoke(app, ["refresh", "My Watch", "--workers", "5"])
    assert result.exit_code == 2


@patch("src.workspace.momentum_execution.MomentumAnalyzer.run_analysis")
def test_refresh_sequential_persists_every_member_and_exits_0(mock_run: MagicMock) -> None:
    mock_run.side_effect = lambda **kwargs: _mock_momentum_run(kwargs["ticker"])
    _create_momentum_only("My Watch", ["AAPL", "MSFT"])

    result = runner.invoke(app, ["refresh", "My Watch", "--workers", "1"])

    assert result.exit_code == 0, result.output
    output = normalize_cli_output(result.output)
    assert "AAPL" in output
    assert "MSFT" in output
    assert "completed=2" in output
    assert mock_run.call_count == 2


def _retire_momentum_entries(*retired: str) -> None:
    """Rewrite the named tickers' Momentum entries into the retired version-1 stored shape."""
    path = src.cli_workspace.settings.database_url.removeprefix("sqlite:///")
    with closing(sqlite3.connect(path)) as connection:
        for ticker in retired:
            ((selection_json,),) = connection.execute(
                "SELECT selection_json FROM watchlist_entries WHERE ticker = ? AND method_id = 'sma_crossover'",
                (ticker,),
            ).fetchall()
            selection = json.loads(selection_json)
            selection.pop("as_of")
            selection.pop("use_cache")
            selection["config_schema_version"] = 1
            connection.execute(
                "UPDATE watchlist_entries SET selection_json = ?, config_schema_version = 1 "
                "WHERE ticker = ? AND method_id = 'sma_crossover'",
                (json.dumps(selection), ticker),
            )
        connection.commit()


def _stored_tickers() -> list[str]:
    """Return the stored entries' tickers in position order, read without decoding any selection."""
    path = src.cli_workspace.settings.database_url.removeprefix("sqlite:///")
    with closing(sqlite3.connect(path)) as connection:
        rows = connection.execute("SELECT ticker FROM watchlist_entries ORDER BY position").fetchall()
    return [ticker for (ticker,) in rows]


def _store_momentum_entry_as_retired_version_one(name: str, tickers: list[str], retired: str) -> None:
    """Seed Momentum entries, then rewrite the ``retired`` ticker's into the retired version-1 stored shape."""
    _create_momentum_only(name, tickers)
    _retire_momentum_entries(retired)


@pytest.mark.parametrize("arguments", [["watchlist", "show", "Old Watch"], ["refresh", "Old Watch"]])
def test_a_retired_version_one_momentum_entry_reports_a_readable_error(arguments: list[str]) -> None:
    _store_momentum_entry_as_retired_version_one("Old Watch", ["AAPL", "MSFT"], retired="MSFT")

    result = runner.invoke(app, arguments)

    assert result.exit_code == 1
    message = normalize_cli_output(result.output)
    assert message.strip() == (
        "Watchlist 'Old Watch', entry 2 (MSFT, momentum): saved by an earlier version "
        '(selection version 1) and can no longer be read. Remove it with: ian watchlist remove-entry "Old Watch" 2'
    )


def test_the_removal_command_in_the_retired_entry_error_restores_the_watchlist() -> None:
    _store_momentum_entry_as_retired_version_one("Old Watch", ["AAPL", "MSFT"], retired="MSFT")

    result = runner.invoke(app, ["watchlist", "remove-entry", "Old Watch", "2"])
    shown = runner.invoke(app, ["watchlist", "show", "Old Watch"])

    assert result.exit_code == 0, result.output
    assert shown.exit_code == 0, shown.output
    assert "AAPL" in shown.output
    assert "MSFT" not in shown.output


_REMOVAL_COMMAND = re.compile(r'Remove it with: ian (watchlist remove-entry) "([^"]+)" (\d+)')


def test_printed_removal_command_removes_one_unreadable_entry_at_a_time() -> None:
    """Three retired entries and one valid: each run removes exactly one and names the next."""
    _create_momentum_only("Old Watch", ["AAPL", "MSFT", "KO", "NVDA"])
    _retire_momentum_entries("AAPL", "KO", "NVDA")

    shown = runner.invoke(app, ["watchlist", "show", "Old Watch"])
    assert shown.exit_code == 1
    expected_remaining = [["MSFT", "KO", "NVDA"], ["MSFT", "NVDA"], ["MSFT"]]
    expected_next = [("KO", "2"), ("NVDA", "2")]
    output = normalize_cli_output(shown.output)
    assert "entry 1 (AAPL, momentum)" in output

    for step, remaining in enumerate(expected_remaining):
        match = _REMOVAL_COMMAND.search(output)
        assert match is not None, output
        command, name, index = match.groups()
        result = runner.invoke(app, [*command.split(), name, index])
        assert _stored_tickers() == remaining
        output = normalize_cli_output(result.output)
        if step < len(expected_next):
            ticker, next_index = expected_next[step]
            assert result.exit_code == 1
            assert output.startswith("Removed 1 entry from watchlist 'Old Watch'.")
            assert f"entry {next_index} ({ticker}, momentum)" in output
            assert f'remove-entry "Old Watch" {next_index}' in output
        else:
            assert result.exit_code == 0, output
            assert "MSFT" in output

    final = runner.invoke(app, ["watchlist", "show", "Old Watch"])
    assert final.exit_code == 0, final.output
    assert "MSFT" in final.output
    assert "AAPL" not in final.output
    assert "KO" not in final.output
    assert "NVDA" not in final.output


def test_remove_by_ticker_commits_when_another_entry_is_unreadable() -> None:
    _create_momentum_only("Old Watch", ["AAPL", "MSFT", "KO"])
    _retire_momentum_entries("KO")

    result = runner.invoke(app, ["watchlist", "remove-ticker", "Old Watch", "AAPL"])

    assert result.exit_code == 1
    output = normalize_cli_output(result.output)
    assert output.startswith("Removed 1 entry for AAPL from watchlist 'Old Watch'.")
    assert "entry 2 (KO, momentum)" in output
    assert 'remove-entry "Old Watch" 2' in output
    assert _stored_tickers() == ["MSFT", "KO"]


def test_remove_by_ticker_counts_every_entry_it_removes_when_another_is_unreadable() -> None:
    momentum = MomentumSelection(short_window=2, long_window=3)
    _seed("Old Watch", [("AAPL", momentum), ("KO", momentum), ("AAPL", GrahamNumberSelection())])
    _retire_momentum_entries("KO")

    result = runner.invoke(app, ["watchlist", "remove-ticker", "Old Watch", "AAPL"])

    assert result.exit_code == 1
    assert normalize_cli_output(result.output).startswith("Removed 2 entries for AAPL from watchlist 'Old Watch'.")
    assert _stored_tickers() == ["KO"]


def test_remove_by_method_commits_when_another_entry_is_unreadable() -> None:
    _seed("Old Watch", [("KO", GrahamNumberSelection()), ("AAPL", MomentumSelection(short_window=2, long_window=3))])
    _retire_momentum_entries("AAPL")

    result = runner.invoke(app, ["watchlist", "remove-method", "Old Watch", "--analysis", "graham-number"])

    assert result.exit_code == 1
    output = normalize_cli_output(result.output)
    assert output.startswith("Removed 1 entry for graham-number from watchlist 'Old Watch'.")
    assert "entry 1 (AAPL, momentum)" in output
    assert _stored_tickers() == ["AAPL"]


@patch("src.workspace.momentum_execution.MomentumAnalyzer.run_analysis")
def test_refresh_reuses_a_momentum_selections_as_of_and_no_cache(mock_run: MagicMock) -> None:
    mock_run.side_effect = lambda **kwargs: _mock_momentum_run(kwargs["ticker"])
    boundary = datetime(2026, 8, 1, tzinfo=UTC)
    selection = MomentumSelection(short_window=2, long_window=3, as_of=boundary, use_cache=False)
    _seed("My Watch", [("AAPL", selection)])

    result = runner.invoke(app, ["refresh", "My Watch", "--workers", "1"])

    assert result.exit_code == 0, result.output
    context = mock_run.call_args.kwargs["context"]
    assert context.as_of == boundary
    assert context.use_cache is False


@patch("src.workspace.momentum_execution.MomentumAnalyzer.run_analysis")
def test_refresh_json_emits_one_stable_final_document(mock_run: MagicMock) -> None:
    mock_run.side_effect = lambda **kwargs: _mock_momentum_run(kwargs["ticker"])
    _create_momentum_only("My Watch", ["AAPL"])

    result = runner.invoke(app, ["refresh", "My Watch", "--workers", "1", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["watchlist_name"] == "My Watch"
    assert len(payload["results"]) == 1
    assert payload["results"][0]["ticker"] == "AAPL"
    assert payload["results"][0]["status"] == "completed"
    assert payload["results"][0]["analysis_run_id"] is not None
    assert payload["counts"] == {"completed": 1}


def test_refresh_persists_a_not_applicable_etf_outcome_and_still_exits_0() -> None:
    profile = fixture_known_etf_profile()
    _seed("My Watch", [("FLSW", GrahamNumberSelection())])

    with (
        patch("src.cli_workspace.build_graham_resolver", return_value=_graham_resolver()),
        patch("src.workspace.graham_number_execution.compose_graham_profile", return_value=profile),
    ):
        result = runner.invoke(app, ["refresh", "My Watch", "--workers", "1"])

    assert result.exit_code == 0, result.output
    payload = json.loads(runner.invoke(app, ["runs", "list", "--ticker", "FLSW", "--json"]).output)
    assert len(payload) == 1
    assert payload[0]["status"] == "not_applicable"


@patch("src.workspace.momentum_execution.MomentumAnalyzer.run_analysis")
def test_refresh_storage_failure_is_visible_and_nonzero_exit(mock_run: MagicMock) -> None:
    mock_run.side_effect = lambda **kwargs: _mock_momentum_run(kwargs["ticker"])
    _create_momentum_only("My Watch", ["AAPL"])

    with patch.object(SQLiteAnalysisRunRepository, "insert", side_effect=AnalysisRunConflictError("duplicate")):
        result = runner.invoke(app, ["refresh", "My Watch", "--workers", "1"])

    assert result.exit_code == 1
    assert "Traceback" not in result.output
    output = normalize_cli_output(result.output)
    assert "error=1" in output or "error" in output


@patch("src.workspace.momentum_execution.MomentumAnalyzer.run_analysis")
def test_refresh_interrupted_stops_admission_persists_completed_and_exits_130(mock_run: MagicMock) -> None:
    """Simulates Ctrl+C by invoking the installed handler directly (portable, no OS signal)."""
    _create_momentum_only("My Watch", ["AAPL", "MSFT"])
    captured_handlers: list[Callable[[int, object], None]] = []

    def fake_signal(_sig: int, handler: Callable[[int, object], None]) -> None:
        captured_handlers.append(handler)

    call_count = 0

    def fake_run_analysis(**kwargs: object) -> MomentumRun:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Simulate Ctrl+C arriving while AAPL's job is running.
            captured_handlers[0](signal.SIGINT, None)
        return _mock_momentum_run(str(kwargs["ticker"]))

    mock_run.side_effect = fake_run_analysis

    with patch("src.cli_workspace.signal.signal", side_effect=fake_signal):
        result = runner.invoke(app, ["refresh", "My Watch", "--workers", "1"])

    assert result.exit_code == 130
    output = normalize_cli_output(result.output)
    assert "AAPL" in output
    assert "completed" in output
    assert "MSFT" not in output
    # Exactly one call: MSFT's job was never admitted after cancellation.
    assert mock_run.call_count == 1


def test_refresh_graham_growth_selection_persists_with_configured_assumptions() -> None:
    """Exercises the Graham Growth dispatch branch, not just Momentum/Number."""
    growth = GrahamGrowthSelection(expected_growth=6.0, aaa_yield_override=4.4)
    _seed("My Watch", [("SYNTH", growth)])

    with patch("src.cli_workspace.build_graham_resolver", return_value=_graham_growth_resolver()):
        result = runner.invoke(app, ["refresh", "My Watch", "--workers", "1"])

    assert result.exit_code == 0, result.output
    payload = json.loads(runner.invoke(app, ["runs", "list", "--ticker", "SYNTH", "--json"]).output)
    assert len(payload) == 1
    assert payload[0]["method_id"] == "graham_growth_value"
    assert payload[0]["status"] == "completed"


def test_refresh_fcf_growth_selection_persists() -> None:
    """Exercises the FCF/Earnings Growth dispatch branch."""
    _seed("My Watch", [("ACME", FCFGrowthSelection())])

    with patch("src.cli_workspace.build_sec_production_provider", return_value=_fcf_provider()):
        result = runner.invoke(app, ["refresh", "My Watch", "--workers", "1"])

    assert result.exit_code == 0, result.output
    payload = json.loads(runner.invoke(app, ["runs", "list", "--ticker", "ACME", "--json"]).output)
    assert len(payload) == 1
    assert payload[0]["method_id"] == "reported_fcf_eps_cagr"
    assert payload[0]["status"] == "completed"


def test_refresh_unavailable_outcome_still_persists_and_exits_1() -> None:
    """An unavailable (not failed-to-execute) financial outcome still triggers exit 1."""
    _seed("My Watch", [(SUBJECT_MISSING, GrahamNumberSelection())])

    with patch("src.cli_workspace.build_graham_resolver", return_value=_graham_resolver()):
        result = runner.invoke(app, ["refresh", "My Watch", "--workers", "1"])

    assert result.exit_code == 1
    output = normalize_cli_output(result.output)
    assert "unavailable" in output


@patch("src.workspace.momentum_execution.MomentumAnalyzer.run_analysis")
def test_refresh_no_save_executes_but_persists_nothing(mock_run: MagicMock) -> None:
    mock_run.side_effect = lambda **kwargs: _mock_momentum_run(kwargs["ticker"])
    _create_momentum_only("My Watch", ["AAPL", "MSFT"])

    result = runner.invoke(app, ["refresh", "My Watch", "--workers", "1", "--no-save"])

    assert result.exit_code == 0, result.output
    output = normalize_cli_output(result.output)
    assert "(not saved)" in output
    assert "AAPL" in output
    assert "MSFT" in output
    assert "completed=2" in output
    assert mock_run.call_count == 2

    payload = json.loads(runner.invoke(app, ["runs", "list", "--ticker", "AAPL", "--json"]).output)
    assert payload == []


@patch("src.workspace.momentum_execution.MomentumAnalyzer.run_analysis")
def test_refresh_no_save_json_reports_saved_false_and_a_null_run_id(mock_run: MagicMock) -> None:
    mock_run.side_effect = lambda **kwargs: _mock_momentum_run(kwargs["ticker"])
    _create_momentum_only("My Watch", ["AAPL"])

    result = runner.invoke(app, ["refresh", "My Watch", "--workers", "1", "--no-save", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["results"][0]["saved"] is False
    assert payload["results"][0]["analysis_run_id"] is None
    assert payload["results"][0]["status"] == "completed"
    assert payload["counts"] == {"completed": 1}


def test_refresh_no_save_unavailable_outcome_still_exits_1() -> None:
    """--no-save still reflects a real financial outcome in the exit code, not just storage failures."""
    _seed("My Watch", [(SUBJECT_MISSING, GrahamNumberSelection())])

    with patch("src.cli_workspace.build_graham_resolver", return_value=_graham_resolver()):
        result = runner.invoke(app, ["refresh", "My Watch", "--workers", "1", "--no-save"])

    assert result.exit_code == 1
    output = normalize_cli_output(result.output)
    assert "unavailable" in output
    assert "(not saved)" in output

    payload = json.loads(runner.invoke(app, ["runs", "list", "--ticker", SUBJECT_MISSING, "--json"]).output)
    assert payload == []


@patch("src.workspace.momentum_execution.MomentumAnalyzer.run_analysis")
def test_refresh_text_shows_the_alias_and_json_keeps_the_canonical_method_id(mock_run: MagicMock) -> None:
    mock_run.side_effect = lambda **kwargs: _mock_momentum_run(kwargs["ticker"])
    _create_momentum_only("My Watch", ["AAPL"])

    text = runner.invoke(app, ["refresh", "My Watch", "--workers", "1", "--no-save"])
    as_json = runner.invoke(app, ["refresh", "My Watch", "--workers", "1", "--no-save", "--json"])

    assert "momentum" in text.output
    assert "sma_crossover" not in text.output
    assert json.loads(as_json.output)["results"][0]["method_id"] == "sma_crossover"


def test_runs_list_by_alias_does_not_decode_a_watchlists_unreadable_entries() -> None:
    """D6: the alias vocabulary reads run rows only, so a retired stored entry cannot affect it."""
    _store_momentum_entry_as_retired_version_one("Old Watch", ["AAPL", "MSFT"], retired="MSFT")

    result = runner.invoke(app, ["runs", "list", "--analysis", "momentum"])

    assert result.exit_code == 0, result.output
    assert "No matching runs." in result.output
