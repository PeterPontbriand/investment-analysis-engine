from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.llm_client import LLMClient
from src.core.tools.parser import ParsedToolCall, ToolParser, ToolParsingError
from src.orchestrator.context import ContextConfig, MessageContext
from src.orchestrator.dispatcher import AsyncToolDispatcher
from src.orchestrator.loop import AgentOrchestrator, OrchestratorConfig
from src.orchestrator.prompts import SystemPromptBuilder
from src.orchestrator.types import (
    ChatMessage,
    Role,
    ToolCallRequest,
    ToolCallResult,
)

# ---------------------------------------------------------------------------
# 1. Prompt Builder Tests
# ---------------------------------------------------------------------------


def test_system_prompt_builder_default() -> None:
    builder = SystemPromptBuilder()
    prompt = builder.build()
    assert "You are a financial analysis assistant." in prompt
    assert "AVAILABLE TOOLS SCHEMA:" not in prompt


def test_system_prompt_builder_with_schema() -> None:
    builder = SystemPromptBuilder(tool_schemas_json='{"tools": [{"name": "get_stock_price"}]}')
    prompt = builder.build()
    assert "AVAILABLE TOOLS SCHEMA:" in prompt
    assert "get_stock_price" in prompt
    assert "Respond with JSON tool invocations" in prompt


# ---------------------------------------------------------------------------
# 2. Context Management Tests
# ---------------------------------------------------------------------------


def test_context_add_and_ollama_payload() -> None:
    context = MessageContext()
    context.set_system_prompt("System prompt test")
    context.add_message(ChatMessage(role=Role.USER, content="Hello"))

    payload = context.to_ollama_payload()
    assert len(payload) == 2
    assert payload[0] == {"role": "system", "content": "System prompt test"}
    assert payload[1] == {"role": "user", "content": "Hello"}


def test_context_truncation_preserves_system_prompt() -> None:
    config = ContextConfig(max_history_messages=5, preserve_system_prompt=True)
    context = MessageContext(config=config)
    context.set_system_prompt("Preserved System Prompt")

    # Add 10 messages (1 system + 10 user/assistant)
    for i in range(10):
        role = Role.USER if i % 2 == 0 else Role.ASSISTANT
        context.add_message(ChatMessage(role=role, content=f"Message {i}"))

    messages = context.get_messages()
    assert len(messages) == 5
    assert messages[0].role == Role.SYSTEM
    assert messages[0].content == "Preserved System Prompt"
    # Should keep the 4 most recent messages after truncation
    assert messages[-1].content == "Message 9"


# ---------------------------------------------------------------------------
# 3. Async Tool Dispatcher Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatcher_sync_and_async_handlers() -> None:
    dispatcher = AsyncToolDispatcher()

    # Register sync handler
    def sync_add(a: int, b: int) -> int:
        return a + b

    # Register async handler
    async def async_multiply(a: int, b: int) -> int:
        return a * b

    dispatcher.register_tool("add", sync_add)
    dispatcher.register_tool("multiply", async_multiply)

    # Dispatch sync
    res_add = await dispatcher.dispatch(ToolCallRequest(tool_name="add", arguments={"a": 2, "b": 3}))
    assert res_add.success is True
    assert res_add.result == 5

    # Dispatch async
    res_mult = await dispatcher.dispatch(ToolCallRequest(tool_name="multiply", arguments={"a": 3, "b": 4}))
    assert res_mult.success is True
    assert res_mult.result == 12


@pytest.mark.asyncio
async def test_dispatcher_unregistered_and_exception_handling() -> None:
    dispatcher = AsyncToolDispatcher()

    def failing_tool() -> None:
        raise ValueError("Calculation failed")

    dispatcher.register_tool("fail", failing_tool)

    # Test unregistered tool
    res_unreg = await dispatcher.dispatch(ToolCallRequest(tool_name="unknown", arguments={}))
    assert res_unreg.success is False
    assert "Unregistered tool" in (res_unreg.error_message or "")

    # Test tool throwing an exception
    res_fail = await dispatcher.dispatch(ToolCallRequest(tool_name="fail", arguments={}))
    assert res_fail.success is False
    assert "Calculation failed" in (res_fail.error_message or "")


@pytest.mark.asyncio
async def test_dispatcher_duplicate_registration_raises() -> None:
    dispatcher = AsyncToolDispatcher()
    dispatcher.register_tool("test", lambda: None)
    with pytest.raises(ValueError, match="already registered"):
        dispatcher.register_tool("test", lambda: None)


# ---------------------------------------------------------------------------
# 4. Agent Orchestrator Loop Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_orchestrator_single_step_terminal() -> None:
    """Test orchestrator stopping when no tool calls are parsed (direct text response)."""
    llm_mock = MagicMock(spec=LLMClient)
    llm_mock.generate = AsyncMock(return_value="Direct assistant answer")

    parser_mock = MagicMock(spec=ToolParser)
    parser_mock.parse.side_effect = ToolParsingError("No JSON found")

    dispatcher_mock = MagicMock(spec=AsyncToolDispatcher)

    orchestrator = AgentOrchestrator(llm_client=llm_mock, dispatcher=dispatcher_mock, parser=parser_mock)
    context = MessageContext()

    steps = []
    async for step in orchestrator.run_stream("Hello agent", context=context):
        steps.append(step)

    assert len(steps) == 1
    assert steps[0].step_number == 1
    assert steps[0].is_terminal is True
    assert steps[0].message.content == "Direct assistant answer"
    assert len(steps[0].executed_tools) == 0


@pytest.mark.asyncio
async def test_orchestrator_tool_execution_loop() -> None:
    """Test multi-step execution where a tool is called and then answered."""
    llm_mock = MagicMock(spec=LLMClient)
    # Step 1 returns tool call payload text; Step 2 returns final answer
    llm_mock.generate = AsyncMock(
        side_effect=[
            '{"name": "get_quote", "parameters": {"ticker": "AAPL"}}',
            "Apple is currently trading at $180.",
        ]
    )

    parser_mock = MagicMock(spec=ToolParser)
    parser_mock.parse.side_effect = [
        ParsedToolCall(tool_name="get_quote", arguments={"ticker": "AAPL"}),
        ToolParsingError("No tool call in final text"),
    ]

    dispatcher_mock = MagicMock(spec=AsyncToolDispatcher)
    dispatcher_mock.dispatch = AsyncMock(
        return_value=ToolCallResult(
            call_id="call-123",
            tool_name="get_quote",
            success=True,
            result={"price": 180.0},
        )
    )

    orchestrator = AgentOrchestrator(llm_client=llm_mock, dispatcher=dispatcher_mock, parser=parser_mock)
    context = MessageContext()

    steps = []
    async for step in orchestrator.run_stream("What is Apple price?", context=context):
        steps.append(step)

    assert len(steps) == 2

    # Step 1 assertion
    assert steps[0].step_number == 1
    assert steps[0].is_terminal is False
    assert len(steps[0].executed_tools) == 1
    assert steps[0].executed_tools[0].result == {"price": 180.0}

    # Step 2 assertion
    assert steps[1].step_number == 2
    assert steps[1].is_terminal is True
    assert steps[1].message.content == "Apple is currently trading at $180."


@pytest.mark.asyncio
async def test_orchestrator_max_steps_exceeded() -> None:
    """Test orchestrator stopping cleanly when max_steps threshold is hit."""
    llm_mock = MagicMock(spec=LLMClient)
    llm_mock.generate = AsyncMock(return_value='{"name": "loop_forever"}')

    parser_mock = MagicMock(spec=ToolParser)
    parser_mock.parse.return_value = ParsedToolCall(tool_name="loop_forever", arguments={})

    dispatcher_mock = MagicMock(spec=AsyncToolDispatcher)
    dispatcher_mock.dispatch = AsyncMock(
        return_value=ToolCallResult(
            call_id="call-loop",
            tool_name="loop_forever",
            success=True,
            result="ok",
        )
    )

    config = OrchestratorConfig(max_steps=2)
    orchestrator = AgentOrchestrator(
        llm_client=llm_mock,
        dispatcher=dispatcher_mock,
        parser=parser_mock,
        config=config,
    )
    context = MessageContext()

    steps = []
    async for step in orchestrator.run_stream("Start loop", context=context):
        steps.append(step)

    # 2 execution steps + 1 final step for max iterations warning message
    assert len(steps) == 3
    assert steps[-1].is_terminal is True
    assert "Exceeded maximum iteration steps." in steps[-1].message.content
