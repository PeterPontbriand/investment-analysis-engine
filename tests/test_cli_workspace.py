"""Focused tests for the watchlist (F1) and Analysis Run browsing (F2) CLI commands."""

import importlib
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from alembic.config import Config
from sqlalchemy import update
from typer.testing import CliRunner

import src.cli_workspace
from alembic import command
from src.cli import app
from src.config import ProjectSettings
from src.data.repositories.analysis_runs import SQLiteAnalysisRunRepository
from src.data.repositories.schema import analysis_runs
from src.data.repositories.sqlite import SQLiteDatabase
from src.evaluation.fixtures.market_data import FixtureDataClient
from src.workspace.codecs import encode_evidence
from src.workspace.execution import ExecutionCapture, execute
from src.workspace.models import RunOutcome
from src.workspace.momentum_execution import run_momentum
from src.workspace.requests import AnalysisRequest, MomentumSelection
from src.workspace.runs import AnalysisRun
from tests._cli_helpers import isolated_cli_database, normalize_cli_output  # noqa: F401

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
    assert result.exit_code == 2


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
    assert "sma_crossover" in output


def test_watchlist_create_seeding_requires_analysis_with_tickers() -> None:
    result = runner.invoke(app, ["watchlist", "create", "Bad", "AAPL"])
    assert result.exit_code == 2
    assert "--analysis is required" in normalize_cli_output(result.output)


def test_watchlist_create_seeding_requires_tickers_with_analysis() -> None:
    result = runner.invoke(app, ["watchlist", "create", "Bad", "--analysis", "momentum"])
    assert result.exit_code == 2
    assert "At least one TICKER is required" in normalize_cli_output(result.output)


def test_watchlist_create_rejects_an_unknown_analysis_alias() -> None:
    result = runner.invoke(app, ["watchlist", "create", "Bad", "--analysis", "bogus", "AAPL"])
    assert result.exit_code == 2
    assert "--analysis must be one of" in normalize_cli_output(result.output)


def test_watchlist_create_graham_growth_requires_its_assumptions() -> None:
    """Amendment A1 (§12): a method missing a required flag is a usage error, as the direct command produces."""
    result = runner.invoke(app, ["watchlist", "create", "Bad", "--analysis", "graham-growth", "AAPL"])
    assert result.exit_code == 2
    assert "--expected-growth" in normalize_cli_output(result.output)

    result = runner.invoke(
        app, ["watchlist", "create", "Bad", "--analysis", "graham-growth", "--expected-growth", "6.0", "AAPL"]
    )
    assert result.exit_code == 2
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
    assert "graham_growth_value" in output
    assert "expected_growth=6.0" in output
    assert "aaa_yield_override=4.4" in output


def test_watchlist_create_rejects_invalid_momentum_windows() -> None:
    """Mirrors the direct ``momentum`` command's own window/RSI validation exactly."""
    cases = [
        (["--short-window", "0"], "short window must be positive"),
        (["--long-window", "0"], "long window must be positive"),
        (["--rsi-period", "0"], "RSI period must be positive"),
        (["--short-window", "30", "--long-window", "10"], "must be smaller than long window"),
    ]
    for flags, expected_message in cases:
        result = runner.invoke(app, ["watchlist", "create", "Bad Windows", "--analysis", "momentum", *flags, "AAPL"])
        assert result.exit_code == 2, result.output
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
    assert "reported_fcf_eps_cagr" in output
    assert "currency=EUR" in output


def test_watchlist_create_fcf_growth_rejects_an_invalid_growth_years() -> None:
    result = runner.invoke(
        app, ["watchlist", "create", "Bad FCF", "--analysis", "fcf-growth", "--growth-years", "7", "AAPL"]
    )
    assert result.exit_code == 2
    assert "--growth-years must be 3, 4, or 5" in normalize_cli_output(result.output)


def test_watchlist_create_fcf_growth_rejects_an_invalid_forward_policy() -> None:
    result = runner.invoke(
        app, ["watchlist", "create", "Bad FCF", "--analysis", "fcf-growth", "--forward-policy", "bogus", "AAPL"]
    )
    assert result.exit_code == 2
    assert "--forward-policy must be" in normalize_cli_output(result.output)


def test_watchlist_create_fcf_growth_rejects_an_invalid_classification_basis() -> None:
    result = runner.invoke(
        app,
        ["watchlist", "create", "Bad FCF", "--analysis", "fcf-growth", "--classification-basis", "bogus", "AAPL"],
    )
    assert result.exit_code == 2
    assert "--classification-basis must be" in normalize_cli_output(result.output)


def test_watchlist_create_fcf_growth_rejects_an_invalid_currency() -> None:
    result = runner.invoke(
        app, ["watchlist", "create", "Bad FCF", "--analysis", "fcf-growth", "--currency", "US", "AAPL"]
    )
    assert result.exit_code == 2
    assert "--currency must be a three-letter ISO 4217 code" in normalize_cli_output(result.output)


def test_watchlist_create_rejects_a_blank_seed_ticker() -> None:
    result = runner.invoke(app, ["watchlist", "create", "Blank Ticker", "--analysis", "momentum", "  "])
    assert result.exit_code == 2


def test_watchlist_add_selection_appends_and_allows_the_same_method_twice() -> None:
    """The amendment's headline capability: comparing one method via two providers on one ticker."""
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
            "--data-provider",
            "massive",
            "--bvps",
            "12.5",
        ],
    )
    assert result.exit_code == 0, result.output
    output = normalize_cli_output(result.output)
    assert "Entries (2):" in output
    assert "security_provider_id=sec_edgar" in output
    assert "security_provider_id=massive" in output


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
    assert result.exit_code == 2


def test_watchlist_remove_entry_by_1_based_index_and_renumbers_survivors() -> None:
    _create("Trimmed")
    runner.invoke(app, ["watchlist", "add-selection", "Trimmed", "AAPL", "MSFT", "GOOG", "--analysis", "momentum"])

    result = runner.invoke(app, ["watchlist", "remove-entry", "Trimmed", "1"])
    assert result.exit_code == 0, result.output
    output = normalize_cli_output(result.output)
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
    assert result.exit_code == 2
    assert "INDEX must be 1 or greater" in normalize_cli_output(result.output)


def test_watchlist_remove_entry_missing_watchlist_exits_1() -> None:
    result = runner.invoke(app, ["watchlist", "remove-entry", "Nonexistent", "1"])
    assert result.exit_code == 1
    assert "No watchlist named" in normalize_cli_output(result.output)


def test_watchlist_remove_rejects_a_blank_ticker() -> None:
    _create("Blank Ticker Remove")
    result = runner.invoke(app, ["watchlist", "remove", "Blank Ticker Remove", "  "])
    assert result.exit_code == 2


def test_watchlist_remove_removes_every_entry_for_a_ticker_across_methods() -> None:
    _create("Bulk By Ticker")
    runner.invoke(app, ["watchlist", "add-selection", "Bulk By Ticker", "AAPL", "MSFT", "--analysis", "momentum"])
    runner.invoke(app, ["watchlist", "add-selection", "Bulk By Ticker", "AAPL", "--analysis", "graham-number"])

    result = runner.invoke(app, ["watchlist", "remove", "Bulk By Ticker", "AAPL"])
    assert result.exit_code == 0, result.output
    output = normalize_cli_output(result.output)
    assert "Entries (1):" in output
    assert "MSFT" in output
    assert "AAPL" not in output


def test_watchlist_remove_missing_watchlist_exits_1() -> None:
    result = runner.invoke(app, ["watchlist", "remove", "Nonexistent", "AAPL"])
    assert result.exit_code == 1
    assert "No watchlist named" in normalize_cli_output(result.output)


def test_watchlist_remove_requires_at_least_one_ticker() -> None:
    _create("No Tickers To Remove")
    result = runner.invoke(app, ["watchlist", "remove", "No Tickers To Remove"])
    assert result.exit_code == 2
    assert "Missing argument" in normalize_cli_output(result.output)


def test_watchlist_disable_removes_every_entry_for_a_method_across_tickers() -> None:
    _create("Bulk By Method")
    runner.invoke(app, ["watchlist", "add-selection", "Bulk By Method", "AAPL", "MSFT", "--analysis", "momentum"])
    runner.invoke(app, ["watchlist", "add-selection", "Bulk By Method", "AAPL", "--analysis", "graham-number"])

    result = runner.invoke(app, ["watchlist", "disable", "Bulk By Method", "--analysis", "momentum"])
    assert result.exit_code == 0, result.output
    output = normalize_cli_output(result.output)
    assert "Entries (1):" in output
    assert "graham_number" in output
    assert "sma_crossover" not in output


def test_watchlist_disable_missing_watchlist_exits_1() -> None:
    result = runner.invoke(app, ["watchlist", "disable", "Nonexistent", "--analysis", "momentum"])
    assert result.exit_code == 1
    assert "No watchlist named" in normalize_cli_output(result.output)


def test_watchlist_show_groups_by_ticker_by_default_and_by_method_on_request() -> None:
    _create("Grouped")
    runner.invoke(app, ["watchlist", "add-selection", "Grouped", "AAPL", "MSFT", "--analysis", "momentum"])
    runner.invoke(app, ["watchlist", "add-selection", "Grouped", "AAPL", "--analysis", "graham-number"])

    by_ticker = normalize_cli_output(runner.invoke(app, ["watchlist", "show", "Grouped"]).output)
    assert by_ticker.index("AAPL") < by_ticker.index("sma_crossover") < by_ticker.index("graham_number")
    assert by_ticker.index("MSFT") > by_ticker.index("graham_number")  # MSFT is its own later group

    by_method = normalize_cli_output(
        runner.invoke(app, ["watchlist", "show", "Grouped", "--group-by", "method"]).output
    )
    assert by_method.index("sma_crossover") < by_method.index("AAPL") < by_method.index("graham_number")


def test_watchlist_show_rejects_an_invalid_group_by() -> None:
    _create("Bad Group By")
    result = runner.invoke(app, ["watchlist", "show", "Bad Group By", "--group-by", "bogus"])
    assert result.exit_code == 2
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
    assert result.exit_code == 2


def test_runs_show_missing_id_exits_1() -> None:
    result = runner.invoke(app, ["runs", "show", "11111111-1111-4111-8111-111111111111"])
    assert result.exit_code == 1
    assert "No Analysis Run" in normalize_cli_output(result.output)


def test_runs_show_invalid_id_is_a_usage_error() -> None:
    result = runner.invoke(app, ["runs", "show", "not-a-uuid"])
    assert result.exit_code == 2
    output = normalize_cli_output(result.output)
    assert "not a shortened or partial value" in output
    assert "RUN_ID" in output


def test_runs_show_rejects_conflicting_view_flags() -> None:
    run_id = "11111111-1111-4111-8111-111111111111"
    result = runner.invoke(app, ["runs", "show", run_id, "--details", "--json"])
    assert result.exit_code == 2


class _FixtureClient(FixtureDataClient):
    """FixtureDataClient with a stable provider identity for the full resolver path."""

    @property
    def provider_id(self) -> str:
        return "fixture"


_DEFAULT_RUN_ID = UUID("33333333-3333-4333-8333-333333333333")


def _insert_momentum_run(
    ticker: str = "AAPL",
    *,
    run_id: UUID | None = None,
    outcome: RunOutcome = RunOutcome.COMPLETED,
) -> AnalysisRun:
    """Insert one real, genuinely-executed Momentum run through the isolated database."""
    resolved_run_id = run_id if run_id is not None else _DEFAULT_RUN_ID
    database = SQLiteDatabase(src.cli_workspace.settings)
    try:
        repository = SQLiteAnalysisRunRepository(database)
        selection = MomentumSelection(short_window=2, long_window=3)
        request = AnalysisRequest(ticker=ticker, selection=selection)

        def capture() -> ExecutionCapture:
            native = run_momentum(selection, ticker, _FixtureClient())
            return ExecutionCapture(native_evidence=native, profile=None, outcome=outcome)

        return execute(
            request,
            capture=capture,
            repository=repository,
            id_factory=lambda: resolved_run_id,
            clock=lambda: datetime(2026, 9, 19, 12, tzinfo=UTC),
        )
    finally:
        database.close()


def test_runs_show_replays_a_real_persisted_run_and_exits_0_even_when_failed() -> None:
    """A pure successful read exits 0 even when it shows a failed historical run.

    A genuine execution failure is simulated here purely to exercise the "pure read
    exits 0 even for a failed historical run" contract rule; Momentum itself has no
    native failure status (see D1).
    """
    run = _insert_momentum_run(outcome=RunOutcome.FAILED)
    result = runner.invoke(app, ["runs", "show", str(run.analysis_run_id)])
    assert result.exit_code == 0
    assert "AAPL" in normalize_cli_output(result.output)


def test_runs_show_rejects_a_corrupted_stored_envelope_without_a_raw_traceback() -> None:
    """A row whose relational columns disagree with its own envelope is a sanitized exit 1.

    ``SQLiteAnalysisRunRepository.get`` raises a plain ``ValueError`` for this case
    (documented on the repository itself), distinct from the codec's typed
    `UnsupportedRunVersionError`/`InvalidStoredRunError` — `runs show` must catch
    both classes, or a corrupted row would print a raw Python traceback instead of
    the sanitized message the contract requires.
    """
    run = _insert_momentum_run()
    database = SQLiteDatabase(src.cli_workspace.settings)
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
    assert "Malformed or inconsistent" in normalize_cli_output(result.output)


def test_runs_show_rejects_an_unsupported_stored_method_version() -> None:
    """A self-consistent but unsupported stored method_version raises from the evidence codec.

    Unlike `projection_version` (a pydantic `Literal[1]`, so an unsupported value can
    never even round-trip through the repository), `method_version` is a plain
    `int`, so a genuinely stored, self-consistent row with an unsupported value is
    possible — and must surface as the same sanitized exit 1, not a raw traceback.
    """
    selection = MomentumSelection(short_window=2, long_window=3)
    native = run_momentum(selection, "AAPL", _FixtureClient())
    run = AnalysisRun(
        analysis_run_id=UUID("66666666-6666-4666-8666-666666666666"),
        ticker="AAPL",
        analysis_id="momentum",
        method_id="sma_crossover",
        config_schema_version=1,
        requested_config=selection,
        started_at=datetime(2026, 9, 19, 12, tzinfo=UTC),
        completed_at=datetime(2026, 9, 19, 12, tzinfo=UTC),
        method_version=99,
        result_schema_version=1,
        evidence_codec_version=1,
        status=RunOutcome.COMPLETED,
        result_evidence=encode_evidence(native),
    )
    database = SQLiteDatabase(src.cli_workspace.settings)
    try:
        SQLiteAnalysisRunRepository(database).insert(run)
    finally:
        database.close()

    result = runner.invoke(app, ["runs", "show", str(run.analysis_run_id)])
    assert result.exit_code == 1
    assert "Unsupported Analysis Run method or version" in normalize_cli_output(result.output)


def test_runs_list_rejects_an_invalid_ticker_or_refresh_id_as_a_usage_error() -> None:
    result = runner.invoke(app, ["runs", "list", "--ticker", "   "])
    assert result.exit_code == 2

    result = runner.invoke(app, ["runs", "list", "--refresh-id", "not-a-uuid"])
    assert result.exit_code == 2
    output = normalize_cli_output(result.output)
    assert "not a shortened or partial value" in output
    assert "--refresh-id" in output


def test_runs_list_json_and_text_render_real_persisted_summaries() -> None:
    run = _insert_momentum_run()

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
    config = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "0001_persistence")  # older head: newer workspace tables never created

    with patch("src.cli_workspace.settings", ProjectSettings(database_url=url)):
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
        assert runner.invoke(app, ["watchlist", "remove", "--help"]).exit_code == 0
        assert runner.invoke(app, ["watchlist", "disable", "--help"]).exit_code == 0
        assert runner.invoke(app, ["runs", "show", "--help"]).exit_code == 0


def test_module_import_has_no_storage_side_effects() -> None:
    with patch.object(SQLiteDatabase, "__init__", side_effect=AssertionError("import must not open a database")):
        importlib.reload(src.cli_workspace)
