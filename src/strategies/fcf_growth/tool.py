"""Free Cash Flow & Earnings Growth's production analysis-tool arguments, dependencies and handler."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import field_validator

from src.analysis.base_analyzer import AnalysisContext
from src.orchestrator.analysis_tool_arguments import AnalysisToolArguments
from src.orchestrator.tool_runtime import ToolRuntime
from src.strategies.fcf_growth.analyzer import FCFEarningsGrowthAnalyzer
from src.strategies.fcf_growth.models import FCFEarningsGrowthConfig, FCFEarningsGrowthPolicy, FCFEarningsGrowthResult
from src.strategies.fcf_growth.vocabulary import FCFClassificationBasis, ForwardPolicy, HistoricalHorizon


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
    """Injected FCF & Earnings Growth analyzer and provider selection."""

    analyzer: FCFEarningsGrowthAnalyzer
    provider_id: str

    def __post_init__(self) -> None:
        """Reject a missing provider selection before any tool is registered."""
        if not self.provider_id.strip():
            raise ValueError("Analysis tool provider IDs must be non-empty.")


class FCFEarningsGrowthToolHandler:
    """Bind FCF & Earnings Growth's injected analyzer and shared runtime to the analysis tool."""

    def __init__(self, dependencies: FCFEarningsGrowthToolDependencies, runtime: ToolRuntime) -> None:
        """Retain the explicitly injected analyzer, provider selection and shared runtime."""
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
            provider_id=self._dependencies.provider_id,
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
