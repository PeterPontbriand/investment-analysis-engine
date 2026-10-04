"""Deterministic coverage for production analysis-tool registration."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pandas as pd
import pytest

from src.core.analysis_status import CalculationStatus
from src.data.financial.production import ProductionFinancialFactsProvider
from src.data.instrument_profile import InstrumentKind, InstrumentProfile
from src.data.market_data import HistoricalMarketData
from src.data.sec_edgar import SEC_PROVIDER_ID
from src.evaluation.fixtures.fcf_earnings_growth import (
    FixtureAnnualFinancialFactsProvider,
    annual_series,
)
from src.evaluation.fixtures.graham import (
    NOW as GRAHAM_NOW,
)
from src.evaluation.fixtures.graham import (
    PROVIDER_ID as GRAHAM_PROVIDER_ID,
)
from src.evaluation.fixtures.graham import (
    SECURITY_ID as GRAHAM_SECURITY_ID,
)
from src.evaluation.fixtures.graham import (
    FixtureFinancialFactsProvider,
)
from src.evaluation.fixtures.instrument_profiles import fixture_instrument_profile
from src.evaluation.fixtures.market_data import FixtureMarketDataProvider
from src.orchestrator.analysis_tools import (
    ANALYSIS_TOOL_ARGUMENT_MODELS,
    ANALYZE_FCF_EARNINGS_GROWTH_TOOL,
    ANALYZE_GRAHAM_GROWTH_VALUE_TOOL,
    ANALYZE_GRAHAM_NUMBER_TOOL,
    ANALYZE_MOMENTUM_TOOL,
    AnalysisToolDependencies,
    register_analysis_tools,
)
from src.orchestrator.dispatcher import AsyncToolDispatcher
from src.orchestrator.types import ToolCallRequest
from src.strategies.fcf_growth.analyzer import FCFEarningsGrowthAnalyzer
from src.strategies.fcf_growth.input_resolver import ProductionAnnualGrowthSeriesResolver
from src.strategies.fcf_growth.models import FCFEarningsGrowthResult
from src.strategies.graham_growth.analyzer import GrahamGrowthAnalyzer
from src.strategies.graham_growth.calculation import GrahamGrowthCalculationPolicy, GrahamGrowthInputResolver
from src.strategies.graham_growth.service import GrahamGrowthAnalysis
from src.strategies.graham_number.analyzer import GrahamNumberAnalyzer
from src.strategies.graham_number.calculation import GrahamNumberInputResolver
from src.strategies.graham_number.service import GrahamNumberAnalysis
from src.strategies.momentum.analyzer import MomentumAnalyzer, MomentumRun

EXECUTION_TIME = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def _dependencies(*, clock: datetime = EXECUTION_TIME) -> AnalysisToolDependencies:
    """Compose production handlers around deterministic fixture providers."""
    momentum_frame = pd.DataFrame(
        {"Close": [10.0, 10.5, 11.0, 11.8, 12.4, 13.0]},
        index=pd.date_range("2026-01-01", periods=6, tz=UTC),
    )
    momentum = MomentumAnalyzer(
        market_data_provider=FixtureMarketDataProvider(momentum_frame),
        start_date="2026-01-01",
    )
    graham_provider = FixtureFinancialFactsProvider()

    def graham_clock() -> datetime:
        return GRAHAM_NOW

    graham_number_analyzer = GrahamNumberAnalyzer(
        GrahamNumberInputResolver(provider=graham_provider, clock=graham_clock)
    )
    graham_growth_analyzer = GrahamGrowthAnalyzer(
        GrahamGrowthInputResolver(provider=graham_provider, clock=graham_clock),
        policy=GrahamGrowthCalculationPolicy(
            base_pe=8.5,
            growth_multiplier=2.0,
            baseline_aaa_yield=4.4,
        ),
    )

    annual_facts = tuple(replace(fact, provider_id=SEC_PROVIDER_ID) for fact in annual_series(range(2020, 2026)))
    annual_provider = ProductionFinancialFactsProvider(sec_edgar=FixtureAnnualFinancialFactsProvider(annual_facts))
    fcf = FCFEarningsGrowthAnalyzer(ProductionAnnualGrowthSeriesResolver(annual_provider, clock=lambda: clock))
    return AnalysisToolDependencies(
        momentum_analyzer=momentum,
        graham_number_analyzer=graham_number_analyzer,
        graham_growth_analyzer=graham_growth_analyzer,
        graham_security_provider_id=GRAHAM_PROVIDER_ID,
        graham_quote_provider_id=GRAHAM_PROVIDER_ID,
        fcf_analyzer=fcf,
        fcf_provider_id=SEC_PROVIDER_ID,
        clock=lambda: clock,
    )


def _call(tool_name: str, arguments: dict[str, object]) -> ToolCallRequest:
    """Build a stable dispatcher request for one analysis tool."""
    return ToolCallRequest(call_id=f"call-{tool_name}", tool_name=tool_name, arguments=arguments)


@pytest.mark.asyncio
async def test_registered_handlers_execute_all_approved_strategies() -> None:
    """The production dispatcher reaches every native strategy result boundary."""
    dispatcher = AsyncToolDispatcher()
    register_analysis_tools(dispatcher, _dependencies())

    momentum = await dispatcher.dispatch(
        _call(
            ANALYZE_MOMENTUM_TOOL,
            {
                "ticker": "mom",
                "short_window": 2,
                "long_window": 3,
                "rsi_period": 2,
                "as_of": "2026-01-06T23:59:00Z",
            },
        )
    )
    number = await dispatcher.dispatch(_call(ANALYZE_GRAHAM_NUMBER_TOOL, {"ticker": GRAHAM_SECURITY_ID}))
    growth = await dispatcher.dispatch(
        _call(
            ANALYZE_GRAHAM_GROWTH_VALUE_TOOL,
            {
                "ticker": GRAHAM_SECURITY_ID,
                "expected_growth": 5.0,
                "current_aaa_yield": 4.15,
            },
        )
    )
    fcf = await dispatcher.dispatch(_call(ANALYZE_FCF_EARNINGS_GROWTH_TOOL, {"ticker": "acme"}))

    assert momentum.success is True
    assert isinstance(momentum.result, MomentumRun)
    assert momentum.result.metrics.ticker == "MOM"
    assert number.success is True
    assert isinstance(number.result, GrahamNumberAnalysis)
    assert number.result.result.status is CalculationStatus.OK
    assert growth.success is True
    assert isinstance(growth.result, GrahamGrowthAnalysis)
    assert growth.result.result.status is CalculationStatus.OK
    assert fcf.success is True
    assert isinstance(fcf.result, FCFEarningsGrowthResult)
    assert fcf.result.execution_status is CalculationStatus.OK
    assert fcf.result.ticker == "ACME"
    assert fcf.result.effective_as_of == EXECUTION_TIME


class _RecordingMarketDataProvider(FixtureMarketDataProvider):
    """Fixture provider that records each ``use_cache`` value it is asked for."""

    def __init__(self, frame: pd.DataFrame) -> None:
        super().__init__(frame)
        self.use_cache_calls: list[bool] = []

    def fetch_historical_data(
        self, ticker: str, start_date: str, end_date: str | None = None, *, use_cache: bool = True
    ) -> HistoricalMarketData:
        self.use_cache_calls.append(use_cache)
        return super().fetch_historical_data(ticker, start_date, end_date, use_cache=use_cache)


@pytest.mark.asyncio
@pytest.mark.parametrize(("arguments", "expected"), [({}, True), ({"use_cache": False}, False)])
async def test_momentum_tool_use_cache_argument_reaches_the_provider(
    arguments: dict[str, object], *, expected: bool
) -> None:
    """The tool's ``use_cache`` argument, defaulting to True, is the per-call cache switch."""
    frame = pd.DataFrame(
        {"Close": [10.0, 10.5, 11.0, 11.8, 12.4, 13.0]},
        index=pd.date_range("2026-01-01", periods=6, tz=UTC),
    )
    provider = _RecordingMarketDataProvider(frame)
    dependencies = replace(
        _dependencies(), momentum_analyzer=MomentumAnalyzer(market_data_provider=provider, start_date="2026-01-01")
    )
    dispatcher = AsyncToolDispatcher()
    register_analysis_tools(dispatcher, dependencies)

    result = await dispatcher.dispatch(
        _call(ANALYZE_MOMENTUM_TOOL, {"ticker": "MOM", "short_window": 2, "long_window": 3, **arguments})
    )

    assert result.success is True
    assert provider.use_cache_calls == [expected]


@pytest.mark.asyncio
async def test_registered_handlers_apply_known_etf_policy_without_changing_momentum() -> None:
    """One injected profile drives consistent native applicability across handlers."""
    profile_calls: list[str] = []

    def resolve_profile(ticker: str) -> InstrumentProfile:
        profile_calls.append(ticker)
        return fixture_instrument_profile(
            ticker,
            kind=InstrumentKind.ETF,
            provider_value="ETF",
            instrument_name="Franklin FTSE Switzerland ETF",
        )

    dependencies = replace(_dependencies(), profile_resolver=resolve_profile)
    dispatcher = AsyncToolDispatcher()
    register_analysis_tools(dispatcher, dependencies)

    momentum = await dispatcher.dispatch(
        _call(
            ANALYZE_MOMENTUM_TOOL,
            {"ticker": "FLSW", "short_window": 2, "long_window": 3, "rsi_period": 2},
        )
    )
    number = await dispatcher.dispatch(_call(ANALYZE_GRAHAM_NUMBER_TOOL, {"ticker": "FLSW"}))
    growth = await dispatcher.dispatch(
        _call(
            ANALYZE_GRAHAM_GROWTH_VALUE_TOOL,
            {"ticker": "FLSW", "expected_growth": 5.0, "current_aaa_yield": 4.4},
        )
    )
    fcf = await dispatcher.dispatch(_call(ANALYZE_FCF_EARNINGS_GROWTH_TOOL, {"ticker": "FLSW"}))

    assert momentum.success is True
    assert isinstance(momentum.result, MomentumRun)
    assert momentum.result.metrics.status.value == "BULLISH"
    assert momentum.result.instrument_profile is not None
    assert momentum.result.instrument_profile.ticker == "FLSW"
    assert number.success is True
    assert isinstance(number.result, GrahamNumberAnalysis)
    assert number.result.result.status is CalculationStatus.NOT_APPLICABLE
    assert growth.success is True
    assert isinstance(growth.result, GrahamGrowthAnalysis)
    assert growth.result.result.status is CalculationStatus.NOT_APPLICABLE
    assert fcf.success is True
    assert isinstance(fcf.result, FCFEarningsGrowthResult)
    assert fcf.result.execution_status is CalculationStatus.NOT_APPLICABLE
    assert profile_calls == ["FLSW", "FLSW", "FLSW", "FLSW"]


@pytest.mark.asyncio
async def test_handler_validation_fails_closed_before_analysis() -> None:
    """Naive timestamps and unknown arguments become structured dispatch failures."""
    dispatcher = AsyncToolDispatcher()
    register_analysis_tools(dispatcher, _dependencies())

    naive_time = await dispatcher.dispatch(
        _call(
            ANALYZE_MOMENTUM_TOOL,
            {
                "ticker": "MOM",
                "as_of": "2026-01-06T12:00:00",
            },
        )
    )
    unknown_argument = await dispatcher.dispatch(
        _call(
            ANALYZE_GRAHAM_NUMBER_TOOL,
            {"ticker": GRAHAM_SECURITY_ID, "invented": True},
        )
    )

    assert naive_time.success is False
    assert naive_time.error_message is not None
    assert "timezone-aware" in naive_time.error_message
    assert unknown_argument.success is False
    assert unknown_argument.error_message is not None
    assert "Extra inputs are not permitted" in unknown_argument.error_message


def test_registration_exposes_strict_argument_contracts_and_rejects_duplicates() -> None:
    """Stable names have discoverable schemas and cannot be silently replaced."""
    assert tuple(ANALYSIS_TOOL_ARGUMENT_MODELS) == (
        ANALYZE_MOMENTUM_TOOL,
        ANALYZE_GRAHAM_NUMBER_TOOL,
        ANALYZE_GRAHAM_GROWTH_VALUE_TOOL,
        ANALYZE_FCF_EARNINGS_GROWTH_TOOL,
    )
    for argument_model in ANALYSIS_TOOL_ARGUMENT_MODELS.values():
        assert argument_model.model_json_schema()["additionalProperties"] is False

    dispatcher = AsyncToolDispatcher()
    dependencies = _dependencies()
    register_analysis_tools(dispatcher, dependencies)
    with pytest.raises(ValueError, match="already registered"):
        register_analysis_tools(dispatcher, dependencies)


@pytest.mark.asyncio
async def test_fcf_handler_rejects_a_naive_injected_clock() -> None:
    """A missing as_of cannot fall back to an ambiguous execution timestamp."""
    dispatcher = AsyncToolDispatcher()
    register_analysis_tools(
        dispatcher,
        _dependencies(clock=datetime(2026, 3, 1, 12, 0)),
    )

    result = await dispatcher.dispatch(_call(ANALYZE_FCF_EARNINGS_GROWTH_TOOL, {"ticker": "ACME"}))

    assert result.success is False
    assert result.error_message == "Analysis tool clock must return a timezone-aware datetime."
