"""The run context of an analysis-tool call, shared by the strategies whose handlers read the clock first."""

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.orchestrator.analysis_tool_arguments import AnalysisToolArguments
from investment_analysis_engine.orchestrator.tool_runtime import ToolRuntime


def tool_context(runtime: ToolRuntime, arguments: AnalysisToolArguments, *, use_cache: bool) -> AnalysisContext:
    """Build the run context of one tool call: the clock is validated first, then the profile is resolved once.

    The order is fixed. A strategy that must resolve the profile before the clock is validated builds its context
    itself.

    Args:
        runtime: The shared tool runtime, which supplies the clock and the optional profile resolver.
        arguments: The validated arguments, whose ticker and ``as_of`` the context carries.
        use_cache: The strategy's own cache choice from its arguments.

    Returns:
        The context to pass to the analyzer.
    """
    executed_at = runtime.validated_clock_value()
    profile = runtime.resolve_profile(arguments.ticker)
    return AnalysisContext(
        as_of=arguments.as_of, executed_at=executed_at, use_cache=use_cache, instrument_profile=profile
    )
