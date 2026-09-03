import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.llm.client import LLMClient, LLMGenerateResult
from src.orchestrator.context import ContextConfig, MessageContext
from src.orchestrator.loop import AgentOrchestrator, OrchestratorConfig, OrchestratorOptions
from src.orchestrator.prompts import SystemPromptBuilder
from src.schema.config import SchemaConfig
from src.tools.parser import ToolParsingError


def test_llm_client_init() -> None:
    """Verify LLMClient initializes cleanly."""
    client = LLMClient(base_url="http://example.com")
    assert client is not None


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_llm_client_generate_success(mock_post: AsyncMock) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "message": {"role": "assistant", "content": "Hello world"},
        "prompt_eval_count": 11,
        "eval_count": 3,
    }
    mock_post.return_value = mock_response

    client = LLMClient(base_url="http://example.com")
    messages = [{"role": "user", "content": "Hello world"}]

    result = await client.generate(messages)

    assert isinstance(result, LLMGenerateResult)
    assert result.text == "Hello world"
    assert result.prompt_tokens == 11
    assert result.completion_tokens == 3


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_llm_client_generate_missing_usage(mock_post: AsyncMock) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"message": {"role": "assistant", "content": "Hello world"}}
    mock_post.return_value = mock_response

    client = LLMClient(base_url="http://example.com")
    result = await client.generate([{"role": "user", "content": "hi"}])

    assert result.text == "Hello world"
    assert result.prompt_tokens is None
    assert result.completion_tokens is None


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_llm_client_generate_with_schema_format(mock_post: AsyncMock) -> None:
    """format=<dict> is forwarded as a top-level body key."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"message": {"role": "assistant", "content": '{"tool_name": "get_price"}'}}
    mock_post.return_value = mock_response

    schema = {
        "type": "object",
        "properties": {"tool_name": {"type": "string"}},
        "required": ["tool_name"],
    }

    client = LLMClient(base_url="http://example.com")
    await client.generate(
        [{"role": "user", "content": "Get price"}],
        model="llama3",
        temperature=0.1,
        format=schema,
    )

    mock_post.assert_awaited_once()
    body = mock_post.call_args.kwargs["json"]
    assert body["format"] == schema
    assert body["messages"] == [{"role": "user", "content": "Get price"}]
    assert body["model"] == "llama3"
    assert body["stream"] is False
    assert body["options"]["temperature"] == 0.1
    assert mock_post.call_args.args[0] == "/api/chat"
    # `format` must NOT be nested under options.
    assert "format" not in body["options"]


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_llm_client_generate_with_json_string_format(mock_post: AsyncMock) -> None:
    """format="json" (string) is forwarded verbatim."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"message": {"role": "assistant", "content": "{}"}}
    mock_post.return_value = mock_response

    client = LLMClient(base_url="http://example.com")
    await client.generate([{"role": "user", "content": "hi"}], format="json")

    body = mock_post.call_args.kwargs["json"]
    assert body["format"] == "json"
    assert "format" not in body["options"]


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_llm_client_generate_omits_format_when_none(mock_post: AsyncMock) -> None:
    """When format is None, the body must not contain a format key."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"message": {"role": "assistant", "content": "hello"}}
    mock_post.return_value = mock_response

    client = LLMClient(base_url="http://example.com")
    await client.generate([{"role": "user", "content": "hi"}])

    body = mock_post.call_args.kwargs["json"]
    assert "format" not in body
    assert "format" not in body["options"]
    assert "messages" in body
    assert "model" in body
    assert "options" in body
    assert body["stream"] is False


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_llm_client_plain_prompt_uses_native_generate_endpoint(mock_post: AsyncMock) -> None:
    """Plain prompts use Ollama's generate endpoint and native request keys."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "hello"}
    mock_post.return_value = mock_response

    client = LLMClient(base_url="http://example.com", default_model="test-model")
    result = await client.generate("hello")

    assert result.text == "hello"
    mock_post.assert_awaited_once_with(
        "/api/generate",
        json={"model": "test-model", "options": {}, "stream": False, "prompt": "hello"},
        timeout=None,
    )


# --- get_ollama_version tests -------------------------------------------------


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_get_ollama_version_success(mock_get: AsyncMock) -> None:
    """Version endpoint returns the server version string."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"version": "0.5.4"}
    mock_get.return_value = mock_response

    client = LLMClient(base_url="http://remote:11434")
    version = await client.get_ollama_version()

    assert version == "0.5.4"
    # Verify it hit the /api/version path on the remote endpoint
    mock_get.assert_awaited_once()
    assert mock_get.call_args.args[0] == "/api/version"


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_get_ollama_version_1_x(mock_get: AsyncMock) -> None:
    """Version 1.x is correctly surfaced."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"version": "1.0.2"}
    mock_get.return_value = mock_response

    client = LLMClient(base_url="http://remote:11434")
    version = await client.get_ollama_version()
    assert version == "1.0.2"


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_get_ollama_version_http_error_returns_none(mock_get: AsyncMock) -> None:
    """HTTP error → None (unknown capability)."""
    mock_get.side_effect = httpx.ConnectError("connection refused")

    client = LLMClient(base_url="http://unreachable:11434")
    version = await client.get_ollama_version()
    assert version is None


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_get_ollama_version_missing_key_returns_none(mock_get: AsyncMock) -> None:
    """Response without 'version' key → None."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "ok"}
    mock_get.return_value = mock_response

    client = LLMClient(base_url="http://remote:11434")
    version = await client.get_ollama_version()
    assert version is None


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_get_ollama_version_non_string_returns_none(mock_get: AsyncMock) -> None:
    """Non-string version value → None."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"version": 42}
    mock_get.return_value = mock_response

    client = LLMClient(base_url="http://remote:11434")
    version = await client.get_ollama_version()
    assert version is None


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_get_ollama_version_empty_string_returns_none(mock_get: AsyncMock) -> None:
    """Empty version string → None."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"version": ""}
    mock_get.return_value = mock_response

    client = LLMClient(base_url="http://remote:11434")
    version = await client.get_ollama_version()
    assert version is None


# --- Integration test: orchestrator → LLMClient → wire (httpx.MockTransport) ---


@pytest.mark.asyncio
async def test_integration_format_reaches_wire_when_capability_supported() -> None:
    """Integration: AgentOrchestrator → LLMClient → HTTP wire.

    Uses httpx.MockTransport to intercept the actual HTTP requests. Verifies
    that when the remote server reports a supported version, the outgoing
    /api/chat body contains the ``format`` key with the JSON Schema.
    """
    captured_requests: list[httpx.Request] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.6.1"})
        return httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": "I will not call any tools."},
                "prompt_eval_count": 10,
                "eval_count": 5,
            },
        )

    transport = httpx.MockTransport(mock_handler)

    # Create a real LLMClient (with transport injected)
    client = LLMClient(base_url="http://10.0.0.5:11434")
    # Replace the underlying httpx client with one using MockTransport
    client.client = httpx.AsyncClient(
        base_url="http://10.0.0.5:11434",
        timeout=10.0,
        transport=transport,
    )

    parser_mock = MagicMock()
    parser_mock.parse.side_effect = ToolParsingError("No JSON found")
    dispatcher_mock = MagicMock()
    dispatcher_mock.dispatch = AsyncMock()

    config = OrchestratorConfig(
        schema_config=SchemaConfig(use_native_constraint=True),
    )
    orchestrator = AgentOrchestrator(
        llm_client=client,
        dispatcher=dispatcher_mock,
        parser=parser_mock,
        options=OrchestratorOptions(config=config),
    )

    builder = SystemPromptBuilder(inject_runtime_rules=False)
    system_prompt = builder.build()
    ctx_config = ContextConfig(max_history_messages=30, preserve_system_prompt=True)
    context = MessageContext(config=ctx_config)
    context.set_system_prompt(system_prompt)

    async for _step in orchestrator.run_stream("Hello", context=context):
        pass

    # Verify the native chat request was captured and contains format.
    generate_requests = [r for r in captured_requests if r.url.path == "/api/chat"]
    assert len(generate_requests) >= 1, "Expected at least one /api/chat request"

    body = json.loads(generate_requests[0].content)
    assert "format" in body, "Integration: format must be present in the wire body"
    assert body["format"]["type"] == "object"
    assert "tool_name" in body["format"]["properties"]
    assert body["model"] == "qwen2.5-coder:latest"
    assert body["stream"] is False

    # Verify the version endpoint was queried (capability detection occurred)
    version_requests = [r for r in captured_requests if r.url.path == "/api/version"]
    assert len(version_requests) >= 1, "Capability detection must query /api/version"


@pytest.mark.asyncio
async def test_integration_format_absent_from_wire_when_capability_unsupported() -> None:
    """Integration: unsupported server version → format NOT on wire.

    Uses httpx.MockTransport. Remote server reports 0.3.0 (unsupported).
    The /api/chat body must NOT contain a format key.
    """
    captured_requests: list[httpx.Request] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.3.0"})
        return httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": "No tools needed."},
                "prompt_eval_count": 5,
                "eval_count": 3,
            },
        )

    transport = httpx.MockTransport(mock_handler)

    client = LLMClient(base_url="http://10.0.0.5:11434")
    client.client = httpx.AsyncClient(
        base_url="http://10.0.0.5:11434",
        timeout=10.0,
        transport=transport,
    )

    parser_mock = MagicMock()
    parser_mock.parse.side_effect = ToolParsingError("No JSON found")
    dispatcher_mock = MagicMock()
    dispatcher_mock.dispatch = AsyncMock()

    config = OrchestratorConfig(
        schema_config=SchemaConfig(use_native_constraint=True),
    )
    orchestrator = AgentOrchestrator(
        llm_client=client,
        dispatcher=dispatcher_mock,
        parser=parser_mock,
        options=OrchestratorOptions(config=config),
    )

    builder = SystemPromptBuilder(inject_runtime_rules=False)
    system_prompt = builder.build()
    ctx_config = ContextConfig(max_history_messages=30, preserve_system_prompt=True)
    context = MessageContext(config=ctx_config)
    context.set_system_prompt(system_prompt)

    async for _step in orchestrator.run_stream("Hi", context=context):
        pass

    generate_requests = [r for r in captured_requests if r.url.path == "/api/chat"]
    assert len(generate_requests) >= 1
    body = json.loads(generate_requests[0].content)
    assert "format" not in body, "Integration: format must NOT be on wire when server is known-unsupported"
