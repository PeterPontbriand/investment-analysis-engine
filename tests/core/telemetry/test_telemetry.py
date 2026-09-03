"""Unit tests for Step 2.1 telemetry primitives."""

from __future__ import annotations

from pathlib import Path

from src.core.telemetry import (
    RunContext,
    TelemetryMode,
    TrajectoryEventType,
    TrajectoryRecord,
    TrajectoryRecorder,
    TrajectoryRecorderConfig,
)
from src.core.telemetry.models import TrajectoryEvent
from src.core.telemetry.redaction import redact_value, sanitize_exception_message
from src.core.telemetry.sinks import JSONLTrajectorySink
from src.core.telemetry.sinks.base import TrajectorySink


class RecordingSink:
    """Small sink double used to verify recorder behavior."""

    def __init__(self) -> None:
        """Initialise with empty event list and flags."""
        self.events: list[TrajectoryEvent] = []
        self.flushed = False
        self.closed = False

    def record(self, event: TrajectoryEvent) -> None:
        self.events.append(event)

    def flush(self) -> None:
        self.flushed = True

    def close(self) -> None:
        self.closed = True


def test_recorder_assigns_monotonic_sequence_and_single_run_id() -> None:
    """Recorder sequence numbers are assigned centrally and increase by one."""
    sink = RecordingSink()
    recorder = TrajectoryRecorder(RunContext.new(), sink, TrajectoryRecorderConfig(mode=TelemetryMode.LIGHT))

    first = recorder.record(TrajectoryRecord(event_type=TrajectoryEventType.RUN_START, component="test"))
    second = recorder.record(
        TrajectoryRecord(
            event_type=TrajectoryEventType.PROMPT_SENT,
            component="llm",
            payload={"prompt": "hello"},
        )
    )
    third = recorder.record(TrajectoryRecord(event_type=TrajectoryEventType.RUN_END, component="test"))

    assert [event.sequence for event in (first, second, third) if event is not None] == [1, 2, 3]
    assert len({event.run_id for event in sink.events}) == 1
    assert len({event.session_id for event in sink.events}) == 1
    assert len({event.span_id for event in sink.events}) == 3
    assert sink.events[0].event_id != sink.events[1].event_id


def test_recorder_retains_only_bounded_sanitized_event_summaries() -> None:
    """Terminal diagnostics expose metadata without retained event payloads."""
    sink = RecordingSink()
    recorder = TrajectoryRecorder(
        RunContext.new(),
        sink,
        TrajectoryRecorderConfig(recent_event_limit=2),
    )
    recorder.record(TrajectoryRecord(event_type=TrajectoryEventType.RUN_START, component="run"))
    recorder.record(
        TrajectoryRecord(
            event_type=TrajectoryEventType.PROMPT_SENT,
            component="llm",
            payload={"api_key": "must-not-appear"},
        )
    )
    recorder.record(TrajectoryRecord(event_type=TrajectoryEventType.LLM_RESPONSE, component="llm"))

    recent = recorder.recent_events()

    assert [event.sequence for event in recent] == [2, 3]
    assert [event.event_type for event in recent] == ["prompt_sent", "llm_response"]
    assert all(not hasattr(event, "payload") for event in recent)


def test_jsonl_sink_round_trips_events(tmp_path: Path) -> None:
    """JSONL persistence writes one valid JSON object per event."""
    sink = JSONLTrajectorySink(tmp_path)
    recorder = TrajectoryRecorder(RunContext.new(), sink)
    recorder.record(
        TrajectoryRecord(
            event_type=TrajectoryEventType.RUN_START,
            component="test",
            payload={"task": "demo"},
        )
    )
    recorder.record(
        TrajectoryRecord(
            event_type=TrajectoryEventType.RUN_END,
            component="test",
            payload={"status": "completed"},
        )
    )
    recorder.close()

    path = tmp_path / "trajectories" / f"{recorder.run_id}.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    events = [TrajectoryEvent.model_validate_json(line) for line in lines]

    assert len(lines) == 2
    assert [event.sequence for event in events] == [1, 2]
    assert all(event.run_id == recorder.run_id for event in events)


def test_redaction_removes_secret_fields_and_common_tokens() -> None:
    """Telemetry redaction removes common credential-bearing values."""
    value = {
        "api_key": "secret-value",
        "nested": {"password": "also-secret"},
        "message": "Authorization: Bearer super-secret-token",
        "safe": "ordinary text",
    }

    redacted = redact_value(value)

    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"]["password"] == "[REDACTED]"
    assert "super-secret-token" not in redacted["message"]
    assert redacted["safe"] == "ordinary text"
    assert "secret-value" not in sanitize_exception_message(str(value))


def test_recorder_swallow_sink_failures() -> None:
    """A sink failure is observational and does not escape recorder.record()."""

    class FailingSink:
        def record(self, _event: TrajectoryEvent) -> None:
            raise OSError("cannot write")

        def flush(self) -> None:
            raise OSError("cannot flush")

        def close(self) -> None:
            raise OSError("cannot close")

    sink: TrajectorySink = FailingSink()
    recorder = TrajectoryRecorder(RunContext.new(), sink)

    event = recorder.record(TrajectoryRecord(event_type=TrajectoryEventType.RUN_START, component="test"))
    recorder.flush()
    recorder.close()

    assert len(recorder.recent_events()) == 1

    assert event is not None
    assert event.sequence == 1


def test_explicit_run_context_is_preserved() -> None:
    """All events inherit the CLI-created run and session identity."""
    context = RunContext.new()
    sink = RecordingSink()
    recorder = TrajectoryRecorder(context, sink)

    event = recorder.record(TrajectoryRecord(event_type=TrajectoryEventType.RUN_START, component="test"))

    assert event is not None
    assert event.run_id == context.run_id
    assert event.session_id == context.session_id


def test_span_parent_relationship_is_explicit_without_stack_semantics() -> None:
    """Each span retains its own explicit parent independently of creation order."""
    sink = RecordingSink()
    recorder = TrajectoryRecorder(RunContext.new(), sink)
    parent = recorder.start_span()
    first_child = recorder.start_span(parent_span_id=parent)
    second_child = recorder.start_span(parent_span_id=parent)

    assert recorder.get_span_parent(first_child) == parent
    assert recorder.get_span_parent(second_child) == parent

    recorder.end_span(first_child)
    assert recorder.get_span_parent(first_child) is None
    assert recorder.get_span_parent(second_child) == parent

    event = recorder.record(
        TrajectoryRecord(
            event_type=TrajectoryEventType.PROMPT_SENT,
            component="llm",
            span_id=second_child,
            parent_span_id=recorder.get_span_parent(second_child),
        )
    )

    assert event is not None
    assert event.span_id == second_child
    assert event.parent_span_id == parent


def test_jsonl_retention_limits_file_count(tmp_path: Path) -> None:
    """Oldest completed run files are removed when max_log_files is exceeded."""
    for _ in range(3):
        sink = JSONLTrajectorySink(tmp_path, max_log_files=2, max_total_size=10_000)
        recorder = TrajectoryRecorder(RunContext.new(), sink)
        recorder.record(TrajectoryRecord(event_type=TrajectoryEventType.RUN_START, component="test"))
        recorder.close()

    files = list((tmp_path / "trajectories").glob("*.jsonl"))
    assert len(files) == 2
