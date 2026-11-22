"""A storage error after the readiness check answers its precise database code, not an execution error.

A second connection holds a real lock on a migrated file, and the busy wait is a tenth of a second.
"""

from pathlib import Path

import pytest

from investment_analysis_engine.data.repositories.database_errors import DatabaseReason
from tests._database_lock import held_lock, lock_after_readiness, short_wait_settings
from tests.api._support import AUTH, client_for

_BUSY_MESSAGE = (
    "The database is in use by another operation and did not become free within the configured wait. "
    "Close other database operations and retry."
)


def _assert_busy(body: dict[str, object], path: Path) -> None:
    assert body["reason_code"] == "database_busy"
    assert body["status"] == "error"
    assert body["reason"] == _BUSY_MESSAGE
    assert body["database"] == {"database_path": str(path), "expected_revision": None}


def test_a_read_endpoint_answers_database_busy_with_503_when_the_lock_comes_after_readiness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, path = short_wait_settings(tmp_path)

    with client_for(settings) as client, lock_after_readiness(monkeypatch, path, block_reads=True):
        response = client.get("/v1/watchlists", headers=AUTH)

    assert response.status_code == 503, response.text
    _assert_busy(response.json(), path)


def test_a_write_endpoint_answers_database_busy_with_503_while_another_connection_writes(tmp_path: Path) -> None:
    settings, path = short_wait_settings(tmp_path)

    with client_for(settings) as client, held_lock(path):
        response = client.post("/v1/watchlists", json={"name": "Core"}, headers=AUTH)

    assert response.status_code == 503, response.text
    _assert_busy(response.json(), path)


def test_the_endpoints_serve_again_once_the_lock_is_released(tmp_path: Path) -> None:
    settings, path = short_wait_settings(tmp_path)

    with client_for(settings) as client:
        with held_lock(path):
            busy = client.post("/v1/watchlists", json={"name": "Core"}, headers=AUTH)
        created = client.post("/v1/watchlists", json={"name": "Core"}, headers=AUTH)

    assert (busy.status_code, created.status_code) == (503, 201)
    assert DatabaseReason.BUSY.value == busy.json()["reason_code"]
