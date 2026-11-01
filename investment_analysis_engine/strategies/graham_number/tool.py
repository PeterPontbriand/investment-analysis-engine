"""Graham Number's production analysis-tool arguments, dependencies and handler."""

from __future__ import annotations

from dataclasses import dataclass

from investment_analysis_engine.orchestrator.analysis_tool_arguments import AnalysisToolArguments, FiniteFloat
from investment_analysis_engine.orchestrator.tool_runtime import ToolRuntime
from investment_analysis_engine.strategies._shared.tool import tool_context
from investment_analysis_engine.strategies.graham_number.analyzer import GrahamNumberAnalyzer
from investment_analysis_engine.strategies.graham_number.config import GrahamNumberConfig
from investment_analysis_engine.strategies.graham_number.service import GrahamNumberAnalysis


class GrahamNumberToolArguments(AnalysisToolArguments):
    """Validated arguments for Graham Number analysis."""

    eps_override: FiniteFloat | None = None
    bvps_override: FiniteFloat | None = None
    current_price_override: FiniteFloat | None = None


@dataclass(frozen=True)
class GrahamNumberToolDependencies:
    """Injected Graham Number analyzer."""

    analyzer: GrahamNumberAnalyzer


class GrahamNumberToolHandler:
    """Bind Graham Number's injected analyzer and shared runtime to the analysis tool."""

    def __init__(self, dependencies: GrahamNumberToolDependencies, runtime: ToolRuntime) -> None:
        """Retain the explicitly injected analyzer and shared runtime."""
        self._dependencies = dependencies
        self._runtime = runtime

    def __call__(self, **raw_arguments: object) -> GrahamNumberAnalysis:
        """Validate, resolve, and calculate one Graham Number run."""
        arguments = GrahamNumberToolArguments.model_validate(raw_arguments)
        config = GrahamNumberConfig(
            eps_override=arguments.eps_override,
            bvps_override=arguments.bvps_override,
            quote_override=arguments.current_price_override,
        )
        context = tool_context(self._runtime, arguments)
        return self._dependencies.analyzer.run_analysis(ticker=arguments.ticker, config=config, context=context)
