"""Production tool handlers for the approved deterministic analysis strategies."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Final

from pydantic import BaseModel

from src.analysis.base_analyzer import AnalysisContext
from src.data.instrument_profile import InstrumentProfile
from src.orchestrator.dispatcher import AsyncToolDispatcher
from src.strategies.fcf_growth.analyzer import FCFEarningsGrowthAnalyzer
from src.strategies.fcf_growth.models import (
    FCFEarningsGrowthConfig,
    FCFEarningsGrowthPolicy,
    FCFEarningsGrowthResult,
)
from src.strategies.fcf_growth.tool import FCFEarningsGrowthToolArguments
from src.strategies.graham_growth.analyzer import GrahamGrowthAnalyzer
from src.strategies.graham_growth.config import GrahamGrowthConfig
from src.strategies.graham_growth.service import GrahamGrowthAnalysis
from src.strategies.graham_growth.tool import GrahamGrowthValueToolArguments
from src.strategies.graham_number.analyzer import GrahamNumberAnalyzer
from src.strategies.graham_number.config import GrahamNumberConfig
from src.strategies.graham_number.service import GrahamNumberAnalysis
from src.strategies.graham_number.tool import GrahamNumberToolArguments
from src.strategies.momentum.analyzer import (
    MomentumAnalyzer,
    MomentumConfig,
    MomentumRun,
)
from src.strategies.momentum.tool import MomentumToolArguments

ANALYZE_MOMENTUM_TOOL: Final = "analyze_momentum"
ANALYZE_GRAHAM_NUMBER_TOOL: Final = "analyze_graham_number"
ANALYZE_GRAHAM_GROWTH_VALUE_TOOL: Final = "analyze_graham_growth_value"
ANALYZE_FCF_EARNINGS_GROWTH_TOOL: Final = "analyze_fcf_earnings_growth"

ANALYSIS_TOOL_ARGUMENT_MODELS: Final[Mapping[str, type[BaseModel]]] = MappingProxyType(
    {
        ANALYZE_MOMENTUM_TOOL: MomentumToolArguments,
        ANALYZE_GRAHAM_NUMBER_TOOL: GrahamNumberToolArguments,
        ANALYZE_GRAHAM_GROWTH_VALUE_TOOL: GrahamGrowthValueToolArguments,
        ANALYZE_FCF_EARNINGS_GROWTH_TOOL: FCFEarningsGrowthToolArguments,
    }
)


@dataclass(frozen=True)
class AnalysisToolDependencies:
    """Injected production analysis dependencies and provider selections."""

    momentum_analyzer: MomentumAnalyzer
    graham_number_analyzer: GrahamNumberAnalyzer
    graham_growth_analyzer: GrahamGrowthAnalyzer
    graham_security_provider_id: str
    graham_quote_provider_id: str
    fcf_analyzer: FCFEarningsGrowthAnalyzer
    fcf_provider_id: str
    clock: Callable[[], datetime]
    profile_resolver: Callable[[str], InstrumentProfile] | None = None

    def __post_init__(self) -> None:
        """Reject missing provider selections before any tool is registered."""
        provider_ids = (
            self.graham_security_provider_id,
            self.graham_quote_provider_id,
            self.fcf_provider_id,
        )
        if any(not provider_id.strip() for provider_id in provider_ids):
            raise ValueError("Analysis tool provider IDs must be non-empty.")


class AnalysisToolHandlers:
    """Concrete handlers that preserve each strategy's native result contract."""

    def __init__(self, dependencies: AnalysisToolDependencies) -> None:
        """Retain explicitly injected analyzers, resolvers, and policies."""
        self._dependencies = dependencies

    def analyze_momentum(self, **raw_arguments: object) -> MomentumRun:
        """Validate, resolve, and calculate one Momentum run."""
        arguments = MomentumToolArguments.model_validate(raw_arguments)
        config = MomentumConfig(
            short_window=arguments.short_window,
            long_window=arguments.long_window,
            rsi_period=arguments.rsi_period,
        )
        executed_at = self._validated_clock_value()
        profile = self._resolve_profile(arguments.ticker)
        context = AnalysisContext(
            as_of=arguments.as_of,
            executed_at=executed_at,
            use_cache=arguments.use_cache,
            instrument_profile=profile,
        )
        return self._dependencies.momentum_analyzer.run_analysis(
            ticker=arguments.ticker, config=config, context=context
        )

    def analyze_graham_number(self, **raw_arguments: object) -> GrahamNumberAnalysis:
        """Validate, resolve, and calculate one Graham Number run."""
        arguments = GrahamNumberToolArguments.model_validate(raw_arguments)
        profile = self._resolve_profile(arguments.ticker)
        config = GrahamNumberConfig(
            security_provider_id=self._dependencies.graham_security_provider_id,
            quote_provider_id=self._dependencies.graham_quote_provider_id,
            eps_basis=arguments.eps_basis,
            eps_override=arguments.eps_override,
            bvps_override=arguments.bvps_override,
            quote_override=arguments.current_price_override,
        )
        executed_at = self._validated_clock_value()
        context = AnalysisContext(
            as_of=arguments.as_of,
            executed_at=executed_at,
            use_cache=arguments.use_cache,
            instrument_profile=profile,
        )
        return self._dependencies.graham_number_analyzer.run_analysis(
            ticker=arguments.ticker, config=config, context=context
        )

    def analyze_graham_growth_value(self, **raw_arguments: object) -> GrahamGrowthAnalysis:
        """Validate, resolve, and calculate one Graham growth-value run."""
        arguments = GrahamGrowthValueToolArguments.model_validate(raw_arguments)
        profile = self._resolve_profile(arguments.ticker)
        config = GrahamGrowthConfig(
            security_provider_id=self._dependencies.graham_security_provider_id,
            quote_provider_id=self._dependencies.graham_quote_provider_id,
            eps_basis=arguments.eps_basis,
            eps_override=arguments.eps_override,
            expected_growth=arguments.expected_growth,
            aaa_yield_override=arguments.current_aaa_yield,
            quote_override=arguments.current_price_override,
        )
        executed_at = self._validated_clock_value()
        context = AnalysisContext(
            as_of=arguments.as_of,
            executed_at=executed_at,
            use_cache=arguments.use_cache,
            instrument_profile=profile,
        )
        return self._dependencies.graham_growth_analyzer.run_analysis(
            ticker=arguments.ticker, config=config, context=context
        )

    def analyze_fcf_earnings_growth(self, **raw_arguments: object) -> FCFEarningsGrowthResult:
        """Validate, resolve, and calculate one FCF & Earnings Growth run."""
        arguments = FCFEarningsGrowthToolArguments.model_validate(raw_arguments)
        policy = FCFEarningsGrowthPolicy(
            historical_horizon=arguments.historical_horizon,
            classification_basis=arguments.classification_basis,
            forward_policy=arguments.forward_policy,
            include_fcf_yield=arguments.include_fcf_yield,
        )
        config = FCFEarningsGrowthConfig(
            policy=policy,
            currency=arguments.currency,
            provider_id=self._dependencies.fcf_provider_id,
        )
        executed_at = self._validated_clock_value()
        profile = self._resolve_profile(arguments.ticker)
        context = AnalysisContext(
            as_of=arguments.as_of,
            executed_at=executed_at,
            use_cache=arguments.use_cache,
            instrument_profile=profile,
        )
        return self._dependencies.fcf_analyzer.run_analysis(ticker=arguments.ticker, config=config, context=context)

    def _resolve_profile(self, ticker: str) -> InstrumentProfile | None:
        """Resolve optional injected profile evidence once for one tool invocation."""
        resolver = self._dependencies.profile_resolver
        return resolver(ticker) if resolver is not None else None

    def _validated_clock_value(self) -> datetime:
        """Return an unambiguous injected execution timestamp."""
        value = self._dependencies.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Analysis tool clock must return a timezone-aware datetime.")
        return value


def register_analysis_tools(
    dispatcher: AsyncToolDispatcher,
    dependencies: AnalysisToolDependencies,
) -> AnalysisToolHandlers:
    """Register all approved analysis handlers on an existing dispatcher."""
    handlers = AnalysisToolHandlers(dependencies)
    dispatcher.register_tool(ANALYZE_MOMENTUM_TOOL, handlers.analyze_momentum)
    dispatcher.register_tool(ANALYZE_GRAHAM_NUMBER_TOOL, handlers.analyze_graham_number)
    dispatcher.register_tool(ANALYZE_GRAHAM_GROWTH_VALUE_TOOL, handlers.analyze_graham_growth_value)
    dispatcher.register_tool(ANALYZE_FCF_EARNINGS_GROWTH_TOOL, handlers.analyze_fcf_earnings_growth)
    return handlers
