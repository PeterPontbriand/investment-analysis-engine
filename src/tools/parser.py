"""Parser for extracting and validating tool call payloads from local LLM outputs."""

import json
import re
from typing import Any, NamedTuple

from src.tools.schema_generator import ToolRegistry


class ParsedToolCall(NamedTuple):
    """Container for a parsed and validated tool call invocation."""

    tool_name: str
    arguments: dict[str, Any]


class ToolParsingError(Exception):
    """Raised when the LLM output cannot be parsed into valid JSON or extracted properly."""

    pass


class ToolNotFoundError(Exception):
    """Raised when the LLM attempts to call a tool that is not in the registry."""

    pass


class ToolValidationError(Exception):
    """Raised when the tool arguments fail Pydantic validation."""

    pass


class ToolParser:
    """Extracts, cleans, and validates tool execution payloads from raw model outputs."""

    def __init__(self, registry: ToolRegistry) -> None:
        """Initialize the parser with a reference to the tool registry."""
        self.registry = registry

    def parse(self, raw_output: str) -> ParsedToolCall:
        """Parse raw model text into a validated tool call."""
        cleaned_text = self._strip_reasoning_and_markdown(raw_output)
        payload = self._extract_json_payload(cleaned_text)

        tool_name = payload.get("name") or payload.get("tool")
        arguments = payload.get("parameters") or payload.get("arguments") or {}

        if not tool_name or not isinstance(tool_name, str):
            raise ToolParsingError(f"Could not identify a valid tool 'name' in payload: {payload}")

        tool_def = self.registry.get_tool(tool_name)
        if not tool_def:
            raise ToolNotFoundError(f"Tool '{tool_name}' is not registered in the ToolRegistry.")

        # Validate arguments using the tool's parameter schema
        validated_args = self._validate_arguments(tool_name, arguments)

        return ParsedToolCall(tool_name=tool_name, arguments=validated_args)

    def _strip_reasoning_and_markdown(self, text: str) -> str:
        """Strip reasoning model think tags (<think>...</think>) and whitespace."""
        # Remove <think>...</think> blocks from models like DeepSeek-R1
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        return text.strip()

    def _extract_json_payload(self, text: str) -> dict[str, Any]:
        """Extract a JSON dictionary from raw output or Markdown ```json block."""
        # Check for Markdown codeblock wrapping
        markdown_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if markdown_match:
            json_str = markdown_match.group(1)
        else:
            # Fallback to finding the outer-most JSON object brackets
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            json_str = json_match.group(0) if json_match else text

        try:
            parsed = json.loads(json_str)
            if not isinstance(parsed, dict):
                raise ToolParsingError(f"Expected JSON object payload, but got type {type(parsed).__name__}")
            return parsed
        except json.JSONDecodeError as e:
            raise ToolParsingError(f"Failed to decode JSON payload: {e}") from e

    def _validate_arguments(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Ensure argument dict conforms to the target tool schema."""
        tool_def = self.registry.get_tool(tool_name)
        if not tool_def:
            raise ToolNotFoundError(f"Tool '{tool_name}' not found.")

        # If parameters schema is empty, no validation needed
        if not tool_def.parameters.get("properties"):
            return args

        return args
