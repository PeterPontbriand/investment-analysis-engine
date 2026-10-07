"""Failures from the workspace and direct commands reach a caller as one envelope with one set of codes.

``--json`` writes the envelope to standard output and nothing to standard error; text mode writes the
sentence to standard error and nothing to standard output. Exit codes are unchanged except for Momentum's
window check, which now reports like every other failure.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

import src.cli_workspace
from src.cli import app
from src.data.base_client import DataFetchError
from src.data.repositories.readiness import DatabaseReadinessError, ReadinessReason
from src.data.repositories.sqlite import SQLiteDatabase
from src.strategies.momentum.selection import MomentumSelection
from src.workspace.capture import ExecutionCapture
from src.workspace.strategy_types import AnalysisSelection
from tests._cli_helpers import isolated_cli_database, normalize_cli_output, stub_yahoo_identity_metadata  # noqa: F401

runner = CliRunner()

_ENVELOPE_KEYS = {
    "schema_version",
    "status",
    "reason_code",
    "reason",
    "analysis",
    "method",
    "ticker",
    "result",
    "diagnostics",
    "database",
}


def _envelope(result_stdout: str) -> dict[str, object]:
    document = json.loads(result_stdout)
    assert set(document) == _ENVELOPE_KEYS
    assert document["schema_version"] == 6
    assert document["result"] is None
    assert document["diagnostics"] == []
    return dict(document)


def _create(name: str) -> None:
    assert runner.invoke(app, ["watchlist", "create", name]).exit_code == 0


_MOMENTUM_WINDOW_CASES = [
    (["--short-window", "0"], "Invalid momentum window: --short-window must be positive (received 0)."),
    (
        ["--long-window", "0", "--short-window", "1"],
        "Invalid momentum window: --long-window must be positive (received 0).",
    ),
    (["--rsi-period", "0"], "Invalid momentum period: --rsi-period must be positive (received 0)."),
    (
        ["--short-window", "30", "--long-window", "10"],
        "Invalid momentum windows: --short-window (30) must be smaller than --long-window (10).",
    ),
]


@pytest.mark.parametrize(("flags", "sentence"), _MOMENTUM_WINDOW_CASES)
def test_direct_momentum_window_failure_is_an_invalid_parameter_envelope(flags: list[str], sentence: str) -> None:
    result = runner.invoke(app, ["momentum", "ACME", *flags, "--json"])

    assert result.exit_code == 1
    assert not result.stderr
    envelope = _envelope(result.stdout)
    assert envelope["status"] == "error"
    assert envelope["reason_code"] == "invalid_parameter"
    assert envelope["reason"] == sentence
    assert (envelope["analysis"], envelope["method"], envelope["ticker"]) == ("momentum", "sma_crossover", "ACME")
    assert envelope["database"] is None


@pytest.mark.parametrize(("flags", "sentence"), _MOMENTUM_WINDOW_CASES)
def test_direct_momentum_window_failure_in_text_mode_is_the_sentence_on_standard_error(
    flags: list[str], sentence: str
) -> None:
    result = runner.invoke(app, ["momentum", "ACME", *flags])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert normalize_cli_output(result.stderr) == sentence


@pytest.mark.parametrize(("flags", "sentence"), _MOMENTUM_WINDOW_CASES)
def test_watchlist_commands_report_the_same_momentum_window_failure(flags: list[str], sentence: str) -> None:
    created = runner.invoke(app, ["watchlist", "create", "Bad", "--analysis", "momentum", *flags, "AAPL"])
    _create("Good")
    added = runner.invoke(app, ["watchlist", "add-selection", "Good", "--analysis", "momentum", *flags, "AAPL"])

    for result in (created, added):
        assert result.exit_code == 1
        assert result.stdout == ""
        assert normalize_cli_output(result.stderr) == sentence
    assert runner.invoke(app, ["watchlist", "show", "Good", "--json"]).exit_code == 0


def test_momentum_window_failure_is_reported_before_an_invalid_as_of() -> None:
    """The window check keeps its place ahead of the boundary check."""
    result = runner.invoke(app, ["momentum", "ACME", "--short-window", "0", "--as-of", "not-a-date", "--json"])

    assert result.exit_code == 1
    assert _envelope(result.stdout)["reason_code"] == "invalid_parameter"


def test_momentum_usage_errors_other_than_the_windows_stay_usage_errors() -> None:
    result = runner.invoke(app, ["momentum", "ACME", "--as-of", "not-a-date", "--json"])

    assert result.exit_code == 2
    assert result.stdout == ""


@pytest.mark.parametrize(
    ("arguments", "code"),
    [
        (["watchlist", "show", "Missing", "--json"], "watchlist_not_found"),
        (["watchlist", "rename", "Missing", "Other", "--json"], "watchlist_not_found"),
        (["watchlist", "delete", "Missing", "--yes", "--json"], "watchlist_not_found"),
        (["refresh", "Missing", "--json"], "watchlist_not_found"),
        (["runs", "show", "11111111-1111-4111-8111-111111111111", "--json"], "analysis_run_not_found"),
    ],
)
def test_workspace_json_failures_write_the_envelope_to_standard_output_only(arguments: list[str], code: str) -> None:
    result = runner.invoke(app, arguments)

    assert result.exit_code == 1
    assert not result.stderr
    envelope = _envelope(result.stdout)
    assert envelope["reason_code"] == code
    assert envelope["status"] == "error"
    assert (envelope["analysis"], envelope["method"], envelope["ticker"]) == (None, None, None)


@pytest.mark.parametrize(
    "arguments",
    [
        ["watchlist", "show", "Missing"],
        ["watchlist", "rename", "Missing", "Other"],
        ["watchlist", "delete", "Missing", "--yes"],
        ["refresh", "Missing"],
        ["runs", "show", "11111111-1111-4111-8111-111111111111"],
    ],
)
def test_workspace_text_failures_keep_the_sentence_on_standard_error(arguments: list[str]) -> None:
    result = runner.invoke(app, arguments)

    assert result.exit_code == 1
    assert result.stdout == ""
    assert normalize_cli_output(result.stderr)
    assert not normalize_cli_output(result.stderr).startswith("{")


def test_a_watchlist_name_conflict_is_reported_under_its_own_code() -> None:
    _create("One")
    _create("Two")

    result = runner.invoke(app, ["watchlist", "rename", "One", "two", "--json"])

    assert result.exit_code == 1
    assert _envelope(result.stdout)["reason_code"] == "watchlist_name_conflict"


def test_removing_a_missing_entry_is_reported_under_its_own_code() -> None:
    _create("One")

    result = runner.invoke(app, ["watchlist", "remove-entry", "One", "4"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "entry" in normalize_cli_output(result.stderr).lower()


def test_runs_list_json_failure_on_a_readiness_error_carries_the_database_facts(tmp_path: Path) -> None:
    error = DatabaseReadinessError(ReadinessReason.UPGRADE_REQUIRED, tmp_path / "cli.sqlite3", "0001_head")
    with patch("src.cli_workspace.ensure_database_ready", side_effect=error):
        result = runner.invoke(app, ["runs", "list", "--json"])

    assert result.exit_code == 1
    assert not result.stderr
    envelope = _envelope(result.stdout)
    assert envelope["reason_code"] == "database_upgrade_required"
    assert envelope["reason"] == str(error)
    assert envelope["database"] == {"database_path": str(tmp_path / "cli.sqlite3"), "expected_revision": "0001_head"}


def test_a_readiness_error_without_json_stays_text_on_standard_error(tmp_path: Path) -> None:
    error = DatabaseReadinessError(ReadinessReason.BUSY, tmp_path / "cli.sqlite3")
    with patch("src.cli_workspace.ensure_database_ready", side_effect=error):
        result = runner.invoke(app, ["watchlist", "list"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert normalize_cli_output(result.stderr) == normalize_cli_output(str(error))


def test_refresh_json_gives_each_failed_job_a_stable_code_and_keeps_its_text() -> None:
    selection = MomentumSelection(short_window=2, long_window=3)
    database = SQLiteDatabase(src.cli_workspace.settings)
    try:
        _create("Core")
        src.cli_workspace._watchlist_repository(database).add_entries(
            "Core", [("AAPL", selection), ("MSFT", selection), ("KO", selection), ("IBM", selection)]
        )
    finally:
        database.close()
    failures: dict[str, Exception] = {
        "AAPL": DataFetchError("provider down"),
        "MSFT": RuntimeError("boom"),
        "KO": ValueError("bad value"),
        "IBM": DatabaseReadinessError(ReadinessReason.BUSY, None),
    }

    def failing_executor(ticker: str, _selection: AnalysisSelection, **_kwargs: object) -> ExecutionCapture:
        raise failures[ticker]

    with patch("src.cli_workspace._refresh_executor", side_effect=failing_executor):
        result = runner.invoke(app, ["refresh", "Core", "--workers", "1", "--json"])
        text = runner.invoke(app, ["refresh", "Core", "--workers", "1"])

    assert result.exit_code == 1
    jobs = {item["ticker"]: item for item in json.loads(result.stdout)["results"]}
    assert {ticker: item["reason_code"] for ticker, item in jobs.items()} == {
        "AAPL": "provider_error",
        "MSFT": "execution_error",
        "KO": "invalid_input",
        "IBM": "database_busy",
    }
    for ticker, item in jobs.items():
        assert item["error"] == str(failures[ticker])
        assert item["analysis_run_id"] is None
        assert item["saved"] is False
    assert "error: provider down" in normalize_cli_output(text.stdout)
    assert "reason_code" not in text.stdout


@pytest.mark.parametrize(
    ("flag", "value"),
    [("--short-window", "0"), ("--long-window", "0"), ("--rsi-period", "0")],
)
def test_the_window_failure_names_the_offending_option_on_all_three_commands(flag: str, value: str) -> None:
    arguments = [flag, value] if flag != "--long-window" else [flag, value, "--short-window", "1"]
    direct = runner.invoke(app, ["momentum", "ACME", *arguments, "--json"])
    _create("Both")
    created = runner.invoke(app, ["watchlist", "create", "Bad", "--analysis", "momentum", *arguments, "AAPL"])
    added = runner.invoke(app, ["watchlist", "add-selection", "Both", "--analysis", "momentum", *arguments, "AAPL"])

    assert flag in str(_envelope(direct.stdout)["reason"])
    assert flag in normalize_cli_output(created.stderr)
    assert flag in normalize_cli_output(added.stderr)


def test_the_reversed_window_failure_names_both_options() -> None:
    result = runner.invoke(app, ["momentum", "ACME", "--short-window", "30", "--long-window", "10", "--json"])

    reason = str(_envelope(result.stdout)["reason"])
    assert "--short-window" in reason
    assert "--long-window" in reason


def test_a_value_error_from_the_analysis_is_invalid_input_not_invalid_parameter() -> None:
    """The same command reports a bad option and bad data under different codes."""
    with patch(
        "src.strategies.momentum.execution.MomentumAnalyzer.run_analysis", side_effect=ValueError("internal detail")
    ):
        data = runner.invoke(app, ["momentum", "ACME", "--json"])
    option = runner.invoke(app, ["momentum", "ACME", "--short-window", "0", "--json"])

    assert _envelope(data.stdout)["reason_code"] == "invalid_input"
    assert _envelope(option.stdout)["reason_code"] == "invalid_parameter"
