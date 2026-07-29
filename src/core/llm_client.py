from typing import Any

import httpx
from pydantic import BaseModel


class LLMResponse(BaseModel):
    """Response model for the LLM."""

    response: str


class LLMClient:
    """A client for interacting with an LLM."""

    def __init__(self, base_url: str):
        """Initialize the LLM client with a base URL."""
        self.client = httpx.AsyncClient(base_url=base_url)

    async def generate(self, messages: list[dict[str, Any]], response_model: type[BaseModel]) -> Any:
        """Generate structured output from the LLM."""
        try:
            response = await self.client.post("/generate", json={"messages": messages}, timeout=None)
            response.raise_for_status()
            return response_model(**response.json())
        except httpx.HTTPError as e:
            print(f"HTTP error occurred: {e}")
            raise
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            raise

    async def close(self) -> None:
        """Close the client connection."""
        await self.client.aclose()
