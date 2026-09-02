"""Focused catalog and deterministic-runtime checks for the reviewed Momentum cases."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from src.analysis.momentum.momentum_analyzer import MomentumRun
from src.core.constants import TrendStatus
from src.core.metric_result import MetricStatus, ReasonCode
from src.core.telemetry import RunContext, TrajectoryRecorder
from src.core.telemetry.models import TrajectoryEvent
from src.evaluation.cases.momentum import (
    MOMENTUM_BOUNDARY_CASE,
    MOMENTUM_CASES,
    MOMENTUM_ETF_CASE,
    MOMENTUM_SUCCESS_CASE,
)
from src.evaluation.composition import dispatch_fixture_case
from src.evaluation.fixtures.market_data import MOMENTUM_LONG_WINDOW, MOMENTUM_RSI_PERIOD, MOMENTUM_SHORT_WINDOW
from src.evaluation.models import Case, ComponentKind, ComponentOutcome, ComponentResult, ToolName
from src.evaluation.reporting import CaseEvaluationResult, CaseOutcome
from src.evaluation.runner import DeterministicCaseRequest, run_deterministic_suite
from src.orchestrator.analysis_tools import MomentumToolArguments

EXECUTED_AT = datetime(2026, 8, 31, 18, 30, tzinfo=UTC)
RUN_ID = UUID("30000000-0000-0000-0000-000000000003")
SESSION_ID = UUID("40000000-0000-0000-0000-000000000004")


class RecordingSink:
    """Retain deterministic runner telemetry in memory."""

    def __init__(self) -> None:
        """Initialize an empty event collection."""
        self.events: list[TrajectoryEvent] = []

    def record(self, event: TrajectoryEvent) -> None:
        """Retain one event."""
        self.events.append(event)

    def flush(self) -> None:
        """Accept the runner flush request."""

    def close(self) -> None:
        """Accept the runner close request."""


def _recorder() -> TrajectoryRecorder:
    """Build a recorder with stable test identity."""
    return TrajectoryRecorder(RunContext(run_id=RUN_ID, session_id=SESSION_ID), RecordingSink())


def _request(case: Case) -> DeterministicCaseRequest:
    """Pair one reviewed Momentum case with its reviewed configuration."""
    return DeterministicCaseRequest(
        case=case,
        arguments=MomentumToolArguments(
            ticker="FLSW" if case.case_id == "MOM-ETF-01" else "MOM",
            short_window=MOMENTUM_SHORT_WINDOW,
            long_window=MOMENTUM_LONG_WINDOW,
            rsi_period=MOMENTUM_RSI_PERIOD,
        ),
    )


def _component(result: CaseEvaluationResult, kind: ComponentKind) -> ComponentResult:
    """Return one component from the requested case result."""
    return next(component for component in result.components if component.kind is kind)


def _numeric_expectations(case: Case) -> dict[str, float]:
    """Return the reviewed numeric expectation mapping for catalog assertions."""
    return {item.field_path: item.expected_value for item in case.expectation.numerical_expectations}


def test_reviewed_momentum_catalog_contains_the_corrected_minimum_cases() -> None:
    """Catalog IDs, fixtures, prompts, tools, signals, and numeric truth are explicit."""
    assert tuple(case.case_id for case in MOMENTUM_CASES) == ("MOM-01", "MOM-02", "MOM-ETF-01")
    assert MOMENTUM_SUCCESS_CASE.fixture_ids == ("momentum_success",)
    assert MOMENTUM_BOUNDARY_CASE.fixture_ids == ("momentum_boundary",)
    assert MOMENTUM_ETF_CASE.fixture_ids == ("known_etf_profile", "momentum_success")
    assert all(
        case.expectation.tool_constraints.permitted == (ToolName.ANALYZE_MOMENTUM,)
        and case.expectation.tool_constraints.required == (ToolName.ANALYZE_MOMENTUM,)
        for case in MOMENTUM_CASES
    )
    assert "rising-price" in MOMENTUM_SUCCESS_CASE.description
    assert "long window is unavailable" in MOMENTUM_BOUNDARY_CASE.description
    assert _numeric_expectations(MOMENTUM_SUCCESS_CASE) == {
        "metrics.current_price": 104.0,
        "metrics.short_sma_val": 103.5,
        "metrics.long_sma_val": 103.0,
        "metrics.crossover_signal": 0.0,
        "metrics.rsi_result.value": 100.0,
    }
    assert _numeric_expectations(MOMENTUM_BOUNDARY_CASE) == {
        "metrics.current_price": 101.0,
        "metrics.short_sma_val": 100.5,
    }
    assert all(
        expectation.absolute_tolerance == 1e-12 and expectation.relative_tolerance is None
        for case in MOMENTUM_CASES
        for expectation in case.expectation.numerical_expectations
    )


@pytest.mark.asyncio
async def test_reviewed_momentum_cases_run_deterministically_and_pass() -> None:
    """All reviewed Momentum cases pass through fixture composition and the deterministic runner."""
    report = await run_deterministic_suite(
        tuple(_request(case) for case in MOMENTUM_CASES),
        suite_id="step-2.5-momentum-g1",
        suite_version="g1-v1",
        fixture_set_version="step-2.5-b2-v1",
        executed_at=EXECUTED_AT,
        recorder=_recorder(),
    )

    assert report.total_cases == 3
    assert report.passed_cases == 3
    assert report.failed_cases == 0
    assert report.overall_pass_rate == 1.0
    assert tuple(result.case_id for result in report.case_results) == ("MOM-01", "MOM-02", "MOM-ETF-01")
    assert all(result.outcome is CaseOutcome.PASS for result in report.case_results)
    for result in report.case_results:
        assert _component(result, ComponentKind.NUMERICAL_CORRECTNESS).outcome is ComponentOutcome.PASS
        assert _component(result, ComponentKind.FIXTURE_STATUS).outcome is ComponentOutcome.PASS
        assert _component(result, ComponentKind.EXECUTION_STATUS).outcome is ComponentOutcome.PASS
        assert _component(result, ComponentKind.STRATEGY_SELECTION).outcome is ComponentOutcome.NOT_MEASURED


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "status", "rsi_status", "rsi_reason"),
    [
        (MOMENTUM_SUCCESS_CASE, TrendStatus.BULLISH, MetricStatus.OK, None),
        (MOMENTUM_BOUNDARY_CASE, TrendStatus.UNKNOWN, MetricStatus.UNAVAILABLE, ReasonCode.INSUFFICIENT_HISTORY),
        (MOMENTUM_ETF_CASE, TrendStatus.BULLISH, MetricStatus.OK, None),
    ],
)
async def test_reviewed_momentum_native_status_and_boundary_fields_are_exact(
    case: Case,
    status: TrendStatus,
    rsi_status: MetricStatus,
    rsi_reason: ReasonCode | None,
) -> None:
    """The exact nonnumeric dossier outcomes remain explicit native result assertions."""
    result = await dispatch_fixture_case(
        case,
        MomentumToolArguments(
            ticker="FLSW" if case.case_id == "MOM-ETF-01" else "MOM",
            short_window=MOMENTUM_SHORT_WINDOW,
            long_window=MOMENTUM_LONG_WINDOW,
            rsi_period=MOMENTUM_RSI_PERIOD,
        ),
        clock_at=EXECUTED_AT,
    )
    assert isinstance(result.result, MomentumRun)
    metrics = result.result.metrics
    assert metrics.status is status
    assert metrics.rsi_result is not None
    assert metrics.rsi_result.status is rsi_status
    assert metrics.rsi_result.reason_code is rsi_reason
    if case.case_id != "MOM-02":
        assert metrics.long_sma_val == 103.0
        assert metrics.crossover_signal == 0.0
    else:
        assert metrics.long_sma_val is None
        assert metrics.crossover_signal is None
        assert metrics.rsi_result.value is None
