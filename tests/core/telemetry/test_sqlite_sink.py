"""Verify atomic trajectory persistence against migrated temporary databases."""

import json
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError, OperationalError

from alembic import command
from src.config import ProjectSettings
from src.core.telemetry import recorder as recorder_module
from src.core.telemetry.models import TelemetryMode, TrajectoryEvent, TrajectoryEventType
from src.core.telemetry.recorder import TrajectoryRecord, TrajectoryRecorder
from src.core.telemetry.run_context import RunContext
from src.core.telemetry.sinks import JSONLTrajectorySink, SQLiteTrajectorySink, TrajectorySink, read_trajectory
from src.data.repositories.schema import schema_metadata, trajectory_events
from src.data.repositories.sqlite import SQLiteDatabase
from src.data.repositories.trajectory import SQLiteTrajectoryRepository


def test_repository_and_sink_share_immutable_storage(
    database: SQLiteDatabase, event: TrajectoryEvent, tmp_path: Path
) -> None:
    repository = SQLiteTrajectoryRepository(database)
    assert repository.read_trajectory(event.run_id) == []
    repository.record(event)
    sink = SQLiteTrajectorySink(database)
    sink.record(event)
    later = event.model_copy(update={"event_id": uuid4(), "sequence": 3})
    sink.record(later)
    sink.close()
    assert repository.read_trajectory(event.run_id) == [event, later]
    assert read_trajectory(database, event.run_id) == [event, later]
    with pytest.raises(ValueError, match="Conflicting"):
        repository.record(event.model_copy(update={"payload_hash": "different"}))
    with pytest.raises(IntegrityError):
        repository.record(event.model_copy(update={"event_id": uuid4()}))
    assert repository.read_trajectory(event.run_id) == [event, later]
    database.close()
    reopened = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{(tmp_path / 'telemetry.sqlite3').as_posix()}"))
    try:
        assert SQLiteTrajectoryRepository(reopened).read_trajectory(event.run_id) == [event, later]
    finally:
        reopened.close()


def test_repository_concurrent_retry_is_idempotent(database: SQLiteDatabase, event: TrajectoryEvent) -> None:
    repository = SQLiteTrajectoryRepository(database)
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(repository.record, event) for _ in range(4)]
        for future in futures:
            future.result()
    assert repository.read_trajectory(event.run_id) == [event]


def test_repository_does_not_create_schema(tmp_path: Path, event: TrajectoryEvent) -> None:
    path = tmp_path / "unmigrated.sqlite3"
    database = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{path.as_posix()}"))
    repository = SQLiteTrajectoryRepository(database)
    assert not path.exists()
    try:
        with pytest.raises(OperationalError):
            repository.record(event)
        with pytest.raises(OperationalError):
            repository.read_trajectory(event.run_id)
    finally:
        database.close()


@pytest.mark.parametrize("version", [None, 2])
def test_repository_preserves_write_and_read_encoding_policy(
    database: SQLiteDatabase, event: TrajectoryEvent, version: int | None
) -> None:
    with database.transaction() as connection:
        if version is None:
            connection.execute(delete(schema_metadata))
        else:
            connection.execute(update(schema_metadata).values(metadata_value=version))
    repository = SQLiteTrajectoryRepository(database)
    # Existing writes do not check the readback encoding marker.
    repository.record(event)
    repository.record(event)
    with pytest.raises(ValueError, match="encoding version"):
        repository.read_trajectory(event.run_id)


@pytest.fixture
def database(tmp_path: Path) -> Iterator[SQLiteDatabase]:
    url = f"sqlite:///{(tmp_path / 'telemetry.sqlite3').as_posix()}"
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        yield database
    finally:
        database.close()


@pytest.fixture
def event() -> TrajectoryEvent:
    return TrajectoryEvent(
        run_id=uuid4(),
        session_id=uuid4(),
        sequence=1,
        timestamp=datetime(2026, 9, 5, 10, 30, 0, 123456, tzinfo=timezone(timedelta(hours=-4))),
        event_type=TrajectoryEventType.TOOL_RESULT,
        component="tool",
        mode=TelemetryMode.FULL,
        span_id=uuid4(),
        parent_span_id=uuid4(),
        schema_version=2,
        model_tag="local-model",
        provider="local",
        step_index=2,
        tool_name="analyze",
        tool_args={"z": 1, "a": "é"},
        tool_result_summary=[True, None, 2.5],
        prompt_tokens=0,
        completion_tokens=4,
        latency_ms=1.25,
        payload={"nested": [1, {"ok": False}]},
        payload_hash="retained-hash",
        error={"message": "synthetic"},
    )


def rows(database: SQLiteDatabase) -> list[dict[str, object]]:
    with database.read() as connection:
        return [
            dict(row)
            for row in connection.execute(select(trajectory_events).order_by(trajectory_events.c.sequence)).mappings()
        ]


def test_all_fields_and_order(database: SQLiteDatabase, event: TrajectoryEvent) -> None:
    sink: TrajectorySink = SQLiteTrajectorySink(database)
    later = event.model_copy(update={"event_id": uuid4(), "sequence": 3})
    sink.record(later)
    sink.record(event)
    sink.flush()
    sink.close()
    stored = rows(database)
    assert [row["sequence"] for row in stored] == [1, 3]
    assert stored[0]["timestamp"] == "2026-09-05T14:30:00.123456Z"
    assert stored[0]["tool_args_json"] == '{"a":"é","z":1}'
    for row, expected in zip(stored, [event, later], strict=True):
        decoded = dict(row)
        for name in ("tool_args", "tool_result_summary", "payload", "error"):
            encoded = decoded.pop(f"{name}_json")
            assert isinstance(encoded, str)
            decoded[name] = json.loads(encoded)
        assert TrajectoryEvent.model_validate(decoded) == expected


def test_optional_fields_remain_null(database: SQLiteDatabase, event: TrajectoryEvent) -> None:
    minimal = TrajectoryEvent(
        **{name: getattr(event, name) for name, field in TrajectoryEvent.model_fields.items() if field.is_required()}
    )
    SQLiteTrajectorySink(database).record(minimal)
    row = rows(database)[0]
    for name in ("payload_json", "parent_span_id", "latency_ms", "prompt_tokens", "error_json", "payload_hash"):
        assert row[name] is None


def test_duplicate_and_conflicts(database: SQLiteDatabase, event: TrajectoryEvent) -> None:
    sink = SQLiteTrajectorySink(database)
    sink.record(event)
    sink.record(
        event.model_copy(update={"timestamp": event.timestamp.astimezone(UTC), "tool_args": {"a": "é", "z": 1}})
    )
    before = rows(database)
    with pytest.raises(ValueError, match="Conflicting"):
        sink.record(event.model_copy(update={"payload_hash": "different"}))
    with pytest.raises(IntegrityError):
        sink.record(event.model_copy(update={"event_id": uuid4()}))
    assert rows(database) == before
    sink.record(event.model_copy(update={"event_id": uuid4(), "sequence": 2}))
    assert len(rows(database)) == 2


def test_concurrent_duplicate_is_idempotent(database: SQLiteDatabase, event: TrajectoryEvent) -> None:
    sinks = [SQLiteTrajectorySink(database) for _ in range(4)]
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(sink.record, event) for sink in sinks]
        for future in futures:
            future.result()
    assert len(rows(database)) == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("timestamp", datetime(2026, 9, 5)),
        ("latency_ms", float("inf")),
        ("payload", {"nested": [float("nan")]}),
        ("tool_args", {"x": float("-inf")}),
        ("tool_result_summary", object()),
        ("error", {1: "non-string key"}),
        ("payload", (1, 2)),
    ],
)
def test_invalid_values_leave_no_rows(
    database: SQLiteDatabase, event: TrajectoryEvent, field: str, value: object
) -> None:
    with pytest.raises((ValueError, TypeError)):
        SQLiteTrajectorySink(database).record(event.model_copy(update={field: value}))
    assert rows(database) == []


def test_close_and_database_ownership(database: SQLiteDatabase, event: TrajectoryEvent) -> None:
    sink = SQLiteTrajectorySink(database)
    sink.flush()
    sink.close()
    sink.close()
    sink.flush()
    with pytest.raises(RuntimeError, match="closed"):
        sink.record(event)
    SQLiteTrajectorySink(database).record(event)
    assert len(rows(database)) == 1


def test_missing_schema_is_explicit_and_recorder_fails_open(tmp_path: Path, event: TrajectoryEvent) -> None:
    path = tmp_path / "unmigrated.sqlite3"
    database = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{path.as_posix()}"))
    sink = SQLiteTrajectorySink(database)
    assert not path.exists()
    try:
        with pytest.raises(OperationalError):
            sink.record(event)
        recorder = TrajectoryRecorder(RunContext.new(), sink)
        assert recorder.record(TrajectoryRecord(TrajectoryEventType.RUN_START, "test")) is not None
        recorder.flush()
        recorder.close()
    finally:
        database.close()


def test_recorder_sanitized_payload_is_preserved(database: SQLiteDatabase) -> None:
    recorder = TrajectoryRecorder(RunContext.new(), SQLiteTrajectorySink(database))
    event = recorder.record(
        TrajectoryRecord(
            TrajectoryEventType.PROMPT_SENT, "test", payload={"api_key": "synthetic-secret", "message": "hello"}
        )
    )
    assert event is not None
    stored = rows(database)[0]
    assert "synthetic-secret" not in str(stored)
    assert json.loads(str(stored["payload_json"])) == event.payload
    assert stored["payload_hash"] == event.payload_hash
    recorder.close()


@pytest.mark.parametrize("mode", list(TelemetryMode))
def test_jsonl_sqlite_equivalence(
    database: SQLiteDatabase, event: TrajectoryEvent, tmp_path: Path, mode: TelemetryMode
) -> None:
    jsonl = JSONLTrajectorySink(tmp_path / "jsonl")
    sqlite = SQLiteTrajectorySink(database)
    events = [
        event.model_copy(update={"event_id": uuid4(), "sequence": index * 2, "event_type": kind, "mode": mode})
        for index, kind in enumerate(TrajectoryEventType, start=1)
    ]
    for item in events:
        jsonl.record(item)
    # Arrival order is not used to reconstruct the trajectory.
    for item in reversed(events):
        sqlite.record(item)
    sqlite.record(event.model_copy(update={"run_id": uuid4(), "session_id": event.session_id}))
    jsonl.close()
    sqlite.close()
    assert jsonl.path is not None
    expected = [
        TrajectoryEvent.model_validate_json(line) for line in jsonl.path.read_text(encoding="utf-8").splitlines()
    ]
    assert read_trajectory(database, event.run_id) == expected == events
    assert read_trajectory(database, uuid4()) == []


def test_readback_preserves_missing_fields(database: SQLiteDatabase, event: TrajectoryEvent) -> None:
    minimal = TrajectoryEvent(
        **{name: getattr(event, name) for name, field in TrajectoryEvent.model_fields.items() if field.is_required()}
    )
    SQLiteTrajectorySink(database).record(minimal)
    assert read_trajectory(database, minimal.run_id) == [minimal]


@pytest.mark.parametrize("version", [None, 2])
def test_readback_rejects_missing_or_unknown_encoding(database: SQLiteDatabase, version: int | None) -> None:
    with database.transaction() as connection:
        if version is None:
            connection.execute(delete(schema_metadata))
        else:
            connection.execute(update(schema_metadata).values(metadata_value=version))
    with pytest.raises(ValueError, match="encoding version"):
        read_trajectory(database, uuid4())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("payload_json", "{"),
        ("payload_json", "NaN"),
        ("payload_json", "1e999"),
        ("tool_args_json", "[]"),
        ("event_id", "not-a-uuid"),
        ("payload_json", '{"duplicate":1,"duplicate":2}'),
    ],
)
def test_readback_rejects_corrupt_rows(
    database: SQLiteDatabase, event: TrajectoryEvent, field: str, value: str
) -> None:
    SQLiteTrajectorySink(database).record(event)
    with database.transaction() as connection:
        connection.execute(update(trajectory_events).values(**{field: value}))
    with pytest.raises(ValueError, match="Expecting|finite|validation error|Malformed"):
        read_trajectory(database, event.run_id)


def test_settings_default_selects_jsonl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    selected = ProjectSettings(telemetry_log_dir=tmp_path / "logs", telemetry_level="INFO")
    assert selected.telemetry_sink == "jsonl"
    monkeypatch.setattr(recorder_module, "settings", selected)
    recorder = TrajectoryRecorder.from_settings(RunContext.new())
    assert isinstance(recorder.sink, JSONLTrajectorySink)
    event = recorder.record(TrajectoryRecord(TrajectoryEventType.RUN_START, "test"))
    recorder.close()
    assert recorder.sink.path is not None
    assert TrajectoryEvent.model_validate_json(recorder.sink.path.read_text(encoding="utf-8")) == event


def test_settings_sqlite_selection_and_disposal(database: SQLiteDatabase, monkeypatch: pytest.MonkeyPatch) -> None:
    selected = ProjectSettings(telemetry_sink="sqlite", telemetry_level="INFO")
    monkeypatch.setattr(recorder_module, "settings", selected)

    def create_database(config: ProjectSettings) -> SQLiteDatabase:
        assert config is selected
        return database

    monkeypatch.setattr(recorder_module, "SQLiteDatabase", create_database)
    recorder = TrajectoryRecorder.from_settings(RunContext.new(), mode=TelemetryMode.FULL, model_tag="test-model")
    assert isinstance(recorder.sink, SQLiteTrajectorySink)
    event = recorder.record(TrajectoryRecord(TrajectoryEventType.RUN_START, "test"))
    assert event is not None
    assert event.mode == TelemetryMode.FULL
    assert event.model_tag == "test-model"
    assert read_trajectory(database, recorder.run_id) == [event]
    recorder.close()
    recorder.close()
    with pytest.raises(RuntimeError, match="closed"), database.read():
        pytest.fail("The runtime-owned database was not disposed.")


@pytest.mark.parametrize("level", ["INFO", "OFF"])
def test_sqlite_settings_are_lazy_and_do_not_migrate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, level: Literal["INFO", "OFF"]
) -> None:
    path = tmp_path / "not-migrated.sqlite3"
    selected = ProjectSettings(
        database_url=f"sqlite:///{path.as_posix()}", telemetry_sink="sqlite", telemetry_level=level
    )
    monkeypatch.setattr(recorder_module, "settings", selected)
    recorder = TrajectoryRecorder.from_settings(RunContext.new())
    assert not path.exists()
    result = recorder.record(TrajectoryRecord(TrajectoryEventType.RUN_START, "test"))
    recorder.close()
    if level == "OFF":
        assert result is None
        assert not path.exists()
    else:
        assert result is not None
        database = SQLiteDatabase(selected)
        try:
            with database.read() as connection:
                assert connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type = 'table'").all() == []
        finally:
            database.close()


def test_locked_database_failure_is_fail_open_and_recovers(
    database: SQLiteDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    selected = ProjectSettings(
        database_url=f"sqlite:///{(tmp_path / 'telemetry.sqlite3').as_posix()}",
        database_busy_timeout_ms=10,
        telemetry_sink="sqlite",
        telemetry_level="INFO",
    )
    monkeypatch.setattr(recorder_module, "settings", selected)
    recorder = TrajectoryRecorder.from_settings(RunContext.new())
    try:
        with database.transaction() as connection:
            connection.execute(update(schema_metadata).values(metadata_value=1))
            failed = recorder.record(TrajectoryRecord(TrajectoryEventType.RUN_START, "test"))
            assert failed is not None
            assert "continuing without affecting agent execution" in caplog.text
        assert read_trajectory(database, recorder.run_id) == []
        recovered = recorder.record(TrajectoryRecord(TrajectoryEventType.RUN_END, "test"))
        assert recovered is not None
        assert recovered.sequence == 2
        assert read_trajectory(database, recorder.run_id) == [recovered]
    finally:
        recorder.close()
