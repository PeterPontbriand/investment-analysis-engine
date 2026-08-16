from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.llm.client import LLMClient, LLMGenerateResult
from src.orchestrator.context import ContextConfig, MessageContext
from src.orchestrator.dispatcher import AsyncToolDispatcher
from src.orchestrator.loop import AgentOrchestrator, OrchestratorConfig, OrchestratorOptions
from src.orchestrator.prompts import SystemPromptBuilder
from src.orchestrator.types import (
    ChatMessage,
    Role,
    ToolCallRequest,
    ToolCallResult,
)
from src.tools.parser import ParsedToolCall, ToolParser, ToolParsingError

# ---------------------------------------------------------------------------
# Helper – canonical way to create a context with runtime rules injected
# ---------------------------------------------------------------------------


def make_context_with_runtime_rules(
    *,
    max_history_messages: int = 30,
    preserve_system_prompt: bool = True,
    tool_schemas_json: str | None = None,
    rules_path: Path | str | None = None,
) -> MessageContext:
    """
    Example factory that future application code should mirror.

    Builds the system prompt (including RUNTIME_AGENTS.md when present)
    and injects it into a fresh MessageContext.
    """
    builder = SystemPromptBuilder(
        tool_schemas_json=tool_schemas_json,
        rules_path=rules_path,
        inject_runtime_rules=True,
    )
    system_prompt = builder.build()

    config = ContextConfig(
        max_history_messages=max_history_messages,
        preserve_system_prompt=preserve_system_prompt,
    )
    context = MessageContext(config=config)
    context.set_system_prompt(system_prompt)
    return context


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


def test_system_prompt_builder_injects_runtime_rules(tmp_path: Path) -> None:
    """RUNTIME_AGENTS.md content is appended under a clear heading when present."""
    rules_file = tmp_path / "RUNTIME_AGENTS.md"
    rules_file.write_text("# Agent Rules\n- Always be precise\n- Prefer tool results", encoding="utf-8")

    builder = SystemPromptBuilder(
        inject_runtime_rules=True,
        rules_path=rules_file,
    )
    prompt = builder.build()

    assert "# RUNTIME AGENT RULES" in prompt
    assert "Always be precise" in prompt
    assert "Prefer tool results" in prompt
    assert "You are a financial analysis assistant." in prompt


def test_system_prompt_builder_missing_rules_file_is_silent(tmp_path: Path) -> None:
    """Missing rules file must not raise; prompt remains valid."""
    missing = tmp_path / "does_not_exist.md"
    builder = SystemPromptBuilder(inject_runtime_rules=True, rules_path=missing)
    prompt = builder.build()
    assert "You are a financial analysis assistant." in prompt
    assert "# RUNTIME AGENT RULES" not in prompt


def test_system_prompt_builder_can_disable_injection() -> None:
    builder = SystemPromptBuilder(inject_runtime_rules=False)
    prompt = builder.build()
    assert "# RUNTIME AGENT RULES" not in prompt


# ---------------------------------------------------------------------------
# 2. Context Management Tests
# ---------------------------------------------------------------------------


def test_context_add_and_ollama_payload() -> None:
    # Use the recommended factory so the system prompt already contains rules
    context = make_context_with_runtime_rules()
    context.add_message(ChatMessage(role=Role.USER, content="Hello"))

    payload = context.to_ollama_payload()
    assert len(payload) >= 2
    assert payload[0]["role"] == "system"
    assert "You are a financial analysis assistant." in payload[0]["content"]
    assert payload[-1] == {"role": "user", "content": "Hello"}


def test_context_truncation_preserves_system_prompt() -> None:
    context = make_context_with_runtime_rules(
        max_history_messages=5,
        preserve_system_prompt=True,
    )

    # Add 10 messages (system already present + 10 more)
    for i in range(10):
        role = Role.USER if i % 2 == 0 else Role.ASSISTANT
        context.add_message(ChatMessage(role=role, content=f"Message {i}"))

    messages = context.get_messages()
    assert len(messages) == 5
    assert messages[0].role == Role.SYSTEM
    assert "You are a financial analysis assistant." in messages[0].content
    # Most recent non-system messages are retained
    assert messages[-1].content == "Message 9"


# ---------------------------------------------------------------------------
# 3. Async Tool Dispatcher Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatcher_sync_and_async_handlers() -> None:
    dispatcher = AsyncToolDispatcher()

    def sync_add(a: int, b: int) -> int:
        return a + b

    async def async_multiply(a: int, b: int) -> int:
        return a * b

    dispatcher.register_tool("add", sync_add)
    dispatcher.register_tool("multiply", async_multiply)

    res_add = await dispatcher.dispatch(ToolCallRequest(tool_name="add", arguments={"a": 2, "b": 3}))
    assert res_add.success is True
    assert res_add.result == 5

    res_mult = await dispatcher.dispatch(ToolCallRequest(tool_name="multiply", arguments={"a": 3, "b": 4}))
    assert res_mult.success is True
    assert res_mult.result == 12


@pytest.mark.asyncio
async def test_dispatcher_unregistered_and_exception_handling() -> None:
    dispatcher = AsyncToolDispatcher()

    def failing_tool() -> None:
        raise ValueError("Calculation failed")

    dispatcher.register_tool("fail", failing_tool)

    res_unreg = await dispatcher.dispatch(ToolCallRequest(tool_name="unknown", arguments={}))
    assert res_unreg.success is False
    assert "Unregistered tool" in (res_unreg.error_message or "")

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
    llm_mock.generate = AsyncMock(return_value=LLMGenerateResult(text="Direct assistant answer"))

    parser_mock = MagicMock(spec=ToolParser)
    parser_mock.parse.side_effect = ToolParsingError("No JSON found")

    dispatcher_mock = MagicMock(spec=AsyncToolDispatcher)

    orchestrator = AgentOrchestrator(llm_client=llm_mock, dispatcher=dispatcher_mock, parser=parser_mock)

    # Canonical context creation with runtime rules
    context = make_context_with_runtime_rules()

    steps = []
    async for step in orchestrator.run_stream("Hello agent", context=context):
        steps.append(step)

    assert len(steps) == 1
    assert steps[0].step_number == 1
    assert steps[0].is_terminal is True
    assert steps[0].message.content == "Direct assistant answer"
    assert len(steps[0].executed_tools) == 0

    # System prompt (with rules) is still present after the run
    messages = context.get_messages()
    assert messages[0].role == Role.SYSTEM
    assert "You are a financial analysis assistant." in messages[0].content


@pytest.mark.asyncio
async def test_orchestrator_tool_execution_loop() -> None:
    """Test multi-step execution where a tool is called and then answered."""
    llm_mock = MagicMock(spec=LLMClient)
    llm_mock.generate = AsyncMock(
        side_effect=[
            LLMGenerateResult(text='{"name": "get_quote", "parameters": {"ticker": "AAPL"}}'),
            LLMGenerateResult(text="Apple is currently trading at $180."),
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
    context = make_context_with_runtime_rules()

    steps = []
    async for step in orchestrator.run_stream("What is Apple price?", context=context):
        steps.append(step)

    assert len(steps) == 2

    assert steps[0].step_number == 1
    assert steps[0].is_terminal is False
    assert len(steps[0].executed_tools) == 1
    assert steps[0].executed_tools[0].result == {"price": 180.0}

    assert steps[1].step_number == 2
    assert steps[1].is_terminal is True
    assert steps[1].message.content == "Apple is currently trading at $180."

    # Rules remain in the system message after tool rounds
    assert context.get_messages()[0].role == Role.SYSTEM


@pytest.mark.asyncio
async def test_orchestrator_max_steps_exceeded() -> None:
    """Test orchestrator stopping cleanly when max_steps threshold is hit."""
    llm_mock = MagicMock(spec=LLMClient)
    llm_mock.generate = AsyncMock(return_value=LLMGenerateResult(text='{"name": "loop_forever"}'))

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
        options=OrchestratorOptions(config=config),
    )

    context = make_context_with_runtime_rules()

    steps = []
    async for step in orchestrator.run_stream("Start loop", context=context):
        steps.append(step)

    assert len(steps) == 3
    assert steps[-1].is_terminal is True
    assert "Exceeded maximum iteration steps." in steps[-1].message.content
