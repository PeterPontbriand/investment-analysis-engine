"""The action endpoints, in process: watchlist actions, selection forms and direct analysis."""

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import httpx2
import pytest
from starlette.testclient import TestClient

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.api.checks import PREFLIGHT_ALLOWED_METHODS
from investment_analysis_engine.api.routes import ROUTES
from investment_analysis_engine.application.analysis import AnalysisOutcome
from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.failures import SavingFailureError, describe_failure
from investment_analysis_engine.application.runs import replay_run_document
from investment_analysis_engine.application.selections import FIXED_SELECTION_FIELDS, build_selection, selection_schema
from investment_analysis_engine.application.watchlists import get_watchlist_by_name
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.config.component_settings import clear_component_settings_cache
from investment_analysis_engine.strategy_wiring import STRATEGIES, StrategyDescriptor
from investment_analysis_engine.workspace_documents.watchlist import build_watchlist_document
from scripts.generate_schemas import SCHEMA_DIRECTORY
from tests.api._support import AUTH, client_for, runs_by_alias, store

_BODY_ROUTES = (
    ("POST", "/v1/watchlists", {"name": "Core"}),
    ("PATCH", "/v1/watchlists/{id}", {"name": "Main"}),
    ("POST", "/v1/watchlists/{id}/entries", {"method_id": "m", "tickers": ["KO"], "selection": {}}),
    ("POST", "/v1/watchlists/{id}/remove-tickers", {"tickers": ["KO"]}),
    ("POST", "/v1/watchlists/{id}/remove-method", {"method_id": "m"}),
    ("POST", "/v1/analyses", {"ticker": "KO", "method_id": "m", "selection": {}}),
)
_MISSING = uuid4()


def _fields(descriptor: StrategyDescriptor) -> dict[str, object]:
    """Return a valid set of selection fields for a strategy: the fields of its golden run's selection."""
    selection = runs_by_alias()[descriptor.alias].requested_config
    dumped = selection.model_dump(mode="json")
    for name in FIXED_SELECTION_FIELDS:
        dumped.pop(name)
    return dumped


def _context(settings: ProjectSettings) -> ApplicationContext:
    return ApplicationContext(settings=settings)


def _create(client: TestClient, name: str = "Core") -> dict[str, object]:
    response = client.post("/v1/watchlists", json={"name": name}, headers=AUTH)
    assert response.status_code == 201, response.text
    document: dict[str, object] = response.json()
    return document


def _add(client: TestClient, watchlist_id: object, descriptor: StrategyDescriptor, *tickers: str) -> httpx2.Response:
    return client.post(
        f"/v1/watchlists/{watchlist_id}/entries",
        json={"method_id": descriptor.method_id, "tickers": list(tickers), "selection": _fields(descriptor)},
        headers=AUTH,
    )


def _retire(settings: ProjectSettings, ticker: str) -> None:
    """Rewrite one stored entry into a shape this version cannot read."""
    path = settings.database_url.removeprefix("sqlite:///")
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("UPDATE watchlist_entries SET selection_json = '{\"x\":1}' WHERE ticker = ?", (ticker,))
        connection.commit()


def _failure(response: httpx2.Response, status: int, code: str) -> dict[str, object]:
    assert response.status_code == status, response.text
    body: dict[str, object] = response.json()
    assert body["reason_code"] == code
    assert body["schema_version"] == 13
    return body


# --- request bodies (J5) ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("method", "path", "body"), _BODY_ROUTES, ids=[item[1] for item in _BODY_ROUTES])
def test_a_body_with_an_unknown_field_is_rejected_naming_it(
    method: str, path: str, body: dict[str, object], isolated_cli_settings: ProjectSettings
) -> None:
    with client_for(isolated_cli_settings) as client:
        response = client.request(method, path.format(id=_MISSING), json={**body, "colour": "red"}, headers=AUTH)

    failure = _failure(response, 400, "invalid_parameter")
    assert failure["parameters"] == ["colour"]
    assert failure["errors"] is None


@pytest.mark.parametrize(("method", "path", "body"), _BODY_ROUTES, ids=[item[1] for item in _BODY_ROUTES])
def test_a_missing_or_non_json_content_type_is_rejected_under_body(
    method: str, path: str, body: dict[str, object], isolated_cli_settings: ProjectSettings
) -> None:
    content = json.dumps(body, ensure_ascii=False).encode()
    with client_for(isolated_cli_settings) as client:
        missing = client.request(method, path.format(id=_MISSING), content=content, headers=AUTH)
        plain = client.request(
            method, path.format(id=_MISSING), content=content, headers={**AUTH, "Content-Type": "text/plain"}
        )
        with_charset = client.request(
            method,
            path.format(id=_MISSING),
            content=content,
            headers={**AUTH, "Content-Type": "application/json; charset=utf-8"},
        )

    for response in (missing, plain):
        assert _failure(response, 400, "invalid_parameter")["parameters"] == ["body"]
    assert with_charset.status_code != 400 or with_charset.json()["parameters"] != ["body"]


@pytest.mark.parametrize(("method", "path", "body"), _BODY_ROUTES, ids=[item[1] for item in _BODY_ROUTES])
@pytest.mark.parametrize("content", [b"", b"{", b"[1]", b'"text"', b"null"])
def test_a_body_that_is_not_one_json_object_is_rejected_under_body(
    method: str, path: str, body: dict[str, object], content: bytes, isolated_cli_settings: ProjectSettings
) -> None:
    del body
    with client_for(isolated_cli_settings) as client:
        response = client.request(
            method,
            path.format(id=_MISSING),
            content=content,
            headers={**AUTH, "Content-Type": "application/json"},
        )

    assert _failure(response, 400, "invalid_parameter")["parameters"] == ["body"]


def test_a_missing_or_mistyped_field_is_named_by_its_path(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        missing = client.post("/v1/watchlists", json={}, headers=AUTH)
        mistyped = client.post("/v1/watchlists", json={"name": 5}, headers=AUTH)
        element = client.post(f"/v1/watchlists/{_MISSING}/remove-tickers", json={"tickers": ["KO", 7]}, headers=AUTH)
        flag = client.post("/v1/analyses", json={"ticker": "KO", "method_id": "m", "save": "yes"}, headers=AUTH)

    assert _failure(missing, 400, "invalid_parameter")["parameters"] == ["name"]
    assert _failure(mistyped, 400, "invalid_parameter")["parameters"] == ["name"]
    assert _failure(element, 400, "invalid_parameter")["parameters"] == ["tickers[1]"]
    assert _failure(flag, 400, "invalid_parameter")["parameters"] == ["save"]


# --- create, rename, delete ------------------------------------------------------------------------------------------


def test_creating_a_watchlist_answers_201_with_the_watchlist_document(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        created = client.post("/v1/watchlists", json={"name": "  Core  "}, headers=AUTH)
        shown = client.get(f"/v1/watchlists/{created.json()['watchlist_id']}", headers=AUTH)

    assert created.status_code == 201
    assert created.json() == shown.json()
    assert created.json()["schema_version"] == 2
    assert (created.json()["display_name"], created.json()["entries"]) == ("Core", [])


def test_creating_a_watchlist_with_a_used_name_is_a_409_and_a_blank_name_a_400_with_its_rule(
    isolated_cli_settings: ProjectSettings,
) -> None:
    with client_for(isolated_cli_settings) as client:
        _create(client)
        again = client.post("/v1/watchlists", json={"name": "core"}, headers=AUTH)
        blank = client.post("/v1/watchlists", json={"name": "  "}, headers=AUTH)

    _failure(again, 409, "watchlist_name_conflict")
    failure = _failure(blank, 400, "invalid_parameter")
    assert failure["parameters"] == ["name"]
    assert failure["errors"] == [
        {"rule": "watchlist.blank_name", "parameters": ["name"], "arguments": {}, "message": "name must not be blank."}
    ]


def test_renaming_answers_the_rename_document_and_names_its_parameter_name(
    isolated_cli_settings: ProjectSettings,
) -> None:
    with client_for(isolated_cli_settings) as client:
        created = _create(client)
        _create(client, "Other")
        renamed = client.patch(f"/v1/watchlists/{created['watchlist_id']}", json={"name": "Main"}, headers=AUTH)
        blank = client.patch(f"/v1/watchlists/{created['watchlist_id']}", json={"name": " "}, headers=AUTH)
        conflict = client.patch(f"/v1/watchlists/{created['watchlist_id']}", json={"name": "other"}, headers=AUTH)
        missing = client.patch(f"/v1/watchlists/{_MISSING}", json={"name": "Main"}, headers=AUTH)
        not_a_uuid = client.patch("/v1/watchlists/nope", json={"name": "Main"}, headers=AUTH)

    assert renamed.status_code == 200
    assert list(renamed.json()) == ["schema_version", "watchlist", "unreadable"]
    assert renamed.json()["unreadable"] is None
    assert renamed.json()["watchlist"]["display_name"] == "Main"
    failure = _failure(blank, 400, "invalid_parameter")
    assert failure["parameters"] == ["name"]
    assert failure["reason"] == "name must not be blank."
    _failure(conflict, 409, "watchlist_name_conflict")
    _failure(missing, 404, "watchlist_not_found")
    assert _failure(not_a_uuid, 400, "invalid_parameter")["parameters"] == ["watchlist_id"]


def test_deleting_answers_the_delete_document_and_a_missing_watchlist_is_a_404(
    isolated_cli_settings: ProjectSettings,
) -> None:
    with client_for(isolated_cli_settings) as client:
        created = _create(client)
        deleted = client.delete(f"/v1/watchlists/{created['watchlist_id']}", headers=AUTH)
        again = client.delete(f"/v1/watchlists/{created['watchlist_id']}", headers=AUTH)

    assert deleted.json() == {"schema_version": 2, "deleted": True, "watchlist": created, "unreadable": None}
    _failure(again, 404, "watchlist_not_found")


def test_renaming_and_deleting_a_watchlist_with_an_unreadable_entry_commit_and_answer_200(
    isolated_cli_settings: ProjectSettings,
) -> None:
    descriptor = STRATEGIES[0]
    with client_for(isolated_cli_settings) as client:
        created = _create(client)
        assert _add(client, created["watchlist_id"], descriptor, "MSFT").status_code == 200
        _retire(isolated_cli_settings, "MSFT")
        renamed = client.patch(f"/v1/watchlists/{created['watchlist_id']}", json={"name": "Main"}, headers=AUTH)
        deleted = client.delete(f"/v1/watchlists/{created['watchlist_id']}", headers=AUTH)

    for response in (renamed, deleted):
        assert response.status_code == 200
        assert response.json()["watchlist"] is None
        unreadable = response.json()["unreadable"]
        assert (unreadable["entry_number"], unreadable["ticker"], unreadable["method_id"]) == (
            1,
            "MSFT",
            descriptor.method_id,
        )
        assert "ian " not in unreadable["reason"]
    assert deleted.json()["deleted"] is True


# --- entries ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("descriptor", STRATEGIES, ids=lambda item: item.alias)
def test_adding_entries_stores_one_entry_per_normalized_ticker_for_every_strategy(
    descriptor: StrategyDescriptor, isolated_cli_settings: ProjectSettings
) -> None:
    with client_for(isolated_cli_settings) as client:
        created = _create(client)
        response = _add(client, created["watchlist_id"], descriptor, " ko ", "msft")

    stored = get_watchlist_by_name(_context(isolated_cli_settings), "Core")
    assert response.status_code == 200
    assert response.json() == json.loads(
        json.dumps(build_watchlist_document(stored).model_dump(mode="json"), ensure_ascii=False)
    )
    assert [entry["ticker"] for entry in response.json()["entries"]] == ["KO", "MSFT"]
    assert [entry["index"] for entry in response.json()["entries"]] == [1, 2]
    assert {entry.selection.method_id for entry in stored.entries} == {descriptor.method_id}


def test_an_omitted_selection_field_takes_its_configured_value(isolated_cli_settings: ProjectSettings) -> None:
    descriptor = next(item for item in STRATEGIES if item.selection_settings_fields)
    fields = _fields(descriptor)
    for name in descriptor.selection_settings_fields:
        fields.pop(name)
    with client_for(isolated_cli_settings) as client:
        created = _create(client)
        response = client.post(
            f"/v1/watchlists/{created['watchlist_id']}/entries",
            json={"method_id": descriptor.method_id, "tickers": ["KO"], "selection": fields},
            headers=AUTH,
        )

    expected = build_selection(_context(isolated_cli_settings), descriptor.method_id, fields)
    assert response.status_code == 200
    assert response.json()["entries"][0]["selection"] == expected.model_dump(mode="json") | {
        "as_of": response.json()["entries"][0]["selection"]["as_of"]
    }


def test_a_selection_as_of_is_text_parsed_under_its_path(isolated_cli_settings: ProjectSettings) -> None:
    descriptor = STRATEGIES[0]
    fields = _fields(descriptor)
    with client_for(isolated_cli_settings) as client:
        created = _create(client)
        url = f"/v1/watchlists/{created['watchlist_id']}/entries"
        body = {"method_id": descriptor.method_id, "tickers": ["KO"]}
        ok = client.post(url, json=body | {"selection": fields | {"as_of": "2025-12-31"}}, headers=AUTH)
        bad_text = client.post(url, json=body | {"selection": fields | {"as_of": "tomorrow"}}, headers=AUTH)
        empty = client.post(url, json=body | {"selection": fields | {"as_of": " "}}, headers=AUTH)
        number = client.post(url, json=body | {"selection": fields | {"as_of": 5}}, headers=AUTH)
        naive = client.post(url, json=body | {"selection": fields | {"as_of": "2025-12-31T10:00:00"}}, headers=AUTH)

    assert ok.status_code == 200
    assert ok.json()["entries"][0]["selection"]["as_of"] == "2025-12-31"
    failure = _failure(bad_text, 400, "invalid_parameter")
    assert failure["parameters"] == ["selection.as_of"]
    assert failure["errors"][0]["rule"] == "selection.as_of_syntax"  # type: ignore[index]
    assert failure["errors"][0]["parameters"] == ["selection.as_of"]  # type: ignore[index]
    assert _failure(empty, 400, "invalid_parameter")["parameters"] == ["selection.as_of"]
    assert _failure(number, 400, "invalid_parameter")["errors"][0]["rule"] == "selection.as_of_type"  # type: ignore[index]
    assert _failure(naive, 400, "invalid_parameter")["parameters"] == ["selection.as_of"]


def test_selection_errors_are_named_by_path_and_listed_in_field_order(isolated_cli_settings: ProjectSettings) -> None:
    descriptor = next(item for item in STRATEGIES if len(item.selection_settings_fields) >= 2)
    first, second = descriptor.selection_settings_fields[:2]
    fields = _fields(descriptor) | {first: "x", second: "y"}
    with client_for(isolated_cli_settings) as client:
        created = _create(client)
        response = client.post(
            f"/v1/watchlists/{created['watchlist_id']}/entries",
            json={"method_id": descriptor.method_id, "tickers": ["KO"], "selection": fields},
            headers=AUTH,
        )

    failure = _failure(response, 400, "invalid_parameter")
    errors = failure["errors"]
    assert isinstance(errors, list)
    assert [error["parameters"] for error in errors[:2]] == [[f"selection.{first}"], [f"selection.{second}"]]
    assert (failure["reason"], failure["parameters"]) == (errors[0]["message"], errors[0]["parameters"])
    assert all(error["rule"].startswith("pydantic.") for error in errors[:2])
    assert errors[0]["message"].startswith(f"Invalid selection.{first}")


def test_a_nested_selection_field_is_named_by_its_full_path(isolated_cli_settings: ProjectSettings) -> None:
    descriptor = next(item for item in STRATEGIES if "policy" in _fields(item))
    policy = _fields(descriptor)["policy"]
    assert isinstance(policy, dict)
    nested = next(iter(policy))
    fields = _fields(descriptor) | {"policy": {**policy, nested: "not-a-valid-value"}}
    with client_for(isolated_cli_settings) as client:
        created = _create(client)
        response = client.post(
            f"/v1/watchlists/{created['watchlist_id']}/entries",
            json={"method_id": descriptor.method_id, "tickers": ["KO"], "selection": fields},
            headers=AUTH,
        )

    failure = _failure(response, 400, "invalid_parameter")
    assert failure["parameters"] == [f"selection.policy.{nested}"]


def test_the_fields_a_class_fixes_and_an_undeclared_method_are_rejected(isolated_cli_settings: ProjectSettings) -> None:
    descriptor = STRATEGIES[0]
    with client_for(isolated_cli_settings) as client:
        created = _create(client)
        url = f"/v1/watchlists/{created['watchlist_id']}/entries"
        fixed = client.post(
            url,
            json={"method_id": descriptor.method_id, "tickers": ["KO"], "selection": {"method_id": "x"}},
            headers=AUTH,
        )
        undeclared = client.post(url, json={"method_id": "nope", "tickers": ["KO"]}, headers=AUTH)

    assert _failure(fixed, 400, "invalid_parameter")["parameters"] == ["selection.method_id"]
    assert _failure(undeclared, 400, "invalid_parameter")["parameters"] == ["method_id"]


def test_adding_with_no_tickers_a_blank_ticker_a_missing_watchlist_or_an_unreadable_entry_fails(
    isolated_cli_settings: ProjectSettings,
) -> None:
    descriptor = STRATEGIES[0]
    with client_for(isolated_cli_settings) as client:
        created = _create(client)
        url = f"/v1/watchlists/{created['watchlist_id']}/entries"
        body = {"method_id": descriptor.method_id, "selection": _fields(descriptor)}
        none = client.post(url, json=body | {"tickers": []}, headers=AUTH)
        blank = client.post(url, json=body | {"tickers": ["KO", " "]}, headers=AUTH)
        missing = client.post(f"/v1/watchlists/{_MISSING}/entries", json=body | {"tickers": ["KO"]}, headers=AUTH)
        assert _add(client, created["watchlist_id"], descriptor, "MSFT").status_code == 200
        _retire(isolated_cli_settings, "MSFT")
        refused = client.post(url, json=body | {"tickers": ["KO"]}, headers=AUTH)

    assert _failure(none, 400, "invalid_parameter")["parameters"] == ["tickers"]
    assert _failure(blank, 400, "invalid_parameter")["parameters"] == ["tickers"]
    _failure(missing, 404, "watchlist_not_found")
    refusal = _failure(refused, 409, "stored_selection_unreadable")
    assert "ian " not in str(refusal["reason"])


# --- removals --------------------------------------------------------------------------------------------------------


def _seeded(client: TestClient) -> str:
    created = _create(client)
    watchlist_id = str(created["watchlist_id"])
    first, second = STRATEGIES[0], STRATEGIES[1]
    assert _add(client, watchlist_id, first, "KO", "MSFT").status_code == 200
    assert _add(client, watchlist_id, second, "KO").status_code == 200
    return watchlist_id


def test_removing_an_entry_answers_the_removal_document_with_the_count(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        watchlist_id = _seeded(client)
        removed = client.delete(f"/v1/watchlists/{watchlist_id}/entries/2", headers=AUTH)

    assert removed.status_code == 200
    assert list(removed.json()) == ["schema_version", "removed", "watchlist", "unreadable"]
    assert removed.json()["removed"] == 1
    assert [entry["ticker"] for entry in removed.json()["watchlist"]["entries"]] == ["KO", "KO"]


def test_removing_an_entry_that_is_missing_or_numbered_badly_fails(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        watchlist_id = _seeded(client)
        beyond = client.delete(f"/v1/watchlists/{watchlist_id}/entries/9", headers=AUTH)
        zero = client.delete(f"/v1/watchlists/{watchlist_id}/entries/0", headers=AUTH)
        text = client.delete(f"/v1/watchlists/{watchlist_id}/entries/two", headers=AUTH)
        missing = client.delete(f"/v1/watchlists/{_MISSING}/entries/1", headers=AUTH)

    _failure(beyond, 404, "watchlist_entry_not_found")
    failure = _failure(zero, 400, "invalid_parameter")
    assert failure["parameters"] == ["entry_number"]
    assert failure["errors"][0]["rule"] == "watchlist.entry_number_below_one"  # type: ignore[index]
    assert _failure(text, 400, "invalid_parameter")["errors"] is None
    _failure(missing, 404, "watchlist_not_found")


def test_removing_by_ticker_or_method_counts_the_removed_entries_and_is_idempotent(
    isolated_cli_settings: ProjectSettings,
) -> None:
    with client_for(isolated_cli_settings) as client:
        watchlist_id = _seeded(client)
        by_ticker = client.post(f"/v1/watchlists/{watchlist_id}/remove-tickers", json={"tickers": ["ko"]}, headers=AUTH)
        nothing = client.post(f"/v1/watchlists/{watchlist_id}/remove-tickers", json={"tickers": ["ZZZ"]}, headers=AUTH)
        by_method = client.post(
            f"/v1/watchlists/{watchlist_id}/remove-method", json={"method_id": STRATEGIES[0].method_id}, headers=AUTH
        )
        empty = client.post(f"/v1/watchlists/{watchlist_id}/remove-tickers", json={"tickers": []}, headers=AUTH)
        undeclared = client.post(
            f"/v1/watchlists/{watchlist_id}/remove-method", json={"method_id": "nope"}, headers=AUTH
        )
        missing = client.post(
            f"/v1/watchlists/{_MISSING}/remove-method", json={"method_id": STRATEGIES[0].method_id}, headers=AUTH
        )

    assert by_ticker.json()["removed"] == 2
    assert nothing.json()["removed"] == 0
    assert by_method.json()["removed"] == 1
    assert by_method.json()["watchlist"]["entries"] == []
    assert _failure(empty, 400, "invalid_parameter")["parameters"] == ["tickers"]
    assert _failure(undeclared, 400, "invalid_parameter")["parameters"] == ["method_id"]
    _failure(missing, 404, "watchlist_not_found")


def test_a_removal_beside_an_unreadable_entry_commits_and_answers_200_with_the_entry(
    isolated_cli_settings: ProjectSettings,
) -> None:
    first, second = STRATEGIES[0], STRATEGIES[1]
    with client_for(isolated_cli_settings) as client:
        created = _create(client)
        watchlist_id = str(created["watchlist_id"])
        assert _add(client, watchlist_id, first, "KO").status_code == 200
        assert _add(client, watchlist_id, second, "MSFT").status_code == 200
        _retire(isolated_cli_settings, "MSFT")
        removed = client.delete(f"/v1/watchlists/{watchlist_id}/entries/1", headers=AUTH)

    assert removed.status_code == 200
    document = removed.json()
    assert (document["removed"], document["watchlist"]) == (1, None)
    assert document["unreadable"]["ticker"] == "MSFT"
    assert document["unreadable"]["method_id"] == second.method_id


# --- the selection form (J7) -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("descriptor", STRATEGIES, ids=lambda item: item.alias)
def test_the_selection_form_holds_the_published_schema_and_the_configured_defaults(
    descriptor: StrategyDescriptor, isolated_cli_settings: ProjectSettings
) -> None:
    with client_for(isolated_cli_settings) as client:
        response = client.get(f"/v1/strategies/{descriptor.method_id}/selection", headers=AUTH)

    published = json.loads((SCHEMA_DIRECTORY / "selections" / f"{descriptor.alias}.schema.json").read_text("utf-8"))
    assert response.status_code == 200
    assert list(response.json()) == ["schema_version", "schema", "defaults"]
    assert response.json()["schema_version"] == 1
    assert (
        response.json()["schema"]
        == published
        == json.loads(json.dumps(selection_schema(descriptor), ensure_ascii=False))
    )
    assert set(response.json()["defaults"]) == set(descriptor.selection_settings_fields)
    if descriptor.selection_settings_fields:
        built = build_selection(_context(isolated_cli_settings), descriptor.method_id, {})
        for name, value in response.json()["defaults"].items():
            assert value == getattr(built, name)


def test_the_selection_defaults_follow_a_changed_settings_file(tmp_path: Path) -> None:
    descriptor = next(item for item in STRATEGIES if "short_window" in item.selection_settings_fields)
    folder = tmp_path / "config"
    (folder / "strategies").mkdir(parents=True)
    (folder / "strategies" / f"{descriptor.alias}.toml").write_text("short_window = 7\nlong_window = 90\n", "utf-8")
    clear_component_settings_cache()
    try:
        with client_for(ProjectSettings(config_dir=folder)) as client:
            response = client.get(f"/v1/strategies/{descriptor.method_id}/selection", headers=AUTH)
    finally:
        clear_component_settings_cache()

    assert response.json()["defaults"]["short_window"] == 7
    assert response.json()["defaults"]["long_window"] == 90


def test_the_defaults_of_a_strategy_without_settings_fields_are_an_empty_object(
    isolated_cli_settings: ProjectSettings,
) -> None:
    descriptor = next(item for item in STRATEGIES if not item.selection_settings_fields)
    with client_for(isolated_cli_settings) as client:
        response = client.get(f"/v1/strategies/{descriptor.method_id}/selection", headers=AUTH)

    assert response.json()["defaults"] == {}


def test_the_selection_form_of_an_undeclared_method_is_an_invalid_parameter(
    isolated_cli_settings: ProjectSettings,
) -> None:
    with client_for(isolated_cli_settings) as client:
        response = client.get("/v1/strategies/nope/selection", headers=AUTH)

    assert _failure(response, 400, "invalid_parameter")["parameters"] == ["method_id"]


# --- direct analysis (J10, J11) --------------------------------------------------------------------------------------


def _outcome(descriptor: StrategyDescriptor, settings: ProjectSettings, *, run_outcome: RunOutcome) -> AnalysisOutcome:
    run = runs_by_alias()[descriptor.alias]
    store(settings, run)
    return AnalysisOutcome(
        document=replay_run_document(_context(settings), run.analysis_run_id),
        analysis_run_id=run.analysis_run_id,
        outcome=run_outcome,
        text_renderer=lambda mode: f"{descriptor.alias} as {mode.value}",
    )


@pytest.mark.parametrize("descriptor", STRATEGIES, ids=lambda item: item.alias)
def test_an_analysis_is_the_strategy_document_and_its_text_in_each_mode(
    descriptor: StrategyDescriptor, isolated_cli_settings: ProjectSettings
) -> None:
    outcome = _outcome(descriptor, isolated_cli_settings, run_outcome=RunOutcome.COMPLETED)
    with (
        client_for(isolated_cli_settings) as client,
        patch("investment_analysis_engine.api.handlers.analyze", return_value=outcome) as analyze,
    ):
        response = client.post(
            "/v1/analyses",
            json={"ticker": " ko ", "method_id": descriptor.method_id, "selection": _fields(descriptor)},
            headers=AUTH,
        )

    assert response.status_code == 200
    body = response.json()
    assert list(body) == ["schema_version", "analysis_run_id", "document", "text"]
    assert body["analysis_run_id"] == str(outcome.analysis_run_id)
    assert body["document"] == json.loads(json.dumps(outcome.document.model_dump(mode="json"), ensure_ascii=False))
    assert body["text"] == {mode: f"{descriptor.alias} as {mode}" for mode in ("concise", "details", "diagnostics")}
    context, ticker, selection = analyze.call_args.args
    assert (ticker, selection.method_id) == (" ko ", descriptor.method_id)  # the operation normalizes its own ticker
    assert isinstance(context, ApplicationContext)
    assert analyze.call_args.kwargs == {"save": False, "provider_check": isolated_cli_settings.provider_check}


@pytest.mark.parametrize(("save", "check"), [(True, True), (False, False), (True, None)])
def test_save_and_provider_check_reach_the_analysis(
    save: bool, check: bool | None, isolated_cli_settings: ProjectSettings
) -> None:
    descriptor = STRATEGIES[0]
    outcome = _outcome(descriptor, isolated_cli_settings, run_outcome=RunOutcome.COMPLETED)
    with (
        client_for(isolated_cli_settings) as client,
        patch("investment_analysis_engine.api.handlers.analyze", return_value=outcome) as analyze,
    ):
        response = client.post(
            "/v1/analyses",
            json={
                "ticker": "KO",
                "method_id": descriptor.method_id,
                "selection": _fields(descriptor),
                "save": save,
                "provider_check": check,
            },
            headers=AUTH,
        )

    assert response.status_code == 200
    expected = isolated_cli_settings.provider_check if check is None else check
    assert analyze.call_args.kwargs == {"save": save, "provider_check": expected}


@pytest.mark.parametrize("run_outcome", [RunOutcome.UNAVAILABLE, RunOutcome.FAILED])
def test_an_unavailable_or_failed_analysis_is_still_a_200(
    run_outcome: RunOutcome, isolated_cli_settings: ProjectSettings
) -> None:
    descriptor = STRATEGIES[0]
    outcome = _outcome(descriptor, isolated_cli_settings, run_outcome=run_outcome)
    with (
        client_for(isolated_cli_settings) as client,
        patch("investment_analysis_engine.api.handlers.analyze", return_value=outcome),
    ):
        response = client.post(
            "/v1/analyses",
            json={"ticker": "KO", "method_id": descriptor.method_id, "selection": _fields(descriptor)},
            headers=AUTH,
        )

    assert response.status_code == 200


def test_an_analysis_that_is_not_saved_has_no_run_id(isolated_cli_settings: ProjectSettings) -> None:
    descriptor = STRATEGIES[0]
    outcome = _outcome(descriptor, isolated_cli_settings, run_outcome=RunOutcome.COMPLETED)
    unsaved = AnalysisOutcome(
        document=outcome.document, analysis_run_id=None, outcome=outcome.outcome, text_renderer=outcome.text_renderer
    )
    with (
        client_for(isolated_cli_settings) as client,
        patch("investment_analysis_engine.api.handlers.analyze", return_value=unsaved),
    ):
        response = client.post(
            "/v1/analyses",
            json={"ticker": "KO", "method_id": descriptor.method_id, "selection": _fields(descriptor)},
            headers=AUTH,
        )

    assert response.json()["analysis_run_id"] is None


def test_an_analysis_request_that_breaks_a_rule_is_rejected_before_anything_runs(
    isolated_cli_settings: ProjectSettings,
) -> None:
    descriptor = STRATEGIES[0]
    with (
        client_for(isolated_cli_settings) as client,
        patch("investment_analysis_engine.api.handlers.analyze") as analyze,
    ):
        undeclared = client.post("/v1/analyses", json={"ticker": "KO", "method_id": "nope"}, headers=AUTH)
        bad_field = client.post(
            "/v1/analyses",
            json={"ticker": "KO", "method_id": descriptor.method_id, "selection": {"colour": "red"}},
            headers=AUTH,
        )

    assert _failure(undeclared, 400, "invalid_parameter")["parameters"] == ["method_id"]
    assert _failure(bad_field, 400, "invalid_parameter")["parameters"] == ["selection.colour"]
    analyze.assert_not_called()


def test_a_run_saved_after_the_analysis_finished_reports_the_save_failure(
    isolated_cli_settings: ProjectSettings,
) -> None:
    descriptor = STRATEGIES[0]
    with (
        client_for(isolated_cli_settings) as client,
        patch("investment_analysis_engine.api.handlers.analyze", side_effect=SavingFailureError(OSError("disk"))),
    ):
        response = client.post(
            "/v1/analyses",
            json={"ticker": "KO", "method_id": descriptor.method_id, "selection": _fields(descriptor), "save": True},
            headers=AUTH,
        )

    failure = response.json()
    description = describe_failure(OSError("disk"), "KO", saving=True)
    assert response.status_code == 500
    assert failure["reason"] == "KO was analyzed, but the result could not be saved."
    assert failure["reason"] == description.message
    assert failure["reason_code"] == description.code.value
    assert "disk" not in response.text


# --- CORS (J6) -------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["GET", "POST", "PATCH", "DELETE"])
def test_a_preflight_for_each_declared_method_allows_it_with_the_content_type_header(
    method: str, isolated_cli_settings: ProjectSettings
) -> None:
    origin = "tauri://localhost"
    with client_for(isolated_cli_settings, origins=[origin]) as client:
        response = client.options(
            "/v1/watchlists",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": "authorization, content-type",
            },
        )

    assert response.status_code == 204
    assert method in response.headers["access-control-allow-methods"].split(", ")
    assert response.headers["access-control-allow-headers"] == "Authorization, Content-Type, Accept-Language"


def test_the_route_table_declares_the_methods_a_preflight_allows() -> None:
    assert set(PREFLIGHT_ALLOWED_METHODS.split(", ")) == {route.method for route in ROUTES}


def test_a_blank_ticker_is_rejected_by_the_analysis_naming_ticker(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        blank = client.post("/v1/analyses", json={"ticker": " ", "method_id": STRATEGIES[0].method_id}, headers=AUTH)

    failure = _failure(blank, 400, "invalid_parameter")
    assert failure["parameters"] == ["ticker"]
    assert failure["reason"] == "ticker must be a non-empty symbol."
    assert failure["errors"][0]["rule"] == "analysis.blank_ticker"  # type: ignore[index]
