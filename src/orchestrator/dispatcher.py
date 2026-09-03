import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from src.orchestrator.types import ToolCallRequest, ToolCallResult

logger = logging.getLogger(__name__)

ToolHandler = Callable[..., Any | Awaitable[Any]]


class AsyncToolDispatcher:
    """Dispatches tool calls to registered handlers, supporting both synchronous and asynchronous functions."""

    def __init__(self) -> None:
        """Initializes the AsyncToolDispatcher with an empty registry of tool handlers."""
        self._handlers: dict[str, ToolHandler] = {}

    def register_tool(self, name: str, handler: ToolHandler) -> None:
        """Registers a tool handler for a given tool name."""
        if name in self._handlers:
            raise ValueError(f"Tool '{name}' is already registered.")
        self._handlers[name] = handler

    async def dispatch(self, call: ToolCallRequest) -> ToolCallResult:
        """Dispatches a tool call to the appropriate handler, returning the result or an error message."""
        if call.tool_name not in self._handlers:
            return ToolCallResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                success=False,
                result=None,
                error_message=f"Unregistered tool: '{call.tool_name}'",
            )
        handler = self._handlers[call.tool_name]
        try:
            if inspect.iscoroutinefunction(handler):
                res = await handler(**call.arguments)
            else:
                res = await asyncio.to_thread(handler, **call.arguments)
            return ToolCallResult(call_id=call.call_id, tool_name=call.tool_name, success=True, result=res)
        except Exception as exc:
            logger.exception(f"Tool '{call.tool_name}' execution failed.")
            return ToolCallResult(
                call_id=call.call_id, tool_name=call.tool_name, success=False, result=None, error_message=str(exc)
            )

    def cancellation_is_cooperative(self, tool_name: str) -> bool:
        """Return whether cancelling dispatch can cancel the registered handler."""
        handler = self._handlers.get(tool_name)
        return handler is None or inspect.iscoroutinefunction(handler)
