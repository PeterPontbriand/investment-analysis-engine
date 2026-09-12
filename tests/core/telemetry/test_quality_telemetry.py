"""Quality failure causality, sanitization, persistence and fail-open behavior."""

import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config

from alembic import command
from src.config import ProjectSettings
from src.core.telemetry import RunContext, TrajectoryRecorder
from src.core.telemetry.models import TrajectoryEvent
from src.core.telemetry.quality import record_cli_quality, record_quality
from src.core.telemetry.sinks.sqlite import SQLiteTrajectorySink, read_trajectory
from src.data.quality import QualityContext, QualityDecision, QualityOutcome
from src.data.quality_reporting import publish_quality, quality_observer
from src.data.repositories import SQLiteDatabase


def decision() -> QualityDecision:
    return QualityDecision(
        "historical.currency",
        QualityOutcome.FAIL,
        "Currency conflicts.",
        QualityContext("ABC:api_key=secret-value", datetime(2026, 9, 8, tzinfo=UTC)),
    )


def test_candidate_rejection_is_diagnostic_without_console_warning(caplog: pytest.LogCaptureFixture) -> None:
    """Rejected candidates can recover; observers retain evidence without alarming users."""
    item = decision()
    observed: list[QualityDecision] = []
    with caplog.at_level(logging.DEBUG, logger="src.data.quality_reporting"), quality_observer(observed.append):
        publish_quality((item,))
    assert observed == [item]
    records = [record for record in caplog.records if record.name == "src.data.quality_reporting"]
    assert records
    assert all(record.levelno == logging.DEBUG for record in records)
    assert "historical.currency" in records[0].getMessage()
    assert "secret-value" not in records[0].getMessage()


def test_quality_failure_roundtrip_keeps_run_and_span_and_redacts(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'quality.sqlite3').as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    context = RunContext.new()
    span, parent = uuid4(), uuid4()
    database = SQLiteDatabase(ProjectSettings(database_url=url))
    recorder = TrajectoryRecorder(context, SQLiteTrajectorySink(database))
    with record_quality(recorder, span_id=span, parent_span_id=parent):
        publish_quality((decision(),))
    recorder.close()
    database.close()
    reopened = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        events = read_trajectory(reopened, context.run_id)
        assert len(events) == 1
        event = events[0]
        assert event.component == "data_quality"
        assert event.span_id == span
        assert event.parent_span_id == parent
        assert event.run_id == context.run_id
        assert "secret-value" not in event.to_json_line()
        assert "historical.currency" in event.to_json_line()
    finally:
        reopened.close()


def test_nested_observers_restore_after_exception_and_ignore_nonfailures() -> None:
    outer: list[QualityDecision] = []
    inner: list[QualityDecision] = []
    item = decision()
    with quality_observer(outer.append):
        with pytest.raises(RuntimeError, match="stop"), quality_observer(inner.append):  # noqa: PT012
            publish_quality((item,))
            raise RuntimeError("stop")
        publish_quality((item, QualityDecision("rule", QualityOutcome.PASS, "Valid.", item.context)))
    publish_quality((item,))
    assert outer == [item]
    assert inner == [item]


def test_broken_recorder_cannot_change_quality_outcome(monkeypatch: pytest.MonkeyPatch) -> None:
    class UnusedSink:
        def record(self, event: object) -> None:  # noqa: ARG002
            raise AssertionError("unreachable")

        def flush(self) -> None:
            pass

        def close(self) -> None:
            pass

    recorder = TrajectoryRecorder(RunContext.new(), UnusedSink())

    def broken(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("recorder unavailable")

    monkeypatch.setattr(recorder, "record", broken)
    item = decision()
    with record_quality(recorder, span_id=uuid4()):
        publish_quality((item,))
    assert item.outcome is QualityOutcome.FAIL


@pytest.mark.parametrize("close_fails", [False, True])
def test_cli_quality_uses_existing_run_and_closes_lazily(monkeypatch: pytest.MonkeyPatch, close_fails: bool) -> None:
    events: list[TrajectoryEvent] = []

    class Sink:
        def record(self, event: TrajectoryEvent) -> None:
            events.append(event)

        def flush(self) -> None:
            pass

        def close(self) -> None:
            pass

    context = RunContext.new()
    recorder = TrajectoryRecorder(context, Sink())
    created: list[RunContext] = []
    closed: list[bool] = []

    def factory(run_context: RunContext) -> TrajectoryRecorder:
        created.append(run_context)
        return recorder

    def close() -> None:
        closed.append(True)
        if close_fails:
            raise RuntimeError("close unavailable")

    monkeypatch.setattr("src.core.telemetry.quality.get_current_run_context", lambda: context)
    monkeypatch.setattr(TrajectoryRecorder, "from_settings", factory)
    monkeypatch.setattr(recorder, "close", close)
    with record_cli_quality():
        assert not created
        publish_quality((decision(), decision()))
    assert created == [context]
    assert closed == [True]
    assert len(events) == 2
    assert all(event.run_id == context.run_id for event in events)
    assert events[0].span_id == events[1].span_id


def test_cli_without_run_context_does_not_invent_a_trajectory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.core.telemetry.quality.get_current_run_context", lambda: None)
    with record_cli_quality():
        publish_quality((decision(),))
