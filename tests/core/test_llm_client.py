from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.llm_client import LLMClient, LLMResponse


def test_llm_client_init() -> None:
    """Verify LLMClient initializes cleanly."""
    client = LLMClient(base_url="http://example.com")
    assert client is not None


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_llm_client_generate_success(mock_post: AsyncMock) -> None:
    """Verify async client request handling."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "Hello world"}
    mock_post.return_value = mock_response

    client = LLMClient(base_url="http://example.com")
    messages = [{"role": "user", "content": "Hello world"}]

    # Pass response_model as a keyword argument
    result = await client.generate(messages, response_model=LLMResponse)

    # Assert string output or match expected representation
    assert isinstance(result, str)
    assert "Hello world" in result
