"""Production tool handlers for the approved deterministic analysis strategies."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from types import MappingProxyType
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.analysis.fcf_earnings_growth import (
    FCFClassificationBasis,
    FCFEarningsGrowthAnalyzer,
    FCFEarningsGrowthPolicy,
    FCFEarningsGrowthResult,
    ForwardPolicy,
    HistoricalHorizon,
)
from src.analysis.graham_value.input_resolver import GrahamInputResolver
from src.analysis.graham_value.service import (
    GrahamGrowthAnalysis,
    GrahamGrowthCalculationPolicy,
    GrahamNumberAnalysis,
    run_graham_growth_analysis,
    run_graham_number_analysis,
)
from src.analysis.momentum.momentum_analyzer import MomentumAnalyzer, MomentumConfig, MomentumPolicy, MomentumRun
from src.data.instrument_profile import InstrumentProfile
from src.orchestrator.dispatcher import AsyncToolDispatcher

ANALYZE_MOMENTUM_TOOL: Final = "analyze_momentum"
ANALYZE_GRAHAM_NUMBER_TOOL: Final = "analyze_graham_number"
ANALYZE_GRAHAM_GROWTH_VALUE_TOOL: Final = "analyze_graham_growth_value"
ANALYZE_FCF_EARNINGS_GROWTH_TOOL: Final = "analyze_fcf_earnings_growth"

FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
PositiveFiniteFloat = Annotated[float, Field(gt=0, allow_inf_nan=False)]


class _AnalysisToolArguments(BaseModel):
    """Shared validation for production analysis-tool arguments."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ticker: str
    as_of: datetime | None = None

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        """Normalize and require a non-empty ticker symbol."""
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("ticker must be a non-empty string.")
        return normalized

    @field_validator("as_of")
    @classmethod
    def require_aware_as_of(cls, value: datetime | None) -> datetime | None:
        """Reject ambiguous point-in-time boundaries."""
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("as_of must be timezone-aware.")
        return value


_MOMENTUM_DEFAULTS = MomentumPolicy()


class MomentumToolArguments(_AnalysisToolArguments):
    """Validated arguments for Momentum analysis."""

    short_window: int = Field(default=_MOMENTUM_DEFAULTS.short_window, gt=0)
    long_window: int = Field(default=_MOMENTUM_DEFAULTS.long_window, gt=0)
    rsi_period: int = Field(default=_MOMENTUM_DEFAULTS.rsi_period, gt=0)

    @model_validator(mode="after")
    def require_ordered_windows(self) -> MomentumToolArguments:
        """Require the short window to precede the long window."""
        if self.short_window >= self.long_window:
            raise ValueError("short_window must be smaller than long_window.")
        return self


class GrahamNumberToolArguments(_AnalysisToolArguments):
    """Validated arguments for Graham Number analysis."""

    eps_basis: Literal["three_year_average", "ttm", "fiscal_year"] = "three_year_average"
    eps_override: FiniteFloat | None = None
    bvps_override: FiniteFloat | None = None
    current_price_override: FiniteFloat | None = None
    use_cache: bool = True


class GrahamGrowthValueToolArguments(_AnalysisToolArguments):
    """Validated arguments for Graham growth-value analysis."""

    eps_basis: Literal["three_year_average", "ttm", "fiscal_year"] = "three_year_average"
    expected_growth: FiniteFloat
    current_aaa_yield: PositiveFiniteFloat
    eps_override: FiniteFloat | None = None
    current_price_override: FiniteFloat | None = None
    use_cache: bool = True


class FCFEarningsGrowthToolArguments(_AnalysisToolArguments):
    """Validated arguments for Free Cash Flow & Earnings Growth analysis."""

    historical_horizon: HistoricalHorizon = HistoricalHorizon.LONGEST_AVAILABLE
    classification_basis: FCFClassificationBasis = FCFClassificationBasis.TOTAL_FCF
    forward_policy: ForwardPolicy = ForwardPolicy.DISPLAY_ONLY
    include_fcf_yield: bool = True
    currency: str = "USD"
    use_cache: bool = True

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        """Normalize and require a non-empty currency identifier."""
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("currency must be a non-empty string.")
        return normalized


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
    graham_resolver: GrahamInputResolver
    graham_security_provider_id: str
    graham_quote_provider_id: str
    graham_growth_policy: GrahamGrowthCalculationPolicy
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
        run = self._dependencies.momentum_analyzer.run_with_context(
            config=config,
            ticker=arguments.ticker,
            as_of=arguments.as_of,
        )
        profile = self._resolve_profile(arguments.ticker)
        return replace(run, instrument_profile=profile) if profile is not None else run

    def analyze_graham_number(self, **raw_arguments: object) -> GrahamNumberAnalysis:
        """Validate, resolve, and calculate one Graham Number run."""
        arguments = GrahamNumberToolArguments.model_validate(raw_arguments)
        profile = self._resolve_profile(arguments.ticker)
        return run_graham_number_analysis(
            resolver=self._dependencies.graham_resolver,
            ticker=arguments.ticker,
            security_provider_id=self._dependencies.graham_security_provider_id,
            quote_provider_id=self._dependencies.graham_quote_provider_id,
            eps_basis=arguments.eps_basis,
            eps_override=arguments.eps_override,
            bvps_override=arguments.bvps_override,
            quote_override=arguments.current_price_override,
            as_of=arguments.as_of,
            use_cache=arguments.use_cache,
            instrument_profile=profile,
        )

    def analyze_graham_growth_value(self, **raw_arguments: object) -> GrahamGrowthAnalysis:
        """Validate, resolve, and calculate one Graham growth-value run."""
        arguments = GrahamGrowthValueToolArguments.model_validate(raw_arguments)
        profile = self._resolve_profile(arguments.ticker)
        return run_graham_growth_analysis(
            resolver=self._dependencies.graham_resolver,
            ticker=arguments.ticker,
            security_provider_id=self._dependencies.graham_security_provider_id,
            quote_provider_id=self._dependencies.graham_quote_provider_id,
            eps_basis=arguments.eps_basis,
            eps_override=arguments.eps_override,
            expected_growth=arguments.expected_growth,
            aaa_yield_override=arguments.current_aaa_yield,
            quote_override=arguments.current_price_override,
            as_of=arguments.as_of,
            use_cache=arguments.use_cache,
            policy=self._dependencies.graham_growth_policy,
            instrument_profile=profile,
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
        effective_as_of = arguments.as_of or self._validated_clock_value()
        profile = self._resolve_profile(arguments.ticker)
        return self._dependencies.fcf_analyzer.run_analysis(
            ticker=arguments.ticker,
            policy=policy,
            currency=arguments.currency,
            as_of=arguments.as_of,
            provider_id=self._dependencies.fcf_provider_id,
            use_cache=arguments.use_cache,
            effective_as_of=effective_as_of,
            instrument_profile=profile,
        )

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
