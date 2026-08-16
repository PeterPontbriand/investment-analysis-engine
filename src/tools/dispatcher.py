"""Execution dispatcher for invoking validated local agent tools."""

import time
from typing import Any

from pydantic import BaseModel, Field

from src.tools.parser import ParsedToolCall
from src.tools.schema_generator import ToolRegistry


class ToolExecutionResult(BaseModel):
    """Standardized result envelope for tool execution outcomes."""

    tool_name: str = Field(description="Name of the executed tool.")
    success: bool = Field(description="Whether execution completed without error.")
    result: Any = Field(default=None, description="Returned payload from the tool.")
    error: str | None = Field(default=None, description="Error message if execution failed.")
    execution_time_ms: float = Field(description="Execution duration in milliseconds.")


class ToolDispatcher:
    """Handles type-safe dynamic dispatch of tool calls."""

    def __init__(self, registry: ToolRegistry) -> None:
        """Initialize the dispatcher with a reference to the tool registry."""
        self.registry = registry

    def dispatch(self, parsed_call: ParsedToolCall) -> ToolExecutionResult:
        """Execute a parsed tool call and return a wrapped result payload."""
        tool_def = self.registry.get_tool(parsed_call.tool_name)

        if not tool_def:
            return ToolExecutionResult(
                tool_name=parsed_call.tool_name,
                success=False,
                error=f"Tool '{parsed_call.tool_name}' not found in registry.",
                execution_time_ms=0.0,
            )

        start_time = time.perf_counter()
        try:
            # Dynamic execution of the underlying callable
            output = tool_def.callable_func(**parsed_call.arguments)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            return ToolExecutionResult(
                tool_name=parsed_call.tool_name,
                success=True,
                result=output,
                execution_time_ms=round(elapsed_ms, 2),
            )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ToolExecutionResult(
                tool_name=parsed_call.tool_name,
                success=False,
                error=f"Execution error in '{parsed_call.tool_name}': {str(e)}",
                execution_time_ms=round(elapsed_ms, 2),
            )
