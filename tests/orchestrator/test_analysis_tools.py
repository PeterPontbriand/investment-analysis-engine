"""Deterministic coverage for production analysis-tool registration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from typing import cast
from unittest.mock import MagicMock

import pandas as pd
import pytest

from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.strategy_errors import UndeclaredStrategyError
from investment_analysis_engine.data.instrument_profile import InstrumentKind, InstrumentProfile
from investment_analysis_engine.data.market_data import HistoricalMarketData
from investment_analysis_engine.evaluation.catalog import build_deterministic_requests
from investment_analysis_engine.evaluation.composition import compose_fixture_dependencies
from investment_analysis_engine.evaluation.fixtures.graham import (
    SECURITY_ID as GRAHAM_SECURITY_ID,
)
from investment_analysis_engine.evaluation.fixtures.instrument_profiles import fixture_instrument_profile
from investment_analysis_engine.evaluation.fixtures.market_data import (
    GOLDEN_MOMENTUM_SETTINGS,
    FixtureMarketDataProvider,
)
from investment_analysis_engine.evaluation.models import Case
from investment_analysis_engine.orchestrator.analysis_tools import register_analysis_tools
from investment_analysis_engine.orchestrator.dispatcher import AsyncToolDispatcher
from investment_analysis_engine.orchestrator.tool_names import ToolName
from investment_analysis_engine.orchestrator.tool_runtime import AnalysisToolHandler, ToolRuntime
from investment_analysis_engine.orchestrator.types import ToolCallRequest
from investment_analysis_engine.strategies.fcf_growth.models import FCFEarningsGrowthResult
from investment_analysis_engine.strategies.fcf_growth.tool import FCFEarningsGrowthToolDependencies
from investment_analysis_engine.strategies.graham_growth.service import GrahamGrowthAnalysis
from investment_analysis_engine.strategies.graham_growth.tool import GrahamGrowthToolDependencies
from investment_analysis_engine.strategies.graham_number.service import GrahamNumberAnalysis
from investment_analysis_engine.strategies.graham_number.tool import GrahamNumberToolDependencies
from investment_analysis_engine.strategies.momentum.analyzer import MomentumAnalyzer, MomentumConfig, MomentumRun
from investment_analysis_engine.strategies.momentum.settings import MomentumSettings
from investment_analysis_engine.strategies.momentum.tool import MomentumToolDependencies, MomentumToolHandler
from investment_analysis_engine.strategy_wiring import STRATEGIES, StrategyDescriptor, bind_handlers

EXECUTION_TIME = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
ANALYZE_MOMENTUM_TOOL = ToolName.ANALYZE_MOMENTUM.value
ANALYZE_GRAHAM_NUMBER_TOOL = ToolName.ANALYZE_GRAHAM_NUMBER.value
ANALYZE_GRAHAM_GROWTH_VALUE_TOOL = ToolName.ANALYZE_GRAHAM_GROWTH_VALUE.value
ANALYZE_FCF_EARNINGS_GROWTH_TOOL = ToolName.ANALYZE_FCF_EARNINGS_GROWTH.value


@dataclass(frozen=True)
class _Composition:
    """Each declared tool's dependency instance, composed by the evaluation tier, plus the shared runtime."""

    dependencies: Mapping[ToolName, object]
    runtime: ToolRuntime


def _register(dispatcher: AsyncToolDispatcher, composition: _Composition) -> None:
    """Bind every declared handler to the composition and register it on the dispatcher."""
    register_analysis_tools(dispatcher, bind_handlers(STRATEGIES, composition.dependencies, composition.runtime))


def _golden_case(descriptor: StrategyDescriptor) -> Case:
    """Return the first reviewed golden case whose arguments are the descriptor's own."""
    return next(
        request.case
        for request in build_deterministic_requests()
        if type(request.arguments) is descriptor.tool_arguments
    )


def _dependencies(*, clock: datetime = EXECUTION_TIME) -> _Composition:
    """Compose every declared strategy's dependencies from its evaluation-tier entry and its golden case.

    The fixtures are composed at ``EXECUTION_TIME``; ``clock`` is only the shared runtime's clock, so a test can give
    a handler an ambiguous one.
    """
    dependencies = {
        descriptor.tool: compose_fixture_dependencies(_golden_case(descriptor), clock_at=EXECUTION_TIME).dependencies[
            descriptor.tool
        ]
        for descriptor in STRATEGIES
    }
    return _Composition(dependencies=dependencies, runtime=ToolRuntime(clock=lambda: clock))


def _call(tool_name: str, arguments: dict[str, object]) -> ToolCallRequest:
    """Build a stable dispatcher request for one analysis tool."""
    return ToolCallRequest(call_id=f"call-{tool_name}", tool_name=tool_name, arguments=arguments)


@pytest.mark.asyncio
async def test_registered_handlers_execute_all_approved_strategies() -> None:
    """The production dispatcher reaches every native strategy result boundary."""
    dispatcher = AsyncToolDispatcher()
    _register(dispatcher, _dependencies())

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
    composition = _dependencies()
    dependencies = replace(
        composition,
        dependencies={
            **composition.dependencies,
            ToolName.ANALYZE_MOMENTUM: MomentumToolDependencies(
                analyzer=MomentumAnalyzer(market_data_provider=provider, start_date="2026-01-01"),
                settings=GOLDEN_MOMENTUM_SETTINGS,
            ),
        },
    )
    dispatcher = AsyncToolDispatcher()
    _register(dispatcher, dependencies)

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

    composition = _dependencies()
    dependencies = replace(composition, runtime=replace(composition.runtime, profile_resolver=resolve_profile))
    dispatcher = AsyncToolDispatcher()
    _register(dispatcher, dependencies)

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
    _register(dispatcher, _dependencies())

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
    assert tuple(descriptor.tool.value for descriptor in STRATEGIES[:4]) == (
        ANALYZE_MOMENTUM_TOOL,
        ANALYZE_GRAHAM_NUMBER_TOOL,
        ANALYZE_GRAHAM_GROWTH_VALUE_TOOL,
        ANALYZE_FCF_EARNINGS_GROWTH_TOOL,
    )
    for descriptor in STRATEGIES:
        assert descriptor.tool_arguments.model_json_schema()["additionalProperties"] is False

    dispatcher = AsyncToolDispatcher()
    dependencies = _dependencies()
    _register(dispatcher, dependencies)
    with pytest.raises(ValueError, match="already registered"):
        _register(dispatcher, dependencies)


@pytest.mark.asyncio
async def test_fcf_handler_rejects_a_naive_injected_clock() -> None:
    """A missing as_of cannot fall back to an ambiguous execution timestamp."""
    dispatcher = AsyncToolDispatcher()
    _register(dispatcher, _dependencies(clock=datetime(2026, 3, 1, 12, 0)))

    result = await dispatcher.dispatch(_call(ANALYZE_FCF_EARNINGS_GROWTH_TOOL, {"ticker": "ACME"}))

    assert result.success is False
    assert result.error_message == "Analysis tool clock must return a timezone-aware datetime."


def test_registration_requires_a_handler_for_every_tool_and_no_other() -> None:
    """Registration checks the injected mapping against ``ToolName`` in both directions."""
    composition = _dependencies()
    handlers: dict[ToolName, AnalysisToolHandler[object]] = dict(
        bind_handlers(STRATEGIES, composition.dependencies, composition.runtime)
    )
    dispatcher = AsyncToolDispatcher()

    without_fcf: dict[ToolName, AnalysisToolHandler[object]] = {
        tool: handler for tool, handler in handlers.items() if tool is not ToolName.ANALYZE_FCF_EARNINGS_GROWTH
    }
    with pytest.raises(UndeclaredStrategyError, match="analyze_fcf_earnings_growth"):
        register_analysis_tools(dispatcher, without_fcf)

    with_unknown = cast(
        "Mapping[ToolName, AnalysisToolHandler[object]]",
        {**handlers, "analyze_unknown": handlers[ToolName.ANALYZE_MOMENTUM]},
    )
    with pytest.raises(UndeclaredStrategyError, match="analyze_unknown"):
        register_analysis_tools(dispatcher, with_unknown)

    assert not dispatcher._handlers, "a rejected mapping must leave the dispatcher empty"


def test_dependency_classes_reject_blank_provider_ids() -> None:
    """Provider selections are required before any tool is registered."""
    composition = _dependencies()
    number = composition.dependencies[ToolName.ANALYZE_GRAHAM_NUMBER]
    growth = composition.dependencies[ToolName.ANALYZE_GRAHAM_GROWTH_VALUE]
    fcf = composition.dependencies[ToolName.ANALYZE_FCF_EARNINGS_GROWTH]
    assert isinstance(number, GrahamNumberToolDependencies)
    assert isinstance(growth, GrahamGrowthToolDependencies)
    assert isinstance(fcf, FCFEarningsGrowthToolDependencies)
    with pytest.raises(ValueError, match="provider IDs must be non-empty"):
        replace(number, security_provider_id=" ")
    with pytest.raises(ValueError, match="provider IDs must be non-empty"):
        replace(number, quote_provider_id="")
    with pytest.raises(ValueError, match="provider IDs must be non-empty"):
        replace(growth, security_provider_id="")
    with pytest.raises(ValueError, match="provider IDs must be non-empty"):
        replace(growth, quote_provider_id=" ")
    with pytest.raises(ValueError, match="provider IDs must be non-empty"):
        replace(fcf, provider_id="  ")


_CONFIGURED = MomentumSettings(short_window=4, long_window=9, rsi_period=6, history_start_date=date(2026, 1, 1))


def _momentum_handler() -> tuple[MomentumToolHandler, MagicMock]:
    """Bind a Momentum handler to a recording analyzer and the configured settings above."""
    analyzer = MagicMock(spec=MomentumAnalyzer)
    handler = MomentumToolHandler(
        MomentumToolDependencies(analyzer=analyzer, settings=_CONFIGURED),
        ToolRuntime(clock=lambda: EXECUTION_TIME),
    )
    return handler, analyzer


def test_momentum_tool_fills_every_omitted_argument_from_its_settings() -> None:
    handler, analyzer = _momentum_handler()

    handler(ticker="MOM")

    config = analyzer.run_analysis.call_args.kwargs["config"]
    assert config == MomentumConfig(short_window=4, long_window=9, rsi_period=6)


def test_momentum_tool_explicit_arguments_win_over_its_settings() -> None:
    handler, analyzer = _momentum_handler()

    handler(ticker="MOM", short_window=2, rsi_period=3)

    config = analyzer.run_analysis.call_args.kwargs["config"]
    assert config == MomentumConfig(short_window=2, long_window=9, rsi_period=3)


def test_momentum_tool_validates_a_given_window_against_the_configured_other_one() -> None:
    handler, analyzer = _momentum_handler()

    with pytest.raises(ValueError, match="must be smaller than Long window"):
        handler(ticker="MOM", short_window=9)
    analyzer.run_analysis.assert_not_called()
