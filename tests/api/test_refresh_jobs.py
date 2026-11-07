"""The refresh job endpoints: start, follow, stop and the latest job, with a fake run function and no provider."""

import threading
import time
from contextlib import AbstractContextManager
from unittest.mock import patch
from uuid import uuid4

import httpx2
import pytest
from starlette.testclient import TestClient

from investment_analysis_engine.api import refresh_documents
from investment_analysis_engine.api.request_bodies import MAX_REQUEST_BODY_BYTES
from investment_analysis_engine.api.responses import STATUS_BY_CODE
from investment_analysis_engine.api.routes import ROUTES
from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.database import open_database
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.data.repositories.readiness import DatabaseReadinessError, ReadinessReason
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.strategy_wiring import STRATEGIES, StrategyDescriptor
from tests.api._support import AUTH, client_for
from tests.api.test_actions import _add, _create, _fields, _retire
from tests.application._refresh_fakes import FakeRuns, Probe, fakes

_ENDED = {"completed", "stopped", "failed"}
_JOB_KEYS = [
    "schema_version",
    "refresh_id",
    "watchlist_id",
    "state",
    "totals",
    "events",
    "next_after",
    "has_more",
    "summary",
    "failure",
]
_MOMENTUM = STRATEGIES[0]


def _entry(descriptor: StrategyDescriptor, ticker: str, **fields: object) -> dict[str, object]:
    return {"ticker": ticker, "method_id": descriptor.method_id, "selection": _fields(descriptor) | fields}


def _start(client: TestClient, body: dict[str, object]) -> httpx2.Response:
    return client.post("/v1/refreshes", json=body, headers=AUTH)


def _job(client: TestClient, refresh_id: object, after: object = None) -> httpx2.Response:
    suffix = "" if after is None else f"?after={after}"
    return client.get(f"/v1/refreshes/{refresh_id}/job{suffix}", headers=AUTH)


def _ended(client: TestClient, refresh_id: object) -> dict[str, object]:
    """Poll the job until it ends and return its document."""
    for _ in range(1500):
        response = _job(client, refresh_id)
        assert response.status_code == 200, response.text
        document: dict[str, object] = response.json()
        if document["state"] in _ENDED:
            return document
        time.sleep(0.01)
    raise AssertionError("the job did not end")


def _failure(response: httpx2.Response, status: int, code: str) -> dict[str, object]:
    assert response.status_code == status, response.text
    body: dict[str, object] = response.json()
    assert body["reason_code"] == code
    assert body["schema_version"] == 13
    return body


# --- the start request ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("descriptor", STRATEGIES, ids=lambda item: item.alias)
def test_each_strategy_is_refreshed_through_the_endpoints_from_a_list_of_entries(
    descriptor: StrategyDescriptor, isolated_cli_settings: ProjectSettings
) -> None:
    body = {"entries": [_entry(descriptor, "KO"), _entry(descriptor, "PG")], "save": False, "workers": 1}
    with client_for(isolated_cli_settings) as client, fakes(Probe()):
        started = _start(client, body)
        document = started.json()
        ended = _ended(client, document["refresh_id"])
        latest = client.get("/v1/refreshes/job", headers=AUTH).json()

    assert started.status_code == 202
    assert started.headers["location"] == f"/v1/refreshes/{document['refresh_id']}/job"
    assert list(document) == _JOB_KEYS
    assert document["state"] == "running" or document["state"] in _ENDED  # a fast job may have ended already
    assert document["next_after"] == len(document["events"])  # an ordinary view at after 0: the events so far
    assert (document["watchlist_id"], document["summary"], document["failure"]) == (None, None, None)
    assert ended["state"] == "completed"
    assert ended["totals"] == {"admitted": 2, "finished": 2, "remaining": 0}
    events = ended["events"]
    assert isinstance(events, list)
    assert [(item["sequence"], item["kind"], item["position"]) for item in events] == [
        (1, "started", 0),
        (2, "finished", 0),
        (3, "started", 1),
        (4, "finished", 1),
    ]
    finished = [item for item in events if item["kind"] == "finished"]
    assert [item["ticker"] for item in finished] == ["KO", "PG"]
    for item in finished:
        assert item["method_id"] == descriptor.method_id
        assert item["result"]["saved"] is False
        assert item["result"]["status"] == "completed"
        analysis = item["analysis"]
        assert list(analysis) == ["schema_version", "analysis_run_id", "document", "text"]
        assert analysis["analysis_run_id"] is None
        assert analysis["document"] == {
            "ticker": item["ticker"],
            "method_id": descriptor.method_id,
            "provider_check": None,
        }
        assert analysis["text"] == {
            mode: f"{item['ticker']} {descriptor.method_id} as {mode}" for mode in ("concise", "details", "diagnostics")
        }
    started_events = [item for item in events if item["kind"] == "started"]
    assert all(item["result"] is None and item["analysis"] is None for item in started_events)
    summary = ended["summary"]
    assert isinstance(summary, dict)
    assert summary["schema_version"] == 3
    assert (summary["watchlist_id"], summary["watchlist_name"]) == (None, None)
    assert ended["failure"] is None
    assert latest == ended


def test_a_watchlist_is_refreshed_with_the_defaults_of_the_command_line(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client, fakes(Probe()):
        watchlist = _create(client)
        assert _add(client, watchlist["watchlist_id"], _MOMENTUM, "KO", "PG").status_code == 200
        started = _start(client, {"watchlist_id": watchlist["watchlist_id"]})
        ended = _ended(client, started.json()["refresh_id"])

    assert started.status_code == 202
    assert started.json()["watchlist_id"] == watchlist["watchlist_id"]
    assert ended["state"] == "completed"
    summary = ended["summary"]
    assert isinstance(summary, dict)
    assert (summary["watchlist_id"], summary["watchlist_name"]) == (watchlist["watchlist_id"], "Core")
    assert [item["saved"] for item in summary["results"]] == [True, True]  # save defaults to true
    events = ended["events"]
    assert isinstance(events, list)
    for item in (item for item in events if item["kind"] == "finished"):
        assert item["analysis"]["analysis_run_id"] == item["result"]["analysis_run_id"] is not None


def test_workers_and_the_provider_check_default_as_on_the_command_line(isolated_cli_settings: ProjectSettings) -> None:
    with (
        client_for(isolated_cli_settings) as client,
        fakes(Probe()),
        patch("investment_analysis_engine.api.handlers.prepare_refresh") as prepare,
    ):
        prepare.side_effect = RuntimeError("stop here")
        client.post("/v1/refreshes", json={"entries": [_entry(_MOMENTUM, "KO")]}, headers=AUTH)
        client.post(
            "/v1/refreshes",
            json={"entries": [_entry(_MOMENTUM, "KO")], "workers": 3, "save": False, "provider_check": False},
            headers=AUTH,
        )

    defaults, given = prepare.call_args_list
    assert defaults.kwargs == {"workers": 2, "save": True, "provider_check": isolated_cli_settings.provider_check}
    assert given.kwargs == {"workers": 3, "save": False, "provider_check": False}


@pytest.mark.parametrize(
    ("body", "parameters"),
    [
        ({}, ["watchlist_id", "entries"]),
        ({"watchlist_id": str(uuid4()), "entries": []}, ["watchlist_id", "entries"]),
        ({"watchlist_id": "nope"}, ["watchlist_id"]),
        ({"entries": []}, ["entries"]),
        ({"entries": [{"ticker": "KO"}]}, ["entries[0].method_id"]),
        ({"entries": [{"ticker": "KO", "method_id": "m", "colour": 1}]}, ["entries[0].colour"]),
        ({"entries": [{"ticker": "KO", "method_id": "m"}], "workers": 9}, ["workers"]),
        ({"entries": [{"ticker": "KO", "method_id": "m"}], "workers": "2"}, ["workers"]),
        ({"entries": [{"ticker": "KO", "method_id": "m"}], "save": "yes"}, ["save"]),
        ({"entries": [{"ticker": "KO", "method_id": "m"}], "extra": 1}, ["extra"]),
    ],
)
def test_a_rejected_start_request_is_a_400_naming_its_parameters(
    body: dict[str, object], parameters: list[str], isolated_cli_settings: ProjectSettings
) -> None:
    body = {
        key: [{**item, "method_id": _MOMENTUM.method_id} if item.get("method_id") == "m" else item for item in value]
        if key == "entries" and isinstance(value, list)
        else value
        for key, value in body.items()
    }
    with client_for(isolated_cli_settings) as client:
        response = _start(client, body)
        latest = client.get("/v1/refreshes/job", headers=AUTH)

    assert _failure(response, 400, "invalid_parameter")["parameters"] == parameters
    _failure(latest, 404, "refresh_job_not_found")  # nothing started


def test_entry_errors_are_named_by_their_index_and_listed_together(isolated_cli_settings: ProjectSettings) -> None:
    entries = [
        _entry(_MOMENTUM, "KO"),
        {"ticker": "PG", "method_id": "no_such_method", "selection": {}},
        _entry(_MOMENTUM, "T", short_window=50, long_window=10),
        _entry(_MOMENTUM, "KO"),
    ]
    with client_for(isolated_cli_settings) as client:
        failure = _failure(_start(client, {"entries": entries}), 400, "invalid_parameter")

    errors = failure["errors"]
    assert isinstance(errors, list)
    assert [item["parameters"] for item in errors] == [
        ["entries[1].method_id"],
        ["entries[2].selection.short_window", "entries[2].selection.long_window"],
        ["entries[3]"],
    ]
    assert [item["rule"] for item in errors][2] == "entries.duplicate"
    assert failure["parameters"] == ["entries[1].method_id"]


def test_an_empty_list_of_entries_names_its_rule(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        failure = _failure(_start(client, {"entries": []}), 400, "invalid_parameter")

    assert failure["reason"] == "entries must hold at least one entry."
    assert failure["errors"][0]["rule"] == "refresh.entries_empty"  # type: ignore[index]


def test_a_missing_watchlist_an_empty_one_and_an_unreadable_one_are_refused_before_the_202(
    isolated_cli_settings: ProjectSettings,
) -> None:
    with client_for(isolated_cli_settings) as client, fakes(Probe()):
        missing = _start(client, {"watchlist_id": str(uuid4())})
        empty = _create(client, "Empty")
        empty_response = _start(client, {"watchlist_id": empty["watchlist_id"]})
        broken = _create(client, "Broken")
        assert _add(client, broken["watchlist_id"], _MOMENTUM, "KO", "PG").status_code == 200
        _retire(isolated_cli_settings, "PG")
        unreadable = _start(client, {"watchlist_id": broken["watchlist_id"]})
        none_started = client.get("/v1/refreshes/job", headers=AUTH)

    _failure(missing, 404, "watchlist_not_found")
    assert (
        _failure(empty_response, 409, "watchlist_empty")["reason"]
        == "Watchlist 'Empty' has no entries; there is nothing to refresh."
    )
    _failure(unreadable, 409, "stored_selection_unreadable")
    _failure(none_started, 404, "refresh_job_not_found")


def test_a_busy_database_is_a_503_before_the_202(isolated_cli_settings: ProjectSettings) -> None:
    busy = DatabaseReadinessError(ReadinessReason.BUSY, None)
    with (
        client_for(isolated_cli_settings) as client,
        patch("investment_analysis_engine.application.refresh.open_database", side_effect=busy),
    ):
        response = _start(client, {"entries": [_entry(_MOMENTUM, "KO")]})

    _failure(response, 503, "database_busy")


# --- following a job -----------------------------------------------------------------------------------------------


def test_after_selects_later_events_and_a_bad_after_is_a_400(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client, fakes(Probe()):
        started = _start(client, {"entries": [_entry(_MOMENTUM, "KO"), _entry(_MOMENTUM, "PG")], "save": False})
        refresh_id = started.json()["refresh_id"]
        _ended(client, refresh_id)
        everything = _job(client, refresh_id, 0).json()
        after_two = _job(client, refresh_id, 2).json()
        beyond = _job(client, refresh_id, 99).json()
        negative = _job(client, refresh_id, -1)
        text = _job(client, refresh_id, "x")
        twice = client.get(f"/v1/refreshes/{refresh_id}/job?after=1&after=2", headers=AUTH)
        unknown = client.get(f"/v1/refreshes/{refresh_id}/job?before=1", headers=AUTH)

    assert [item["sequence"] for item in everything["events"]] == [1, 2, 3, 4]
    assert (everything["next_after"], everything["has_more"]) == (4, False)
    assert [item["sequence"] for item in after_two["events"]] == [3, 4]
    assert (beyond["events"], beyond["next_after"], beyond["has_more"]) == ([], 99, False)
    assert _failure(negative, 400, "invalid_parameter")["parameters"] == ["after"]
    _failure(text, 400, "invalid_parameter")
    _failure(twice, 400, "invalid_parameter")
    _failure(unknown, 400, "invalid_parameter")


def test_a_poll_holds_events_to_the_budget_and_always_returns_one(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client, fakes(Probe()):
        started = _start(client, {"entries": [_entry(_MOMENTUM, "KO"), _entry(_MOMENTUM, "PG")], "save": False})
        refresh_id = started.json()["refresh_id"]
        _ended(client, refresh_id)
        with patch("investment_analysis_engine.api.handlers.MAX_REQUEST_BODY_BYTES", 1):
            seen: list[int] = []
            after = 0
            for _ in range(10):
                page = _job(client, refresh_id, after).json()
                seen.extend(item["sequence"] for item in page["events"])
                after = page["next_after"]
                assert len(page["events"]) == 1 or not page["events"]  # each event is larger than a one-byte budget
                if not page["has_more"]:
                    break

    assert seen == [1, 2, 3, 4]
    assert MAX_REQUEST_BODY_BYTES == 1_048_576


def test_an_older_job_is_not_found_once_a_new_one_replaces_it_and_one_runs_at_a_time(
    isolated_cli_settings: ProjectSettings,
) -> None:
    gate, entered = threading.Event(), threading.Event()
    runs = FakeRuns(gate=gate, entered=entered)
    body = {"entries": [_entry(_MOMENTUM, "KO")], "save": False}
    with client_for(isolated_cli_settings) as client, fakes(Probe(), runs):
        first = _start(client, body).json()["refresh_id"]
        assert entered.wait(30)
        refused = _start(client, body)
        gate.set()
        _ended(client, first)
        second = _start(client, body).json()["refresh_id"]
        _ended(client, second)
        old = _job(client, first)
        old_stop = client.post(f"/v1/refreshes/{first}/job/stop", headers=AUTH)
        current = _job(client, second)

    failure = _failure(refused, 409, "refresh_job_running")
    assert first in str(failure["reason"])
    assert first != second
    _failure(old, 404, "refresh_job_not_found")
    _failure(old_stop, 404, "refresh_job_not_found")
    assert current.status_code == 200


def test_an_unknown_id_and_a_malformed_one_are_refused(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        unknown = _job(client, uuid4())
        malformed = _job(client, "nope")
        stop_malformed = client.post("/v1/refreshes/nope/job/stop", headers=AUTH)
        latest = client.get("/v1/refreshes/job", headers=AUTH)

    _failure(unknown, 404, "refresh_job_not_found")
    _failure(malformed, 400, "invalid_parameter")
    _failure(stop_malformed, 400, "invalid_parameter")
    assert _failure(latest, 404, "refresh_job_not_found")["reason"] == "This server has not started a refresh job."


# --- stopping ------------------------------------------------------------------------------------------------------


def test_stop_ends_the_job_stopped_and_is_idempotent(isolated_cli_settings: ProjectSettings) -> None:
    gate, entered = threading.Event(), threading.Event()
    body = {"entries": [_entry(_MOMENTUM, "KO"), _entry(_MOMENTUM, "PG"), _entry(_MOMENTUM, "T")], "workers": 1}
    with client_for(isolated_cli_settings) as client, fakes(Probe(), FakeRuns(gate=gate, entered=entered)):
        refresh_id = _start(client, body).json()["refresh_id"]
        assert entered.wait(30)
        first = client.post(f"/v1/refreshes/{refresh_id}/job/stop", headers=AUTH)
        second = client.post(f"/v1/refreshes/{refresh_id}/job/stop", headers=AUTH)
        mid = _job(client, refresh_id).json()
        gate.set()
        ended = _ended(client, refresh_id)
        third = client.post(f"/v1/refreshes/{refresh_id}/job/stop", headers=AUTH)

    assert first.status_code == second.status_code == third.status_code == 200
    assert list(first.json()) == _JOB_KEYS
    assert first.json()["state"] == second.json()["state"] == mid["state"] == "stopping"
    assert ended["state"] == "stopped"
    assert ended["totals"] == {"admitted": 1, "finished": 1, "remaining": 2}
    assert [item["ticker"] for item in ended["summary"]["results"]] == ["KO"]  # type: ignore[index]
    assert third.json()["state"] == "stopped"


def test_a_client_that_passes_on_each_next_after_sees_every_event_exactly_once(
    isolated_cli_settings: ProjectSettings,
) -> None:
    gate, entered = threading.Event(), threading.Event()
    runs = FakeRuns(gate=gate, entered=entered, blocked=frozenset({"PG"}))
    body = {"entries": [_entry(_MOMENTUM, "KO"), _entry(_MOMENTUM, "PG"), _entry(_MOMENTUM, "T")], "workers": 1}
    seen: list[int] = []

    def take(document: dict[str, object]) -> int:
        events = document["events"]
        assert isinstance(events, list)
        seen.extend(item["sequence"] for item in events)
        next_after = document["next_after"]
        assert isinstance(next_after, int)
        return next_after

    with (
        client_for(isolated_cli_settings) as client,
        fakes(Probe(), runs),
        patch("investment_analysis_engine.api.handlers.MAX_REQUEST_BODY_BYTES", 1),  # one event in each answer
    ):
        started = _start(client, body)
        refresh_id = started.json()["refresh_id"]
        after = take(started.json())
        assert entered.wait(30)
        for _ in range(1500):  # wait, without reading events, until the second entry has started
            if _job(client, refresh_id, 999).json()["totals"]["admitted"] == 2:
                break
            time.sleep(0.01)
        while after < 1:  # the client has the first event; three are recorded
            after = take(_job(client, refresh_id, after).json())
        given = after
        stop = client.post(f"/v1/refreshes/{refresh_id}/job/stop?after={given}", headers=AUTH)
        stopped = stop.json()
        after = take(stopped)
        gate.set()
        for _ in range(1500):
            polled = _job(client, refresh_id, after).json()
            after = take(polled)
            if polled["state"] in _ENDED and not polled["has_more"]:
                break
            time.sleep(0.01)

    assert stop.status_code == 200
    assert stopped["state"] == "stopping"
    assert [item["sequence"] for item in stopped["events"]] == [given + 1]  # the event after the `after` it was given
    assert (stopped["next_after"], stopped["has_more"]) == (given + 1, True)
    assert polled["state"] == "stopped"
    assert seen == [1, 2, 3, 4]  # every event exactly once, the stop answer's included


def test_a_stop_with_a_rejected_after_changes_nothing(isolated_cli_settings: ProjectSettings) -> None:
    gate, entered = threading.Event(), threading.Event()
    body = {"entries": [_entry(_MOMENTUM, "KO"), _entry(_MOMENTUM, "PG")], "workers": 1}
    with client_for(isolated_cli_settings) as client, fakes(Probe(), FakeRuns(gate=gate, entered=entered)):
        refresh_id = _start(client, body).json()["refresh_id"]
        assert entered.wait(30)
        negative = client.post(f"/v1/refreshes/{refresh_id}/job/stop?after=-1", headers=AUTH)
        text = client.post(f"/v1/refreshes/{refresh_id}/job/stop?after=x", headers=AUTH)
        state = _job(client, refresh_id).json()["state"]
        gate.set()
        ended = _ended(client, refresh_id)

    assert _failure(negative, 400, "invalid_parameter")["parameters"] == ["after"]
    _failure(text, 400, "invalid_parameter")
    assert state == "running"
    assert ended["state"] == "completed"  # it was never stopped


def test_an_event_that_cannot_be_built_fails_the_job_with_its_failure_document(
    isolated_cli_settings: ProjectSettings,
) -> None:
    gate, entered = threading.Event(), threading.Event()
    runs = FakeRuns(gate=gate, entered=entered)
    body = {"entries": [_entry(_MOMENTUM, "KO"), _entry(_MOMENTUM, "PG")], "workers": 1}
    real = refresh_documents._event_of  # noqa: SLF001 - the one builder of an event

    def failing_second(sequence: int, progress: object) -> object:
        if sequence == 2:
            raise RuntimeError("cannot build")
        return real(sequence, progress)  # type: ignore[arg-type]

    with (
        client_for(isolated_cli_settings) as client,
        fakes(Probe(), runs),
        patch("investment_analysis_engine.api.refresh_documents._event_of", side_effect=failing_second),
    ):
        refresh_id = _start(client, body).json()["refresh_id"]
        gate.set()
        ended = _ended(client, refresh_id)

    assert ended["state"] == "failed"
    assert ended["summary"] is None
    events = ended["events"]
    assert isinstance(events, list)
    assert [item["sequence"] for item in events] == [1]
    assert ended["failure"]["reason_code"] == "execution_error"  # type: ignore[index]
    assert ended["failure"]["reason"] == "The request failed unexpectedly."  # type: ignore[index]
    assert [ticker for ticker, _ in runs.calls] == ["KO"]  # nothing more was admitted


def test_a_stop_after_the_last_admission_ends_completed(isolated_cli_settings: ProjectSettings) -> None:
    gate, entered = threading.Event(), threading.Event()
    body = {"entries": [_entry(_MOMENTUM, "KO"), _entry(_MOMENTUM, "PG")], "workers": 2, "save": False}
    with client_for(isolated_cli_settings) as client, fakes(Probe(), FakeRuns(gate=gate, entered=entered)):
        refresh_id = _start(client, body).json()["refresh_id"]
        assert entered.wait(30)
        for _ in range(1500):
            if _job(client, refresh_id).json()["totals"]["admitted"] == 2:
                break
            time.sleep(0.01)
        stopped = client.post(f"/v1/refreshes/{refresh_id}/job/stop", headers=AUTH).json()
        gate.set()
        ended = _ended(client, refresh_id)

    assert stopped["state"] == "stopping"
    assert ended["state"] == "completed"
    assert len(ended["summary"]["results"]) == 2  # type: ignore[index]


def test_a_job_that_fails_after_the_202_is_failed(isolated_cli_settings: ProjectSettings) -> None:
    calls: list[ApplicationContext] = []
    real = open_database

    def open_once(context: ApplicationContext) -> AbstractContextManager[SQLiteDatabase]:
        calls.append(context)
        if len(calls) > 1:
            raise DatabaseReadinessError(ReadinessReason.BUSY, None)
        return real(context)

    body = {"entries": [_entry(_MOMENTUM, "KO")], "save": True}
    with (
        client_for(isolated_cli_settings) as client,
        fakes(Probe()),
        patch("investment_analysis_engine.application.refresh.open_database", side_effect=open_once),
    ):
        started = _start(client, body)
        ended = _ended(client, started.json()["refresh_id"])

    assert started.status_code == 202
    assert ended["state"] == "failed"
    assert ended["summary"] is None
    failure = ended["failure"]
    assert isinstance(failure, dict)
    assert (failure["reason_code"], failure["schema_version"]) == ("database_busy", 13)
    assert ended["events"] == []


def test_the_events_of_a_job_that_failed_midway_are_kept(isolated_cli_settings: ProjectSettings) -> None:
    body = {"entries": [_entry(_MOMENTUM, "KO"), _entry(_MOMENTUM, "PG")], "workers": 1, "save": False}
    with (
        client_for(isolated_cli_settings) as client,
        fakes(Probe()),
        patch(
            "investment_analysis_engine.application.refresh.provider_check_findings", side_effect=RuntimeError("boom")
        ),
    ):
        refresh_id = _start(client, body).json()["refresh_id"]
        ended = _ended(client, refresh_id)

    assert ended["state"] == "failed"
    assert ended["failure"]["reason_code"] == "execution_error"  # type: ignore[index]
    assert len(ended["events"]) == 4  # type: ignore[arg-type]
    assert ended["summary"] is None


def test_a_job_that_raised_has_no_analysis_in_its_finished_event(isolated_cli_settings: ProjectSettings) -> None:
    body = {"entries": [_entry(_MOMENTUM, "KO")], "save": False}
    with client_for(isolated_cli_settings) as client, fakes(Probe(), FakeRuns(raising=frozenset({"KO"}))):
        ended = _ended(client, _start(client, body).json()["refresh_id"])

    finished = ended["events"][1]  # type: ignore[index]
    assert ended["state"] == "completed"
    assert finished["analysis"] is None
    assert finished["result"]["error"] is not None
    assert finished["result"]["reason_code"] == "execution_error"


def test_a_failed_provider_run_carries_its_provider_check_in_the_summary_and_none_in_its_event(
    isolated_cli_settings: ProjectSettings,
) -> None:
    body = {"entries": [_entry(_MOMENTUM, "KO")], "save": False, "provider_check": True}
    with client_for(isolated_cli_settings) as client, fakes(Probe(), FakeRuns(failing=frozenset({"KO"}))):
        ended = _ended(client, _start(client, body).json()["refresh_id"])

    finished = ended["events"][1]  # type: ignore[index]
    assert finished["analysis"]["document"]["provider_check"] is None
    assert ended["summary"]["provider_check"][0]["provider_id"] == "yfinance"  # type: ignore[index]


# --- the table ------------------------------------------------------------------------------------------------------


def test_the_refresh_routes_declare_their_statuses_and_the_codes_map_to_them() -> None:
    routes = {route.operation_id: route for route in ROUTES}
    start = routes["start_refresh"]
    assert (start.method, start.path, start.success_status) == ("POST", "/v1/refreshes", 202)
    assert {status for status, _ in start.responses} == {202, 400, 401, 404, 405, 409, 500, 503}
    for name in ("get_refresh_job", "get_latest_refresh_job", "stop_refresh_job"):
        assert {status for status, _ in routes[name].responses} == {200, 400, 401, 404, 405, 500}
    assert routes["get_latest_refresh_job"].path == "/v1/refreshes/job"
    assert routes["stop_refresh_job"].method == "POST"
    assert STATUS_BY_CODE[next(code for code in STATUS_BY_CODE if code.value == "refresh_job_not_found")] == 404
    conflicts = {code.value for code, status in STATUS_BY_CODE.items() if status == 409}
    assert {"watchlist_empty", "refresh_job_running"} <= conflicts


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/v1/refreshes"),
        ("GET", "/v1/refreshes/job"),
        ("GET", "/v1/refreshes/00000000-0000-4000-8000-000000000000/job"),
        ("POST", "/v1/refreshes/00000000-0000-4000-8000-000000000000/job/stop"),
    ],
)
def test_a_preflight_for_each_refresh_route_is_answered_and_a_wrong_method_is_a_405(
    method: str, path: str, isolated_cli_settings: ProjectSettings
) -> None:
    origin = "tauri://localhost"
    wrong = "DELETE"
    with client_for(isolated_cli_settings, origins=[origin]) as client:
        preflight = client.options(path, headers={"Origin": origin, "Access-Control-Request-Method": method})
        refused = client.request(wrong, path, headers=AUTH)

    assert preflight.status_code == 204
    assert method in preflight.headers["access-control-allow-methods"].split(", ")
    assert refused.status_code == 405
