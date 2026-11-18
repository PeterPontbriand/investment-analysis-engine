"""A ``--json`` refusal over an unreadable stored entry names that entry, and no other failure does."""

import json
import sqlite3
from contextlib import closing

import pytest
from typer.testing import CliRunner

from investment_analysis_engine.cli import app
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.strategy_wiring import GRAHAM_NUMBER
from tests._cli_helpers import normalize_cli_output

runner = CliRunner()

_GRAHAM = "graham-number"


def _run(*arguments: str) -> tuple[int, dict[str, object]]:
    result = runner.invoke(app, list(arguments))
    return result.exit_code, json.loads(result.stdout)


def _seed_with_an_unreadable_second_entry(settings: ProjectSettings) -> None:
    """Create ``Core`` holding KO, MSFT and AAPL for graham-number, then make MSFT's stored selection unreadable."""
    assert runner.invoke(app, ["watchlist", "create", "Core"]).exit_code == 0
    assert runner.invoke(app, ["watchlist", "add-selection", _GRAHAM, "Core", "KO", "MSFT", "AAPL"]).exit_code == 0
    path = settings.database_url.removeprefix("sqlite:///")
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("UPDATE watchlist_entries SET selection_json = '{\"x\":1}' WHERE ticker = 'MSFT'")
        connection.commit()


@pytest.mark.parametrize(
    "arguments",
    [
        ["watchlist", "show", "Core", "--json"],
        ["watchlist", "add-selection", _GRAHAM, "Core", "NVDA", "--json"],
        ["refresh", "Core", "--json"],
    ],
    ids=["show", "add", "refresh"],
)
def test_a_refusal_over_an_unreadable_entry_carries_that_entry(
    arguments: list[str], isolated_cli_settings: ProjectSettings
) -> None:
    _seed_with_an_unreadable_second_entry(isolated_cli_settings)

    code, failure = _run(*arguments)

    assert (code, failure["reason_code"], failure["schema_version"]) == (1, "stored_selection_unreadable", 15)
    unreadable = failure["unreadable"]
    assert isinstance(unreadable, dict)
    assert (unreadable["entry_number"], unreadable["ticker"], unreadable["method_id"]) == (
        2,
        "MSFT",
        GRAHAM_NUMBER.method_id,
    )
    assert "entry 2 (MSFT, graham-number)" in normalize_cli_output(str(unreadable["reason"]))


def test_the_entry_reason_matches_the_one_a_rename_reports_for_the_same_entry(
    isolated_cli_settings: ProjectSettings,
) -> None:
    _seed_with_an_unreadable_second_entry(isolated_cli_settings)

    _, renamed = _run("watchlist", "rename", "Core", "Main", "--json")
    _, refused = _run("watchlist", "show", "Main", "--json")

    shown = refused["unreadable"]
    reported = renamed["unreadable"]
    assert isinstance(shown, dict)
    assert isinstance(reported, dict)
    assert shown["reason"] == reported["reason"]
    assert "ian " not in str(shown["reason"])


def test_every_other_failure_has_no_unreadable_entry(isolated_cli_settings: ProjectSettings) -> None:
    del isolated_cli_settings

    code, failure = _run("watchlist", "show", "Nowhere", "--json")

    assert (code, failure["reason_code"], failure["unreadable"]) == (1, "watchlist_not_found", None)
