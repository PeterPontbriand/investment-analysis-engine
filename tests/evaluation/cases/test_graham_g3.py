"""Focused catalog and deterministic checks for the reviewed Graham G3 cases."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from src.analysis.graham_value.input_resolver import GrahamInputResolver
from src.analysis.graham_value.service import GrahamGrowthAnalysis, GrahamNumberAnalysis, run_graham_number_analysis
from src.core.analysis_status import CalculationStatus
from src.core.telemetry import RunContext, TrajectoryRecorder
from src.core.telemetry.models import TrajectoryEvent
from src.data.financial.cache import InMemoryResolvedInputCache, ResolvedInputCacheKey
from src.data.financial.facts import FinancialField
from src.data.financial.provenance import FinancialSubjectKind, ResolvedInput, SourceKind
from src.evaluation.cases.graham_growth import GRG_01, GRG_ETF_01
from src.evaluation.cases.graham_resolution import GRN_04, GRN_05
from src.evaluation.composition import dispatch_fixture_case
from src.evaluation.fixtures.graham import (
    BVPS_AVAIL,
    FIELD_BVPS,
    GOLDEN_HISTORICAL_AS_OF,
    NOW,
    PROVIDER_ID,
    RETRIEVED_AT,
    SECURITY_ID,
    FixtureFinancialFactsProvider,
)
from src.evaluation.models import Case, ComponentKind, ComponentOutcome, ComponentResult, GrahamMethod, ToolName
from src.evaluation.reporting import CaseEvaluationResult, CaseOutcome
from src.evaluation.runner import DeterministicCaseRequest, run_deterministic_suite
from src.orchestrator.analysis_tools import GrahamGrowthValueToolArguments, GrahamNumberToolArguments

EXECUTED_AT = datetime(2026, 8, 31, 18, 30, tzinfo=UTC)
RUN_ID = UUID("b0000000-0000-0000-0000-00000000000b")
SESSION_ID = UUID("c0000000-0000-0000-0000-00000000000c")


class RecordingSink:
    """Accept deterministic runner telemetry without persistence."""

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


def _growth_arguments(case: Case = GRG_01) -> GrahamGrowthValueToolArguments:
    """Build the exact reviewed GRG-01 arguments."""
    return GrahamGrowthValueToolArguments(
        ticker="FLSW" if case.case_id == "GRG-ETF-01" else SECURITY_ID,
        eps_basis="ttm",
        expected_growth=6.5,
        current_aaa_yield=4.15,
    )


def _number_arguments(case: Case) -> GrahamNumberToolArguments:
    """Build exact reviewed arguments for one resolution case."""
    as_of = GOLDEN_HISTORICAL_AS_OF if case.case_id == "GRN-05" else NOW
    return GrahamNumberToolArguments(ticker=SECURITY_ID, as_of=as_of)


def _component(result: CaseEvaluationResult, kind: ComponentKind) -> ComponentResult:
    """Return one component from a case result."""
    return next(component for component in result.components if component.kind is kind)


def _seeded_precedence_resolver() -> GrahamInputResolver:
    """Build the reviewed test-local cache evidence for GRN-04."""
    cache = InMemoryResolvedInputCache(clock=lambda: NOW)
    cached_bvps = ResolvedInput(
        field_name=FinancialField.BVPS,
        value=20.0,
        source_kind=SourceKind.PROVIDER,
        resolved_at=NOW,
        units="currency_per_share",
        currency="USD",
        provider_id=PROVIDER_ID,
        provider_field=FIELD_BVPS,
        available_at=BVPS_AVAIL,
        as_of=NOW,
        retrieved_at=RETRIEVED_AT,
    )
    cache.put(
        ResolvedInputCacheKey(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id=SECURITY_ID,
            field_name=FinancialField.BVPS,
            basis=None,
            provider_id=PROVIDER_ID,
            analysis_as_of=NOW,
            schema_version=1,
        ),
        cached_bvps,
    )
    return GrahamInputResolver(provider=FixtureFinancialFactsProvider(), cache=cache, clock=lambda: NOW)


@pytest.mark.parametrize(
    ("case", "tool", "method"),
    [
        (GRG_01, ToolName.ANALYZE_GRAHAM_GROWTH_VALUE, GrahamMethod.GRAHAM_GROWTH_VALUE),
        (GRG_ETF_01, ToolName.ANALYZE_GRAHAM_GROWTH_VALUE, GrahamMethod.GRAHAM_GROWTH_VALUE),
        (GRN_04, ToolName.ANALYZE_GRAHAM_NUMBER, GrahamMethod.GRAHAM_NUMBER),
        (GRN_05, ToolName.ANALYZE_GRAHAM_NUMBER, GrahamMethod.GRAHAM_NUMBER),
    ],
)
def test_reviewed_g3_catalog_constraints_and_expectations_are_explicit(
    case: Case,
    tool: ToolName,
    method: GrahamMethod,
) -> None:
    """Stable IDs, strategy/method constraints, and reviewed numeric truth are present."""
    assert case.expectation.tool_constraints.permitted == (tool,)
    assert case.expectation.tool_constraints.required == (tool,)
    assert case.expectation.graham_method_constraints.permitted == (method,)
    assert case.expectation.graham_method_constraints.required == (method,)
    assert case.task
    if case.case_id == "GRG-ETF-01":
        assert case.fixture_ids == ("known_etf_profile",)
    elif case.case_id == "GRN-04":
        assert case.fixture_ids == ("graham_facts", "graham_precedence_cache")
    else:
        assert case.fixture_ids == ("graham_facts",)

    if case.case_id == "GRG-01":
        values = {item.field_path: item.expected_value for item in case.expectation.numerical_expectations}
        assert values["result.growth_value"] == 109.41686746987952
        assert values["margin_of_safety_percent"] == 52.20115398167724
    elif case.case_id == "GRN-04":
        values = {item.field_path: item.expected_value for item in case.expectation.numerical_expectations}
        assert values["result.maximum_indicated_price"] == 47.43416490252569
        assert values["margin_of_safety_percent"] == -10.258081084537493
    elif case.case_id == "GRN-05":
        assert case.expectation.numerical_expectations == ()
    else:
        assert case.expectation.domain_outcome_expectations


@pytest.mark.asyncio
async def test_growth_case_runner_keeps_strategy_and_method_selection_independent() -> None:
    """GRG-01 passes numerically while deterministic selection remains unmeasured."""
    request = DeterministicCaseRequest(case=GRG_01, arguments=_growth_arguments())
    report = await run_deterministic_suite(
        (request,),
        suite_id="step-2.5-graham-g3-growth",
        suite_version="g3-v1",
        fixture_set_version="step-2.5-b2-v1",
        executed_at=EXECUTED_AT,
        recorder=_recorder(),
    )

    assert report.passed_cases == 1
    result = report.case_results[0]
    assert result.case_id == "GRG-01"
    assert result.outcome is CaseOutcome.PASS
    assert _component(result, ComponentKind.NUMERICAL_CORRECTNESS).outcome is ComponentOutcome.PASS
    assert _component(result, ComponentKind.STRATEGY_SELECTION).outcome is ComponentOutcome.NOT_MEASURED
    assert _component(result, ComponentKind.GRAHAM_METHOD_SELECTION).outcome is ComponentOutcome.NOT_MEASURED


@pytest.mark.asyncio
async def test_growth_case_native_outputs_match_reviewed_assumptions_and_method() -> None:
    """GRG-01 retains exact TTM assumptions and growth-value output."""
    dispatch_result = await dispatch_fixture_case(GRG_01, _growth_arguments(), clock_at=EXECUTED_AT)
    assert isinstance(dispatch_result.result, GrahamGrowthAnalysis)
    analysis = dispatch_result.result
    assert analysis.assembly.status is CalculationStatus.OK
    assert analysis.result.status is CalculationStatus.OK
    assert analysis.assembly.eps is not None
    assert analysis.assembly.eps.value == 4.8
    assert analysis.assembly.eps.basis == "ttm"
    assert analysis.assembly.expected_growth is not None
    assert analysis.assembly.expected_growth.value == 6.5
    assert analysis.assembly.current_aaa_yield is not None
    assert analysis.assembly.current_aaa_yield.value == 4.15
    assert analysis.policy.base_pe == 8.5
    assert analysis.policy.growth_multiplier == 2.0
    assert analysis.policy.baseline_aaa_yield == 4.4
    assert analysis.result.growth_value == pytest.approx(109.41686746987952, abs=1e-9)
    assert analysis.margin_of_safety_percent == pytest.approx(52.20115398167724, abs=1e-9)


def test_precedence_case_native_outputs_match_reviewed_cache_and_provider_sources() -> None:
    """GRN-04 proves override, cache, provider precedence through the resolver boundary."""
    analysis = run_graham_number_analysis(
        resolver=_seeded_precedence_resolver(),
        ticker=SECURITY_ID,
        security_provider_id=PROVIDER_ID,
        eps_basis="three_year_average",
        eps_override=5.0,
        bvps_override=None,
        quote_override=None,
        quote_provider_id=PROVIDER_ID,
        as_of=NOW,
        use_cache=True,
    )
    assert analysis.assembly.status is CalculationStatus.OK
    assert analysis.result.status is CalculationStatus.OK
    assert analysis.assembly.eps is not None
    assert analysis.assembly.eps.source_kind is SourceKind.OVERRIDE
    assert analysis.assembly.bvps is not None
    assert analysis.assembly.bvps.source_kind is SourceKind.CACHE
    assert analysis.assembly.current_price is not None
    assert analysis.assembly.current_price.source_kind is SourceKind.PROVIDER
    assert analysis.result.maximum_indicated_price == pytest.approx(47.43416490252569, abs=1e-9)
    assert analysis.margin_of_safety_percent == pytest.approx(-10.258081084537493, abs=1e-9)


@pytest.mark.asyncio
async def test_historical_as_of_case_rejects_unpublished_evidence_without_zero_substitution() -> None:
    """GRN-05 reports input unavailability and no fabricated valuation output."""
    dispatch_result = await dispatch_fixture_case(GRN_05, _number_arguments(GRN_05), clock_at=EXECUTED_AT)
    assert isinstance(dispatch_result.result, GrahamNumberAnalysis)
    analysis = dispatch_result.result
    assert analysis.assembly.status is CalculationStatus.INPUT_UNAVAILABLE
    assert analysis.result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert analysis.assembly.eps is None
    assert analysis.assembly.bvps is None
    assert analysis.result.maximum_indicated_price is None
    assert analysis.assembly.current_price is None
    assert analysis.margin_of_safety_percent is None
