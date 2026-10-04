"""Deterministic fixture composition for production analysis-tool dispatch."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from types import MappingProxyType
from typing import Final

from src.config import settings
from src.core.constants import ConfigKeys
from src.core.strategy_errors import require
from src.data.financial.cache import InMemoryResolvedInputCache
from src.data.financial.facts import FinancialFactRequest, FinancialFactsProvider, ProviderFact
from src.data.instrument_profile import InstrumentProfile
from src.data.sec_edgar import SEC_PROVIDER_ID
from src.data.sec_edgar.financial_facts import SecEdgarFinancialFactsAdapter
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
from src.evaluation.models import Case
from src.orchestrator.analysis_tool_arguments import AnalysisToolArguments
from src.orchestrator.analysis_tools import register_analysis_tools
from src.orchestrator.dispatcher import AsyncToolDispatcher
from src.orchestrator.tool_names import ToolName
from src.orchestrator.tool_runtime import ToolRuntime
from src.orchestrator.types import ToolCallRequest, ToolCallResult
from src.strategies.fcf_growth.analyzer import FCFEarningsGrowthAnalyzer
from src.strategies.fcf_growth.input_resolver import ProductionAnnualGrowthSeriesResolver
from src.strategies.fcf_growth.tool import FCFEarningsGrowthToolDependencies
from src.strategies.graham_growth.analyzer import GrahamGrowthAnalyzer
from src.strategies.graham_growth.calculation import GrahamGrowthCalculationPolicy, GrahamGrowthInputResolver
from src.strategies.graham_growth.tool import GrahamGrowthToolDependencies
from src.strategies.graham_number.analyzer import GrahamNumberAnalyzer
from src.strategies.graham_number.calculation import GrahamNumberInputResolver
from src.strategies.graham_number.tool import GrahamNumberToolDependencies
from src.strategies.momentum.analyzer import MomentumAnalyzer
from src.strategies.momentum.tool import MomentumToolDependencies
from src.strategy_wiring import STRATEGIES, bind_handlers, tool_for_arguments

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


class FixtureCompositionError(ValueError):
    """Raised when a case cannot be composed from approved fixture evidence."""


class _UnavailableFinancialFactsProvider:
    """Return explicit absence when a case did not select Graham facts."""

    def fetch_facts(
        self,
        request: FinancialFactRequest,
        *,
        effective_as_of: datetime,  # noqa: ARG002
    ) -> tuple[ProviderFact, ...]:
        """Return no facts for every request without consulting another provider."""
        del request
        return ()


@dataclass(frozen=True)
class FixtureDependencies:
    """Fixture-backed dependency instances, one per declared tool, and the shared runtime."""

    dependencies: Mapping[ToolName, object]
    runtime: ToolRuntime


@dataclass(frozen=True)
class _FixtureContext:
    """Case-level fixture selections and the providers several strategies share, built once per case."""

    fixture_ids: frozenset[str]
    clock_at: datetime
    momentum_fixture_id: str | None
    fcf_fixture_id: str | None
    sec_fpi_provider: SecEdgarFinancialFactsAdapter | None
    graham_provider: FinancialFactsProvider
    graham_cache: InMemoryResolvedInputCache | None

    @property
    def graham_provider_id(self) -> str:
        """Return the provider identity both Graham strategies are configured with."""
        return SEC_PROVIDER_ID if self.sec_fpi_provider is not None else GRAHAM_PROVIDER_ID


def compose_fixture_dependencies(case: Case, *, clock_at: datetime) -> FixtureDependencies:
    """Build every declared strategy's tool dependencies from a supplied case's fixtures.

    Args:
        case: Typed case containing only explicitly selected fixture identifiers.
        clock_at: Fixed timezone-aware execution time for every clocked resolver.

    Returns:
        One fixture-backed dependency instance per declared tool, with the shared runtime.

    Raises:
        FixtureCompositionError: If identifiers conflict, are unsupported, or the
            supplied clock is ambiguous.
        UndeclaredStrategyError: If a declared tool has no fixture composition below.
    """
    context = _fixture_context(case, clock_at=clock_at)
    dependencies = {
        descriptor.tool: require(_COMPOSERS_BY_TOOL, descriptor.tool, what="fixture composition for tool")(context)
        for descriptor in STRATEGIES
    }
    runtime = ToolRuntime(
        clock=lambda: clock_at,
        profile_resolver=_profile_resolver(context.fixture_ids, clock_at=clock_at),
    )
    return FixtureDependencies(dependencies=MappingProxyType(dependencies), runtime=runtime)


def _fixture_context(case: Case, *, clock_at: datetime) -> _FixtureContext:
    """Validate the case's fixture selections and build the providers shared across strategies."""
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

    sec_fpi_provider = (
        fixture_sec_fpi_adapter(sec_fpi_fixture_id, clock_at=clock_at) if sec_fpi_fixture_id is not None else None
    )
    graham_provider: FinancialFactsProvider = (
        sec_fpi_provider
        if sec_fpi_provider is not None
        else FixtureFinancialFactsProvider(quote_retrieved_at=clock_at)
        if GRAHAM_FACTS_FIXTURE_ID in fixture_ids
        else _UnavailableFinancialFactsProvider()
    )
    graham_cache = precedence_bvps_cache() if GRAHAM_PRECEDENCE_CACHE_FIXTURE_ID in fixture_ids else None
    return _FixtureContext(
        fixture_ids=fixture_ids,
        clock_at=clock_at,
        momentum_fixture_id=momentum_fixture_id,
        fcf_fixture_id=fcf_fixture_id,
        sec_fpi_provider=sec_fpi_provider,
        graham_provider=graham_provider,
        graham_cache=graham_cache,
    )


def _compose_momentum(context: _FixtureContext) -> MomentumToolDependencies:
    """Build Momentum's dependencies from the selected price fixture."""
    momentum_frame = (
        momentum_success_frame()
        if context.momentum_fixture_id == MOMENTUM_SUCCESS_FIXTURE_ID
        else momentum_boundary_frame()
        if context.momentum_fixture_id == MOMENTUM_BOUNDARY_FIXTURE_ID
        else momentum_boundary_frame().iloc[0:0].copy()
    )
    return MomentumToolDependencies(
        analyzer=MomentumAnalyzer(
            market_data_provider=FixtureMarketDataProvider(momentum_frame),
            start_date=str(settings.get_analysis_settings()[ConfigKeys.DEFAULT_SECTION][ConfigKeys.START_DATE]),
        )
    )


def _compose_graham_number(context: _FixtureContext) -> GrahamNumberToolDependencies:
    """Build Graham Number's dependencies from the selected Graham facts."""
    clock_at = context.clock_at

    def graham_clock() -> datetime:
        return clock_at

    resolver = GrahamNumberInputResolver(
        provider=context.graham_provider, cache=context.graham_cache, clock=graham_clock
    )
    return GrahamNumberToolDependencies(
        analyzer=GrahamNumberAnalyzer(resolver),
        security_provider_id=context.graham_provider_id,
        quote_provider_id=context.graham_provider_id,
    )


def _compose_graham_growth(context: _FixtureContext) -> GrahamGrowthToolDependencies:
    """Build Graham growth-value's dependencies from the selected Graham facts."""
    clock_at = context.clock_at

    def graham_clock() -> datetime:
        return clock_at

    resolver = GrahamGrowthInputResolver(
        provider=context.graham_provider, cache=context.graham_cache, clock=graham_clock
    )
    return GrahamGrowthToolDependencies(
        analyzer=GrahamGrowthAnalyzer(
            resolver,
            policy=GrahamGrowthCalculationPolicy(
                base_pe=GOLDEN_GROWTH_BASE_PE,
                growth_multiplier=GOLDEN_GROWTH_MULTIPLIER,
                baseline_aaa_yield=GOLDEN_BASELINE_AAA_YIELD,
            ),
        ),
        security_provider_id=context.graham_provider_id,
        quote_provider_id=context.graham_provider_id,
    )


def _compose_fcf_growth(context: _FixtureContext) -> FCFEarningsGrowthToolDependencies:
    """Build FCF & Earnings Growth's dependencies from the selected annual facts."""
    clock_at = context.clock_at
    annual_facts = _annual_facts(context.fcf_fixture_id)
    annual_provider = context.sec_fpi_provider or FixtureAnnualFinancialFactsProvider(
        tuple(replace(fact, provider_id=SEC_PROVIDER_ID) for fact in annual_facts)
    )
    return FCFEarningsGrowthToolDependencies(
        analyzer=FCFEarningsGrowthAnalyzer(
            ProductionAnnualGrowthSeriesResolver(annual_provider, clock=lambda: clock_at)
        ),
        provider_id=SEC_PROVIDER_ID,
    )


# Each tool is paired with the function that builds its dependencies; a declared tool with no pair here
# fails closed in ``compose_fixture_dependencies``.
_COMPOSERS_BY_TOOL: Final[Mapping[ToolName, Callable[[_FixtureContext], object]]] = MappingProxyType(
    {
        ToolName.ANALYZE_MOMENTUM: _compose_momentum,
        ToolName.ANALYZE_GRAHAM_NUMBER: _compose_graham_number,
        ToolName.ANALYZE_GRAHAM_GROWTH_VALUE: _compose_graham_growth,
        ToolName.ANALYZE_FCF_EARNINGS_GROWTH: _compose_fcf_growth,
    }
)


def compose_fixture_dispatcher(case: Case, *, clock_at: datetime) -> AsyncToolDispatcher:
    """Register every declared production handler with fixture-backed dependencies."""
    fixtures = compose_fixture_dependencies(case, clock_at=clock_at)
    dispatcher = AsyncToolDispatcher()
    register_analysis_tools(dispatcher, bind_handlers(STRATEGIES, fixtures.dependencies, fixtures.runtime))
    return dispatcher


async def dispatch_fixture_case(
    case: Case,
    arguments: AnalysisToolArguments,
    *,
    clock_at: datetime,
) -> ToolCallResult:
    """Execute one typed production-tool call for a supplied case without an LLM."""
    tool_name = tool_for_arguments(arguments)
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
