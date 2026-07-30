"""Unit tests for Pydantic tool registration, parsing, and execution layers."""

import pytest

from src.core.tools.dispatcher import ToolDispatcher
from src.core.tools.parser import (
    ToolParser,
)
from src.core.tools.schema_generator import ToolRegistry


@pytest.fixture
def populated_registry() -> ToolRegistry:
    registry = ToolRegistry()

    @registry.register
    def calculate_roi(initial_investment: float, net_profit: float) -> float:
        """Calculate Return on Investment (ROI) percentage."""
        if initial_investment <= 0:
            raise ValueError("Initial investment must be greater than zero.")
        return (net_profit / initial_investment) * 100.0

    return registry


def test_schema_generator_ollama_format(populated_registry: ToolRegistry) -> None:
    ollama_tools = populated_registry.to_ollama_tools()
    assert len(ollama_tools) == 1
    tool = ollama_tools[0]
    assert tool["type"] == "function"
    assert tool["function"]["name"] == "calculate_roi"
    assert "Calculate Return on Investment" in tool["function"]["description"]
    assert "properties" in tool["function"]["parameters"]


def test_parser_markdown_extraction(populated_registry: ToolRegistry) -> None:
    parser = ToolParser(populated_registry)
    raw_llm_output = """
    Here is the tool call:
    ```json
    {
        "name": "calculate_roi",
        "parameters": {
            "initial_investment": 1000.0,
            "net_profit": 250.0
        }
    }
    ```
    """
    parsed = parser.parse(raw_llm_output)
    assert parsed.tool_name == "calculate_roi"
    assert parsed.arguments["initial_investment"] == 1000.0
    assert parsed.arguments["net_profit"] == 250.0


def test_parser_think_tag_stripping(populated_registry: ToolRegistry) -> None:
    parser = ToolParser(populated_registry)
    raw_llm_output = """<think>
    The user wants to find ROI. I should call calculate_roi with investment 100 and profit 50.
    </think>
    {"name": "calculate_roi", "parameters": {"initial_investment": 100, "net_profit": 50}}"""

    parsed = parser.parse(raw_llm_output)
    assert parsed.tool_name == "calculate_roi"
    assert parsed.arguments["net_profit"] == 50


def test_dispatcher_successful_execution(populated_registry: ToolRegistry) -> None:
    parser = ToolParser(populated_registry)
    dispatcher = ToolDispatcher(populated_registry)

    raw_output = '{"name": "calculate_roi", "parameters": {"initial_investment": 1000.0, "net_profit": 200.0}}'
    parsed_call = parser.parse(raw_output)

    result = dispatcher.dispatch(parsed_call)
    assert result.success is True
    assert result.result == 20.0
    assert result.error is None
    assert result.execution_time_ms >= 0.0


def test_dispatcher_runtime_exception_handling(populated_registry: ToolRegistry) -> None:
    parser = ToolParser(populated_registry)
    dispatcher = ToolDispatcher(populated_registry)

    raw_output = '{"name": "calculate_roi", "parameters": {"initial_investment": 0.0, "net_profit": 200.0}}'
    parsed_call = parser.parse(raw_output)

    result = dispatcher.dispatch(parsed_call)
    assert result.success is False
    assert result.result is None
    assert "Initial investment must be greater than zero" in str(result.error)
