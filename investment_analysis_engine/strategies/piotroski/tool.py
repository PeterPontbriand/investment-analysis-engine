"""The Piotroski F-Score strategy's analysis-tool arguments, dependencies and handler."""

from __future__ import annotations

from dataclasses import dataclass

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.orchestrator.analysis_tool_arguments import AnalysisToolArguments
from investment_analysis_engine.orchestrator.tool_runtime import ToolRuntime
from investment_analysis_engine.strategies.piotroski.analyzer import PiotroskiAnalyzer, PiotroskiResult


class PiotroskiToolArguments(AnalysisToolArguments):
    """Validated arguments for the Piotroski F-Score analysis."""

    use_cache: bool = True


@dataclass(frozen=True)
class PiotroskiToolDependencies:
    """The injected Piotroski F-Score analyzer."""

    analyzer: PiotroskiAnalyzer


class PiotroskiToolHandler:
    """Bind the Piotroski F-Score analyzer and the shared runtime to the analysis tool."""

    def __init__(self, dependencies: PiotroskiToolDependencies, runtime: ToolRuntime) -> None:
        """Retain the injected analyzer and shared runtime."""
        self._dependencies = dependencies
        self._runtime = runtime

    def __call__(self, **raw_arguments: object) -> PiotroskiResult:
        """Validate the arguments and run one Piotroski F-Score analysis."""
        arguments = PiotroskiToolArguments.model_validate(raw_arguments)
        executed_at = self._runtime.validated_clock_value()
        profile = self._runtime.resolve_profile(arguments.ticker)
        context = AnalysisContext(
            as_of=arguments.as_of,
            executed_at=executed_at,
            use_cache=arguments.use_cache,
            instrument_profile=profile,
        )
        return self._dependencies.analyzer.run_analysis(ticker=arguments.ticker, context=context)
