"""Deterministic fixture composition for production analysis-tool dispatch."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from typing import Final

from src.analysis.fcf_earnings_growth import FCFEarningsGrowthAnalyzer, ProductionAnnualGrowthSeriesResolver
from src.analysis.graham_value.input_resolver import GrahamInputResolver
from src.analysis.graham_value.service import GrahamGrowthCalculationPolicy
from src.analysis.momentum.momentum_analyzer import MomentumAnalyzer
from src.data.financial.facts import FinancialFactRequest, ProviderFact
from src.data.instrument_profile import InstrumentProfile
from src.data.sec_edgar import SEC_PROVIDER_ID
from src.evaluation.fixtures.fcf_earnings_growth import (
    FixtureAnnualFinancialFactsProvider,
    fcf_growth_nonmeaningful_facts,
    fcf_growth_period_as_of_facts,
    fcf_growth_success_facts,
)
from src.evaluation.fixtures.graham import (
    GOLDEN_BASELINE_AAA_YIELD,
    GOLDEN_GROWTH_BASE_PE,
    GOLDEN_GROWTH_MULTIPLIER,
    FixtureFinancialFactsProvider,
    precedence_bvps_cache,
)
from src.evaluation.fixtures.graham import (
    PROVIDER_ID as GRAHAM_PROVIDER_ID,
)
from src.evaluation.fixtures.instrument_profiles import GOLDEN_ETF_TICKER, fixture_known_etf_profile
from src.evaluation.fixtures.market_data import (
    FixtureDataClient,
    FixtureMarketDataProvider,
    momentum_boundary_frame,
    momentum_success_frame,
)
from src.evaluation.fixtures.sec_edgar_fpi import (
    SEC_FPI_FIXTURE_IDS,
    SEC_FPI_NVO_FIXTURE_ID,
    fixture_nvo_security_unit_profile,
    fixture_sec_fpi_adapter,
)
from src.evaluation.models import Case, ToolName
from src.orchestrator.analysis_tools import (
    AnalysisToolDependencies,
    FCFEarningsGrowthToolArguments,
    GrahamGrowthValueToolArguments,
    GrahamNumberToolArguments,
    MomentumToolArguments,
    register_analysis_tools,
)
from src.orchestrator.dispatcher import AsyncToolDispatcher
from src.orchestrator.types import ToolCallRequest, ToolCallResult

MOMENTUM_SUCCESS_FIXTURE_ID: Final = "momentum_success"
MOMENTUM_BOUNDARY_FIXTURE_ID: Final = "momentum_boundary"
GRAHAM_FACTS_FIXTURE_ID: Final = "graham_facts"
GRAHAM_PRECEDENCE_CACHE_FIXTURE_ID: Final = "graham_precedence_cache"
FCF_GROWTH_SUCCESS_FIXTURE_ID: Final = "fcf_growth_success"
FCF_GROWTH_NONMEANINGFUL_FIXTURE_ID: Final = "fcf_growth_nonmeaningful"
FCF_GROWTH_PERIOD_AS_OF_FIXTURE_ID: Final = "fcf_growth_period_as_of"
KNOWN_ETF_PROFILE_FIXTURE_ID: Final = "known_etf_profile"

SUPPORTED_FIXTURE_IDS: Final = frozenset(
    {
        MOMENTUM_SUCCESS_FIXTURE_ID,
        MOMENTUM_BOUNDARY_FIXTURE_ID,
        GRAHAM_FACTS_FIXTURE_ID,
        GRAHAM_PRECEDENCE_CACHE_FIXTURE_ID,
        FCF_GROWTH_SUCCESS_FIXTURE_ID,
        FCF_GROWTH_NONMEANINGFUL_FIXTURE_ID,
        FCF_GROWTH_PERIOD_AS_OF_FIXTURE_ID,
        KNOWN_ETF_PROFILE_FIXTURE_ID,
        *SEC_FPI_FIXTURE_IDS,
    }
)

_MOMENTUM_FIXTURE_IDS: Final = frozenset({MOMENTUM_SUCCESS_FIXTURE_ID, MOMENTUM_BOUNDARY_FIXTURE_ID})
_FCF_FIXTURE_IDS: Final = frozenset(
    {
        FCF_GROWTH_SUCCESS_FIXTURE_ID,
        FCF_GROWTH_NONMEANINGFUL_FIXTURE_ID,
        FCF_GROWTH_PERIOD_AS_OF_FIXTURE_ID,
    }
)

type AnalysisToolArguments = (
    MomentumToolArguments | GrahamNumberToolArguments | GrahamGrowthValueToolArguments | FCFEarningsGrowthToolArguments
)


class FixtureCompositionError(ValueError):
    """Raised when a case cannot be composed from approved fixture evidence."""


class _UnavailableFinancialFactsProvider:
    """Return explicit absence when a case did not select Graham facts."""

    def fetch_facts(self, request: FinancialFactRequest) -> tuple[ProviderFact, ...]:
        """Return no facts for every request without consulting another provider."""
        del request
        return ()


def compose_fixture_dependencies(case: Case, *, clock_at: datetime) -> AnalysisToolDependencies:
    """Build all production-handler dependencies from a supplied case's fixtures.

    Args:
        case: Typed case containing only explicitly selected fixture identifiers.
        clock_at: Fixed timezone-aware execution time for every clocked resolver.

    Returns:
        Fixture-backed dependencies suitable for ``register_analysis_tools``.

    Raises:
        FixtureCompositionError: If identifiers conflict, are unsupported, or the
            supplied clock is ambiguous.
    """
    _validate_clock(clock_at)
    fixture_ids = frozenset(case.fixture_ids)
    unknown_ids = fixture_ids - SUPPORTED_FIXTURE_IDS
    if unknown_ids:
        joined = ", ".join(sorted(unknown_ids))
        raise FixtureCompositionError(f"Unsupported fixture IDs: {joined}.")

    momentum_fixture_id = _selected_variant(
        fixture_ids,
        _MOMENTUM_FIXTURE_IDS,
        label="Momentum price",
    )
    fcf_fixture_id = _selected_variant(
        fixture_ids,
        _FCF_FIXTURE_IDS,
        label="FCF/Earnings Growth facts",
    )
    sec_fpi_fixture_id = _selected_variant(fixture_ids, SEC_FPI_FIXTURE_IDS, label="SEC FPI evidence")

    momentum_frame = (
        momentum_success_frame()
        if momentum_fixture_id == MOMENTUM_SUCCESS_FIXTURE_ID
        else momentum_boundary_frame()
        if momentum_fixture_id == MOMENTUM_BOUNDARY_FIXTURE_ID
        else momentum_boundary_frame().iloc[0:0].copy()
    )
    momentum_analyzer = MomentumAnalyzer(
        default_ticker="FIXTURE",
        data_client=FixtureDataClient(),
        market_data_provider=FixtureMarketDataProvider(momentum_frame),
    )

    sec_fpi_provider = (
        fixture_sec_fpi_adapter(sec_fpi_fixture_id, clock_at=clock_at) if sec_fpi_fixture_id is not None else None
    )
    graham_provider = (
        sec_fpi_provider
        if sec_fpi_provider is not None
        else FixtureFinancialFactsProvider()
        if GRAHAM_FACTS_FIXTURE_ID in fixture_ids
        else _UnavailableFinancialFactsProvider()
    )
    graham_cache = precedence_bvps_cache() if GRAHAM_PRECEDENCE_CACHE_FIXTURE_ID in fixture_ids else None
    graham_resolver = GrahamInputResolver(provider=graham_provider, cache=graham_cache, clock=lambda: clock_at)

    annual_facts = _annual_facts(fcf_fixture_id)
    annual_provider = sec_fpi_provider or FixtureAnnualFinancialFactsProvider(
        tuple(replace(fact, provider_id=SEC_PROVIDER_ID) for fact in annual_facts)
    )
    fcf_analyzer = FCFEarningsGrowthAnalyzer(
        ProductionAnnualGrowthSeriesResolver(annual_provider, clock=lambda: clock_at)
    )

    profile_resolver = _profile_resolver(fixture_ids, clock_at=clock_at)
    return AnalysisToolDependencies(
        momentum_analyzer=momentum_analyzer,
        graham_resolver=graham_resolver,
        graham_security_provider_id=SEC_PROVIDER_ID if sec_fpi_provider is not None else GRAHAM_PROVIDER_ID,
        graham_quote_provider_id=SEC_PROVIDER_ID if sec_fpi_provider is not None else GRAHAM_PROVIDER_ID,
        graham_growth_policy=GrahamGrowthCalculationPolicy(
            base_pe=GOLDEN_GROWTH_BASE_PE,
            growth_multiplier=GOLDEN_GROWTH_MULTIPLIER,
            baseline_aaa_yield=GOLDEN_BASELINE_AAA_YIELD,
        ),
        fcf_analyzer=fcf_analyzer,
        fcf_provider_id=SEC_PROVIDER_ID,
        clock=lambda: clock_at,
        profile_resolver=profile_resolver,
    )


def compose_fixture_dispatcher(case: Case, *, clock_at: datetime) -> AsyncToolDispatcher:
    """Register all four production handlers with fixture-backed dependencies."""
    dispatcher = AsyncToolDispatcher()
    register_analysis_tools(dispatcher, compose_fixture_dependencies(case, clock_at=clock_at))
    return dispatcher


async def dispatch_fixture_case(
    case: Case,
    arguments: AnalysisToolArguments,
    *,
    clock_at: datetime,
) -> ToolCallResult:
    """Execute one typed production-tool call for a supplied case without an LLM."""
    tool_name = _tool_name(arguments)
    _require_tool_evidence(case, tool_name=tool_name, ticker=arguments.ticker)
    dispatcher = compose_fixture_dispatcher(case, clock_at=clock_at)
    request = ToolCallRequest(
        call_id=f"golden:{case.case_id}:{tool_name.value}",
        tool_name=tool_name.value,
        arguments=arguments.model_dump(mode="python"),
    )
    return await dispatcher.dispatch(request)


def _selected_variant(
    fixture_ids: frozenset[str],
    candidates: frozenset[str],
    *,
    label: str,
) -> str | None:
    """Return one selected variant while rejecting ambiguous fixture evidence."""
    selected = fixture_ids & candidates
    if len(selected) > 1:
        joined = ", ".join(sorted(selected))
        raise FixtureCompositionError(f"Conflicting {label} fixture IDs: {joined}.")
    return next(iter(selected), None)


def _annual_facts(fixture_id: str | None) -> tuple[ProviderFact, ...]:
    """Return the selected annual fixture evidence or an explicitly empty set."""
    if fixture_id == FCF_GROWTH_SUCCESS_FIXTURE_ID:
        return fcf_growth_success_facts()
    if fixture_id == FCF_GROWTH_NONMEANINGFUL_FIXTURE_ID:
        return fcf_growth_nonmeaningful_facts()
    if fixture_id == FCF_GROWTH_PERIOD_AS_OF_FIXTURE_ID:
        return fcf_growth_period_as_of_facts()
    return ()


def _profile_resolver(fixture_ids: frozenset[str], *, clock_at: datetime) -> Callable[[str], InstrumentProfile] | None:
    """Build an exact-ticker profile resolver without any provider fallback."""
    profile = (
        fixture_known_etf_profile()
        if KNOWN_ETF_PROFILE_FIXTURE_ID in fixture_ids
        else fixture_nvo_security_unit_profile(resolved_at=clock_at)
        if SEC_FPI_NVO_FIXTURE_ID in fixture_ids
        else None
    )
    if profile is None:
        return None

    def resolve(ticker: str) -> InstrumentProfile:
        if ticker.strip().upper() != profile.ticker:
            raise FixtureCompositionError(
                f"Profile fixture for {profile.ticker!r} cannot satisfy ticker {ticker.strip().upper()!r}."
            )
        return profile

    return resolve


def _tool_name(arguments: AnalysisToolArguments) -> ToolName:
    """Map one strict production argument model to its existing tool name."""
    if isinstance(arguments, MomentumToolArguments):
        return ToolName.ANALYZE_MOMENTUM
    if isinstance(arguments, GrahamNumberToolArguments):
        return ToolName.ANALYZE_GRAHAM_NUMBER
    if isinstance(arguments, GrahamGrowthValueToolArguments):
        return ToolName.ANALYZE_GRAHAM_GROWTH_VALUE
    if isinstance(arguments, FCFEarningsGrowthToolArguments):
        return ToolName.ANALYZE_FCF_EARNINGS_GROWTH
    raise TypeError(f"Unsupported analysis-tool argument model: {type(arguments).__name__}.")


def _require_tool_evidence(case: Case, *, tool_name: ToolName, ticker: str) -> None:
    """Require the selected tool's fixture capability before registration."""
    fixture_ids = frozenset(case.fixture_ids)
    has_matching_etf_profile = (
        KNOWN_ETF_PROFILE_FIXTURE_ID in fixture_ids and ticker.strip().upper() == GOLDEN_ETF_TICKER
    )
    if tool_name is ToolName.ANALYZE_MOMENTUM:
        required = _MOMENTUM_FIXTURE_IDS
        label = "Momentum price"
    elif tool_name in (ToolName.ANALYZE_GRAHAM_NUMBER, ToolName.ANALYZE_GRAHAM_GROWTH_VALUE):
        if has_matching_etf_profile:
            return
        required = frozenset({GRAHAM_FACTS_FIXTURE_ID, *SEC_FPI_FIXTURE_IDS})
        label = "Graham financial-fact"
    else:
        if has_matching_etf_profile:
            return
        required = _FCF_FIXTURE_IDS | SEC_FPI_FIXTURE_IDS
        label = "FCF/Earnings Growth fact"
    if not fixture_ids & required:
        raise FixtureCompositionError(f"Case {case.case_id!r} has no selected {label} fixture.")


def _validate_clock(clock_at: datetime) -> None:
    """Reject an ambiguous deterministic execution clock."""
    if clock_at.tzinfo is None or clock_at.utcoffset() is None:
        raise FixtureCompositionError("Fixture composition clock must be timezone-aware.")
