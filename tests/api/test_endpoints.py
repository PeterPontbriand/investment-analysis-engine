"""Every read endpoint, in process: its document is the one the command line writes, parsed."""

import json
import sqlite3
from contextlib import closing
from importlib.metadata import version
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from investment_analysis_engine.api.documents import API_VERSIONS
from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.database import open_database
from investment_analysis_engine.application.runs import compare_refresh_runs, replay_run_document, replay_run_text
from investment_analysis_engine.application.watchlists import get_watchlist_by_name, watchlist_repository
from investment_analysis_engine.cli import app
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.help.locales import LOCALES
from investment_analysis_engine.reporting.presentation import PresentationMode
from investment_analysis_engine.reporting.replay_inputs import TextPresentationMode
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.strategy_wiring import STRATEGIES, StrategyDescriptor
from investment_analysis_engine.workspace.watchlists import WatchlistName, WatchlistSpec
from investment_analysis_engine.workspace_documents.watchlist import (
    build_watchlist_document,
    build_watchlist_list_document,
)
from tests._runs_compare_refresh import MOMENTUM, refresh
from tests.api._support import AUTH, client_for, runs_by_alias, store

runner = CliRunner()

_SELECTION = MomentumSelection(short_window=2, long_window=3, rsi_period=14)
_MODES: tuple[tuple[str, TextPresentationMode, list[str]], ...] = (
    ("concise", PresentationMode.CONCISE, []),
    ("details", PresentationMode.DETAILS, ["--details"]),
    ("diagnostics", PresentationMode.DIAGNOSTICS, ["--diagnostics"]),
)


def test_info_names_the_served_versions_and_never_the_sec_identity(isolated_cli_settings: ProjectSettings) -> None:
    configured = ProjectSettings(
        **(isolated_cli_settings.model_dump() | {"sec_user_agent": "Someone someone@example.com"})
    )
    unset = ProjectSettings(**(isolated_cli_settings.model_dump() | {"sec_user_agent": None}))
    with client_for(configured) as client:
        response = client.get("/v1/info", headers=AUTH)
    with client_for(unset) as client:
        absent = client.get("/v1/info", headers=AUTH)

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": 2,
        "api_versions": list(API_VERSIONS),
        "engine_version": version("investment-analysis-engine"),
        "sec_identity_configured": True,
        "locales": [{"tag": item.tag, "name": item.name} for item in LOCALES],
    }
    assert "someone@example.com" not in response.text
    assert absent.json()["sec_identity_configured"] is False
    assert list(response.json()) == [
        "schema_version",
        "api_versions",
        "engine_version",
        "sec_identity_configured",
        "locales",
    ]


def test_strategies_lists_every_declared_strategy_in_order(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        response = client.get("/v1/strategies", headers=AUTH)

    assert response.json() == {
        "schema_version": 2,
        "items": [
            {"analysis": item.analysis_id, "method": item.method_id, "label": item.label, "term": item.term}
            for item in STRATEGIES
        ],
    }


def test_the_watchlist_list_and_a_watchlist_by_id_are_the_commands_documents(
    isolated_cli_settings: ProjectSettings,
) -> None:
    context = ApplicationContext(settings=isolated_cli_settings)
    with open_database(context) as database:
        repository = watchlist_repository(database)
        repository.create(WatchlistSpec(display_name="Empty"))
        repository.create(WatchlistSpec(display_name="Core"))
        repository.add_entries(WatchlistName("Core"), [("AAPL", _SELECTION), ("msft", _SELECTION)])
        summaries = repository.list()
    core = get_watchlist_by_name(context, "Core")

    with client_for(isolated_cli_settings) as client:
        listed = client.get("/v1/watchlists", headers=AUTH)
        shown = client.get(f"/v1/watchlists/{core.watchlist_id}", headers=AUTH)

    assert listed.json() == build_watchlist_list_document(summaries).model_dump(mode="json")
    assert shown.json() == build_watchlist_document(core).model_dump(mode="json")
    assert [entry["ticker"] for entry in shown.json()["entries"]] == ["AAPL", "MSFT"]


def test_an_empty_store_lists_empty_documents(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        watchlists = client.get("/v1/watchlists", headers=AUTH)
        runs = client.get("/v1/runs", headers=AUTH)

    assert watchlists.json() == {"schema_version": 1, "items": []}
    assert runs.json() == {"schema_version": 1, "has_more": False, "items": []}


def test_a_missing_watchlist_is_not_found_with_the_message_of_the_operation(
    isolated_cli_settings: ProjectSettings,
) -> None:
    missing = uuid4()
    with client_for(isolated_cli_settings) as client:
        response = client.get(f"/v1/watchlists/{missing}", headers=AUTH)

    assert response.status_code == 404
    assert response.json()["reason_code"] == "watchlist_not_found"
    assert response.json()["reason"] == f"No watchlist with ID {missing} exists."


def test_an_unreadable_entry_is_served_without_a_command_to_run(isolated_cli_settings: ProjectSettings) -> None:
    """The reason names the entry and its state; the command line offers the remedy, the API does not."""
    context = ApplicationContext(settings=isolated_cli_settings)
    with open_database(context) as database:
        repository = watchlist_repository(database)
        created = repository.create(WatchlistSpec(display_name="Core"))
        repository.add_entries(WatchlistName("Core"), [("AAPL", _SELECTION), ("msft", _SELECTION)])
    with closing(sqlite3.connect(isolated_cli_settings.database_url.removeprefix("sqlite:///"))) as connection:
        connection.execute("UPDATE watchlist_entries SET selection_json = '{\"x\":1}' WHERE ticker = 'MSFT'")
        connection.commit()

    with client_for(isolated_cli_settings) as client:
        unreadable = client.get(f"/v1/watchlists/{created.watchlist_id}", headers=AUTH)
        missing = client.get(f"/v1/watchlists/{uuid4()}", headers=AUTH)
        malformed = client.get("/v1/watchlists/not-an-id", headers=AUTH)

    document = unreadable.json()
    assert document["reason_code"] == "stored_selection_unreadable"
    assert document["reason"] == (
        "Watchlist 'Core', entry 2 (MSFT, momentum): its stored selection is not in a shape this version can read."
    )
    for response in (unreadable, missing, malformed):
        assert response.status_code >= 400
        assert "ian " not in response.text


def test_the_runs_list_filters_and_pages_like_the_command(isolated_cli_settings: ProjectSettings) -> None:
    runs = list(runs_by_alias().values())
    store(isolated_cli_settings, *runs)
    first = runs[0]
    with client_for(isolated_cli_settings) as client:
        everything = client.get("/v1/runs", headers=AUTH).json()
        by_method = client.get("/v1/runs", params={"method_id": first.method_id}, headers=AUTH).json()
        by_ticker = client.get("/v1/runs", params={"ticker": first.ticker.lower()}, headers=AUTH).json()
        first_page = client.get("/v1/runs", params={"limit": 1}, headers=AUTH).json()
        last_page = client.get("/v1/runs", params={"limit": 1, "offset": len(runs) - 1}, headers=AUTH).json()
    cli_listing = json.loads(runner.invoke(app, ["runs", "list", "--json"]).stdout)

    assert list(everything) == ["schema_version", "has_more", "items"]
    assert {item["analysis_run_id"] for item in everything["items"]} == {str(run.analysis_run_id) for run in runs}
    assert everything["items"] == cli_listing["items"]
    assert str(first.analysis_run_id) in {item["analysis_run_id"] for item in by_method["items"]}
    assert {item["method_id"] for item in by_method["items"]} == {first.method_id}
    assert str(first.analysis_run_id) in {item["analysis_run_id"] for item in by_ticker["items"]}
    assert (len(first_page["items"]), first_page["has_more"]) == (1, len(runs) > 1)
    assert (len(last_page["items"]), last_page["has_more"]) == (1, False)


@pytest.mark.parametrize("descriptor", STRATEGIES, ids=lambda item: item.alias)
def test_a_saved_run_of_each_strategy_is_served_as_its_document_and_as_text_in_every_mode(
    descriptor: StrategyDescriptor, isolated_cli_settings: ProjectSettings
) -> None:
    run = runs_by_alias()[descriptor.alias]
    store(isolated_cli_settings, run)
    context = ApplicationContext(settings=isolated_cli_settings)
    run_id = str(run.analysis_run_id)

    with client_for(isolated_cli_settings) as client:
        document = client.get(f"/v1/runs/{run_id}", headers=AUTH)
        texts = {
            mode: client.get(f"/v1/runs/{run_id}/text", params={"mode": mode}, headers=AUTH) for mode, *_ in _MODES
        }

    shown = runner.invoke(app, ["runs", "show", run_id, "--json"])
    assert document.status_code == 200
    assert document.json() == json.loads(shown.stdout)
    assert document.json() == replay_run_document(context, run.analysis_run_id).model_dump(mode="json")
    for mode, presentation, flags in _MODES:
        response = texts[mode]
        assert response.status_code == 200
        assert list(response.json()) == ["schema_version", "mode", "text"]
        assert response.json()["schema_version"] == 1
        assert response.json()["mode"] == mode
        assert response.json()["text"] == replay_run_text(context, run.analysis_run_id, presentation)
        assert response.json()["text"] == runner.invoke(app, ["runs", "show", run_id, *flags]).stdout.rstrip("\n")


def test_a_missing_run_is_not_found_for_the_document_and_the_text(isolated_cli_settings: ProjectSettings) -> None:
    missing = uuid4()
    with client_for(isolated_cli_settings) as client:
        document = client.get(f"/v1/runs/{missing}", headers=AUTH)
        text = client.get(f"/v1/runs/{missing}/text", params={"mode": "concise"}, headers=AUTH)

    for response in (document, text):
        assert response.status_code == 404
        assert response.json()["reason_code"] == "analysis_run_not_found"
        assert response.json()["reason"] == f"No Analysis Run with ID {missing} exists."


@pytest.mark.usefixtures("stub_yahoo_identity_metadata")
def test_the_compare_endpoint_serves_the_refreshs_document(isolated_cli_settings: ProjectSettings) -> None:
    refresh_id = refresh(isolated_cli_settings, entries=[("SYNTH", MOMENTUM)])
    expected = compare_refresh_runs(ApplicationContext(settings=isolated_cli_settings), refresh_id)

    with client_for(isolated_cli_settings) as client:
        response = client.get(f"/v1/refreshes/{refresh_id}/compare", headers=AUTH)
        unknown = client.get(f"/v1/refreshes/{uuid4()}/compare", headers=AUTH)

    assert response.status_code == 200
    assert response.json() == expected.model_dump(mode="json")
    assert (unknown.status_code, unknown.json()["reason_code"]) == (404, "analysis_run_not_found")


def test_a_response_body_is_compact_utf_8_json_in_field_order(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        response = client.get("/v1/runs", headers=AUTH)

    assert response.content == b'{"schema_version":1,"has_more":false,"items":[]}'
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == "no-store"
