"""Graham growth-value's production analysis-tool arguments, dependencies and handler."""

from __future__ import annotations

from dataclasses import dataclass

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.orchestrator.analysis_tool_arguments import (
    AnalysisToolArguments,
    FiniteFloat,
    PositiveFiniteFloat,
)
from investment_analysis_engine.orchestrator.tool_runtime import ToolRuntime
from investment_analysis_engine.strategies.graham_growth.analyzer import GrahamGrowthAnalyzer
from investment_analysis_engine.strategies.graham_growth.config import GrahamGrowthConfig, GrahamGrowthEPSBasis
from investment_analysis_engine.strategies.graham_growth.service import GrahamGrowthAnalysis


class GrahamGrowthValueToolArguments(AnalysisToolArguments):
    """Validated arguments for Graham growth-value analysis."""

    eps_basis: GrahamGrowthEPSBasis = "three_year_average"
    expected_growth: FiniteFloat
    current_aaa_yield: PositiveFiniteFloat
    eps_override: FiniteFloat | None = None
    current_price_override: FiniteFloat | None = None
    use_cache: bool = True


@dataclass(frozen=True)
class GrahamGrowthToolDependencies:
    """Injected Graham growth-value analyzer."""

    analyzer: GrahamGrowthAnalyzer


class GrahamGrowthToolHandler:
    """Bind Graham growth-value's injected analyzer and shared runtime to the analysis tool."""

    def __init__(self, dependencies: GrahamGrowthToolDependencies, runtime: ToolRuntime) -> None:
        """Retain the explicitly injected analyzer and shared runtime."""
        self._dependencies = dependencies
        self._runtime = runtime

    def __call__(self, **raw_arguments: object) -> GrahamGrowthAnalysis:
        """Validate, resolve, and calculate one Graham growth-value run."""
        arguments = GrahamGrowthValueToolArguments.model_validate(raw_arguments)
        profile = self._runtime.resolve_profile(arguments.ticker)
        config = GrahamGrowthConfig(
            eps_basis=arguments.eps_basis,
            eps_override=arguments.eps_override,
            expected_growth=arguments.expected_growth,
            aaa_yield_override=arguments.current_aaa_yield,
            quote_override=arguments.current_price_override,
        )
        executed_at = self._runtime.validated_clock_value()
        context = AnalysisContext(
            as_of=arguments.as_of,
            executed_at=executed_at,
            use_cache=arguments.use_cache,
            instrument_profile=profile,
        )
        return self._dependencies.analyzer.run_analysis(ticker=arguments.ticker, config=config, context=context)
