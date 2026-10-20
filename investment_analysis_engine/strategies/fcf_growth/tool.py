"""Free Cash Flow & Earnings Growth's production analysis-tool arguments, dependencies and handler."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import field_validator

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.orchestrator.analysis_tool_arguments import AnalysisToolArguments
from investment_analysis_engine.orchestrator.tool_runtime import ToolRuntime
from investment_analysis_engine.strategies.fcf_growth.analyzer import FCFEarningsGrowthAnalyzer
from investment_analysis_engine.strategies.fcf_growth.models import (
    FCFEarningsGrowthConfig,
    FCFEarningsGrowthPolicy,
    FCFEarningsGrowthResult,
)
from investment_analysis_engine.strategies.fcf_growth.vocabulary import (
    FCFClassificationBasis,
    ForwardPolicy,
    HistoricalHorizon,
)


class FCFEarningsGrowthToolArguments(AnalysisToolArguments):
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


@dataclass(frozen=True)
class FCFEarningsGrowthToolDependencies:
    """Injected FCF & Earnings Growth analyzer."""

    analyzer: FCFEarningsGrowthAnalyzer


class FCFEarningsGrowthToolHandler:
    """Bind FCF & Earnings Growth's injected analyzer and shared runtime to the analysis tool."""

    def __init__(self, dependencies: FCFEarningsGrowthToolDependencies, runtime: ToolRuntime) -> None:
        """Retain the explicitly injected analyzer and shared runtime."""
        self._dependencies = dependencies
        self._runtime = runtime

    def __call__(self, **raw_arguments: object) -> FCFEarningsGrowthResult:
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
        )
        executed_at = self._runtime.validated_clock_value()
        profile = self._runtime.resolve_profile(arguments.ticker)
        context = AnalysisContext(
            as_of=arguments.as_of,
            executed_at=executed_at,
            use_cache=arguments.use_cache,
            instrument_profile=profile,
        )
        return self._dependencies.analyzer.run_analysis(ticker=arguments.ticker, config=config, context=context)
