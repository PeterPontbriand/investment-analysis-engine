"""Focused checks for deterministic fixture composition and production dispatch."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.core.analysis_status import CalculationStatus
from src.core.strategy_errors import UndeclaredStrategyError
from src.evaluation import composition
from src.evaluation.composition import (
    compose_fixture_dependencies,
    compose_fixture_dispatcher,
    dispatch_fixture_case,
)
from src.evaluation.fixture_context import FixtureCompositionError
from src.evaluation.fixture_ids import (
    FCF_GROWTH_NONMEANINGFUL_FIXTURE_ID,
    FCF_GROWTH_PERIOD_AS_OF_FIXTURE_ID,
    FCF_GROWTH_SUCCESS_FIXTURE_ID,
    GRAHAM_FACTS_FIXTURE_ID,
    KNOWN_ETF_PROFILE_FIXTURE_ID,
    MOMENTUM_BOUNDARY_FIXTURE_ID,
    MOMENTUM_SUCCESS_FIXTURE_ID,
)
from src.evaluation.fixtures.graham import (
    GOLDEN_EXPECTED_GROWTH,
)
from src.evaluation.fixtures.graham import (
    NOW as GRAHAM_NOW,
)
from src.evaluation.fixtures.graham import (
    SECURITY_ID as GRAHAM_SECURITY_ID,
)
from src.evaluation.fixtures.instrument_profiles import GOLDEN_ETF_TICKER
from src.evaluation.fixtures.market_data import MOMENTUM_LONG_WINDOW, MOMENTUM_RSI_PERIOD, MOMENTUM_SHORT_WINDOW
from src.evaluation.models import Case, Expectation
from src.orchestrator.analysis_tool_arguments import AnalysisToolArguments
from src.orchestrator.tool_names import ToolName
from src.orchestrator.types import ToolCallRequest
from src.strategies.fcf_growth.models import FCFEarningsGrowthResult
from src.strategies.fcf_growth.tool import FCFEarningsGrowthToolArguments
from src.strategies.graham_growth.service import GrahamGrowthAnalysis
from src.strategies.graham_growth.tool import GrahamGrowthValueToolArguments
from src.strategies.graham_number.service import GrahamNumberAnalysis
from src.strategies.graham_number.tool import GrahamNumberToolArguments
from src.strategies.momentum.analyzer import MomentumRun
from src.strategies.momentum.tool import MomentumToolArguments

EXECUTION_TIME = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def _case(case_id: str, *fixture_ids: str) -> Case:
    """Build a small supplied case without introducing a production catalog."""
    return Case(
        case_id=case_id,
        description=f"Synthetic composition case {case_id}.",
        task="Execute the explicitly supplied production analysis tool.",
        fixture_ids=fixture_ids,
        expectation=Expectation(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "arguments", "expected_type"),
    [
        (
            _case("momentum", MOMENTUM_SUCCESS_FIXTURE_ID),
            MomentumToolArguments(
                ticker="MOM",
                short_window=MOMENTUM_SHORT_WINDOW,
                long_window=MOMENTUM_LONG_WINDOW,
                rsi_period=MOMENTUM_RSI_PERIOD,
            ),
            MomentumRun,
        ),
        (
            _case("graham-number", GRAHAM_FACTS_FIXTURE_ID),
            GrahamNumberToolArguments(ticker=GRAHAM_SECURITY_ID),
            GrahamNumberAnalysis,
        ),
        (
            _case("graham-growth", GRAHAM_FACTS_FIXTURE_ID),
            GrahamGrowthValueToolArguments(
                ticker=GRAHAM_SECURITY_ID,
                eps_basis="ttm",
                expected_growth=GOLDEN_EXPECTED_GROWTH,
                current_aaa_yield=4.15,
            ),
            GrahamGrowthAnalysis,
        ),
        (
            _case("fcf-growth", FCF_GROWTH_SUCCESS_FIXTURE_ID),
            FCFEarningsGrowthToolArguments(ticker="ACME"),
            FCFEarningsGrowthResult,
        ),
    ],
)
async def test_fixture_cases_reach_all_four_production_handlers(
    case: Case,
    arguments: AnalysisToolArguments,
    expected_type: type[object],
) -> None:
    """Each approved fixture capability reaches its existing native result boundary."""
    result = await dispatch_fixture_case(case, arguments, clock_at=EXECUTION_TIME)

    assert result.success is True
    assert isinstance(result.result, expected_type)
    assert result.call_id == f"golden:{case.case_id}:{result.tool_name}"


@pytest.mark.asyncio
async def test_supplied_momentum_case_preserves_reviewed_fixture_values() -> None:
    """The small end-to-end proof uses the typed case, fixture, and real dispatcher."""
    case = _case("momentum-success", MOMENTUM_SUCCESS_FIXTURE_ID)
    arguments = MomentumToolArguments(
        ticker="MOM",
        short_window=MOMENTUM_SHORT_WINDOW,
        long_window=MOMENTUM_LONG_WINDOW,
        rsi_period=MOMENTUM_RSI_PERIOD,
    )

    result = await dispatch_fixture_case(case, arguments, clock_at=EXECUTION_TIME)

    assert result.success is True
    assert isinstance(result.result, MomentumRun)
    assert result.result.metrics.current_price == 104.0
    assert result.result.metrics.short_sma_val == 103.5
    assert result.result.metrics.long_sma_val == 103.0
    assert result.result.metrics.rsi_result is not None
    assert result.result.metrics.rsi_result.value == 100.0


@pytest.mark.asyncio
async def test_known_etf_profile_is_sufficient_without_manufactured_company_facts() -> None:
    """Affirmative profile evidence short-circuits Graham fact resolution as reviewed."""
    case = _case("known-etf", KNOWN_ETF_PROFILE_FIXTURE_ID)

    result = await dispatch_fixture_case(
        case,
        GrahamNumberToolArguments(ticker=GOLDEN_ETF_TICKER),
        clock_at=EXECUTION_TIME,
    )

    assert result.success is True
    assert isinstance(result.result, GrahamNumberAnalysis)
    assert result.result.result.status is CalculationStatus.NOT_APPLICABLE
    assert result.result.assembly.eps is None
    assert result.result.assembly.bvps is None


@pytest.mark.asyncio
async def test_missing_selected_facts_remain_typed_unavailable() -> None:
    """A selected fixture never falls through to live facts for an absent subject."""
    case = _case("absent-fcf-subject", FCF_GROWTH_SUCCESS_FIXTURE_ID)

    result = await dispatch_fixture_case(
        case,
        FCFEarningsGrowthToolArguments(ticker="ABSENT"),
        clock_at=EXECUTION_TIME,
    )

    assert result.success is True
    assert isinstance(result.result, FCFEarningsGrowthResult)
    assert result.result.execution_status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.result.annual_observations == ()


@pytest.mark.asyncio
async def test_registered_unselected_graham_capability_has_no_hidden_fixture_data() -> None:
    """Direct dispatcher access still sees explicit absence, never default facts."""
    dispatcher = compose_fixture_dispatcher(
        _case("momentum-only", MOMENTUM_SUCCESS_FIXTURE_ID),
        clock_at=EXECUTION_TIME,
    )

    result = await dispatcher.dispatch(
        ToolCallRequest(
            call_id="missing-graham-facts",
            tool_name=ToolName.ANALYZE_GRAHAM_NUMBER.value,
            arguments={"ticker": GRAHAM_SECURITY_ID},
        )
    )

    assert result.success is True
    assert isinstance(result.result, GrahamNumberAnalysis)
    assert result.result.result.status is CalculationStatus.INPUT_UNAVAILABLE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments",
    [
        MomentumToolArguments(ticker="MOM"),
        GrahamNumberToolArguments(ticker=GRAHAM_SECURITY_ID),
        GrahamGrowthValueToolArguments(
            ticker=GRAHAM_SECURITY_ID,
            expected_growth=GOLDEN_EXPECTED_GROWTH,
            current_aaa_yield=4.15,
        ),
        FCFEarningsGrowthToolArguments(ticker="ACME"),
    ],
)
async def test_missing_tool_fixture_fails_before_dispatch(arguments: AnalysisToolArguments) -> None:
    """Every production tool requires its own selected fixture capability."""
    with pytest.raises(FixtureCompositionError, match="has no selected"):
        await dispatch_fixture_case(
            _case("missing-evidence", KNOWN_ETF_PROFILE_FIXTURE_ID),
            arguments,
            clock_at=EXECUTION_TIME,
        )


@pytest.mark.asyncio
async def test_etf_profile_does_not_apply_to_a_different_ticker() -> None:
    """Profile evidence is exact-ticker data rather than a global classification."""
    with pytest.raises(FixtureCompositionError, match="Graham financial-fact"):
        await dispatch_fixture_case(
            _case("profile-mismatch", KNOWN_ETF_PROFILE_FIXTURE_ID),
            GrahamNumberToolArguments(ticker=GRAHAM_SECURITY_ID),
            clock_at=EXECUTION_TIME,
        )


@pytest.mark.parametrize(
    "fixture_ids",
    [
        ("unknown_fixture",),
        (MOMENTUM_SUCCESS_FIXTURE_ID, MOMENTUM_BOUNDARY_FIXTURE_ID),
        (FCF_GROWTH_SUCCESS_FIXTURE_ID, FCF_GROWTH_NONMEANINGFUL_FIXTURE_ID),
        (FCF_GROWTH_SUCCESS_FIXTURE_ID, FCF_GROWTH_PERIOD_AS_OF_FIXTURE_ID),
    ],
)
def test_unsupported_or_conflicting_fixture_ids_fail_closed(fixture_ids: tuple[str, ...]) -> None:
    """Composition never guesses among unknown or mutually exclusive evidence."""
    with pytest.raises(FixtureCompositionError):
        compose_fixture_dependencies(_case("invalid-composition", *fixture_ids), clock_at=EXECUTION_TIME)


def test_composition_rejects_a_naive_clock() -> None:
    """Every resolver and handler receives an unambiguous injected clock."""
    with pytest.raises(FixtureCompositionError, match="timezone-aware"):
        compose_fixture_dependencies(
            _case("naive-clock", GRAHAM_FACTS_FIXTURE_ID),
            clock_at=GRAHAM_NOW.replace(tzinfo=None),
        )


class _UndeclaredArguments(AnalysisToolArguments):
    """Arguments of a strategy that no descriptor declares."""


@pytest.mark.asyncio
async def test_arguments_of_an_undeclared_strategy_fail_closed_before_dispatch() -> None:
    """An arguments model no descriptor declares raises the typed error, naming the model."""
    with pytest.raises(UndeclaredStrategyError, match="_UndeclaredArguments"):
        await dispatch_fixture_case(
            _case("undeclared-arguments", MOMENTUM_SUCCESS_FIXTURE_ID),
            _UndeclaredArguments(ticker="MOM"),
            clock_at=EXECUTION_TIME,
        )


def test_a_declared_tool_without_a_fixture_composition_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every declared tool must be paired with the function that builds its dependencies."""
    without_fcf = {
        tool: build
        for tool, build in composition._COMPOSERS_BY_TOOL.items()
        if tool is not ToolName.ANALYZE_FCF_EARNINGS_GROWTH
    }
    monkeypatch.setattr(composition, "_COMPOSERS_BY_TOOL", without_fcf)
    with pytest.raises(UndeclaredStrategyError, match="fixture composition for tool .*ANALYZE_FCF_EARNINGS_GROWTH"):
        compose_fixture_dependencies(_case("unpaired", MOMENTUM_SUCCESS_FIXTURE_ID), clock_at=EXECUTION_TIME)


def test_each_strategy_receives_its_own_dependency_class_and_graham_shares_providers() -> None:
    """Fixture composition builds one dependency class per tool; both Graham resolvers share one provider."""
    fixtures = compose_fixture_dependencies(
        _case("shared", GRAHAM_FACTS_FIXTURE_ID, MOMENTUM_SUCCESS_FIXTURE_ID), clock_at=EXECUTION_TIME
    )
    assert {tool: type(value).__name__ for tool, value in fixtures.dependencies.items()} == {
        ToolName.ANALYZE_MOMENTUM: "MomentumToolDependencies",
        ToolName.ANALYZE_GRAHAM_NUMBER: "GrahamNumberToolDependencies",
        ToolName.ANALYZE_GRAHAM_GROWTH_VALUE: "GrahamGrowthToolDependencies",
        ToolName.ANALYZE_FCF_EARNINGS_GROWTH: "FCFEarningsGrowthToolDependencies",
    }
    assert fixtures.runtime.validated_clock_value() == EXECUTION_TIME
    assert fixtures.runtime.profile_resolver is None
