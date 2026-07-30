"""Automatic JSON Schema generation and tool registry for Ollama-driven agent workflows."""

import inspect
from collections.abc import Callable
from typing import Any, get_type_hints

from pydantic import BaseModel, Field, create_model


class ToolDefinition(BaseModel):
    """Container for a registered tool and its metadata."""

    name: str = Field(description="Unique name of the tool.")
    description: str = Field(description="Description of what the tool does.")
    parameters: dict[str, Any] = Field(description="JSON Schema representation of parameters.")
    callable_func: Callable[..., Any] = Field(description="The actual executable Python callable.")

    model_config = {"arbitrary_types_allowed": True}


class ToolRegistry:
    """Registry to manage analytical tools and format schemas for local LLMs."""

    def __init__(self) -> None:
        """Initialize an empty tool registry."""
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        func: Callable[..., Any] | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Any:
        """Register a Python callable as a tool.

        Can be used as a standard method or a decorator.
        """

        def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
            tool_name = name or f.__name__
            tool_desc = (description or f.__doc__ or "").strip()
            if not tool_desc:
                raise ValueError(f"Tool '{tool_name}' must have a docstring or explicit description.")

            parameters_schema = self._generate_schema_from_callable(f)

            tool_def = ToolDefinition(
                name=tool_name,
                description=tool_desc,
                parameters=parameters_schema,
                callable_func=f,
            )
            self._tools[tool_name] = tool_def
            return f

        if func is None:
            return decorator
        return decorator(func)

    def get_tool(self, name: str) -> ToolDefinition | None:
        """Retrieve a registered tool by name."""
        return self._tools.get(name)

    def get_all_tools(self) -> list[ToolDefinition]:
        """Retrieve list of all registered tool definitions."""
        return list(self._tools.values())

    def to_ollama_tools(self) -> list[dict[str, Any]]:
        """Export all registered tools formatted specifically for Ollama's tool array."""
        ollama_tools: list[dict[str, Any]] = []
        for tool in self._tools.values():
            ollama_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
            )
        return ollama_tools

    def _generate_schema_from_callable(self, func: Callable[..., Any]) -> dict[str, Any]:
        """Extract a valid JSON schema from a function using Pydantic dynamic modeling."""
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)

        fields: dict[str, Any] = {}
        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue

            param_type = type_hints.get(param_name, Any)
            default_val = ... if param.default is inspect.Parameter.empty else param.default

            fields[param_name] = (param_type, default_val)

        # Create a dynamic Pydantic model to leverage Pydantic's robust schema generator
        dynamic_model: type[BaseModel] = create_model(f"{func.__name__}_args", **fields)
        schema = dynamic_model.model_json_schema()

        # Strip Pydantic meta fields not required by Ollama schema
        schema.pop("title", None)
        return schema
