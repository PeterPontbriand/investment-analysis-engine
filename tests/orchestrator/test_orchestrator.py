from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.llm.client import LLMClient, LLMGenerateResult
from src.orchestrator.context import ContextConfig, MessageContext
from src.orchestrator.dispatcher import AsyncToolDispatcher
from src.orchestrator.loop import AgentOrchestrator, OrchestratorConfig, OrchestratorOptions
from src.orchestrator.prompts import SystemPromptBuilder
from src.orchestrator.reliability import ReliabilityTripReason
from src.orchestrator.types import (
    ChatMessage,
    Role,
    ToolCallRequest,
    ToolCallResult,
)
from src.schema.config import SchemaConfig
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

    config = OrchestratorConfig(schema_config=SchemaConfig(use_native_constraint=False))
    orchestrator = AgentOrchestrator(
        llm_client=llm_mock,
        dispatcher=dispatcher_mock,
        parser=parser_mock,
        options=OrchestratorOptions(config=config),
    )

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

    config = OrchestratorConfig(
        schema_config=SchemaConfig(
            use_native_constraint=False,
            max_validation_retries=0,
        ),
    )
    orchestrator = AgentOrchestrator(
        llm_client=llm_mock,
        dispatcher=dispatcher_mock,
        parser=parser_mock,
        options=OrchestratorOptions(config=config),
    )
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

    config = OrchestratorConfig(
        max_steps=2,
        schema_config=SchemaConfig(use_native_constraint=False),
    )
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
    assert orchestrator.last_reliability_failure is not None
    assert orchestrator.last_reliability_failure.reason is ReliabilityTripReason.MAX_STEPS_EXCEEDED


# ---------------------------------------------------------------------------
# 5. Native schema constraint forwarding (Step 2.2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_orchestrator_forwards_native_schema_format_to_llm() -> None:
    """When use_native_constraint is enabled, forward a top-level format kwarg.

    The orchestrator must forward a top-level ``format`` kwarg to
    LLMClient.generate carrying the ToolCallResponse JSON Schema. The call
    must succeed (no TypeError).
    """
    llm_mock = MagicMock(spec=LLMClient)
    llm_mock.generate = AsyncMock(return_value=LLMGenerateResult(text="Direct answer"))

    parser_mock = MagicMock(spec=ToolParser)
    parser_mock.parse.side_effect = ToolParsingError("No JSON found")

    dispatcher_mock = MagicMock(spec=AsyncToolDispatcher)

    config = OrchestratorConfig(
        schema_config=SchemaConfig(use_native_constraint=True, ollama_version="0.5.4"),
    )
    orchestrator = AgentOrchestrator(
        llm_client=llm_mock,
        dispatcher=dispatcher_mock,
        parser=parser_mock,
        options=OrchestratorOptions(config=config),
    )

    context = make_context_with_runtime_rules()
    async for _step in orchestrator.run_stream("Hello", context=context):
        pass

    llm_mock.generate.assert_awaited()
    call_kwargs = llm_mock.generate.call_args.kwargs
    assert "format" in call_kwargs, "orchestrator must forward the format kwarg"
    fmt = call_kwargs["format"]
    assert isinstance(fmt, dict), "format must be a JSON Schema dict"
    assert fmt.get("type") == "object"
    # Schema for ToolCallResponse must include the required tool_name field.
    assert "tool_name" in fmt.get("properties", {})


@pytest.mark.asyncio
async def test_orchestrator_omits_format_when_native_constraint_disabled() -> None:
    """Omit the format kwarg when native constraint is disabled.

    When use_native_constraint is disabled, the orchestrator must not send a
    ``format`` kwarg to LLMClient.generate.
    """
    llm_mock = MagicMock(spec=LLMClient)
    llm_mock.generate = AsyncMock(return_value=LLMGenerateResult(text="Direct answer"))

    parser_mock = MagicMock(spec=ToolParser)
    parser_mock.parse.side_effect = ToolParsingError("No JSON found")

    dispatcher_mock = MagicMock(spec=AsyncToolDispatcher)

    config = OrchestratorConfig(
        schema_config=SchemaConfig(use_native_constraint=False),
    )
    orchestrator = AgentOrchestrator(
        llm_client=llm_mock,
        dispatcher=dispatcher_mock,
        parser=parser_mock,
        options=OrchestratorOptions(config=config),
    )

    context = make_context_with_runtime_rules()
    async for _step in orchestrator.run_stream("Hello", context=context):
        pass

    llm_mock.generate.assert_awaited()
    call_kwargs = llm_mock.generate.call_args.kwargs
    assert "format" not in call_kwargs, "format must be omitted when native constraint is disabled"


# ---------------------------------------------------------------------------
# 5b. Capability resolution (runtime version-driven format decision)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_orchestrator_format_included_when_remote_server_supports() -> None:
    """Remote server reports a supported version → native format IS sent.

    The LLMClient's get_ollama_version() returns "0.6.1" (supported),
    so the orchestrator must include the format kwarg.
    """
    llm_mock = MagicMock(spec=LLMClient)
    llm_mock.generate = AsyncMock(return_value=LLMGenerateResult(text="Direct answer"))
    # Simulate the remote server reporting a supported version
    llm_mock.get_ollama_version = AsyncMock(return_value="0.6.1")

    parser_mock = MagicMock(spec=ToolParser)
    parser_mock.parse.side_effect = ToolParsingError("No JSON found")

    dispatcher_mock = MagicMock(spec=AsyncToolDispatcher)

    config = OrchestratorConfig(
        schema_config=SchemaConfig(use_native_constraint=True),
    )
    orchestrator = AgentOrchestrator(
        llm_client=llm_mock,
        dispatcher=dispatcher_mock,
        parser=parser_mock,
        options=OrchestratorOptions(config=config),
    )

    context = make_context_with_runtime_rules()
    async for _step in orchestrator.run_stream("Hello", context=context):
        pass

    llm_mock.generate.assert_awaited()
    call_kwargs = llm_mock.generate.call_args.kwargs
    assert "format" in call_kwargs, "format must be included when server capability is confirmed"
    assert call_kwargs["format"]["type"] == "object"


@pytest.mark.asyncio
async def test_orchestrator_format_omitted_when_remote_server_unsupported() -> None:
    """Remote server reports an unsupported version → native format NOT sent.

    The LLMClient's get_ollama_version() returns "0.3.0" (below 0.5.0),
    so the orchestrator must NOT include the format kwarg.
    """
    llm_mock = MagicMock(spec=LLMClient)
    llm_mock.generate = AsyncMock(return_value=LLMGenerateResult(text="Direct answer"))
    # Simulate the remote server reporting an old unsupported version
    llm_mock.get_ollama_version = AsyncMock(return_value="0.3.0")

    parser_mock = MagicMock(spec=ToolParser)
    parser_mock.parse.side_effect = ToolParsingError("No JSON found")

    dispatcher_mock = MagicMock(spec=AsyncToolDispatcher)

    config = OrchestratorConfig(
        schema_config=SchemaConfig(use_native_constraint=True),
    )
    orchestrator = AgentOrchestrator(
        llm_client=llm_mock,
        dispatcher=dispatcher_mock,
        parser=parser_mock,
        options=OrchestratorOptions(config=config),
    )

    context = make_context_with_runtime_rules()
    async for _step in orchestrator.run_stream("Hello", context=context):
        pass

    llm_mock.generate.assert_awaited()
    call_kwargs = llm_mock.generate.call_args.kwargs
    assert "format" not in call_kwargs, "format must be omitted when server is known-unsupported"


@pytest.mark.asyncio
async def test_orchestrator_format_omitted_when_capability_unknown() -> None:
    """Remote capability cannot be determined → safe default: NO format.

    The LLMClient's get_ollama_version() returns None (unreachable/malformed),
    so the orchestrator must NOT assume support and must omit the format kwarg.
    """
    llm_mock = MagicMock(spec=LLMClient)
    llm_mock.generate = AsyncMock(return_value=LLMGenerateResult(text="Direct answer"))
    # Simulate the remote server being unreachable
    llm_mock.get_ollama_version = AsyncMock(return_value=None)

    parser_mock = MagicMock(spec=ToolParser)
    parser_mock.parse.side_effect = ToolParsingError("No JSON found")

    dispatcher_mock = MagicMock(spec=AsyncToolDispatcher)

    config = OrchestratorConfig(
        schema_config=SchemaConfig(use_native_constraint=True),
    )
    orchestrator = AgentOrchestrator(
        llm_client=llm_mock,
        dispatcher=dispatcher_mock,
        parser=parser_mock,
        options=OrchestratorOptions(config=config),
    )

    context = make_context_with_runtime_rules()
    async for _step in orchestrator.run_stream("Hello", context=context):
        pass

    llm_mock.generate.assert_awaited()
    call_kwargs = llm_mock.generate.call_args.kwargs
    assert "format" not in call_kwargs, (
        "format must be omitted when capability is UNKNOWN (safe default: do not assume support)"
    )


@pytest.mark.asyncio
async def test_orchestrator_static_ollama_version_override_works() -> None:
    """Static ollama_version config bypasses remote query and classifies correctly."""
    llm_mock = MagicMock(spec=LLMClient)
    llm_mock.generate = AsyncMock(return_value=LLMGenerateResult(text="Direct answer"))
    # get_ollama_version should NOT be called when static override is set
    llm_mock.get_ollama_version = AsyncMock(return_value="0.3.0")

    parser_mock = MagicMock(spec=ToolParser)
    parser_mock.parse.side_effect = ToolParsingError("No JSON found")

    dispatcher_mock = MagicMock(spec=AsyncToolDispatcher)

    config = OrchestratorConfig(
        schema_config=SchemaConfig(
            use_native_constraint=True,
            ollama_version="1.0.0",  # static override: supported
        ),
    )
    orchestrator = AgentOrchestrator(
        llm_client=llm_mock,
        dispatcher=dispatcher_mock,
        parser=parser_mock,
        options=OrchestratorOptions(config=config),
    )

    context = make_context_with_runtime_rules()
    async for _step in orchestrator.run_stream("Hello", context=context):
        pass

    # Static override used → remote query NOT made
    llm_mock.get_ollama_version.assert_not_awaited()
    call_kwargs = llm_mock.generate.call_args.kwargs
    assert "format" in call_kwargs, "static override of supported version → format included"


@pytest.mark.asyncio
async def test_orchestrator_get_ollama_version_not_called_when_disabled() -> None:
    """When use_native_constraint=False, no version query is made at all."""
    llm_mock = MagicMock(spec=LLMClient)
    llm_mock.generate = AsyncMock(return_value=LLMGenerateResult(text="Direct answer"))
    llm_mock.get_ollama_version = AsyncMock(return_value="0.5.4")

    parser_mock = MagicMock(spec=ToolParser)
    parser_mock.parse.side_effect = ToolParsingError("No JSON found")

    dispatcher_mock = MagicMock(spec=AsyncToolDispatcher)

    config = OrchestratorConfig(
        schema_config=SchemaConfig(use_native_constraint=False),
    )
    orchestrator = AgentOrchestrator(
        llm_client=llm_mock,
        dispatcher=dispatcher_mock,
        parser=parser_mock,
        options=OrchestratorOptions(config=config),
    )

    context = make_context_with_runtime_rules()
    async for _step in orchestrator.run_stream("Hello", context=context):
        pass

    # Version query must NOT be made when native constraint is disabled
    llm_mock.get_ollama_version.assert_not_awaited()
    call_kwargs = llm_mock.generate.call_args.kwargs
    assert "format" not in call_kwargs


# ---------------------------------------------------------------------------
# 6. Schema-violation retry path (Step 2.2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schema_retry_recovers_after_one_invalid_response() -> None:
    """When the first response is schema-invalid and the second is valid.

    The orchestrator must re-issue the LLM call with the retry prompt and
    succeed without falling through to the legacy parser for step 1.
    """
    invalid_json = '{"name": "get_quote", "parameters": {"ticker": "AAPL"}}'
    valid_json = '{"tool_name": "get_quote", "tool_args": {"ticker": "AAPL"}}'
    terminal_text = "Apple is currently trading at $180."

    # Step 1: call1=invalid → retry → call2=valid → tool dispatched
    # Step 2: call3=text → retry → call4=text → parser(raises) → terminal
    llm_mock = MagicMock(spec=LLMClient)
    llm_mock.generate = AsyncMock(
        side_effect=[
            LLMGenerateResult(text=invalid_json),
            LLMGenerateResult(text=valid_json),
            LLMGenerateResult(text=terminal_text),
            LLMGenerateResult(text=terminal_text),
        ]
    )

    # Parser raises: proves it was NOT used for step 1 recovery
    parser_mock = MagicMock(spec=ToolParser)
    parser_mock.parse.side_effect = ToolParsingError("Parser must not be the recovery path")

    dispatcher_mock = MagicMock(spec=AsyncToolDispatcher)
    dispatcher_mock.dispatch = AsyncMock(
        return_value=ToolCallResult(
            call_id="call-retry",
            tool_name="get_quote",
            success=True,
            result={"price": 180.0},
        )
    )

    config = OrchestratorConfig(
        schema_config=SchemaConfig(
            use_native_constraint=True,
            max_validation_retries=1,
            ollama_version="0.5.4",
        ),
    )
    orchestrator = AgentOrchestrator(
        llm_client=llm_mock,
        dispatcher=dispatcher_mock,
        parser=parser_mock,
        options=OrchestratorOptions(config=config),
    )

    context = make_context_with_runtime_rules()
    steps = []
    async for step in orchestrator.run_stream("What is Apple price?", context=context):
        steps.append(step)

    # Step 1: 2 calls (invalid + valid retry). Step 2: 2 calls (text + retry text).
    assert llm_mock.generate.await_count == 4
    # Tool was dispatched from the valid retry response in step 1
    assert len(steps) == 2
    assert steps[0].is_terminal is False
    assert steps[0].executed_tools[0].result == {"price": 180.0}
    assert steps[1].is_terminal is True
    # Step 2 reaches the consecutive-violation cap before parser fallback.
    assert parser_mock.parse.call_count == 0
    assert orchestrator.last_reliability_failure is not None
    assert orchestrator.last_reliability_failure.reason is ReliabilityTripReason.SCHEMA_VIOLATION_LIMIT


@pytest.mark.asyncio
async def test_schema_retry_exhaustion_trips_circuit() -> None:
    """Consecutive invalid responses trip before compatibility fallback."""
    invalid_json = '{"name": "get_quote", "parameters": {"ticker": "AAPL"}}'
    terminal_text = "Apple is currently trading at $180."

    # Step 1: call1,2,3 all invalid → retries exhausted → parser succeeds → tool
    # Step 2: call4,5,6 all text → retries exhausted → parser fails → terminal
    llm_mock = MagicMock(spec=LLMClient)
    llm_mock.generate = AsyncMock(
        side_effect=[
            LLMGenerateResult(text=invalid_json),
            LLMGenerateResult(text=invalid_json),
            LLMGenerateResult(text=invalid_json),
            LLMGenerateResult(text=terminal_text),
            LLMGenerateResult(text=terminal_text),
            LLMGenerateResult(text=terminal_text),
        ]
    )

    # Step 1: parser succeeds (fallback). Step 2: parser fails (terminal).
    parser_mock = MagicMock(spec=ToolParser)
    parser_mock.parse.side_effect = [
        ParsedToolCall(tool_name="get_quote", arguments={"ticker": "AAPL"}),
        ToolParsingError("No JSON in final text"),
    ]

    dispatcher_mock = MagicMock(spec=AsyncToolDispatcher)
    dispatcher_mock.dispatch = AsyncMock(
        return_value=ToolCallResult(
            call_id="call-exhaust",
            tool_name="get_quote",
            success=True,
            result={"price": 180.0},
        )
    )

    config = OrchestratorConfig(
        schema_config=SchemaConfig(
            use_native_constraint=True,
            max_validation_retries=2,
            ollama_version="0.5.4",
        ),
    )
    orchestrator = AgentOrchestrator(
        llm_client=llm_mock,
        dispatcher=dispatcher_mock,
        parser=parser_mock,
        options=OrchestratorOptions(config=config),
    )

    context = make_context_with_runtime_rules()
    steps = []
    async for step in orchestrator.run_stream("What is Apple price?", context=context):
        steps.append(step)

    assert llm_mock.generate.await_count == 3
    assert parser_mock.parse.call_count == 0
    assert len(steps) == 1
    assert steps[0].is_terminal is True
    assert orchestrator.last_reliability_failure is not None
    assert orchestrator.last_reliability_failure.reason is ReliabilityTripReason.SCHEMA_VIOLATION_LIMIT


@pytest.mark.asyncio
async def test_schema_retry_does_not_use_parser_as_primary_recovery() -> None:
    """Even when the parser COULD handle the response, it must NOT be invoked.

    During the retry budget the retry prompt is the primary recovery mechanism.
    """
    invalid_json = '{"name": "get_quote", "parameters": {"ticker": "AAPL"}}'
    terminal_text = "Apple is currently trading at $180."

    # Step 1: call1=invalid → retry → call2=invalid → exhausted → parser(succeeds) → tool
    # Step 2: call3=text → retry → call4=text → exhausted → parser(fails) → terminal
    llm_mock = MagicMock(spec=LLMClient)
    llm_mock.generate = AsyncMock(
        side_effect=[
            LLMGenerateResult(text=invalid_json),
            LLMGenerateResult(text=invalid_json),
            LLMGenerateResult(text=terminal_text),
            LLMGenerateResult(text=terminal_text),
        ]
    )

    parser_mock = MagicMock(spec=ToolParser)
    parser_mock.parse.side_effect = [
        ParsedToolCall(tool_name="get_quote", arguments={"ticker": "AAPL"}),
        ToolParsingError("No JSON in final text"),
    ]

    dispatcher_mock = MagicMock(spec=AsyncToolDispatcher)
    dispatcher_mock.dispatch = AsyncMock(
        return_value=ToolCallResult(
            call_id="call-gate",
            tool_name="get_quote",
            success=True,
            result="ok",
        )
    )

    config = OrchestratorConfig(
        schema_config=SchemaConfig(
            use_native_constraint=True,
            max_validation_retries=1,
            ollama_version="0.5.4",
        ),
    )
    orchestrator = AgentOrchestrator(
        llm_client=llm_mock,
        dispatcher=dispatcher_mock,
        parser=parser_mock,
        options=OrchestratorOptions(config=config),
    )

    context = make_context_with_runtime_rules()
    steps = []
    async for step in orchestrator.run_stream("What is Apple price?", context=context):
        steps.append(step)

    # Step 1 reaches the cap after the initial response and one retry.
    assert llm_mock.generate.await_count == 2
    # The second consecutive violation trips before parser fallback or tool work.
    assert parser_mock.parse.call_count == 0
    assert orchestrator.last_reliability_failure is not None
    assert orchestrator.last_reliability_failure.reason is ReliabilityTripReason.SCHEMA_VIOLATION_LIMIT
    # Verify the retry feedback message was injected into context
    msgs = context.get_messages()
    user_msgs = [m for m in msgs if m.role == Role.USER]
    retry_feedback_msgs = [
        m for m in user_msgs if "schema" in m.content.lower() or "did not match" in m.content.lower()
    ]
    assert len(retry_feedback_msgs) >= 1, "retry feedback message must be present in context"


@pytest.mark.asyncio
async def test_provider_compat_parser_fallback_when_native_disabled() -> None:
    """When use_native_constraint is False, the legacy parser IS the recovery path.

    The provider-compatibility mode expects the parser for non-JSON responses.
    No retry loop should be triggered (max_retries is forced to 0).
    """
    llm_mock = MagicMock(spec=LLMClient)
    llm_mock.generate = AsyncMock(
        side_effect=[
            LLMGenerateResult(text='{"name": "get_quote", "parameters": {"ticker": "AAPL"}}'),
            LLMGenerateResult(text="Apple is currently trading at $180."),
        ]
    )

    # Step 1: parser succeeds → tool. Step 2: parser fails → terminal.
    parser_mock = MagicMock(spec=ToolParser)
    parser_mock.parse.side_effect = [
        ParsedToolCall(tool_name="get_quote", arguments={"ticker": "AAPL"}),
        ToolParsingError("No JSON in final text"),
    ]

    dispatcher_mock = MagicMock(spec=AsyncToolDispatcher)
    dispatcher_mock.dispatch = AsyncMock(
        return_value=ToolCallResult(
            call_id="call-compat",
            tool_name="get_quote",
            success=True,
            result={"price": 180.0},
        )
    )

    config = OrchestratorConfig(
        schema_config=SchemaConfig(
            use_native_constraint=False,
            max_validation_retries=3,  # must be ignored when native is off
        ),
    )
    orchestrator = AgentOrchestrator(
        llm_client=llm_mock,
        dispatcher=dispatcher_mock,
        parser=parser_mock,
        options=OrchestratorOptions(config=config),
    )

    context = make_context_with_runtime_rules()
    steps = []
    async for step in orchestrator.run_stream("What is Apple price?", context=context):
        steps.append(step)

    # Exactly one LLM call per step (no retries when native is disabled)
    assert llm_mock.generate.await_count == 2
    # Parser is the immediate fallback (one call per step)
    assert parser_mock.parse.call_count == 2
    # Tool executed in step 1
    assert len(steps) == 2
    assert steps[0].is_terminal is False
    assert steps[0].executed_tools[0].result == {"price": 180.0}
    assert steps[1].is_terminal is True
    # No retry feedback messages in context (retry loop was never entered)
    user_msgs = [m for m in context.get_messages() if m.role == Role.USER]
    retry_msgs = [m for m in user_msgs if "schema" in m.content.lower() or "did not match" in m.content.lower()]
    assert len(retry_msgs) == 0, "no retry feedback when native constraint is disabled"


# ---------------------------------------------------------------------------
# 7. Prompt-fallback (fallback_to_prompt) behaviour (Step 2.2)
# ---------------------------------------------------------------------------


def _find_schema_instruction(messages: list[dict[str, str]]) -> dict[str, str] | None:
    """Locate a system-role message that carries the explicit schema instruction."""
    for msg in messages:
        if msg.get("role") != "system":
            continue
        content = msg.get("content", "")
        if "JSON Schema" in content and "Schema:" in content:
            return msg
    return None


@pytest.mark.asyncio
async def test_prompt_fallback_injects_schema_when_native_unsupported() -> None:
    """Native capability False + fallback_to_prompt=True → prompt injected, no format.

    The orchestrator must:
      * NOT send the native ``format`` kwarg (server is known-unsupported).
      * Inject an explicit JSON-schema instruction message into the prompt.
      * Reuse the existing Pydantic validation/retry loop.
    """
    invalid_json = '{"name": "get_quote", "parameters": {"ticker": "AAPL"}}'
    valid_json = '{"tool_name": "get_quote", "tool_args": {"ticker": "AAPL"}}'

    llm_mock = MagicMock(spec=LLMClient)
    llm_mock.generate = AsyncMock(
        side_effect=[
            LLMGenerateResult(text=invalid_json),
            LLMGenerateResult(text=valid_json),
        ]
    )
    llm_mock.get_ollama_version = AsyncMock(return_value="0.3.0")  # known-unsupported

    # Parser must NOT be used as primary recovery; only as last resort if retries exhaust.
    parser_mock = MagicMock(spec=ToolParser)
    parser_mock.parse.side_effect = ToolParsingError("Parser must not be the recovery path")

    dispatcher_mock = MagicMock(spec=AsyncToolDispatcher)
    dispatcher_mock.dispatch = AsyncMock(
        return_value=ToolCallResult(
            call_id="call-prompt-fb",
            tool_name="get_quote",
            success=True,
            result={"price": 180.0},
        )
    )

    config = OrchestratorConfig(
        max_steps=1,
        schema_config=SchemaConfig(
            use_native_constraint=True,
            fallback_to_prompt=True,
            max_validation_retries=1,
        ),
    )
    orchestrator = AgentOrchestrator(
        llm_client=llm_mock,
        dispatcher=dispatcher_mock,
        parser=parser_mock,
        options=OrchestratorOptions(config=config),
    )

    context = make_context_with_runtime_rules()
    steps = []
    async for step in orchestrator.run_stream("What is Apple price?", context=context):
        steps.append(step)

    # Two calls: initial (invalid) + one retry (valid)
    assert llm_mock.generate.await_count == 2
    # Tool executed from the valid retry response — parser NOT used.
    assert steps[0].is_terminal is False
    assert steps[0].executed_tools[0].result == {"price": 180.0}
    assert parser_mock.parse.call_count == 0, "parser must NOT be the primary recovery in prompt mode"

    # Native format must NOT be sent (server known-unsupported)
    first_kwargs = llm_mock.generate.await_args_list[0].kwargs
    assert "format" not in first_kwargs, "native format must be omitted in prompt-fallback mode"

    # Explicit schema instruction must be present in the prompt payload
    first_prompt = first_kwargs["prompt"]
    instr = _find_schema_instruction(first_prompt)
    assert instr is not None, "schema instruction message must be injected in prompt-fallback mode"
    assert "tool_name" in instr["content"]
    assert "tool_args" in instr["content"]

    # The retry call's payload must still carry the instruction (build_retry_messages copies verbatim)
    second_prompt = llm_mock.generate.await_args_list[1].kwargs["prompt"]
    assert _find_schema_instruction(second_prompt) is not None, "schema instruction must persist across retries"


@pytest.mark.asyncio
async def test_prompt_fallback_injects_schema_when_capability_unknown() -> None:
    """Native capability UNKNOWN + fallback_to_prompt=True → prompt injected, no format.

    The unknown-capability safe default (no native constraint) is preserved,
    but the explicit prompt-level instruction is added.
    """
    valid_json = '{"tool_name": "get_quote", "tool_args": {"ticker": "AAPL"}}'

    llm_mock = MagicMock(spec=LLMClient)
    llm_mock.generate = AsyncMock(return_value=LLMGenerateResult(text=valid_json))
    llm_mock.get_ollama_version = AsyncMock(return_value=None)  # unknown

    parser_mock = MagicMock(spec=ToolParser)
    parser_mock.parse.side_effect = ToolParsingError("not used")

    dispatcher_mock = MagicMock(spec=AsyncToolDispatcher)
    dispatcher_mock.dispatch = AsyncMock(
        return_value=ToolCallResult(
            call_id="call-unknown-fb",
            tool_name="get_quote",
            success=True,
            result={"price": 180.0},
        )
    )

    config = OrchestratorConfig(
        schema_config=SchemaConfig(
            use_native_constraint=True,
            fallback_to_prompt=True,
            max_validation_retries=0,
        ),
    )
    orchestrator = AgentOrchestrator(
        llm_client=llm_mock,
        dispatcher=dispatcher_mock,
        parser=parser_mock,
        options=OrchestratorOptions(config=config),
    )

    context = make_context_with_runtime_rules()
    async for _step in orchestrator.run_stream("What is Apple price?", context=context):
        pass

    first_kwargs = llm_mock.generate.await_args_list[0].kwargs
    assert "format" not in first_kwargs, "unknown capability → native format omitted"
    first_prompt = first_kwargs["prompt"]
    instr = _find_schema_instruction(first_prompt)
    assert instr is not None, "schema instruction must be injected when capability unknown + fallback on"
    assert "tool_name" in instr["content"]


@pytest.mark.asyncio
async def test_prompt_fallback_disabled_no_injection_no_retries() -> None:
    """Native capability False + fallback_to_prompt=False → no injection, no retry loop.

    The legacy provider-compat behaviour is preserved: no format kwarg, no
    prompt injection, no Pydantic retry loop, parser as immediate recovery.
    """
    invalid_json = '{"name": "get_quote", "parameters": {"ticker": "AAPL"}}'

    llm_mock = MagicMock(spec=LLMClient)
    llm_mock.generate = AsyncMock(return_value=LLMGenerateResult(text=invalid_json))
    llm_mock.get_ollama_version = AsyncMock(return_value="0.3.0")

    # Parser succeeds → tool recovered without retry.
    parser_mock = MagicMock(spec=ToolParser)
    parser_mock.parse.return_value = ParsedToolCall(tool_name="get_quote", arguments={"ticker": "AAPL"})

    dispatcher_mock = MagicMock(spec=AsyncToolDispatcher)
    dispatcher_mock.dispatch = AsyncMock(
        return_value=ToolCallResult(
            call_id="call-no-fb",
            tool_name="get_quote",
            success=True,
            result={"price": 180.0},
        )
    )

    config = OrchestratorConfig(
        max_steps=1,
        schema_config=SchemaConfig(
            use_native_constraint=True,
            fallback_to_prompt=False,
            max_validation_retries=3,  # must be ignored: no retry loop in this mode
        ),
    )
    orchestrator = AgentOrchestrator(
        llm_client=llm_mock,
        dispatcher=dispatcher_mock,
        parser=parser_mock,
        options=OrchestratorOptions(config=config),
    )

    context = make_context_with_runtime_rules()
    steps = []
    async for step in orchestrator.run_stream("What is Apple price?", context=context):
        steps.append(step)

    # Only ONE LLM call: no retry loop was entered.
    assert llm_mock.generate.await_count == 1
    # Native format is NOT sent (capability unsupported)
    first_kwargs = llm_mock.generate.await_args_list[0].kwargs
    assert "format" not in first_kwargs
    # No prompt-level schema instruction is injected.
    first_prompt = first_kwargs["prompt"]
    assert _find_schema_instruction(first_prompt) is None, (
        "schema instruction must NOT be injected when fallback_to_prompt=False"
    )
    # Parser is the immediate recovery (one call).
    assert parser_mock.parse.call_count == 1
    assert steps[0].is_terminal is False
    assert steps[0].executed_tools[0].result == {"price": 180.0}


@pytest.mark.asyncio
async def test_fallback_to_prompt_ignored_when_use_native_constraint_false() -> None:
    """When use_native_constraint=False, fallback_to_prompt has no effect.

    The flag is scoped to the native-constraint branch; the legacy
    provider-compat behaviour (parser-as-recovery, no retry loop, no
    format, no prompt injection) must be preserved unconditionally.
    """
    invalid_json = '{"name": "get_quote", "parameters": {"ticker": "AAPL"}}'

    llm_mock = MagicMock(spec=LLMClient)
    llm_mock.generate = AsyncMock(return_value=LLMGenerateResult(text=invalid_json))
    llm_mock.get_ollama_version = AsyncMock(return_value="0.6.1")  # would support native if asked

    parser_mock = MagicMock(spec=ToolParser)
    parser_mock.parse.return_value = ParsedToolCall(tool_name="get_quote", arguments={"ticker": "AAPL"})

    dispatcher_mock = MagicMock(spec=AsyncToolDispatcher)
    dispatcher_mock.dispatch = AsyncMock(
        return_value=ToolCallResult(
            call_id="call-legacy",
            tool_name="get_quote",
            success=True,
            result={"price": 180.0},
        )
    )

    config = OrchestratorConfig(
        max_steps=1,
        schema_config=SchemaConfig(
            use_native_constraint=False,
            fallback_to_prompt=True,  # must be ignored in this branch
            max_validation_retries=5,  # must be ignored in this branch
        ),
    )
    orchestrator = AgentOrchestrator(
        llm_client=llm_mock,
        dispatcher=dispatcher_mock,
        parser=parser_mock,
        options=OrchestratorOptions(config=config),
    )

    context = make_context_with_runtime_rules()
    async for _step in orchestrator.run_stream("What is Apple price?", context=context):
        pass

    # No version query (explicit opt-out)
    llm_mock.get_ollama_version.assert_not_awaited()
    # No retry loop
    assert llm_mock.generate.await_count == 1
    # No native format
    first_kwargs = llm_mock.generate.await_args_list[0].kwargs
    assert "format" not in first_kwargs
    # No prompt injection
    first_prompt = first_kwargs["prompt"]
    assert _find_schema_instruction(first_prompt) is None, (
        "fallback_to_prompt must NOT take effect when use_native_constraint=False"
    )
    # Parser is the immediate recovery
    assert parser_mock.parse.call_count == 1


@pytest.mark.asyncio
async def test_prompt_fallback_retry_persists_instruction_across_retries() -> None:
    """The prompt-level schema instruction must survive the retry loop.

    ``build_retry_messages`` copies the original message list verbatim, so
    the schema instruction injected on the initial attempt must still be
    present on every subsequent retry call.
    """
    invalid_json = '{"name": "get_quote", "parameters": {"ticker": "AAPL"}}'
    valid_json = '{"tool_name": "get_quote", "tool_args": {"ticker": "AAPL"}}'

    llm_mock = MagicMock(spec=LLMClient)
    llm_mock.generate = AsyncMock(
        side_effect=[
            LLMGenerateResult(text=invalid_json),  # attempt 1
            LLMGenerateResult(text=invalid_json),  # retry 1 (still invalid)
            LLMGenerateResult(text=valid_json),  # retry 2 (valid)
        ]
    )
    llm_mock.get_ollama_version = AsyncMock(return_value="0.3.0")

    parser_mock = MagicMock(spec=ToolParser)
    parser_mock.parse.side_effect = ToolParsingError("not used")

    dispatcher_mock = MagicMock(spec=AsyncToolDispatcher)
    dispatcher_mock.dispatch = AsyncMock(
        return_value=ToolCallResult(
            call_id="call-persist",
            tool_name="get_quote",
            success=True,
            result={"price": 180.0},
        )
    )

    config = OrchestratorConfig(
        max_steps=1,
        schema_config=SchemaConfig(
            use_native_constraint=True,
            fallback_to_prompt=True,
            max_validation_retries=2,
        ),
    )
    orchestrator = AgentOrchestrator(
        llm_client=llm_mock,
        dispatcher=dispatcher_mock,
        parser=parser_mock,
        options=OrchestratorOptions(config=config),
    )

    context = make_context_with_runtime_rules()
    steps = []
    async for step in orchestrator.run_stream("What is Apple price?", context=context):
        steps.append(step)

    # 3 calls: initial + 2 retries; parser not used
    assert llm_mock.generate.await_count == 3
    assert parser_mock.parse.call_count == 0
    assert steps[0].executed_tools[0].result == {"price": 180.0}

    # Every call (initial + both retries) must carry the schema instruction.
    for i, call in enumerate(llm_mock.generate.await_args_list):
        prompt = call.kwargs["prompt"]
        assert _find_schema_instruction(prompt) is not None, f"schema instruction missing on call #{i}"
        # Native format must NOT be present on any call
        assert "format" not in call.kwargs, f"native format leaked on call #{i}"
