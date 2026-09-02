"""Integration checks for deterministic Golden-Suite execution and telemetry."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from src.core.telemetry import RunContext, TrajectoryRecorder
from src.core.telemetry.models import TrajectoryEvent, TrajectoryEventType
from src.evaluation.composition import (
    KNOWN_ETF_PROFILE_FIXTURE_ID,
    MOMENTUM_BOUNDARY_FIXTURE_ID,
    MOMENTUM_SUCCESS_FIXTURE_ID,
)
from src.evaluation.fixtures.market_data import MOMENTUM_LONG_WINDOW, MOMENTUM_RSI_PERIOD, MOMENTUM_SHORT_WINDOW
from src.evaluation.models import (
    Case,
    ComponentKind,
    ComponentOutcome,
    ComponentResult,
    DomainOutcomeExpectation,
    Expectation,
    NumericalExpectation,
    ToolConstraints,
    ToolName,
)
from src.evaluation.reporting import CaseOutcome, EvaluationReport
from src.evaluation.runner import DeterministicCaseRequest, run_deterministic_suite
from src.orchestrator.analysis_tools import MomentumToolArguments

EXECUTED_AT = datetime(2026, 8, 31, 18, 30, tzinfo=UTC)
RUN_ID = UUID("10000000-0000-0000-0000-000000000001")
SESSION_ID = UUID("20000000-0000-0000-0000-000000000002")


class RecordingSink:
    """Retain Step 2.1 events in memory without filesystem persistence."""

    def __init__(self) -> None:
        """Initialize an empty event collection."""
        self.events: list[TrajectoryEvent] = []
        self.flushed = False
        self.closed = False

    def record(self, event: TrajectoryEvent) -> None:
        """Retain one event."""
        self.events.append(event)

    def flush(self) -> None:
        """Record that the runner requested a flush."""
        self.flushed = True

    def close(self) -> None:
        """Record that the runner released the sink."""
        self.closed = True


class FailingSink:
    """Exercise the existing fail-open telemetry boundary."""

    def record(self, event: TrajectoryEvent) -> None:
        """Simulate unavailable telemetry storage."""
        del event
        raise OSError("telemetry unavailable")

    def flush(self) -> None:
        """Simulate a flush failure."""
        raise OSError("telemetry unavailable")

    def close(self) -> None:
        """Simulate a close failure."""
        raise OSError("telemetry unavailable")


def _recorder(sink: RecordingSink | FailingSink) -> TrajectoryRecorder:
    """Build a recorder with stable test identity."""
    return TrajectoryRecorder(RunContext(run_id=RUN_ID, session_id=SESSION_ID), sink)


def _momentum_case(*fixture_ids: str) -> Case:
    """Build the one small synthetic case authorized for E2."""
    return Case(
        case_id="synthetic-momentum-success",
        description="Exercise deterministic Momentum through production dispatch.",
        task="Analyze the supplied rising price fixture with Momentum.",
        fixture_ids=fixture_ids,
        expectation=Expectation(
            tool_constraints=ToolConstraints(
                permitted=(ToolName.ANALYZE_MOMENTUM,),
                required=(ToolName.ANALYZE_MOMENTUM,),
            ),
            numerical_expectations=(
                NumericalExpectation(
                    field_path="metrics.current_price",
                    expected_value=104.0,
                    absolute_tolerance=0.0,
                ),
                NumericalExpectation(
                    field_path="metrics.long_sma_val",
                    expected_value=103.0,
                    absolute_tolerance=0.0,
                ),
                NumericalExpectation(
                    field_path="metrics.rsi_result.value",
                    expected_value=100.0,
                    absolute_tolerance=0.0,
                ),
                NumericalExpectation(
                    field_path="metrics.short_sma_val",
                    expected_value=103.5,
                    absolute_tolerance=0.0,
                ),
            ),
        ),
    )


def _request(*fixture_ids: str) -> DeterministicCaseRequest:
    """Pair the synthetic case with strict production Momentum arguments."""
    return DeterministicCaseRequest(
        case=_momentum_case(*fixture_ids),
        arguments=MomentumToolArguments(
            ticker="mom",
            short_window=MOMENTUM_SHORT_WINDOW,
            long_window=MOMENTUM_LONG_WINDOW,
            rsi_period=MOMENTUM_RSI_PERIOD,
        ),
    )


async def _run(
    recorder: TrajectoryRecorder,
    request: DeterministicCaseRequest,
) -> EvaluationReport:
    """Execute one explicitly supplied request with stable report metadata."""
    return await run_deterministic_suite(
        (request,),
        suite_id="step-2.5-synthetic",
        suite_version="e2-v1",
        fixture_set_version="step-2.5-b2-v1",
        executed_at=EXECUTED_AT,
        recorder=recorder,
    )


def _component(report: EvaluationReport, kind: ComponentKind) -> ComponentResult:
    """Return one component from the single synthetic case."""
    return next(component for component in report.case_results[0].components if component.kind is kind)


@pytest.mark.asyncio
async def test_deterministic_runner_connects_dispatch_evaluation_reporting_and_telemetry() -> None:
    """One supplied typed case traverses the complete E2 deterministic pipeline."""
    sink = RecordingSink()

    report = await _run(_recorder(sink), _request(MOMENTUM_SUCCESS_FIXTURE_ID))

    assert report.executed_at == EXECUTED_AT
    assert report.run_id == str(RUN_ID)
    assert report.total_cases == 1
    assert report.passed_cases == 1
    assert report.failed_cases == 0
    assert report.overall_pass_rate == 1.0
    assert report.case_results[0].outcome is CaseOutcome.PASS
    assert report.case_results[0].trajectory_id == str(RUN_ID)
    assert _component(report, ComponentKind.STRATEGY_SELECTION).outcome is ComponentOutcome.NOT_MEASURED
    assert _component(report, ComponentKind.GRAHAM_METHOD_SELECTION).outcome is ComponentOutcome.NOT_APPLICABLE
    assert _component(report, ComponentKind.NUMERICAL_CORRECTNESS).outcome is ComponentOutcome.PASS
    assert _component(report, ComponentKind.FIXTURE_STATUS).outcome is ComponentOutcome.PASS
    assert _component(report, ComponentKind.EXECUTION_STATUS).outcome is ComponentOutcome.PASS
    serialized = report.model_dump_json()
    assert EvaluationReport.model_validate_json(serialized) == report
    assert report.model_dump_json() == serialized

    assert [event.event_type for event in sink.events] == [
        TrajectoryEventType.RUN_START,
        TrajectoryEventType.STEP_START,
        TrajectoryEventType.TOOL_CALL,
        TrajectoryEventType.TOOL_RESULT,
        TrajectoryEventType.STEP_END,
        TrajectoryEventType.RUN_END,
    ]
    assert all(event.run_id == RUN_ID for event in sink.events)
    assert all(event.model_tag is None for event in sink.events)
    assert not any(
        event.event_type in (TrajectoryEventType.PROMPT_SENT, TrajectoryEventType.LLM_RESPONSE) for event in sink.events
    )
    tool_call = next(event for event in sink.events if event.event_type is TrajectoryEventType.TOOL_CALL)
    tool_result = next(event for event in sink.events if event.event_type is TrajectoryEventType.TOOL_RESULT)
    assert tool_call.tool_name == ToolName.ANALYZE_MOMENTUM.value
    run_payload = sink.events[0].payload
    assert isinstance(run_payload, dict)
    assert run_payload["executed_at"] == EXECUTED_AT.isoformat()
    assert tool_call.tool_args is not None
    assert tool_call.tool_args["ticker"] == "MOM"
    assert isinstance(tool_result.tool_result_summary, dict)
    assert tool_result.tool_result_summary["success"] is True
    numerical_summary = tool_result.tool_result_summary["numerical_observations"]
    assert isinstance(numerical_summary, list)
    assert len(numerical_summary) == 4
    assert sink.flushed is True
    assert sink.closed is True


@pytest.mark.asyncio
async def test_direct_dispatch_telemetry_does_not_become_selection_credit() -> None:
    """A visible scripted tool call remains unmeasured model-selection evidence."""
    sink = RecordingSink()

    report = await _run(_recorder(sink), _request(MOMENTUM_SUCCESS_FIXTURE_ID))

    selection_metric = next(
        metric for metric in report.component_metrics if metric.kind is ComponentKind.STRATEGY_SELECTION
    )
    assert any(event.event_type is TrajectoryEventType.TOOL_CALL for event in sink.events)
    assert selection_metric.not_measured == 1
    assert selection_metric.measured_applicable == 0
    assert selection_metric.pass_rate is None


@pytest.mark.asyncio
async def test_fixture_composition_failure_is_reported_separately() -> None:
    """Missing price evidence fails the fixture component, not numerical correctness."""
    sink = RecordingSink()

    report = await _run(_recorder(sink), _request(KNOWN_ETF_PROFILE_FIXTURE_ID))

    assert report.failed_cases == 1
    assert report.case_results[0].outcome is CaseOutcome.FAIL
    assert _component(report, ComponentKind.FIXTURE_STATUS).outcome is ComponentOutcome.FAIL
    assert _component(report, ComponentKind.EXECUTION_STATUS).outcome is ComponentOutcome.PASS
    assert _component(report, ComponentKind.NUMERICAL_CORRECTNESS).outcome is ComponentOutcome.NOT_APPLICABLE
    assert any(event.event_type is TrajectoryEventType.ERROR for event in sink.events)
    tool_result = next(event for event in sink.events if event.event_type is TrajectoryEventType.TOOL_RESULT)
    assert tool_result.tool_result_summary == {"success": False, "stage": "fixture_composition"}


@pytest.mark.asyncio
async def test_domain_outcome_path_through_null_intermediate_is_missing() -> None:
    """A null parent does not manufacture a present nested-null outcome."""
    base_case = _momentum_case(MOMENTUM_BOUNDARY_FIXTURE_ID)
    expectation = base_case.expectation.model_copy(
        update={
            "domain_outcome_expectations": (
                DomainOutcomeExpectation(field_path="metrics.long_sma_val.impossible", expected_value=None),
            )
        }
    )
    request = DeterministicCaseRequest(
        case=base_case.model_copy(update={"expectation": expectation}),
        arguments=MomentumToolArguments(
            ticker="mom",
            short_window=MOMENTUM_SHORT_WINDOW,
            long_window=MOMENTUM_LONG_WINDOW,
            rsi_period=MOMENTUM_RSI_PERIOD,
        ),
    )

    report = await _run(_recorder(RecordingSink()), request)

    execution = _component(report, ComponentKind.EXECUTION_STATUS)
    assert execution.outcome is ComponentOutcome.FAIL
    assert execution.failure_reason is not None
    assert "missing metrics.long_sma_val.impossible" in execution.failure_reason


@pytest.mark.asyncio
async def test_telemetry_sink_failure_does_not_change_case_or_report_outcome() -> None:
    """Step 2.1 storage failures remain observational and fail open."""
    report = await _run(_recorder(FailingSink()), _request(MOMENTUM_SUCCESS_FIXTURE_ID))

    assert report.passed_cases == 1
    assert report.failed_cases == 0
    assert report.case_results[0].outcome is CaseOutcome.PASS
    assert report.run_id == str(RUN_ID)
