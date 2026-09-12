"""Analysis storage failures retain their safe presentation and bypass contracts."""

import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.cli_support import _production_financial_cache
from src.config import ProjectSettings
from src.core.telemetry.models import TrajectoryEventType
from src.core.telemetry.recorder import TrajectoryRecord, TrajectoryRecorder
from src.core.telemetry.run_context import RunContext
from src.core.telemetry.sinks import SQLiteTrajectorySink
from src.data.repositories import SQLiteDatabase, migrations, readiness
from src.data.repositories.readiness import DatabaseReadinessError, ReadinessReason

COMMANDS = ["momentum", "graham-number", "graham-growth", "fcf-growth"]


def arguments(command: str) -> list[str]:
    """Use valid offline arguments so storage, rather than parsing, fails."""
    return [command, "SYNTH", *(["-g", "5", "-y", "4.5"] if command == "graham-growth" else [])]


@pytest.mark.parametrize("command", COMMANDS)
@pytest.mark.parametrize("mode", [[], ["--details"], ["--diagnostics"], ["--json"]])
@pytest.mark.parametrize("reason", list(ReadinessReason))
def test_typed_readiness_failure_preserves_envelope_and_closes_storage(
    tmp_path: Path, command: str, mode: list[str], reason: ReadinessReason
) -> None:
    path = tmp_path / "selected % café.sqlite3"
    database = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{path.as_posix()}"))
    error = DatabaseReadinessError(reason, path, "0001_persistence")
    error.__cause__ = RuntimeError("private SQL parameters and credentials")
    with (
        patch("src.cli_support.SQLiteDatabase", return_value=database),
        patch("src.cli_support.ensure_database_ready", side_effect=error),
        patch("src.cli._build_sec_production_provider", side_effect=AssertionError("Provider must not run")) as facts,
        patch(
            "src.cli.YFinanceClient.fetch_historical_data", side_effect=AssertionError("Provider must not run")
        ) as history,
    ):
        result = CliRunner().invoke(app, [*arguments(command), *mode])
    assert result.exit_code == 1, result.output
    facts.assert_not_called()
    history.assert_not_called()
    assert "private SQL" not in result.output
    if mode == ["--json"]:
        report = json.loads(result.stdout)
        assert report["schema_version"] == (4 if command == "momentum" else 5)
        assert report["status"] == "error"
        assert report["result"] is None
        assert report["reason_code"] == reason.value
        assert report["reason"] == str(error)
        assert not result.stderr
    else:
        assert not result.stdout
        assert result.stderr.strip() == str(error)
    assert not path.exists()
    with pytest.raises(RuntimeError, match="closed"), database.read():
        pytest.fail("Storage leaked after a readiness failure.")


@pytest.mark.parametrize("command", COMMANDS)
@pytest.mark.parametrize("state", ["incompatible", "corrupt", "older"])
def test_real_rejected_storage_precedes_provider_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str, state: str
) -> None:
    path = tmp_path / "selected.sqlite3"
    selected = ProjectSettings(database_url=f"sqlite:///{path.as_posix()}")
    if state == "corrupt":
        path.write_bytes(b"private-invalid-file")
        reason = ReadinessReason.INVALID_FILE
    elif state == "incompatible":
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("CREATE TABLE private_records(value TEXT)")
            connection.commit()
        reason = ReadinessReason.INCOMPATIBLE_SCHEMA
    else:
        database = SQLiteDatabase(selected)
        try:
            readiness.ensure_database_ready(database)
        finally:
            database.close()
        resources = migrations.migration_resources()
        monkeypatch.setattr(
            readiness,
            "migration_resources",
            lambda: replace(resources, head="synthetic_head", ancestors=frozenset({resources.head})),
        )
        reason = ReadinessReason.UPGRADE_REQUIRED
    before = path.read_bytes()
    with (
        patch("src.cli_support.settings", selected),
        patch("src.cli._build_sec_production_provider", side_effect=AssertionError("Provider must not run")) as facts,
        patch(
            "src.cli.YFinanceClient.fetch_historical_data", side_effect=AssertionError("Provider must not run")
        ) as history,
    ):
        result = CliRunner().invoke(app, [*arguments(command), "--json"])
    assert result.exit_code == 1, result.output
    report = json.loads(result.stdout)
    assert report["reason_code"] == reason.value
    assert json.dumps(str(path)) in report["reason"]
    assert ("alembic upgrade head" in report["reason"]) == (state == "older")
    assert not result.stderr
    assert path.read_bytes() == before
    facts.assert_not_called()
    history.assert_not_called()


@pytest.mark.parametrize("command", [[], *[[name] for name in COMMANDS], ["db"], ["db", "status"], ["db", "upgrade"]])
def test_help_never_opens_storage(tmp_path: Path, command: list[str]) -> None:
    path = tmp_path / "absent" / "help.sqlite3"
    selected = ProjectSettings(database_url=f"sqlite:///{path.as_posix()}")
    with (
        patch("src.cli_support.settings", selected),
        patch("src.cli_database.settings", selected),
        patch("src.cli_support.SQLiteDatabase", side_effect=AssertionError("Storage must not open")) as analysis_db,
        patch("src.cli_database.SQLiteDatabase", side_effect=AssertionError("Storage must not open")) as maintenance_db,
    ):
        result = CliRunner().invoke(app, [*command, "--help"])
    assert result.exit_code == 0, result.output
    analysis_db.assert_not_called()
    maintenance_db.assert_not_called()
    assert not path.parent.exists()


@pytest.mark.parametrize("incompatible", [False, True])
def test_optional_telemetry_failure_does_not_control_cache_readiness(tmp_path: Path, incompatible: bool) -> None:
    telemetry_path = tmp_path / "telemetry.sqlite3"
    cache_path = tmp_path / "analysis.sqlite3"
    telemetry_database = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{telemetry_path.as_posix()}"))
    selected = ProjectSettings(database_url=f"sqlite:///{cache_path.as_posix()}")
    if incompatible:
        cache_path.write_bytes(b"invalid-cache")
    recorder = TrajectoryRecorder(RunContext.new(), SQLiteTrajectorySink(telemetry_database))
    try:
        with patch.object(readiness, "ensure_database_ready", side_effect=AssertionError("Telemetry must not migrate")):
            assert recorder.record(TrajectoryRecord(TrajectoryEventType.RUN_START, "test")) is not None
        assert not Path(str(telemetry_path) + ".readiness.lock").exists()
        with patch("src.cli_support.settings", selected):
            if incompatible:
                with pytest.raises(DatabaseReadinessError) as caught, _production_financial_cache(enabled=True):
                    pytest.fail("Invalid storage was accepted.")
                assert caught.value.reason is ReadinessReason.INVALID_FILE
            else:
                with _production_financial_cache(enabled=True):
                    assert cache_path.exists()
        with telemetry_database.read() as connection:
            assert connection.exec_driver_sql("SELECT name FROM sqlite_schema WHERE type='table'").all() == []
    finally:
        recorder.close()
        telemetry_database.close()


def test_fresh_process_cli_import_does_not_connect_or_create_storage(tmp_path: Path) -> None:
    path = tmp_path / "absent" / "import.sqlite3"
    environment = dict(os.environ, DATABASE_URL=f"sqlite:///{path.as_posix()}", TELEMETRY_LEVEL="OFF")
    script = (
        "from unittest.mock import patch\n"
        "with patch('sqlite3.connect', side_effect=AssertionError('Import must not connect')) as connect:\n"
        "    import src.cli\n"
        "    connect.assert_not_called()\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not result.stdout
    assert not path.parent.exists()
