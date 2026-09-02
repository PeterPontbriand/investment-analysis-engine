"""Focused catalog and deterministic-runtime checks for Graham Number cases."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

import pytest

from src.analysis.graham_value.service import GrahamNumberAnalysis
from src.core.analysis_status import CalculationStatus
from src.core.telemetry import RunContext, TrajectoryRecorder
from src.core.telemetry.models import TrajectoryEvent
from src.evaluation.cases.graham_number import GRA_ETF_01, GRAHAM_NUMBER_CASES, GRN_01, GRN_02, GRN_03
from src.evaluation.composition import dispatch_fixture_case
from src.evaluation.models import Case, ComponentKind, ComponentOutcome, ComponentResult, GrahamMethod, ToolName
from src.evaluation.reporting import CaseEvaluationResult, CaseOutcome
from src.evaluation.runner import DeterministicCaseRequest, run_deterministic_suite
from src.orchestrator.analysis_tools import GrahamNumberToolArguments

EXECUTED_AT = datetime(2026, 8, 31, 18, 30, tzinfo=UTC)
RUN_ID = UUID("70000000-0000-0000-0000-000000000007")
SESSION_ID = UUID("80000000-0000-0000-0000-000000000008")


class RecordingSink:
    """Retain deterministic runner telemetry in memory."""

    def record(self, event: TrajectoryEvent) -> None:
        """Accept one telemetry event."""
        del event

    def flush(self) -> None:
        """Accept the runner flush request."""

    def close(self) -> None:
        """Accept the runner close request."""


def _recorder() -> TrajectoryRecorder:
    """Build a recorder with stable test identity."""
    return TrajectoryRecorder(RunContext(run_id=RUN_ID, session_id=SESSION_ID), RecordingSink())


def _arguments(case: Case) -> GrahamNumberToolArguments:
    """Build reviewed Graham Number arguments for one catalog case."""
    eps_basis: Literal["three_year_average", "ttm"] = "ttm" if case.case_id == "GRN-02" else "three_year_average"
    ticker = "FLSW" if case.case_id == "GRA-ETF-01" else "MISSING_QUOTE" if case.case_id == "GRN-03" else "SYNTH"
    return GrahamNumberToolArguments(ticker=ticker, eps_basis=eps_basis)


def _request(case: Case) -> DeterministicCaseRequest:
    """Pair one reviewed case with its reviewed production arguments."""
    return DeterministicCaseRequest(case=case, arguments=_arguments(case))


def _component(result: CaseEvaluationResult, kind: ComponentKind) -> ComponentResult:
    """Return one component from a case result."""
    return next(component for component in result.components if component.kind is kind)


@pytest.mark.parametrize(
    ("case", "fixture_id", "ticker", "eps_basis"),
    [
        (GRN_01, "graham_facts", "SYNTH", "three_year_average"),
        (GRN_02, "graham_facts", "SYNTH", "ttm"),
        (GRA_ETF_01, "known_etf_profile", "FLSW", "three_year_average"),
        (GRN_03, "graham_facts", "MISSING_QUOTE", "three_year_average"),
    ],
)
def test_reviewed_graham_number_catalog_is_explicit(
    case: Case,
    fixture_id: str,
    ticker: str,
    eps_basis: str,
) -> None:
    """Catalog IDs, fixture/tool/method constraints, prompts, and arguments are stable."""
    assert case.fixture_ids == (fixture_id,)
    assert case.expectation.tool_constraints.permitted == (ToolName.ANALYZE_GRAHAM_NUMBER,)
    assert case.expectation.tool_constraints.required == (ToolName.ANALYZE_GRAHAM_NUMBER,)
    assert case.expectation.graham_method_constraints.permitted == (GrahamMethod.GRAHAM_NUMBER,)
    assert case.expectation.graham_method_constraints.required == (GrahamMethod.GRAHAM_NUMBER,)
    arguments = _arguments(case)
    assert arguments.ticker == ticker
    assert arguments.eps_basis == eps_basis


def test_reviewed_graham_number_catalog_contains_only_the_four_cases() -> None:
    """G2 contributes exactly the reviewed Graham Number IDs in dossier order."""
    assert tuple(case.case_id for case in GRAHAM_NUMBER_CASES) == ("GRN-01", "GRN-02", "GRA-ETF-01", "GRN-03")
    assert "three-completed-fiscal-year" in GRN_01.description
    assert "TTM fact" in GRN_02.description
    assert "not applicable directly" in GRA_ETF_01.description
    assert "missing current quote" in GRN_03.description
    assert tuple(item.field_path for item in GRN_01.expectation.numerical_expectations) == (
        "assembly.eps.value",
        "margin_of_safety_percent",
        "result.maximum_indicated_price",
    )
    assert tuple(item.field_path for item in GRN_02.expectation.numerical_expectations) == (
        "assembly.eps.value",
        "margin_of_safety_percent",
        "result.maximum_indicated_price",
    )
    assert tuple(item.field_path for item in GRN_03.expectation.numerical_expectations) == (
        "result.maximum_indicated_price",
    )
    assert GRA_ETF_01.expectation.numerical_expectations == ()


@pytest.mark.asyncio
async def test_reviewed_graham_number_cases_run_deterministically_and_pass() -> None:
    """All four reviewed cases pass through fixture composition and deterministic evaluation."""
    report = await run_deterministic_suite(
        tuple(_request(case) for case in GRAHAM_NUMBER_CASES),
        suite_id="step-2.5-graham-number-g2",
        suite_version="g2-v1",
        fixture_set_version="step-2.5-b2-v1",
        executed_at=EXECUTED_AT,
        recorder=_recorder(),
    )

    assert report.total_cases == 4
    assert report.passed_cases == 4
    assert report.failed_cases == 0
    assert report.overall_pass_rate == 1.0
    assert all(result.outcome is CaseOutcome.PASS for result in report.case_results)
    for result in report.case_results:
        assert _component(result, ComponentKind.FIXTURE_STATUS).outcome is ComponentOutcome.PASS
        assert _component(result, ComponentKind.EXECUTION_STATUS).outcome is ComponentOutcome.PASS
        assert _component(result, ComponentKind.STRATEGY_SELECTION).outcome is ComponentOutcome.NOT_MEASURED
        assert _component(result, ComponentKind.GRAHAM_METHOD_SELECTION).outcome is ComponentOutcome.NOT_MEASURED
    etf_result = next(result for result in report.case_results if result.case_id == "GRA-ETF-01")
    assert _component(etf_result, ComponentKind.NUMERICAL_CORRECTNESS).outcome is ComponentOutcome.NOT_APPLICABLE


@pytest.mark.asyncio
@pytest.mark.parametrize("case", [GRN_01, GRN_02, GRN_03, GRA_ETF_01])
async def test_reviewed_graham_number_native_outcomes_are_exact(case: Case) -> None:
    """Native status, basis, price-comparison, and applicability outcomes match the dossier."""
    dispatch_result = await dispatch_fixture_case(case, _arguments(case), clock_at=EXECUTED_AT)
    assert isinstance(dispatch_result.result, GrahamNumberAnalysis)
    analysis = dispatch_result.result

    if case.case_id == "GRA-ETF-01":
        assert analysis.assembly.status is CalculationStatus.NOT_APPLICABLE
        assert analysis.result.status is CalculationStatus.NOT_APPLICABLE
        assert analysis.result.maximum_indicated_price is None
        assert analysis.margin_of_safety_percent is None
        assert analysis.result.reason == (
            "Graham Number is a company-level valuation method and does not apply directly to an ETF. "
            "No constituent-level or aggregate ETF valuation was performed."
        )
        return

    assert analysis.assembly.status is CalculationStatus.OK
    assert analysis.result.status is CalculationStatus.OK
    assert analysis.result.maximum_indicated_price is not None
    if case.case_id == "GRN-02":
        assert analysis.assembly.eps is not None
        assert analysis.assembly.eps.value == 4.8
        assert analysis.assembly.eps.basis == "ttm"
    elif case.case_id == "GRN-03":
        assert analysis.assembly.current_price is None
        assert analysis.margin_of_safety_percent is None
        assert analysis.result.maximum_indicated_price == pytest.approx(36.68616905592624, abs=1e-9)
    else:
        assert analysis.margin_of_safety_percent == pytest.approx(-42.56053806073687, abs=1e-9)
