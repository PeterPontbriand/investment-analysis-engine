"""Integration coverage for Step 2.1 orchestration instrumentation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.core.telemetry import RunContext, TrajectoryRecorder
from src.core.telemetry.models import TrajectoryEvent
from src.core.telemetry.sinks import JSONLTrajectorySink
from src.llm.client import LLMGenerateResult
from src.orchestrator.context import MessageContext
from src.orchestrator.dispatcher import AsyncToolDispatcher
from src.orchestrator.loop import AgentOrchestrator, OrchestratorConfig, OrchestratorOptions
from src.tools.parser import ParsedToolCall


class FakeLLMClient:
    """Deterministic LLM double that emits one tool call and then a final answer."""

    def __init__(self) -> None:
        """Initialize the fake client with a call counter."""
        self.calls = 0

    async def generate(
        self,
        prompt: list[dict[str, Any]] | str,  # noqa: ARG002
        model: str | None = None,  # noqa: ARG002
        temperature: float | None = None,  # noqa: ARG002
        response_model: type[Any] | None = None,  # noqa: ARG002
    ) -> LLMGenerateResult:
        self.calls += 1
        if self.calls == 1:
            return LLMGenerateResult(
                text='{"name":"echo","arguments":{"value":"hello"}}',
                prompt_tokens=12,
                completion_tokens=8,
            )
        return LLMGenerateResult(text="done", prompt_tokens=4, completion_tokens=1)


class FakeParser:
    """Deterministic parser double matching the orchestrator's parser boundary."""

    def __init__(self) -> None:
        """Initialize the fake parser with a call counter."""
        self.calls = 0

    def parse(self, raw_output: str) -> ParsedToolCall:  # noqa: ARG002 (unused)
        self.calls += 1
        if self.calls == 1:
            return ParsedToolCall(tool_name="echo", arguments={"value": "hello"})
        raise ValueError("plain response")


@pytest.mark.asyncio
async def test_complete_run_writes_reconstructable_jsonl(tmp_path: Path) -> None:
    """A complete synthetic trajectory contains ordered run, LLM, and tool events."""
    dispatcher = AsyncToolDispatcher()
    dispatcher.register_tool("echo", lambda value: value)
    recorder = TrajectoryRecorder(RunContext.new(), JSONLTrajectorySink(tmp_path))
    options = OrchestratorOptions(
        config=OrchestratorConfig(model_selection="test-model"),
        recorder=recorder,
    )
    orchestrator = AgentOrchestrator(
        llm_client=FakeLLMClient(),
        dispatcher=dispatcher,
        parser=FakeParser(),
        options=options,
    )

    assert orchestrator.run_context == recorder.run_context

    results = [result async for result in orchestrator.run_stream("say hello", MessageContext())]

    path = tmp_path / "trajectories" / f"{recorder.run_id}.jsonl"
    events = [TrajectoryEvent.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines()]

    assert results[-1].is_terminal is True
    assert [event.sequence for event in events] == list(range(1, len(events) + 1))
    assert [event.event_type.value for event in events] == [
        "run_start",
        "step_start",
        "prompt_sent",
        "llm_response",
        "tool_call",
        "tool_result",
        "step_end",
        "step_start",
        "prompt_sent",
        "llm_response",
        "error",
        "step_end",
        "run_end",
    ]
    assert events[-1].payload == {"status": "completed", "final_step": 2}
    assert all(event.run_id == recorder.run_id for event in events)
    assert all(event.session_id == recorder.session_id for event in events)
    step_events = [event for event in events if event.event_type.value == "step_start"]
    assert all(event.parent_span_id == events[0].span_id for event in step_events)
    llm_events = [e for e in events if e.event_type.value == "llm_response"]
    assert llm_events[0].prompt_tokens == 12
    assert llm_events[0].completion_tokens == 8
    assert llm_events[1].prompt_tokens == 4
    assert llm_events[1].completion_tokens == 1
