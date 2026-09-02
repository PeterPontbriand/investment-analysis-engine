"""Deterministic/no-LLM Golden-Suite execution through production dispatch."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Final
from uuid import UUID

from src.analysis.fcf_earnings_growth import FCFEarningsGrowthResult
from src.analysis.graham_value.service import GrahamGrowthAnalysis, GrahamNumberAnalysis
from src.analysis.momentum.momentum_analyzer import MomentumRun
from src.core.telemetry import (
    TrajectoryErrorRecord,
    TrajectoryEventType,
    TrajectoryRecord,
    TrajectoryRecorder,
)
from src.evaluation.composition import (
    AnalysisToolArguments,
    FixtureCompositionError,
    dispatch_fixture_case,
)
from src.evaluation.evaluator import (
    evaluate_domain_outcomes,
    evaluate_fixture_status,
    evaluate_graham_method_selection,
    evaluate_numerical_correctness,
    evaluate_tool_selection,
)
from src.evaluation.models import (
    Case,
    ComponentKind,
    ComponentResult,
    DomainOutcomeObservation,
    ExecutionMode,
    NumericalObservation,
    Observation,
    ToolName,
)
from src.evaluation.reporting import (
    CaseEvaluationResult,
    EvaluationReport,
    build_case_result,
    build_evaluation_report,
)
from src.orchestrator.analysis_tools import (
    FCFEarningsGrowthToolArguments,
    GrahamGrowthValueToolArguments,
    GrahamNumberToolArguments,
    MomentumToolArguments,
)
from src.orchestrator.types import ToolCallResult

logger = logging.getLogger(__name__)

DETERMINISTIC_REQUIRED_COMPONENT_KINDS: Final = (
    ComponentKind.FIXTURE_STATUS,
    ComponentKind.EXECUTION_STATUS,
    ComponentKind.NUMERICAL_CORRECTNESS,
)

type NativeAnalysisResult = MomentumRun | GrahamNumberAnalysis | GrahamGrowthAnalysis | FCFEarningsGrowthResult


@dataclass(frozen=True, slots=True)
class DeterministicCaseRequest:
    """One supplied typed case and the production arguments used to execute it."""

    case: Case
    arguments: AnalysisToolArguments


@dataclass(frozen=True, slots=True)
class _ExecutionEvidence:
    """Internal execution evidence before component evaluation."""

    numerical_observations: tuple[NumericalObservation, ...]
    domain_outcome_observations: tuple[DomainOutcomeObservation, ...]
    tool_result_summary: dict[str, object]
    fixture_failure: str | None = None
    execution_failure: str | None = None


async def run_deterministic_suite(  # noqa: PLR0913
    requests: tuple[DeterministicCaseRequest, ...],
    *,
    suite_id: str,
    suite_version: str,
    fixture_set_version: str,
    executed_at: datetime,
    recorder: TrajectoryRecorder,
) -> EvaluationReport:
    """Execute supplied cases without an LLM and return an in-memory report.

    Args:
        requests: Explicit case/production-argument pairs; no catalog is loaded.
        suite_id: Stable suite identifier supplied by the caller.
        suite_version: Explicit suite contract version.
        fixture_set_version: Explicit fixture evidence version.
        executed_at: Timezone-aware ``datetime`` used for fixtures and reporting.
        recorder: Caller-owned Step 2.1 recorder for observational telemetry.

    Returns:
        Aggregated deterministic evaluation report.

    Raises:
        ValueError: If case identifiers are duplicated or report metadata is invalid.
    """
    _reject_duplicate_cases(requests)

    run_span_id = recorder.start_span()
    run_status = "failed"
    _record(
        recorder,
        TrajectoryRecord(
            event_type=TrajectoryEventType.RUN_START,
            component="evaluation.runner",
            span_id=run_span_id,
            provider="fixture",
            payload={
                "execution_mode": ExecutionMode.DETERMINISTIC_NO_LLM.value,
                "case_count": len(requests),
                "suite_id": suite_id,
                "suite_version": suite_version,
                "fixture_set_version": fixture_set_version,
                "executed_at": executed_at.isoformat(),
            },
        ),
    )
    case_results: list[CaseEvaluationResult] = []
    try:
        for step_index, request in enumerate(requests, start=1):
            case_results.append(
                await _run_case(
                    request,
                    executed_at=executed_at,
                    recorder=recorder,
                    run_span_id=run_span_id,
                    step_index=step_index,
                )
            )
        report = build_evaluation_report(
            suite_id=suite_id,
            suite_version=suite_version,
            fixture_set_version=fixture_set_version,
            execution_mode=ExecutionMode.DETERMINISTIC_NO_LLM,
            executed_at=executed_at,
            required_component_kinds=DETERMINISTIC_REQUIRED_COMPONENT_KINDS,
            case_results=tuple(case_results),
            run_id=str(recorder.run_id),
        )
        run_status = "completed"
        return report
    except Exception as exc:
        _record_error(
            recorder,
            TrajectoryErrorRecord(
                component="evaluation.runner",
                message=str(exc),
                span_id=run_span_id,
                error_type=type(exc).__name__,
            ),
        )
        raise
    finally:
        _record(
            recorder,
            TrajectoryRecord(
                event_type=TrajectoryEventType.RUN_END,
                component="evaluation.runner",
                span_id=run_span_id,
                provider="fixture",
                payload={
                    "status": run_status,
                    "completed_case_count": len(case_results),
                },
            ),
        )
        recorder.end_span(run_span_id)
        recorder.flush()
        recorder.close()


async def _run_case(
    request: DeterministicCaseRequest,
    *,
    executed_at: datetime,
    recorder: TrajectoryRecorder,
    run_span_id: UUID,
    step_index: int,
) -> CaseEvaluationResult:
    """Execute and evaluate one supplied deterministic case."""
    case_span_id = recorder.start_span(parent_span_id=run_span_id)
    tool_span_id = recorder.start_span(parent_span_id=case_span_id)
    tool_name = _tool_name(request.arguments)
    arguments = request.arguments.model_dump(mode="json")
    _record(
        recorder,
        TrajectoryRecord(
            event_type=TrajectoryEventType.STEP_START,
            component="evaluation.runner",
            span_id=case_span_id,
            parent_span_id=run_span_id,
            step_index=step_index,
            provider="fixture",
            payload={"case_id": request.case.case_id},
        ),
    )
    _record(
        recorder,
        TrajectoryRecord(
            event_type=TrajectoryEventType.TOOL_CALL,
            component="evaluation.runner",
            span_id=tool_span_id,
            parent_span_id=case_span_id,
            step_index=step_index,
            provider="fixture",
            tool_name=tool_name.value,
            tool_args=arguments,
        ),
    )

    evidence = await _execute(request, executed_at=executed_at)
    _record(
        recorder,
        TrajectoryRecord(
            event_type=TrajectoryEventType.TOOL_RESULT,
            component="evaluation.runner",
            span_id=tool_span_id,
            parent_span_id=case_span_id,
            step_index=step_index,
            provider="fixture",
            tool_name=tool_name.value,
            tool_result_summary=evidence.tool_result_summary,
        ),
    )
    if evidence.fixture_failure is not None or evidence.execution_failure is not None:
        failure = evidence.fixture_failure or evidence.execution_failure
        assert failure is not None
        _record_error(
            recorder,
            TrajectoryErrorRecord(
                component="evaluation.runner",
                message=failure,
                step_index=step_index,
                span_id=tool_span_id,
                parent_span_id=case_span_id,
                error_type="FixtureError" if evidence.fixture_failure is not None else "ExecutionError",
            ),
        )
    observation = Observation(
        execution_mode=ExecutionMode.DETERMINISTIC_NO_LLM,
        observed_at=executed_at,
        numerical_observations=evidence.numerical_observations,
        domain_outcome_observations=evidence.domain_outcome_observations,
    )
    fixture_status = evaluate_fixture_status(evidence.fixture_failure)
    execution_status = evaluate_domain_outcomes(
        request.case.expectation.domain_outcome_expectations,
        observation,
        execution_failure=evidence.execution_failure,
    )
    components: tuple[ComponentResult, ...] = (
        evaluate_tool_selection(request.case.expectation.tool_constraints, observation),
        evaluate_graham_method_selection(request.case.expectation.graham_method_constraints, observation),
        evaluate_numerical_correctness(
            request.case.expectation.numerical_expectations,
            observation,
            fixture_status=fixture_status,
            execution_status=execution_status,
        ),
        fixture_status,
        execution_status,
    )
    result = build_case_result(
        case_id=request.case.case_id,
        components=components,
        required_component_kinds=DETERMINISTIC_REQUIRED_COMPONENT_KINDS,
        trajectory_id=str(recorder.run_id),
    )
    _record(
        recorder,
        TrajectoryRecord(
            event_type=TrajectoryEventType.STEP_END,
            component="evaluation.runner",
            span_id=case_span_id,
            parent_span_id=run_span_id,
            step_index=step_index,
            provider="fixture",
            payload={"case_id": request.case.case_id, "outcome": result.outcome.value},
        ),
    )
    recorder.end_span(tool_span_id)
    recorder.end_span(case_span_id)
    return result


async def _execute(request: DeterministicCaseRequest, *, executed_at: datetime) -> _ExecutionEvidence:
    """Dispatch one case and classify its native result without telemetry control flow."""
    try:
        dispatch_result = await dispatch_fixture_case(
            request.case,
            request.arguments,
            clock_at=executed_at,
        )
    except FixtureCompositionError as exc:
        return _ExecutionEvidence(
            numerical_observations=(),
            domain_outcome_observations=(),
            tool_result_summary={"success": False, "stage": "fixture_composition"},
            fixture_failure=str(exc),
        )
    except Exception as exc:
        return _ExecutionEvidence(
            numerical_observations=(),
            domain_outcome_observations=(),
            tool_result_summary={
                "success": False,
                "stage": "production_dispatch",
                "error_type": type(exc).__name__,
            },
            execution_failure=f"Production dispatch raised {type(exc).__name__}: {exc}",
        )

    if not dispatch_result.success:
        return _ExecutionEvidence(
            numerical_observations=(),
            domain_outcome_observations=(),
            tool_result_summary={"success": False, "stage": "production_handler"},
            execution_failure=dispatch_result.error_message or "Production dispatch failed without an error message.",
        )
    try:
        native_result = _native_result(dispatch_result)
    except TypeError as exc:
        return _ExecutionEvidence(
            numerical_observations=(),
            domain_outcome_observations=(),
            tool_result_summary={"success": False, "stage": "result_contract"},
            execution_failure=str(exc),
        )
    try:
        numerical = _numerical_observations(request.case, native_result)
        domain_outcomes = _domain_outcome_observations(request.case, native_result)
    except (TypeError, ValueError) as exc:
        return _ExecutionEvidence(
            numerical_observations=(),
            domain_outcome_observations=(),
            tool_result_summary={
                "success": False,
                "stage": "result_extraction",
                "result_type": type(native_result).__name__,
            },
            execution_failure=f"Structured result extraction failed: {exc}",
        )
    return _ExecutionEvidence(
        numerical_observations=numerical,
        domain_outcome_observations=domain_outcomes,
        tool_result_summary={
            "success": True,
            "result_type": type(native_result).__name__,
            "calculation_status": _native_status(native_result),
            "numerical_observations": [observation.model_dump(mode="json") for observation in numerical],
            "domain_outcome_observations": [observation.model_dump(mode="json") for observation in domain_outcomes],
        },
    )


def _native_result(dispatch_result: ToolCallResult) -> NativeAnalysisResult:
    """Require one of the four existing native production result types."""
    result = dispatch_result.result
    if isinstance(result, (MomentumRun, GrahamNumberAnalysis, GrahamGrowthAnalysis, FCFEarningsGrowthResult)):
        return result
    raise TypeError(f"Production dispatcher returned unsupported result type {type(result).__name__!r}.")


def _native_status(result: NativeAnalysisResult) -> str | None:
    """Return one native calculation-status value for telemetry evidence."""
    if isinstance(result, MomentumRun):
        return None
    if isinstance(result, (GrahamNumberAnalysis, GrahamGrowthAnalysis)):
        return result.result.status.value
    return result.execution_status.value


def _numerical_observations(case: Case, result: NativeAnalysisResult) -> tuple[NumericalObservation, ...]:
    """Extract only explicitly expected finite numerical result fields."""
    observations: list[NumericalObservation] = []
    for expectation in case.expectation.numerical_expectations:
        value = _field_value(result, expectation.field_path)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{expectation.field_path!r} is not a numerical result field")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"{expectation.field_path!r} is not finite")
        observations.append(NumericalObservation(field_path=expectation.field_path, value=number))
    return tuple(observations)


def _domain_outcome_observations(
    case: Case,
    result: NativeAnalysisResult,
) -> tuple[DomainOutcomeObservation, ...]:
    """Extract only explicitly expected scalar native-result outcome fields."""
    observations: list[DomainOutcomeObservation] = []
    for expectation in case.expectation.domain_outcome_expectations:
        found, value = _resolved_field_value(result, expectation.field_path)
        if not found:
            continue
        if isinstance(value, Enum):
            value = value.value
        if value is not None and not isinstance(value, (str, bool, int)):
            raise TypeError(f"{expectation.field_path!r} is not a supported domain-outcome field")
        observations.append(DomainOutcomeObservation(field_path=expectation.field_path, value=value))
    return tuple(observations)


def _field_value(result: NativeAnalysisResult, field_path: str) -> object | None:
    """Resolve one reviewed dotted field path from a native typed result."""
    found, value = _resolved_field_value(result, field_path)
    return value if found else None


def _resolved_field_value(result: NativeAnalysisResult, field_path: str) -> tuple[bool, object | None]:
    """Resolve one dotted field path while distinguishing missing fields from explicit nulls."""
    current: object = result
    segments = field_path.split(".")
    for index, segment in enumerate(segments):
        if not hasattr(current, segment):
            return False, None
        current = getattr(current, segment)
        if current is None:
            return index == len(segments) - 1, None
    return True, current


def _tool_name(arguments: AnalysisToolArguments) -> ToolName:
    """Return the production tool identity represented by strict arguments."""
    if isinstance(arguments, MomentumToolArguments):
        return ToolName.ANALYZE_MOMENTUM
    if isinstance(arguments, GrahamNumberToolArguments):
        return ToolName.ANALYZE_GRAHAM_NUMBER
    if isinstance(arguments, GrahamGrowthValueToolArguments):
        return ToolName.ANALYZE_GRAHAM_GROWTH_VALUE
    if isinstance(arguments, FCFEarningsGrowthToolArguments):
        return ToolName.ANALYZE_FCF_EARNINGS_GROWTH
    raise TypeError(f"Unsupported analysis-tool argument model: {type(arguments).__name__}.")


def _reject_duplicate_cases(requests: tuple[DeterministicCaseRequest, ...]) -> None:
    """Reject duplicate supplied identifiers before any case is executed."""
    case_ids = tuple(request.case.case_id for request in requests)
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("deterministic case identifiers must be unique")


def _record(recorder: TrajectoryRecorder, record: TrajectoryRecord) -> None:
    """Keep recorder failures observational and outside execution semantics."""
    try:
        recorder.record(record)
    except Exception:
        logger.exception("Golden-Suite telemetry recording failed; continuing deterministic execution.")


def _record_error(recorder: TrajectoryRecorder, error: TrajectoryErrorRecord) -> None:
    """Keep error-telemetry failures observational and outside execution semantics."""
    try:
        recorder.record_error(error)
    except Exception:
        logger.exception("Golden-Suite error telemetry failed; continuing deterministic execution.")
