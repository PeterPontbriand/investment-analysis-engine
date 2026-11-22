"""A storage error after the readiness check is reported by the command line under its precise database code.

A second connection holds a real lock on a migrated file, and the busy wait is a tenth of a second.
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from investment_analysis_engine.cli import app
from investment_analysis_engine.cli_support import database_message
from investment_analysis_engine.data.repositories.database_errors import DatabaseError, DatabaseReason
from tests._cli_helpers import normalize_cli_output
from tests._database_lock import held_lock, lock_after_readiness, short_wait_settings

pytestmark = pytest.mark.usefixtures("stub_yahoo_identity_metadata")

runner = CliRunner()


def _short_wait(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    settings, path = short_wait_settings(tmp_path)
    monkeypatch.setattr("investment_analysis_engine.cli_support.settings", settings)
    monkeypatch.setattr("investment_analysis_engine.cli_workspace.settings", settings)
    return path


def _assert_busy_document(stdout: str, path: Path) -> None:
    document = json.loads(stdout)
    expected = DatabaseError(DatabaseReason.BUSY, path)
    assert document["status"] == "error"
    assert document["reason_code"] == "database_busy"
    assert document["reason"] == database_message(expected)
    assert document["database"] == {"database_path": str(path), "expected_revision": None}
    assert "did not become free within the configured wait" in document["reason"]


def test_a_read_command_writes_the_database_busy_document(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _short_wait(tmp_path, monkeypatch)

    with lock_after_readiness(monkeypatch, path, block_reads=True):
        result = runner.invoke(app, ["runs", "list", "--json"])

    assert result.exit_code == 1
    assert not result.stderr
    _assert_busy_document(result.stdout, path)


def test_a_write_command_writes_the_database_busy_document(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _short_wait(tmp_path, monkeypatch)

    with held_lock(path):
        result = runner.invoke(app, ["watchlist", "create", "Core", "--json"])

    assert result.exit_code == 1
    assert not result.stderr
    _assert_busy_document(result.stdout, path)


def test_without_json_the_message_is_on_standard_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _short_wait(tmp_path, monkeypatch)

    with held_lock(path):
        result = runner.invoke(app, ["watchlist", "create", "Core"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert normalize_cli_output(result.stderr) == normalize_cli_output(
        database_message(DatabaseError(DatabaseReason.BUSY, path))
    )
