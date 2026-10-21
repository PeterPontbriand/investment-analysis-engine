"""A failed tool call carries its stable failure code, and its provider failure where there is one."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import pytest
from pydantic import BaseModel, ValidationError

from investment_analysis_engine.config.reliability_limits import ReliabilityLimits
from investment_analysis_engine.config.schema_config import SchemaConfig
from investment_analysis_engine.core.failure_codes import FailureReasonCode
from investment_analysis_engine.core.provider_failure_element import ProviderFailure, ProviderFailureInput
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.core.trajectory_events import TelemetryMode, TrajectoryEvent, TrajectoryEventType
from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.data.financial.facts import FinancialProviderError
from investment_analysis_engine.data.market_data import HistoricalMarketData, MarketDataContext
from investment_analysis_engine.data.quality import (
    HistoricalDataQualityError,
    QualityContext,
    evaluate_historical_quality,
)
from investment_analysis_engine.llm.client import LLMClient
from investment_analysis_engine.orchestrator.context import MessageContext
from investment_analysis_engine.orchestrator.dispatcher import AsyncToolDispatcher
from investment_analysis_engine.orchestrator.loop import AgentOrchestrator, OrchestratorConfig, OrchestratorOptions
from investment_analysis_engine.orchestrator.reliability import CircuitBreaker
from investment_analysis_engine.orchestrator.types import ToolCallRequest, ToolCallResult
from investment_analysis_engine.reporting.failure_envelope import failure_envelope
from investment_analysis_engine.telemetry.recorder import TrajectoryRecorder, TrajectoryRecorderConfig
from investment_analysis_engine.telemetry.run_context import RunContext
from investment_analysis_engine.tools.parser import ToolParser


class _Sink:
    """In-memory trajectory sink."""

    def __init__(self) -> None:
        self.events: list[TrajectoryEvent] = []

    def record(self, event: TrajectoryEvent) -> None:
        self.events.append(event)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass


class _Arguments(BaseModel):
    count: int


def _quality_error() -> BaseException:
    frame = pd.DataFrame({"Close": [1.0, float("nan")]}, index=pd.date_range("2026-09-09", periods=2))
    decisions = evaluate_historical_quality(
        HistoricalMarketData(frame, MarketDataContext()),
        context=QualityContext("ACME", datetime(2026, 9, 11, tzinfo=UTC)),
    )
    return HistoricalDataQualityError(decisions, frame)


def _bad_arguments() -> BaseException:
    try:
        _Arguments.model_validate({"count": "many"})
    except ValidationError as exc:
        return exc
    raise AssertionError("the arguments were valid")


def _element(code: FailureReasonCode, kind: ProviderFailureKind) -> ProviderFailure:
    return ProviderFailure(
        reason_code=code, inputs=(ProviderFailureInput(input=None, provider_id="synthetic", kind=kind),)
    )


_UNREACHABLE = _element(FailureReasonCode.PROVIDER_UNREACHABLE, ProviderFailureKind.UNREACHABLE)

# label, exception, expected code, expected provider_failure
_CASES: list[tuple[str, Callable[[], BaseException], FailureReasonCode, ProviderFailure | None]] = [
    ("quality", _quality_error, FailureReasonCode.HISTORICAL_QUALITY, None),
    (
        "provider_with_kind",
        lambda: DataFetchError("down", kind=ProviderFailureKind.UNREACHABLE, provider_id="synthetic"),
        FailureReasonCode.PROVIDER_UNREACHABLE,
        _UNREACHABLE,
    ),
    (
        "financial_provider_with_kind",
        lambda: FinancialProviderError("down", kind=ProviderFailureKind.UNREACHABLE, provider_id="synthetic"),
        FailureReasonCode.PROVIDER_UNREACHABLE,
        _UNREACHABLE,
    ),
    ("provider_without_kind", lambda: DataFetchError("down"), FailureReasonCode.PROVIDER_ERROR, None),
    ("invalid_arguments", _bad_arguments, FailureReasonCode.INVALID_INPUT, None),
    ("unexpected", lambda: RuntimeError("defect"), FailureReasonCode.EXECUTION_ERROR, None),
    ("unregistered", lambda: LookupError("unused"), FailureReasonCode.INVALID_INPUT, None),
]


def _dispatcher_raising(make: Callable[[], BaseException]) -> AsyncToolDispatcher:
    dispatcher = AsyncToolDispatcher()

    def fail() -> None:
        raise make()

    dispatcher.register_tool("tool", fail)
    return dispatcher


def _orchestrator(dispatcher: AsyncToolDispatcher, sink: _Sink) -> AgentOrchestrator:
    limits = ReliabilityLimits()
    recorder = TrajectoryRecorder(RunContext.new(), sink, TrajectoryRecorderConfig(mode=TelemetryMode.LIGHT))
    orchestrator = AgentOrchestrator(
        MagicMock(spec=LLMClient),
        dispatcher,
        MagicMock(spec=ToolParser),
        OrchestratorOptions(
            config=OrchestratorConfig(
                reliability_limits=limits, schema_config=SchemaConfig(use_native_constraint=False)
            ),
            recorder=recorder,
        ),
    )
    orchestrator._circuit = CircuitBreaker(limits, None)  # noqa: SLF001
    return orchestrator


async def _execute(dispatcher: AsyncToolDispatcher, tool_name: str) -> tuple[ToolCallResult, list[TrajectoryEvent]]:
    sink = _Sink()
    orchestrator = _orchestrator(dispatcher, sink)
    context = MessageContext()
    request = ToolCallRequest(tool_name=tool_name, arguments={})
    span = orchestrator.recorder.start_span()
    result = await orchestrator._execute_one_tool(1, request, span, context)  # noqa: SLF001
    return result, sink.events


def _dumped(element: ProviderFailure | None) -> dict[str, Any] | None:
    return None if element is None else element.model_dump(mode="json")


@pytest.mark.asyncio
@pytest.mark.parametrize(("label", "make", "code", "element"), _CASES, ids=[case[0] for case in _CASES])
async def test_dispatcher_and_loop_classify_each_failed_call(
    label: str,
    make: Callable[[], BaseException],
    code: FailureReasonCode,
    element: ProviderFailure | None,
) -> None:
    unregistered = label == "unregistered"
    dispatcher = AsyncToolDispatcher() if unregistered else _dispatcher_raising(make)
    name = "missing" if unregistered else "tool"

    direct = await dispatcher.dispatch(ToolCallRequest(tool_name=name, arguments={}))
    assert direct.success is False
    assert direct.reason_code is code
    assert direct.provider_failure == element

    looped, events = await _execute(dispatcher, name)
    assert looped.reason_code is code
    assert looped.provider_failure == element

    error = next(event for event in events if event.event_type is TrajectoryEventType.ERROR)
    assert error.error is not None
    assert error.error["type"] == "ToolExecutionError"
    assert error.error["reason_code"] == code.value
    assert error.error.get("provider_failure") == _dumped(element)

    summary = next(event for event in events if event.event_type is TrajectoryEventType.TOOL_RESULT)
    assert isinstance(summary.tool_result_summary, dict)
    assert summary.tool_result_summary["success"] is False
    assert summary.tool_result_summary["reason_code"] == code.value
    assert summary.tool_result_summary.get("provider_failure") == _dumped(element)
    json.dumps(error.error, ensure_ascii=False)
    json.dumps(summary.tool_result_summary, ensure_ascii=False)


@pytest.mark.asyncio
async def test_a_successful_call_carries_neither_field() -> None:
    dispatcher = AsyncToolDispatcher()
    dispatcher.register_tool("tool", lambda: 7)

    result, events = await _execute(dispatcher, "tool")

    assert result.success is True
    assert result.reason_code is None
    assert result.provider_failure is None
    summary = next(event for event in events if event.event_type is TrajectoryEventType.TOOL_RESULT)
    assert summary.tool_result_summary == {"success": True, "result": 7}
    assert not any(event.event_type is TrajectoryEventType.ERROR for event in events)


def _result(**fields: Any) -> ToolCallResult:
    return ToolCallResult(call_id="c", tool_name="t", result=None, **fields)


@pytest.mark.parametrize(
    "fields",
    [
        {"success": True, "reason_code": FailureReasonCode.EXECUTION_ERROR},
        {"success": True, "provider_failure": _UNREACHABLE},
        {"success": False},
        {"success": False, "provider_failure": _UNREACHABLE},
        {"success": False, "reason_code": FailureReasonCode.PROVIDER_ERROR, "provider_failure": _UNREACHABLE},
    ],
    ids=["success_with_code", "success_with_element", "failure_without_code", "element_without_code", "code_mismatch"],
)
def test_the_result_rejects_each_inconsistent_combination(fields: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _result(**fields)


def test_the_result_accepts_each_consistent_combination() -> None:
    assert _result(success=True).reason_code is None
    assert _result(success=False, reason_code=FailureReasonCode.EXECUTION_ERROR).provider_failure is None
    both = _result(success=False, reason_code=FailureReasonCode.PROVIDER_UNREACHABLE, provider_failure=_UNREACHABLE)
    assert both.provider_failure == _UNREACHABLE


@pytest.mark.asyncio
@pytest.mark.parametrize("exception_type", [DataFetchError, FinancialProviderError])
async def test_dispatcher_and_failure_envelope_produce_the_same_element(
    exception_type: type[DataFetchError] | type[FinancialProviderError],
) -> None:
    cause = exception_type("down", kind=ProviderFailureKind.NO_DATA, provider_id="synthetic")
    result = await _dispatcher_raising(lambda: cause).dispatch(ToolCallRequest(tool_name="tool", arguments={}))

    assert result.reason_code is FailureReasonCode.PROVIDER_NO_DATA
    assert result.provider_failure is not None
    envelope = failure_envelope(result.reason_code, "down", cause=cause)
    assert envelope.provider_failure == result.provider_failure
