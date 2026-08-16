from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.llm.client import LLMClient, LLMGenerateResult


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
        "response": "Hello world",
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
    mock_response.json.return_value = {"response": "Hello world"}
    mock_post.return_value = mock_response

    client = LLMClient(base_url="http://example.com")
    result = await client.generate([{"role": "user", "content": "hi"}])

    assert result.text == "Hello world"
    assert result.prompt_tokens is None
    assert result.completion_tokens is None
