"""Focused catalog and deterministic checks for the reviewed FCF G4 cases."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from src.analysis.fcf_earnings_growth.models import (
    Classification,
    FCFEarningsGrowthResult,
    HistoricalHorizon,
    MetricStatus,
    ReasonCode,
    TrendClassification,
)
from src.core.analysis_status import CalculationStatus
from src.core.telemetry import RunContext, TrajectoryRecorder
from src.core.telemetry.models import TrajectoryEvent
from src.evaluation.cases.fcf_earnings_growth import (
    FCF_01,
    FCF_02,
    FCF_03,
    FCF_EARNINGS_GROWTH_CASES,
    FCF_ETF_01,
)
from src.evaluation.composition import dispatch_fixture_case
from src.evaluation.evaluator import evaluate_tool_selection
from src.evaluation.fixtures.fcf_earnings_growth import FCF_GROWTH_HISTORICAL_AS_OF
from src.evaluation.models import (
    Case,
    ComponentKind,
    ComponentOutcome,
    ComponentResult,
    ExecutionMode,
    Observation,
    ToolCallObservation,
    ToolName,
)
from src.evaluation.reporting import CaseEvaluationResult, CaseOutcome
from src.evaluation.runner import DeterministicCaseRequest, run_deterministic_suite
from src.orchestrator.analysis_tools import FCFEarningsGrowthToolArguments

EXECUTED_AT = datetime(2026, 8, 31, 18, 30, tzinfo=UTC)
RUN_ID = UUID("d0000000-0000-0000-0000-00000000000d")
SESSION_ID = UUID("e0000000-0000-0000-0000-00000000000e")


class RecordingSink:
    """Accept deterministic runner telemetry in memory."""

    def record(self, event: TrajectoryEvent) -> None:
        """Accept one event."""
        del event

    def flush(self) -> None:
        """Accept a flush request."""

    def close(self) -> None:
        """Accept a close request."""


def _recorder() -> TrajectoryRecorder:
    """Build a recorder with stable test identity."""
    return TrajectoryRecorder(RunContext(run_id=RUN_ID, session_id=SESSION_ID), RecordingSink())


def _arguments(case: Case) -> FCFEarningsGrowthToolArguments:
    """Build the reviewed arguments for one FCF case."""
    return FCFEarningsGrowthToolArguments(
        ticker="FLSW" if case.case_id == "FCF-ETF-01" else "ACME",
        historical_horizon=(
            HistoricalHorizon.FOUR_YEARS if case.case_id == "FCF-03" else HistoricalHorizon.LONGEST_AVAILABLE
        ),
        as_of=FCF_GROWTH_HISTORICAL_AS_OF if case.case_id == "FCF-03" else None,
    )


def _component(result: CaseEvaluationResult, kind: ComponentKind) -> ComponentResult:
    """Return one component from a case result."""
    return next(component for component in result.components if component.kind is kind)


def test_reviewed_fcf_catalog_contains_the_corrected_minimum_cases() -> None:
    """Catalog IDs, fixtures, tool constraints, signals, and truth are explicit."""
    assert tuple(case.case_id for case in FCF_EARNINGS_GROWTH_CASES) == (
        "FCF-01",
        "FCF-02",
        "FCF-03",
        "FCF-ETF-01",
    )
    assert tuple(case.fixture_ids for case in FCF_EARNINGS_GROWTH_CASES) == (
        ("fcf_growth_success",),
        ("fcf_growth_nonmeaningful",),
        ("fcf_growth_period_as_of",),
        ("known_etf_profile",),
    )
    assert all(
        case.expectation.tool_constraints.permitted == (ToolName.ANALYZE_FCF_EARNINGS_GROWTH,)
        and case.expectation.tool_constraints.required == (ToolName.ANALYZE_FCF_EARNINGS_GROWTH,)
        for case in FCF_EARNINGS_GROWTH_CASES
    )


def test_fcf_case_discriminates_momentum_tool_selection() -> None:
    """A plausible Momentum selection fails the FCF strategy constraint independently."""
    observation = Observation(
        execution_mode=ExecutionMode.REAL_LOCAL_OLLAMA,
        observed_at=EXECUTED_AT,
        tool_calls=(ToolCallObservation(tool_name=ToolName.ANALYZE_MOMENTUM),),
    )
    result = evaluate_tool_selection(FCF_01.expectation.tool_constraints, observation)
    assert result.kind is ComponentKind.STRATEGY_SELECTION
    assert result.outcome is ComponentOutcome.FAIL
    assert result.failure_reason is not None
    assert "Missing required tools" in result.failure_reason
    assert "Momentum" in FCF_01.description
    assert "sign change" in FCF_02.description
    assert "period alignment" in FCF_03.description
    assert {item.field_path: item.expected_value for item in FCF_01.expectation.numerical_expectations} == {
        "selected_horizon_years": 5.0,
        "selected_observation_count": 6.0,
        "fcf_cagr.value": 10.197228772148015,
        "fcf_per_share_cagr.value": 10.197228772148015,
        "eps_cagr.value": 17.607902252467357,
    }
    assert {item.field_path: item.expected_value for item in FCF_02.expectation.numerical_expectations} == {
        "selected_horizon_years": 5.0,
        "selected_observation_count": 6.0,
        "eps_cagr.value": 17.607902252467357,
    }
    assert FCF_03.expectation.numerical_expectations == ()
    assert all(
        item.absolute_tolerance in (0.0, 1e-12) and item.relative_tolerance is None
        for case in FCF_EARNINGS_GROWTH_CASES
        for item in case.expectation.numerical_expectations
    )


@pytest.mark.asyncio
async def test_reviewed_fcf_cases_run_deterministically_with_expected_boundary_category() -> None:
    """All four cases pass when their exact native domain outcomes match."""
    report = await run_deterministic_suite(
        tuple(DeterministicCaseRequest(case=case, arguments=_arguments(case)) for case in FCF_EARNINGS_GROWTH_CASES),
        suite_id="step-2.5-fcf-g4",
        suite_version="g4-v1",
        fixture_set_version="step-2.5-b2-v1",
        executed_at=EXECUTED_AT,
        recorder=_recorder(),
    )

    assert report.total_cases == 4
    assert report.passed_cases == 4
    assert report.failed_cases == 0
    assert tuple(result.case_id for result in report.case_results) == (
        "FCF-01",
        "FCF-02",
        "FCF-03",
        "FCF-ETF-01",
    )
    assert all(result.outcome is CaseOutcome.PASS for result in report.case_results)
    boundary = report.case_results[2]
    assert boundary.outcome is CaseOutcome.PASS
    assert _component(boundary, ComponentKind.FIXTURE_STATUS).outcome is ComponentOutcome.PASS
    assert _component(boundary, ComponentKind.EXECUTION_STATUS).outcome is ComponentOutcome.PASS
    assert _component(boundary, ComponentKind.NUMERICAL_CORRECTNESS).outcome is ComponentOutcome.NOT_APPLICABLE


@pytest.mark.asyncio
@pytest.mark.parametrize("case", [FCF_01, FCF_02, FCF_03])
async def test_reviewed_fcf_native_outputs_match_dossier(case: Case) -> None:
    """Native statuses, metrics, classifications, and boundary reasons remain exact."""
    dispatch_result = await dispatch_fixture_case(case, _arguments(case), clock_at=EXECUTED_AT)
    assert isinstance(dispatch_result.result, FCFEarningsGrowthResult)
    result = dispatch_result.result

    if case.case_id == "FCF-01":
        assert result.execution_status is CalculationStatus.OK
        assert result.selected_horizon_years == 5
        assert result.selected_observation_count == 6
        assert result.used_horizon_fallback is False
        assert result.fcf_cagr.status is MetricStatus.OK
        assert result.fcf_per_share_cagr.status is MetricStatus.OK
        assert result.eps_cagr.status is MetricStatus.OK
        assert result.fcf_cagr.value == pytest.approx(10.197228772148015, abs=1e-12)
        assert result.fcf_per_share_cagr.value == pytest.approx(10.197228772148015, abs=1e-12)
        assert result.eps_cagr.value == pytest.approx(17.607902252467357, abs=1e-12)
        assert result.classification is Classification.PASS
        assert result.trend_classification is TrendClassification.BOTH_GROWING
        assert result.classification_reason_code is None
    elif case.case_id == "FCF-02":
        assert result.execution_status is CalculationStatus.OK
        assert result.selected_horizon_years == 5
        assert result.selected_observation_count == 6
        assert result.fcf_cagr.status is MetricStatus.UNAVAILABLE
        assert result.fcf_cagr.reason_code is ReasonCode.SIGN_CHANGE
        assert result.fcf_cagr.value is None
        assert result.fcf_per_share_cagr.status is MetricStatus.UNAVAILABLE
        assert result.fcf_per_share_cagr.reason_code is ReasonCode.SIGN_CHANGE
        assert result.fcf_per_share_cagr.value is None
        assert result.eps_cagr.status is MetricStatus.OK
        assert result.eps_cagr.value == pytest.approx(17.607902252467357, abs=1e-12)
        assert result.classification is Classification.INDETERMINATE
        assert result.trend_classification is TrendClassification.INSUFFICIENT_OR_NONMEANINGFUL_GROWTH
        assert result.classification_reason_code is ReasonCode.SIGN_CHANGE
    else:
        assert result.execution_status is CalculationStatus.INPUT_UNAVAILABLE
        assert result.selected_horizon_years is None
        assert result.selected_observation_count == 0
        assert result.used_horizon_fallback is False
        assert result.fcf_cagr.status is MetricStatus.UNAVAILABLE
        assert result.fcf_cagr.reason_code is ReasonCode.NON_CONTIGUOUS_HISTORY
        assert result.fcf_per_share_cagr.status is MetricStatus.UNAVAILABLE
        assert result.fcf_per_share_cagr.reason_code is ReasonCode.NON_CONTIGUOUS_HISTORY
        assert result.eps_cagr.status is MetricStatus.UNAVAILABLE
        assert result.eps_cagr.reason_code is ReasonCode.NON_CONTIGUOUS_HISTORY
        assert result.classification is Classification.INDETERMINATE
        assert result.trend_classification is TrendClassification.INSUFFICIENT_OR_NONMEANINGFUL_GROWTH
        assert result.classification_reason_code is ReasonCode.NON_CONTIGUOUS_HISTORY


@pytest.mark.asyncio
async def test_reviewed_fcf_etf_native_outcome_is_not_applicable() -> None:
    """The ETF case completes normally without requesting company facts."""
    dispatch_result = await dispatch_fixture_case(FCF_ETF_01, _arguments(FCF_ETF_01), clock_at=EXECUTED_AT)
    assert isinstance(dispatch_result.result, FCFEarningsGrowthResult)
    result = dispatch_result.result

    assert result.execution_status is CalculationStatus.NOT_APPLICABLE
    assert result.selected_horizon_years is None
    assert result.selected_observation_count == 0
    assert result.fcf_cagr.status is MetricStatus.NOT_APPLICABLE
    assert result.fcf_per_share_cagr.status is MetricStatus.NOT_APPLICABLE
    assert result.eps_cagr.status is MetricStatus.NOT_APPLICABLE
    assert result.classification is Classification.INDETERMINATE
    assert result.classification_reason_code is ReasonCode.INSTRUMENT_KIND_NOT_APPLICABLE
