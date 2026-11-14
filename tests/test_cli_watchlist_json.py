"""``--json`` on the watchlist writing commands, and the order in which they check arguments and the database."""

import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from typer.testing import CliRunner

from investment_analysis_engine.cli import app
from investment_analysis_engine.config import ProjectSettings
from tests._cli_helpers import normalize_cli_output
from tests.application._unready_database import unready_database_url

pytestmark = pytest.mark.usefixtures("isolated_cli_settings")

runner = CliRunner()

_GRAHAM = "graham-number"


def _run(*arguments: str) -> tuple[int, str, str]:
    result = runner.invoke(app, list(arguments))
    return result.exit_code, result.stdout, normalize_cli_output(result.stderr)


def _seed_core() -> None:
    """Create ``Core`` holding KO and MSFT for graham-number and AAPL for fcf-growth."""
    assert _run("watchlist", "create", "Core")[0] == 0
    assert _run("watchlist", "add-selection", _GRAHAM, "Core", "KO", "MSFT")[0] == 0
    assert _run("watchlist", "add-selection", "fcf-growth", "Core", "AAPL")[0] == 0


def _retire(settings: ProjectSettings, ticker: str) -> None:
    """Rewrite one stored entry into a shape this version cannot read."""
    path = settings.database_url.removeprefix("sqlite:///")
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("UPDATE watchlist_entries SET selection_json = '{\"x\":1}' WHERE ticker = ?", (ticker,))
        connection.commit()


def _tickers(settings: ProjectSettings) -> list[str]:
    path = settings.database_url.removeprefix("sqlite:///")
    with closing(sqlite3.connect(path)) as connection:
        rows = connection.execute("SELECT ticker FROM watchlist_entries ORDER BY position").fetchall()
    return [ticker for (ticker,) in rows]


def test_create_json_writes_only_the_created_watchlist_document() -> None:
    code, stdout, stderr = _run("watchlist", "create", "Core", "--json")

    document = json.loads(stdout)
    assert (code, stderr) == (0, "")
    assert (document["display_name"], document["updated_at"], document["entries"]) == ("Core", None, [])
    assert list(document) == ["schema_version", "watchlist_id", "display_name", "created_at", "updated_at", "entries"]


def test_add_selection_json_with_several_tickers_writes_the_document_with_all_of_them() -> None:
    _run("watchlist", "create", "Core")
    code, stdout, stderr = _run("watchlist", "add-selection", _GRAHAM, "Core", "KO", "MSFT", "--json")

    document = json.loads(stdout)
    assert (code, stderr) == (0, "")
    assert [entry["ticker"] for entry in document["entries"]] == ["KO", "MSFT"]
    assert [entry["index"] for entry in document["entries"]] == [1, 2]


def test_create_json_failures_write_the_failure_document_and_nothing_to_standard_error() -> None:
    _run("watchlist", "create", "Core")

    cases = [
        (["watchlist", "create", "Core", "--json"], "watchlist_name_conflict", None),
        (["watchlist", "create", " ", "--json"], "invalid_parameter", ["NAME"]),
    ]
    for arguments, reason_code, parameters in cases:
        code, stdout, stderr = _run(*arguments)
        document = json.loads(stdout)
        assert (code, stderr, document["reason_code"]) == (1, "", reason_code), arguments
        assert document.get("parameters") == parameters, arguments
    assert [json.loads(_run("watchlist", "list", "--json")[1])["items"][0]["display_name"]] == ["Core"]


def test_add_selection_json_writes_the_updated_watchlist_document() -> None:
    _run("watchlist", "create", "Core")

    code, stdout, stderr = _run("watchlist", "add-selection", _GRAHAM, "core", "KO", "--json")

    document = json.loads(stdout)
    assert (code, stderr) == (0, "")
    assert (document["display_name"], [entry["ticker"] for entry in document["entries"]]) == ("Core", ["KO"])
    assert document["updated_at"] is not None


def test_add_selection_json_failures_write_the_failure_document(isolated_cli_settings: ProjectSettings) -> None:
    _seed_core()
    _retire(isolated_cli_settings, "MSFT")
    cases = [
        (["watchlist", "add-selection", _GRAHAM, "Nowhere", "KO", "--json"], "watchlist_not_found"),
        (["watchlist", "add-selection", _GRAHAM, "Core", " ", "--json"], "invalid_parameter"),
        (["watchlist", "add-selection", _GRAHAM, "Core", "KO", "--as-of", "nope", "--json"], "invalid_parameter"),
        (["watchlist", "add-selection", _GRAHAM, "Core", "NVDA", "--json"], "stored_selection_unreadable"),
    ]
    for arguments, reason_code in cases:
        code, stdout, stderr = _run(*arguments)
        assert (code, stderr, json.loads(stdout)["reason_code"]) == (1, "", reason_code), arguments
    assert _tickers(isolated_cli_settings) == ["KO", "MSFT", "AAPL"]


@pytest.mark.parametrize(
    ("arguments", "confirmation", "remaining"),
    [
        (["remove-entry", "Core", "2"], "Removed 1 entry from watchlist 'Core'.", ["KO", "AAPL"]),
        (["remove-ticker", "Core", "KO"], "Removed 1 entry for KO from watchlist 'Core'.", ["MSFT", "AAPL"]),
        (
            ["remove-method", "Core", "-a", "graham-number"],
            "Removed 2 entries for graham-number from watchlist 'Core'.",
            ["AAPL"],
        ),
        (["remove-ticker", "Core", "ZZZ"], "No entries for ZZZ in watchlist 'Core'.", ["KO", "MSFT", "AAPL"]),
        (
            ["remove-method", "Core", "-a", "momentum"],
            "No entries for momentum in watchlist 'Core'.",
            ["KO", "MSFT", "AAPL"],
        ),
    ],
    ids=["remove-entry", "remove-ticker", "remove-method", "nothing-for-ticker", "nothing-for-method"],
)
def test_a_removal_with_json_confirms_on_standard_error_and_writes_the_removal_document_to_standard_output(
    arguments: list[str], confirmation: str, remaining: list[str]
) -> None:
    _seed_core()

    code, stdout, stderr = _run("watchlist", *arguments, "--json")

    result = json.loads(stdout)
    document = result["watchlist"]
    assert (code, stderr) == (0, confirmation)
    assert list(result) == ["schema_version", "removed", "watchlist", "unreadable"]
    assert (result["schema_version"], result["unreadable"]) == (2, None)
    assert result["removed"] == 3 - len(remaining)
    assert [entry["ticker"] for entry in document["entries"]] == remaining
    assert [entry["index"] for entry in document["entries"]] == list(range(1, len(remaining) + 1))


def test_a_removal_without_json_still_confirms_on_standard_output_before_the_watchlist() -> None:
    _seed_core()

    code, stdout, stderr = _run("watchlist", "remove-ticker", "Core", "KO")

    assert (code, stderr) == (0, "")
    assert stdout.splitlines()[:2] == ["Removed 1 entry for KO from watchlist 'Core'.", "Watchlist: Core"]


@pytest.mark.parametrize(
    ("arguments", "confirmation"),
    [
        (["remove-ticker", "Core", "KO"], "Removed 1 entry for KO from watchlist 'Core'."),
        (["remove-entry", "Core", "1"], "Removed 1 entry from watchlist 'Core'."),
        (["remove-method", "Core", "-a", "graham-number"], "Removed 1 entry for graham-number from watchlist 'Core'."),
    ],
    ids=["remove-ticker", "remove-entry", "remove-method"],
)
def test_a_removal_with_json_and_another_unreadable_entry_commits_and_writes_the_removal_document(
    arguments: list[str], confirmation: str, isolated_cli_settings: ProjectSettings
) -> None:
    assert _run("watchlist", "create", "Core")[0] == 0
    assert _run("watchlist", "add-selection", _GRAHAM, "Core", "KO")[0] == 0
    assert _run("watchlist", "add-selection", "fcf-growth", "Core", "MSFT")[0] == 0
    _retire(isolated_cli_settings, "MSFT")

    code, stdout, stderr = _run("watchlist", *arguments, "--json")

    document = json.loads(stdout)
    assert (code, stderr) == (1, confirmation)
    assert document["schema_version"] == 2
    assert document["removed"] == 1
    assert document["watchlist"] is None
    unreadable = document["unreadable"]
    assert (unreadable["entry_number"], unreadable["ticker"]) == (1, "MSFT")
    assert unreadable["method_id"] == "reported_fcf_eps_cagr"
    assert unreadable["reason"].startswith("Watchlist 'Core', entry 1 (MSFT, fcf-growth): ")
    assert "ian " not in unreadable["reason"]
    assert _tickers(isolated_cli_settings) == ["MSFT"]


@pytest.mark.parametrize(
    ("arguments", "confirmation"),
    [
        (["remove-ticker", "Core", "KO"], "Removed 1 entry for KO from watchlist 'Core'."),
        (["remove-entry", "Core", "1"], "Removed 1 entry from watchlist 'Core'."),
        (["remove-method", "Core", "-a", "graham-number"], "Removed 1 entry for graham-number from watchlist 'Core'."),
    ],
    ids=["remove-ticker", "remove-entry", "remove-method"],
)
def test_a_removal_without_json_and_another_unreadable_entry_still_fails_with_the_remedy_on_standard_error(
    arguments: list[str], confirmation: str, isolated_cli_settings: ProjectSettings
) -> None:
    assert _run("watchlist", "create", "Core")[0] == 0
    assert _run("watchlist", "add-selection", _GRAHAM, "Core", "KO")[0] == 0
    assert _run("watchlist", "add-selection", "fcf-growth", "Core", "MSFT")[0] == 0
    _retire(isolated_cli_settings, "MSFT")

    code, stdout, stderr = _run("watchlist", *arguments)

    assert code == 1
    assert stdout.splitlines() == [confirmation]
    assert stderr.startswith("Watchlist 'Core', entry 1 (MSFT, fcf-growth): ")
    assert stderr.endswith('Remove it with: ian watchlist remove-entry "Core" 1')


def test_rename_and_delete_with_json_and_an_unreadable_entry_commit_and_write_their_result_document(
    isolated_cli_settings: ProjectSettings,
) -> None:
    assert _run("watchlist", "create", "Core")[0] == 0
    assert _run("watchlist", "add-selection", "fcf-growth", "Core", "MSFT")[0] == 0
    _retire(isolated_cli_settings, "MSFT")

    code, stdout, stderr = _run("watchlist", "rename", "Core", "Main", "--json")

    renamed = json.loads(stdout)
    assert (code, stderr) == (1, "Renamed watchlist 'Core' to 'Main'.")
    assert (renamed["schema_version"], renamed["watchlist"]) == (2, None)
    assert renamed["unreadable"]["method_id"] == "reported_fcf_eps_cagr"

    code, stdout, stderr = _run("watchlist", "delete", "Main", "--yes", "--json")

    deleted = json.loads(stdout)
    assert code == 1
    assert stderr.startswith("Deleted watchlist 'Main'")
    assert (deleted["schema_version"], deleted["deleted"], deleted["watchlist"]) == (2, True, None)
    assert deleted["unreadable"]["entry_number"] == 1
    assert _tickers(isolated_cli_settings) == []


def test_rename_and_delete_without_json_and_an_unreadable_entry_are_unchanged(
    isolated_cli_settings: ProjectSettings,
) -> None:
    assert _run("watchlist", "create", "Core")[0] == 0
    assert _run("watchlist", "add-selection", "fcf-growth", "Core", "MSFT")[0] == 0
    _retire(isolated_cli_settings, "MSFT")

    code, stdout, stderr = _run("watchlist", "rename", "Core", "Main")

    assert (code, stdout.splitlines()) == (1, ["Renamed watchlist 'Core' to 'Main'."])
    assert stderr.endswith('Remove it with: ian watchlist remove-entry "Main" 1')


def test_a_removal_with_json_that_fails_before_the_write_writes_the_failure_document(
    isolated_cli_settings: ProjectSettings,
) -> None:
    _seed_core()
    cases = [
        (["remove-entry", "Core", "0"], "invalid_parameter", ["INDEX"]),
        (["remove-entry", "Core", "9"], "watchlist_entry_not_found", None),
        (["remove-entry", "Nowhere", "1"], "watchlist_not_found", None),
        (["remove-ticker", "Core", " "], "invalid_parameter", ["TICKER"]),
        (["remove-ticker", "Nowhere", "KO"], "watchlist_not_found", None),
        (["remove-method", "Core", "-a", "nope"], "invalid_parameter", ["--analysis"]),
        (["remove-method", "Nowhere", "-a", "momentum"], "watchlist_not_found", None),
    ]
    for arguments, reason_code, parameters in cases:
        code, stdout, stderr = _run("watchlist", *arguments, "--json")
        document = json.loads(stdout)
        assert (code, stderr, document["reason_code"]) == (1, "", reason_code), arguments
        assert document.get("parameters") == parameters, arguments
    assert _tickers(isolated_cli_settings) == ["KO", "MSFT", "AAPL"]


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["watchlist", "create", " "], "NAME must not be blank."),
        (["watchlist", "add-selection", _GRAHAM, "Core", " "], "TICKER must not be empty."),
        (["watchlist", "remove-entry", "Core", "0"], "INDEX must be 1 or greater."),
        (["watchlist", "remove-ticker", "Core", " "], "TICKER must not be empty."),
        (["watchlist", "rename", "Core", " "], "NEW_NAME must not be blank."),
    ],
    ids=["create-name", "add-selection", "remove-entry", "remove-ticker", "rename"],
)
def test_a_rejected_argument_is_reported_even_when_the_database_is_not_ready(
    arguments: list[str], message: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unready = ProjectSettings(database_url=unready_database_url(tmp_path))
    monkeypatch.setattr("investment_analysis_engine.cli_workspace.settings", unready)
    monkeypatch.setattr("investment_analysis_engine.cli_support.settings", unready)

    code, stdout, stderr = _run(*arguments)

    assert (code, stdout, stderr) == (1, "", message)
