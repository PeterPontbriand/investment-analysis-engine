"""Deterministic integration tests for Step 2.6 Slice B enforcement."""

from __future__ import annotations

import asyncio
from pathlib import Path
from threading import Event
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.core.telemetry import RunContext, TelemetryMode, TrajectoryEventType, TrajectoryRecorder
from src.core.telemetry.models import TrajectoryEvent
from src.core.telemetry.recorder import TrajectoryRecorderConfig
from src.core.telemetry.sinks import JSONLTrajectorySink
from src.llm.client import LLMClient, LLMGenerateResult
from src.orchestrator.context import MessageContext
from src.orchestrator.dispatcher import AsyncToolDispatcher
from src.orchestrator.loop import AgentOrchestrator, OrchestratorConfig, OrchestratorOptions
from src.orchestrator.reliability import ReliabilityLimits, ReliabilityTripReason
from src.orchestrator.types import AgentStepResult, ToolCallResult
from src.schema.config import SchemaConfig
from src.tools.parser import ParsedToolCall, ToolParser, ToolParsingError


class RecordingSink:
    """In-memory trajectory sink for retry evidence."""

    def __init__(self) -> None:
        """Initialize an empty event collection."""
        self.events: list[TrajectoryEvent] = []

    def record(self, event: TrajectoryEvent) -> None:
        self.events.append(event)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass


def _config(**limit_overrides: Any) -> OrchestratorConfig:
    limits = ReliabilityLimits.model_validate(limit_overrides)
    return OrchestratorConfig(
        reliability_limits=limits,
        schema_config=SchemaConfig(use_native_constraint=False),
    )


async def _collect(orchestrator: AgentOrchestrator) -> list[AgentStepResult]:
    context = MessageContext()
    return [step async for step in orchestrator.run_stream("test", context)]


def _assert_recovery_order(events: list[TrajectoryEvent], category: str, maximum: int) -> None:
    """Verify causal linkage from each failed attempt through its next request."""
    assert [event.sequence for event in events] == list(range(1, len(events) + 1))
    recoveries = [event for event in events if event.event_type is TrajectoryEventType.RECOVERY_ATTEMPTED]
    assert recoveries
    for retry_number, recovery in enumerate(recoveries, start=1):
        index = events.index(recovery)
        failed, error, _, request = events[index - 2 : index + 2]
        assert failed.event_type is (
            TrajectoryEventType.PROMPT_SENT if category == "llm_transport" else TrajectoryEventType.LLM_RESPONSE
        )
        assert error.event_type is TrajectoryEventType.ERROR
        assert error.component == ("llm" if category == "llm_transport" else "schema_validator")
        assert error.error is not None
        assert error.error["type"]
        assert error.error["message"]
        assert request.event_type is TrajectoryEventType.PROMPT_SENT
        assert recovery.component == "orchestrator"
        assert recovery.step_index == 1
        assert recovery.parent_span_id is not None
        assert recovery.payload == {
            "failure_category": category,
            "retry_number": retry_number,
            "maximum_retries": maximum,
        }
        for related in (failed, error, request):
            assert related.run_id == recovery.run_id
            assert related.session_id == recovery.session_id
            assert related.step_index == recovery.step_index
            assert related.span_id == recovery.span_id
            assert related.parent_span_id == recovery.parent_span_id
        parent = next(event for event in events if event.event_type is TrajectoryEventType.STEP_START)
        assert recovery.parent_span_id == parent.span_id


@pytest.mark.asyncio
async def test_llm_timeout_cancels_async_request_and_returns_trip() -> None:
    """An LLM deadline breach cancels the await and becomes a terminal outcome."""
    cancelled = asyncio.Event()

    async def wait_forever(**_kwargs: Any) -> LLMGenerateResult:
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
        raise AssertionError("unreachable")

    llm = MagicMock(spec=LLMClient)
    llm.generate = AsyncMock(side_effect=wait_forever)
    orchestrator = AgentOrchestrator(
        llm,
        MagicMock(spec=AsyncToolDispatcher),
        MagicMock(spec=ToolParser),
        OrchestratorOptions(config=_config(llm_call_timeout_seconds=0.01)),
    )

    steps = await _collect(orchestrator)

    assert cancelled.is_set()
    assert orchestrator.last_reliability_failure is not None
    assert orchestrator.last_reliability_failure.reason is ReliabilityTripReason.LLM_TIMEOUT
    assert orchestrator.last_reliability_failure.cancellation_confirmed is True
    assert steps[-1].failure == orchestrator.last_reliability_failure
    assert steps[-1].failure is not None
    assert steps[-1].failure.run_id == orchestrator.recorder.run_id
    assert "llm_timeout" in steps[-1].failure.message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("overrides", "expected_reason"),
    [
        (
            {
                "overall_timeout_seconds": 0.01,
                "step_timeout_seconds": 1,
                "llm_call_timeout_seconds": 1,
            },
            ReliabilityTripReason.OVERALL_TIMEOUT,
        ),
        (
            {
                "overall_timeout_seconds": 1,
                "step_timeout_seconds": 0.01,
                "llm_call_timeout_seconds": 1,
            },
            ReliabilityTripReason.STEP_TIMEOUT,
        ),
    ],
)
async def test_earliest_run_or_step_deadline_controls_llm(
    overrides: dict[str, float],
    expected_reason: ReliabilityTripReason,
) -> None:
    """The earliest enclosing deadline determines the terminal reason."""

    async def wait_forever(**_kwargs: Any) -> LLMGenerateResult:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    llm = MagicMock(spec=LLMClient)
    llm.generate = AsyncMock(side_effect=wait_forever)
    orchestrator = AgentOrchestrator(
        llm,
        MagicMock(spec=AsyncToolDispatcher),
        MagicMock(spec=ToolParser),
        OrchestratorOptions(config=_config(**overrides)),
    )

    steps = await _collect(orchestrator)

    assert orchestrator.last_reliability_failure is not None
    assert orchestrator.last_reliability_failure.reason is expected_reason
    assert steps[-1].failure is not None
    assert steps[-1].failure.reason is expected_reason
    assert str(steps[-1].failure.run_id) in steps[-1].failure.message


@pytest.mark.asyncio
async def test_async_tool_timeout_cancels_handler_and_stops_run() -> None:
    """An asynchronous tool is cooperatively cancelled at its deadline."""
    cancelled = asyncio.Event()

    async def wait_forever() -> str:
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
        raise AssertionError("unreachable")

    llm = MagicMock(spec=LLMClient)
    llm.generate = AsyncMock(return_value=LLMGenerateResult(text='{"name":"slow"}'))
    parser = MagicMock(spec=ToolParser)
    parser.parse.return_value = ParsedToolCall(tool_name="slow", arguments={})
    dispatcher = AsyncToolDispatcher()
    dispatcher.register_tool("slow", wait_forever)
    orchestrator = AgentOrchestrator(
        llm,
        dispatcher,
        parser,
        OrchestratorOptions(config=_config(tool_call_timeout_seconds=0.01)),
    )

    steps = await _collect(orchestrator)

    assert cancelled.is_set()
    assert orchestrator.last_reliability_failure is not None
    assert orchestrator.last_reliability_failure.reason is ReliabilityTripReason.TOOL_TIMEOUT
    assert orchestrator.last_reliability_failure.cancellation_confirmed is True
    assert steps[-1].failure == orchestrator.last_reliability_failure


@pytest.mark.asyncio
async def test_sync_tool_timeout_reports_unconfirmed_cancellation() -> None:
    """A timed-out thread-backed synchronous handler is not claimed cancelled."""
    release = Event()

    def blocking_tool() -> str:
        release.wait(timeout=0.2)
        return "late"

    llm = MagicMock(spec=LLMClient)
    llm.generate = AsyncMock(return_value=LLMGenerateResult(text='{"name":"blocking"}'))
    parser = MagicMock(spec=ToolParser)
    parser.parse.return_value = ParsedToolCall(tool_name="blocking", arguments={})
    dispatcher = AsyncToolDispatcher()
    dispatcher.register_tool("blocking", blocking_tool)
    orchestrator = AgentOrchestrator(
        llm,
        dispatcher,
        parser,
        OrchestratorOptions(config=_config(tool_call_timeout_seconds=0.01)),
    )

    try:
        steps = await _collect(orchestrator)
    finally:
        release.set()

    assert orchestrator.last_reliability_failure is not None
    assert orchestrator.last_reliability_failure.reason is ReliabilityTripReason.TOOL_TIMEOUT
    assert orchestrator.last_reliability_failure.cancellation_confirmed is False
    assert steps[-1].failure == orchestrator.last_reliability_failure


@pytest.mark.asyncio
async def test_transient_llm_failures_retry_with_recovery_telemetry(tmp_path: Path) -> None:
    """Eligible transport failures retry within budget and emit one event each."""
    request = httpx.Request("POST", "http://ollama.invalid/generate")
    unavailable = httpx.Response(503, request=request)
    error = httpx.HTTPStatusError(
        "unavailable Bearer synthetic-transport-secret", request=request, response=unavailable
    )
    llm = MagicMock(spec=LLMClient)
    llm.generate = AsyncMock(side_effect=[error, error, LLMGenerateResult(text="completed")])
    parser = MagicMock(spec=ToolParser)
    parser.parse.side_effect = ToolParsingError("terminal text")
    sink = JSONLTrajectorySink(tmp_path)
    recorder = TrajectoryRecorder(
        RunContext.new(),
        sink,
        TrajectoryRecorderConfig(mode=TelemetryMode.LIGHT),
    )
    orchestrator = AgentOrchestrator(
        llm,
        MagicMock(spec=AsyncToolDispatcher),
        parser,
        OrchestratorOptions(config=_config(), recorder=recorder),
    )

    steps = await _collect(orchestrator)

    text = (tmp_path / "trajectories" / f"{recorder.run_id}.jsonl").read_text(encoding="utf-8")
    events = [TrajectoryEvent.model_validate_json(line) for line in text.splitlines()]
    recoveries = [event for event in events if event.event_type is TrajectoryEventType.RECOVERY_ATTEMPTED]
    _assert_recovery_order(events, "llm_transport", 3)
    assert "synthetic-transport-secret" not in text
    errors = [event for event in events if event.component == "llm" and event.error is not None]
    assert len(errors) == 2
    assert all(event.error == {"type": "HTTPStatusError", "message": "unavailable [REDACTED]"} for event in errors)
    assert llm.generate.await_count == 3
    assert [event.payload["retry_number"] for event in recoveries if event.payload] == [1, 2]
    assert orchestrator.last_reliability_failure is None
    assert steps[-1].failure is None


@pytest.mark.asyncio
async def test_transient_llm_retry_exhaustion_trips_after_exact_budget() -> None:
    """No fourth retry starts after three configured corrective attempts."""
    request = httpx.Request("POST", "http://ollama.invalid/generate")
    unavailable = httpx.Response(503, request=request)
    error = httpx.HTTPStatusError("unavailable", request=request, response=unavailable)
    llm = MagicMock(spec=LLMClient)
    llm.generate = AsyncMock(side_effect=error)
    sink = RecordingSink()
    recorder = TrajectoryRecorder(
        RunContext.new(),
        sink,
        TrajectoryRecorderConfig(mode=TelemetryMode.LIGHT),
    )
    orchestrator = AgentOrchestrator(
        llm,
        MagicMock(spec=AsyncToolDispatcher),
        MagicMock(spec=ToolParser),
        OrchestratorOptions(config=_config(), recorder=recorder),
    )

    await _collect(orchestrator)

    recoveries = [event for event in sink.events if event.event_type is TrajectoryEventType.RECOVERY_ATTEMPTED]
    assert llm.generate.await_count == 4
    assert len(recoveries) == 3
    _assert_recovery_order(sink.events, "llm_transport", 3)
    assert orchestrator.last_reliability_failure is not None
    assert orchestrator.last_reliability_failure.reason is ReliabilityTripReason.TRANSIENT_RETRY_LIMIT


@pytest.mark.asyncio
@pytest.mark.parametrize("ollama_version", ["0.5.4", "0.1.0"], ids=["native", "prompt"])
async def test_schema_repair_emits_recovery_and_valid_response_resets_counter(
    tmp_path: Path, ollama_version: str
) -> None:
    """A successful corrective schema retry emits evidence and clears violations."""
    llm = MagicMock(spec=LLMClient)
    llm.generate = AsyncMock(
        side_effect=[
            LLMGenerateResult(text='{"tool_name":"quote","Bearer synthetic-schema-secret":1}'),
            LLMGenerateResult(text='{"tool_name":"quote","tool_args":{}}'),
        ]
    )
    dispatcher = MagicMock(spec=AsyncToolDispatcher)
    dispatcher.dispatch = AsyncMock(
        return_value=ToolCallResult(
            call_id="call",
            tool_name="quote",
            success=True,
            result="ok",
            error_message=None,
        )
    )
    sink = JSONLTrajectorySink(tmp_path)
    recorder = TrajectoryRecorder(RunContext.new(), sink)
    limits = ReliabilityLimits(
        max_steps=1,
        max_transient_retries=1,
        max_consecutive_schema_violations=2,
    )
    config = OrchestratorConfig(
        reliability_limits=limits,
        schema_config=SchemaConfig(
            use_native_constraint=True,
            max_validation_retries=1,
            ollama_version=ollama_version,
        ),
    )
    orchestrator = AgentOrchestrator(
        llm,
        dispatcher,
        MagicMock(spec=ToolParser),
        OrchestratorOptions(config=config, recorder=recorder),
    )

    steps = await _collect(orchestrator)

    text = (tmp_path / "trajectories" / f"{recorder.run_id}.jsonl").read_text(encoding="utf-8")
    events = [TrajectoryEvent.model_validate_json(line) for line in text.splitlines()]
    recoveries = [event for event in events if event.event_type is TrajectoryEventType.RECOVERY_ATTEMPTED]
    _assert_recovery_order(events, "schema_validation", 1)
    assert "synthetic-schema-secret" not in text
    error = events[events.index(recoveries[0]) - 1]
    assert error.error is not None
    assert "[REDACTED]" in error.error["message"]
    assert error.error["type"] == "extra_field"
    assert events[events.index(recoveries[0]) + 2].event_type is TrajectoryEventType.LLM_RESPONSE
    assert llm.generate.await_count == 2
    assert all(("format" in call.kwargs) == (ollama_version == "0.5.4") for call in llm.generate.await_args_list)
    assert steps[0].executed_tools[0].result == "ok"
    assert steps[0].executed_tools[0].success is True
    assert len(recoveries) == 1
    assert recoveries[0].payload is not None
    assert recoveries[0].payload["failure_category"] == "schema_validation"
    assert orchestrator.reliability_snapshot is not None
    assert orchestrator.reliability_snapshot.consecutive_schema_violations == 0


@pytest.mark.asyncio
async def test_nonrecoverable_http_error_is_not_retried() -> None:
    """A provider-invalid request preserves the existing non-retry error path."""
    request = httpx.Request("POST", "http://ollama.invalid/generate")
    response = httpx.Response(400, request=request)
    error = httpx.HTTPStatusError("bad request", request=request, response=response)
    llm = MagicMock(spec=LLMClient)
    llm.generate = AsyncMock(side_effect=error)
    sink = RecordingSink()
    orchestrator = AgentOrchestrator(
        llm,
        MagicMock(spec=AsyncToolDispatcher),
        MagicMock(spec=ToolParser),
        OrchestratorOptions(config=_config(), recorder=TrajectoryRecorder(RunContext.new(), sink)),
    )

    with pytest.raises(httpx.HTTPStatusError):
        await _collect(orchestrator)

    assert llm.generate.await_count == 1
    assert all(event.event_type is not TrajectoryEventType.RECOVERY_ATTEMPTED for event in sink.events)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "repair_budget", "enforce_schema", "expected_calls", "expected_recoveries"),
    [
        ('{"tool_name":"quote"}', 1, True, 1, 0),
        ('{"name":"quote"}', 0, False, 1, 0),
        ('{"name":"quote"}', 1, True, 2, 1),
        ('{"name":"quote"}', 0, True, 1, 0),
    ],
    ids=["initial-success", "repair-disabled", "repair-exhausted", "circuit-rejects-repair"],
)
async def test_schema_recovery_events_match_actual_attempts(
    response: str,
    repair_budget: int,
    enforce_schema: bool,
    expected_calls: int,
    expected_recoveries: int,
) -> None:
    """Recovery events count actual repairs, never initial or rejected attempts."""
    sink = RecordingSink()
    llm = MagicMock(spec=LLMClient)
    llm.generate = AsyncMock(return_value=LLMGenerateResult(text=response))
    dispatcher = MagicMock(spec=AsyncToolDispatcher)
    dispatcher.dispatch = AsyncMock(
        return_value=ToolCallResult(call_id="call", tool_name="quote", success=True, result="ok")
    )
    parser = MagicMock(spec=ToolParser)
    parser.parse.side_effect = ToolParsingError("no fallback tool")
    orchestrator = AgentOrchestrator(
        llm,
        dispatcher,
        parser,
        OrchestratorOptions(
            config=OrchestratorConfig(
                reliability_limits=ReliabilityLimits(max_steps=1, max_consecutive_schema_violations=repair_budget + 1),
                schema_config=SchemaConfig(
                    use_native_constraint=enforce_schema,
                    max_validation_retries=repair_budget,
                    ollama_version="0.5.4",
                ),
            ),
            recorder=TrajectoryRecorder(RunContext.new(), sink),
        ),
    )

    await _collect(orchestrator)

    recoveries = [event for event in sink.events if event.event_type is TrajectoryEventType.RECOVERY_ATTEMPTED]
    assert llm.generate.await_count == expected_calls
    assert len(recoveries) == expected_recoveries
    if expected_recoveries:
        _assert_recovery_order(sink.events, "schema_validation", repair_budget)


@pytest.mark.asyncio
@pytest.mark.parametrize("category", ["llm_transport", "schema_native", "schema_prompt"])
async def test_recovery_sink_failure_preserves_execution(category: str) -> None:
    """A failed recovery write preserves attempts, tool output, and terminal outcome."""

    class RecoveryFailingSink(RecordingSink):
        def __init__(self) -> None:
            super().__init__()
            self.failures = 0

        def record(self, event: TrajectoryEvent) -> None:
            if event.event_type is TrajectoryEventType.RECOVERY_ATTEMPTED:
                self.failures += 1
                raise OSError("synthetic recovery write failure")
            super().record(event)

    working_sink = RecordingSink()
    failing_sink = RecoveryFailingSink()
    outcomes: list[tuple[int, int, str, bool, ReliabilityTripReason]] = []
    for sink in (working_sink, failing_sink):
        llm = MagicMock(spec=LLMClient)
        first: Exception | LLMGenerateResult
        if category == "llm_transport":
            first = httpx.ConnectError("synthetic connection failure")
        else:
            first = LLMGenerateResult(text='{"name":"quote"}')
        llm.generate = AsyncMock(side_effect=[first, LLMGenerateResult(text='{"tool_name":"quote"}')])
        dispatcher = MagicMock(spec=AsyncToolDispatcher)
        dispatcher.dispatch = AsyncMock(
            return_value=ToolCallResult(call_id="call", tool_name="quote", success=True, result="ok")
        )
        orchestrator = AgentOrchestrator(
            llm,
            dispatcher,
            MagicMock(spec=ToolParser),
            OrchestratorOptions(
                config=OrchestratorConfig(
                    reliability_limits=ReliabilityLimits(max_steps=1, max_consecutive_schema_violations=2),
                    schema_config=SchemaConfig(
                        max_validation_retries=1,
                        ollama_version="0.1.0" if category == "schema_prompt" else "0.5.4",
                    ),
                ),
                recorder=TrajectoryRecorder(RunContext.new(), sink),
            ),
        )

        steps = await _collect(orchestrator)

        assert steps[0].executed_tools == [ToolCallResult(call_id="call", tool_name="quote", success=True, result="ok")]
        assert steps[-1].failure is not None
        outcomes.append(
            (
                llm.generate.await_count,
                dispatcher.dispatch.await_count,
                steps[0].executed_tools[0].result,
                steps[-1].is_terminal,
                steps[-1].failure.reason,
            )
        )

    assert outcomes == [(2, 1, "ok", True, ReliabilityTripReason.MAX_STEPS_EXCEEDED)] * 2
    assert failing_sink.failures == 1
    assert sum(event.event_type is TrajectoryEventType.RECOVERY_ATTEMPTED for event in working_sink.events) == 1
    assert all(event.event_type is not TrajectoryEventType.RECOVERY_ATTEMPTED for event in failing_sink.events)
