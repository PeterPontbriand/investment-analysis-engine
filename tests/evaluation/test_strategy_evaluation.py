"""Each strategy's fixture composition and requirement, exercised through its own bound handler."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.core.analysis_status import CalculationStatus
from src.data.quality import HistoricalDataQualityError
from src.data.sec_edgar import SEC_PROVIDER_ID
from src.evaluation.fixture_context import (
    FixtureCompositionError,
    FixtureContext,
    build_fixture_context,
    require_fixture_evidence,
)
from src.evaluation.fixture_ids import (
    GRAHAM_FACTS_FIXTURE_ID,
    GRAHAM_PRECEDENCE_CACHE_FIXTURE_ID,
    KNOWN_ETF_PROFILE_FIXTURE_ID,
    MOMENTUM_BOUNDARY_FIXTURE_ID,
    MOMENTUM_SUCCESS_FIXTURE_ID,
)
from src.evaluation.fixtures.graham import (
    GOLDEN_PRECEDENCE_EPS_OVERRIDE,
    NOW,
    SECURITY_ID,
)
from src.evaluation.fixtures.graham import PROVIDER_ID as GRAHAM_PROVIDER_ID
from src.evaluation.fixtures.instrument_profiles import GOLDEN_ETF_TICKER
from src.evaluation.fixtures.sec_edgar_fpi import SEC_FPI_ASML_FIXTURE_ID, SEC_FPI_FIXTURE_IDS
from src.evaluation.models import Case, Expectation
from src.orchestrator.tool_runtime import ToolRuntime
from src.strategies.graham_growth import evaluation as graham_growth_evaluation
from src.strategies.graham_growth.service import GrahamGrowthAnalysis
from src.strategies.graham_growth.tool import GrahamGrowthValueToolArguments
from src.strategies.graham_number import evaluation as graham_number_evaluation
from src.strategies.graham_number.service import GrahamNumberAnalysis
from src.strategies.graham_number.tool import GrahamNumberToolArguments
from src.strategies.momentum import evaluation as momentum_evaluation
from src.strategies.momentum.analyzer import MomentumRun
from src.strategy_wiring import GRAHAM_GROWTH, GRAHAM_NUMBER, MOMENTUM

EXECUTION_TIME = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def _case(*fixture_ids: str) -> Case:
    """Build a small supplied case."""
    return Case(
        case_id="strategy-evaluation",
        description="Synthetic strategy fixture case.",
        task="Compose the strategy's fixtures.",
        fixture_ids=fixture_ids,
        expectation=Expectation(),
    )


def _context(*fixture_ids: str) -> FixtureContext:
    """Build the cross-strategy context for a supplied case."""
    return build_fixture_context(_case(*fixture_ids), clock_at=EXECUTION_TIME)


def _runtime() -> ToolRuntime:
    """Build the shared runtime with the fixed clock."""
    return ToolRuntime(clock=lambda: EXECUTION_TIME)


def test_momentum_composes_the_selected_price_fixture() -> None:
    """Each price variant reaches the real Momentum handler with its own reviewed frame."""
    handler = MOMENTUM.behavior.bind_handler(
        momentum_evaluation.compose(_context(MOMENTUM_SUCCESS_FIXTURE_ID)), _runtime()
    )
    result = handler(ticker="MOM")
    assert isinstance(result, MomentumRun)
    assert result.metrics.current_price == 104.0

    handler = MOMENTUM.behavior.bind_handler(
        momentum_evaluation.compose(_context(MOMENTUM_BOUNDARY_FIXTURE_ID)), _runtime()
    )
    boundary = handler(ticker="MOM")
    assert isinstance(boundary, MomentumRun)
    assert boundary.metrics.current_price == 101.0


def test_momentum_without_a_price_fixture_has_explicitly_empty_history() -> None:
    """An unselected price variant is an empty frame, never default data."""
    handler = MOMENTUM.behavior.bind_handler(momentum_evaluation.compose(_context(GRAHAM_FACTS_FIXTURE_ID)), _runtime())
    with pytest.raises(HistoricalDataQualityError):
        handler(ticker="MOM")


def test_momentum_rejects_two_price_variants() -> None:
    """Conflicting price fixtures fail closed in Momentum's own composition."""
    with pytest.raises(FixtureCompositionError, match="Conflicting Momentum price fixture IDs"):
        momentum_evaluation.compose(_context(MOMENTUM_SUCCESS_FIXTURE_ID, MOMENTUM_BOUNDARY_FIXTURE_ID))


def test_momentum_requires_a_price_fixture_and_has_no_etf_exemption() -> None:
    """The requirement names the price capability and an ETF profile does not satisfy it."""
    requirement = momentum_evaluation.REQUIREMENT
    assert requirement.required_ids == {MOMENTUM_SUCCESS_FIXTURE_ID, MOMENTUM_BOUNDARY_FIXTURE_ID}
    assert requirement.etf_profile_exempt is False
    with pytest.raises(FixtureCompositionError, match="has no selected Momentum price fixture"):
        require_fixture_evidence(_case(KNOWN_ETF_PROFILE_FIXTURE_ID), requirement, ticker=GOLDEN_ETF_TICKER)


def _graham_number(context: FixtureContext, arguments: GrahamNumberToolArguments) -> GrahamNumberAnalysis:
    """Run the real Graham Number handler over the composed dependencies."""
    handler = GRAHAM_NUMBER.behavior.bind_handler(graham_number_evaluation.compose(context), _runtime())
    result = handler(**arguments.model_dump(mode="python"))
    assert isinstance(result, GrahamNumberAnalysis)
    return result


def test_graham_number_composes_the_selected_facts() -> None:
    """Selected synthetic facts resolve; the provider identity is the fixture's."""
    context = _context(GRAHAM_FACTS_FIXTURE_ID)
    dependencies = graham_number_evaluation.compose(context)
    assert dependencies.security_provider_id == GRAHAM_PROVIDER_ID
    assert dependencies.quote_provider_id == GRAHAM_PROVIDER_ID
    result = _graham_number(context, GrahamNumberToolArguments(ticker=SECURITY_ID))
    assert result.result.status is CalculationStatus.OK


def test_graham_number_without_selected_facts_reports_every_fact_as_absent() -> None:
    """An unselected facts fixture is explicit absence, never default data."""
    result = _graham_number(_context(MOMENTUM_SUCCESS_FIXTURE_ID), GrahamNumberToolArguments(ticker=SECURITY_ID))
    assert result.result.status is CalculationStatus.INPUT_UNAVAILABLE


def test_graham_number_uses_the_foreign_private_issuer_provider_and_identity() -> None:
    """Selected SEC evidence replaces the synthetic provider and carries the SEC provider identity."""
    dependencies = graham_number_evaluation.compose(_context(SEC_FPI_ASML_FIXTURE_ID))
    assert dependencies.security_provider_id == SEC_PROVIDER_ID
    assert dependencies.quote_provider_id == SEC_PROVIDER_ID


def test_graham_number_reads_the_precedence_cache_only_when_selected() -> None:
    """The cached book value is the reviewed one when selected and the provider's otherwise."""
    arguments = GrahamNumberToolArguments(ticker=SECURITY_ID, as_of=NOW, eps_override=GOLDEN_PRECEDENCE_EPS_OVERRIDE)
    cached = _graham_number(_context(GRAHAM_FACTS_FIXTURE_ID, GRAHAM_PRECEDENCE_CACHE_FIXTURE_ID), arguments)
    uncached = _graham_number(_context(GRAHAM_FACTS_FIXTURE_ID), arguments)
    assert cached.result.maximum_indicated_price == pytest.approx(47.43416490252569, abs=1e-9)
    assert uncached.result.maximum_indicated_price != cached.result.maximum_indicated_price


def test_graham_number_requires_company_facts_with_the_etf_exemption() -> None:
    """The requirement lists the synthetic and SEC fact fixtures and exempts a profiled ETF ticker."""
    requirement = graham_number_evaluation.REQUIREMENT
    assert requirement.required_ids == {GRAHAM_FACTS_FIXTURE_ID, *SEC_FPI_FIXTURE_IDS}
    assert requirement.label == "Graham financial-fact"
    assert requirement.etf_profile_exempt is True
    etf_case = _case(KNOWN_ETF_PROFILE_FIXTURE_ID)
    require_fixture_evidence(etf_case, requirement, ticker=GOLDEN_ETF_TICKER)
    with pytest.raises(FixtureCompositionError, match="has no selected Graham financial-fact fixture"):
        require_fixture_evidence(etf_case, requirement, ticker=SECURITY_ID)


def _graham_growth(context: FixtureContext, arguments: GrahamGrowthValueToolArguments) -> GrahamGrowthAnalysis:
    """Run the real Graham growth-value handler over the composed dependencies."""
    handler = GRAHAM_GROWTH.behavior.bind_handler(graham_growth_evaluation.compose(context), _runtime())
    result = handler(**arguments.model_dump(mode="python"))
    assert isinstance(result, GrahamGrowthAnalysis)
    return result


def _growth_arguments() -> GrahamGrowthValueToolArguments:
    """Build the reviewed growth-value arguments for the synthetic security."""
    return GrahamGrowthValueToolArguments(
        ticker=SECURITY_ID, eps_basis="ttm", expected_growth=6.5, current_aaa_yield=4.15
    )


def test_graham_growth_composes_the_selected_facts_with_the_reviewed_policy() -> None:
    """Selected facts resolve and the reviewed policy yields the reviewed growth value."""
    context = _context(GRAHAM_FACTS_FIXTURE_ID)
    dependencies = graham_growth_evaluation.compose(context)
    assert dependencies.security_provider_id == GRAHAM_PROVIDER_ID
    assert dependencies.quote_provider_id == GRAHAM_PROVIDER_ID
    result = _graham_growth(context, _growth_arguments())
    assert result.result.growth_value == pytest.approx(109.41686746987952, abs=1e-9)


def test_graham_growth_without_selected_facts_reports_every_fact_as_absent() -> None:
    """An unselected facts fixture is explicit absence, never default data."""
    result = _graham_growth(_context(MOMENTUM_SUCCESS_FIXTURE_ID), _growth_arguments())
    assert result.result.status is CalculationStatus.INPUT_UNAVAILABLE


def test_graham_growth_uses_the_foreign_private_issuer_identity() -> None:
    """Selected SEC evidence carries the SEC provider identity for both providers."""
    dependencies = graham_growth_evaluation.compose(_context(SEC_FPI_ASML_FIXTURE_ID))
    assert dependencies.security_provider_id == SEC_PROVIDER_ID
    assert dependencies.quote_provider_id == SEC_PROVIDER_ID


def test_graham_growth_shares_the_graham_requirement() -> None:
    """Both Graham strategies state the same capability, label and ETF exemption."""
    assert graham_growth_evaluation.REQUIREMENT == graham_number_evaluation.REQUIREMENT
