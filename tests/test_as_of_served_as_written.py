"""A date as-of is served as that date and a timestamp as given, from the entry to the saved run and the comparison."""

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from typer.testing import CliRunner

from investment_analysis_engine.cli import app
from investment_analysis_engine.config import ProjectSettings
from tests._runs_compare_refresh import offline_refresh, run_ids
from tests.api._support import AUTH, client_for

pytestmark = pytest.mark.usefixtures("isolated_cli_settings", "stub_yahoo_identity_metadata")

runner = CliRunner()

_DATE = "2026-01-31"
_END_OF_DAY = datetime(2026, 1, 31, 23, 59, 59, 999999, tzinfo=UTC)
_TIMESTAMP = "2026-01-31T12:00:00-05:00"
_MOMENTUM_FIELDS: dict[str, object] = {"short_window": 2, "long_window": 3, "rsi_period": 3}
_MOMENTUM_ARGUMENTS = ["--short-window", "2", "--long-window", "3", "--rsi-period", "3", "--no-cache"]
_STRATEGIES = ("sma_crossover", "graham_number")


def _boundaries(document: object, name: str) -> list[object]:
    """Return every value a document holds under a key called ``name``, at any depth."""
    found: list[object] = []
    if isinstance(document, dict):
        for key, value in document.items():
            if key == name:
                found.append(value)
            found.extend(_boundaries(value, name))
    elif isinstance(document, list):
        for item in document:
            found.extend(_boundaries(item, name))
    return found


def _stored_selection_texts(settings: ProjectSettings) -> list[str]:
    path = settings.database_url.removeprefix("sqlite:///")
    with closing(sqlite3.connect(path)) as connection:
        return [text for (text,) in connection.execute("SELECT selection_json FROM watchlist_entries")]


def _add_through_api(client: Any, watchlist_id: str, as_of: str) -> None:
    for method_id, fields in (("sma_crossover", _MOMENTUM_FIELDS), ("graham_number", {})):
        response = client.post(
            f"/v1/watchlists/{watchlist_id}/entries",
            json={"method_id": method_id, "tickers": ["SYNTH"], "selection": {**fields, "as_of": as_of}},
            headers=AUTH,
        )
        assert response.status_code == 200, response.text


def _compared_runs(document: dict[str, Any]) -> list[dict[str, Any]]:
    runs = [entry["run"] for row in document["rows"] for entry in row["entries"] if entry["run"] is not None]
    assert runs
    return runs


@pytest.mark.parametrize(
    ("given", "served"), [(_DATE, _DATE), (_TIMESTAMP, _TIMESTAMP)], ids=["date", "timestamp-with-offset"]
)
def test_an_as_of_added_through_the_api_is_read_back_as_given_from_every_document(
    isolated_cli_settings: ProjectSettings, given: str, served: str
) -> None:
    with client_for(isolated_cli_settings) as client:
        created = client.post("/v1/watchlists", json={"name": "Dated"}, headers=AUTH)
        assert created.status_code == 201, created.text
        watchlist_id = created.json()["watchlist_id"]
        _add_through_api(client, watchlist_id, given)
        refresh_id = UUID(offline_refresh("Dated")["refresh_id"])

        watchlist = client.get(f"/v1/watchlists/{watchlist_id}", headers=AUTH).json()
        ids = run_ids(isolated_cli_settings, refresh_id)
        runs = {method: client.get(f"/v1/runs/{ids[('SYNTH', method)]}", headers=AUTH).json() for method in _STRATEGIES}
        overviews = {
            method: client.get(f"/v1/runs/{ids[('SYNTH', method)]}/overview", headers=AUTH).json()
            for method in _STRATEGIES
        }
        compared = client.get(f"/v1/refreshes/{refresh_id}/compare", headers=AUTH).json()

    assert [entry["selection"]["as_of"] for entry in watchlist["entries"]] == [served] * 2
    for method in _STRATEGIES:
        assert runs[method]["requested_as_of"] == served
        assert runs[method]["effective_as_of"] == served
        assert overviews[method]["requested_as_of"] == served
    assert {run["requested_as_of"] for run in _compared_runs(compared)} == {served}
    assert set(_boundaries(runs["graham_number"], "as_of")) <= {served, None}


def test_the_stored_selection_still_holds_the_end_of_the_day_in_utc(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        created = client.post("/v1/watchlists", json={"name": "Dated"}, headers=AUTH)
        _add_through_api(client, created.json()["watchlist_id"], _DATE)

    texts = _stored_selection_texts(isolated_cli_settings)

    assert len(texts) == 2
    stored = [datetime.fromisoformat(json.loads(text)["as_of"]) for text in texts]
    assert stored == [_END_OF_DAY] * 2


@pytest.mark.parametrize(
    ("given", "served"), [(_DATE, _DATE), (_TIMESTAMP, _TIMESTAMP)], ids=["date", "timestamp-with-offset"]
)
def test_an_as_of_added_with_the_command_line_is_printed_as_given_in_every_json_form(
    isolated_cli_settings: ProjectSettings, given: str, served: str
) -> None:
    assert runner.invoke(app, ["watchlist", "create", "Dated"]).exit_code == 0
    for command in (["momentum", *_MOMENTUM_ARGUMENTS], ["graham-number"]):
        added = runner.invoke(
            app, ["watchlist", "add-selection", *command[:1], "Dated", "SYNTH", *command[1:], "--as-of", given]
        )
        assert added.exit_code == 0, added.output
    refresh_id = UUID(offline_refresh("Dated")["refresh_id"])

    watchlist = json.loads(runner.invoke(app, ["watchlist", "show", "Dated", "--json"]).stdout)
    ids = run_ids(isolated_cli_settings, refresh_id)
    shown = {
        method: json.loads(runner.invoke(app, ["runs", "show", ids[("SYNTH", method)], "--json"]).stdout)
        for method in _STRATEGIES
    }
    compared = json.loads(runner.invoke(app, ["runs", "compare", str(refresh_id), "--json"]).stdout)

    assert [entry["selection"]["as_of"] for entry in watchlist["entries"]] == [served] * 2
    for method in _STRATEGIES:
        assert shown[method]["requested_as_of"] == served
        assert shown[method]["effective_as_of"] == served
    assert {run["requested_as_of"] for run in _compared_runs(compared)} == {served}
    assert set(_boundaries(shown["graham_number"], "as_of")) <= {served, None}
