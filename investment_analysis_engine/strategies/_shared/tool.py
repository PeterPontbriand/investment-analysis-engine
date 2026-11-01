"""The run context of an analysis-tool call, shared by every strategy's tool handler."""

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.orchestrator.analysis_tool_arguments import AnalysisToolArguments
from investment_analysis_engine.orchestrator.tool_runtime import ToolRuntime


def tool_context(runtime: ToolRuntime, arguments: AnalysisToolArguments) -> AnalysisContext:
    """Build the run context of one tool call: the clock is validated first, then the profile is resolved once.

    The order is fixed: a refused clock sends no profile request.

    Args:
        runtime: The shared tool runtime, which supplies the clock and the optional profile resolver.
        arguments: The validated arguments, whose ticker, ``as_of`` and ``use_cache`` the context carries.

    Returns:
        The context to pass to the analyzer.
    """
    executed_at = runtime.validated_clock_value()
    profile = runtime.resolve_profile(arguments.ticker)
    return AnalysisContext(
        as_of=arguments.as_of, executed_at=executed_at, use_cache=arguments.use_cache, instrument_profile=profile
    )
