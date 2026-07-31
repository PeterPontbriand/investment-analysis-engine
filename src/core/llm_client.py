from typing import Any

import httpx
from pydantic import BaseModel

from src.core.config import settings


class LLMResponse(BaseModel):
    """Response model for the LLM."""

    response: str


class LLMClient:
    """A client for interacting with an LLM."""

    def __init__(self, base_url: str, default_model: str | None = None):
        """Initialize the LLM client with a base URL and default model."""
        self.client = httpx.AsyncClient(base_url=base_url)
        self.default_model = default_model or settings.model_selection

    async def generate(
        self,
        prompt: list[dict[str, Any]] | str,
        model: str | None = None,
        temperature: float | None = None,
        response_model: type[BaseModel] | None = None,
    ) -> str:
        """Generates a response from the LLM, optionally passing model and temperature overrides."""
        target_model = model or self.default_model

        # Pass options/temperature to Ollama payload
        options = {}
        if temperature is not None:
            options["temperature"] = temperature

        # ... execute Ollama API call with target_model and options
        try:
            response = await self.client.post(
                "/generate",
                json={"messages": prompt, "target_model": target_model, "options": options},
                timeout=None,
            )
            response.raise_for_status()
            data = response.json()

            if response_model is not None:
                parsed_obj = response_model(**data)
                return str(parsed_obj)

            # Fallback to returning the response string field or raw body
            return str(data.get("response", data))

        except httpx.HTTPError as e:
            print(f"HTTP error occurred: {e}")
            raise
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            raise

    async def close(self) -> None:
        """Close the client connection."""
        await self.client.aclose()
