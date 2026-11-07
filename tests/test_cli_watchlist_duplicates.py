"""``watchlist add-selection`` refuses a duplicate: the same ticker with an equal selection, in the add or stored."""

import json

import pytest
from typer.testing import CliRunner

from investment_analysis_engine.cli import app
from tests._cli_helpers import normalize_cli_output

pytestmark = pytest.mark.usefixtures("isolated_cli_settings")

runner = CliRunner()
_METHOD = "sma_crossover"


def _create(name: str = "Core") -> None:
    assert runner.invoke(app, ["watchlist", "create", name]).exit_code == 0


def _add(*arguments: str, name: str = "Core") -> tuple[int, str]:
    result = runner.invoke(app, ["watchlist", "add-selection", "momentum", name, *arguments])
    return result.exit_code, normalize_cli_output(result.output)


def test_a_ticker_repeated_within_one_add_is_refused_and_nothing_is_written() -> None:
    _create()

    code, output = _add("AAPL", "msft", " aapl ")

    assert code == 1
    assert output.strip() == (
        f"TICKER must not duplicate an entry: AAPL is already listed for {_METHOD} with an equal selection "
        "earlier in this request."
    )
    shown = runner.invoke(app, ["watchlist", "show", "Core", "--json"])
    assert json.loads(shown.stdout)["entries"] == []


def test_an_entry_the_watchlist_already_holds_is_refused() -> None:
    _create()
    assert _add("AAPL")[0] == 0

    code, output = _add("MSFT", "aapl")

    assert code == 1
    assert output.strip() == (
        f"TICKER must not duplicate an entry: AAPL is already listed for {_METHOD} with an equal selection in the "
        "watchlist."
    )
    shown = runner.invoke(app, ["watchlist", "show", "Core", "--json"])
    assert [entry["ticker"] for entry in json.loads(shown.stdout)["entries"]] == ["AAPL"]


def test_the_json_failure_lists_each_duplicate_under_the_one_rule() -> None:
    _create()
    assert _add("AAPL")[0] == 0

    result = runner.invoke(app, ["watchlist", "add-selection", "momentum", "Core", "AAPL", "--json"])

    assert result.exit_code == 1
    document = json.loads(result.stdout)
    assert document["reason_code"] == "invalid_parameter"
    assert document["parameters"] == ["TICKER"]
    assert [item["rule"] for item in document["errors"]] == ["entries.duplicate"]
    assert document["errors"][0]["arguments"] == {"ticker": "AAPL", "method_id": _METHOD, "where": "in the watchlist"}


def test_the_same_ticker_and_method_under_a_different_selection_is_accepted() -> None:
    _create()
    assert _add("AAPL")[0] == 0

    code, output = _add("AAPL", "--short-window", "5", "--long-window", "30")

    assert code == 0, output
    shown = runner.invoke(app, ["watchlist", "show", "Core", "--json"])
    assert [entry["ticker"] for entry in json.loads(shown.stdout)["entries"]] == ["AAPL", "AAPL"]
