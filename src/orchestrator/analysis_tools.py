"""Registration of the production analysis tools on an existing dispatcher."""

from __future__ import annotations

from collections.abc import Mapping

from src.core.strategy_errors import undeclared
from src.orchestrator.dispatcher import AsyncToolDispatcher
from src.orchestrator.tool_names import ToolName
from src.orchestrator.tool_runtime import AnalysisToolHandler


def register_analysis_tools(
    dispatcher: AsyncToolDispatcher,
    handlers: Mapping[ToolName, AnalysisToolHandler[object]],
) -> None:
    """Register one injected handler for every approved analysis tool.

    The mapping is checked against ``ToolName`` in both directions before anything is registered, so a
    tool without a handler, or a handler for no tool, can never leave the dispatcher partly populated.

    Args:
        dispatcher: Existing dispatcher that receives the handlers, in ``ToolName`` declaration order.
        handlers: One bound handler per approved tool.

    Raises:
        UndeclaredStrategyError: If a ``ToolName`` member has no handler, or a handler is keyed by no member.
    """
    for tool in ToolName:
        if tool not in handlers:
            raise undeclared("handler for tool", tool, handlers)
    for tool in handlers:
        if tool not in ToolName:
            raise undeclared("handler key", tool, ToolName)
    for tool in ToolName:
        dispatcher.register_tool(tool.value, handlers[tool])
