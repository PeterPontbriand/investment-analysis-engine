from typing import Any

import httpx
from pydantic import BaseModel, Field

from src.config import settings


class LLMResponse(BaseModel):
    """Response model for the LLM."""

    response: str


class LLMGenerateResult(BaseModel):
    """Text plus optional provider usage (never invent token counts)."""

    text: str
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)


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
    ) -> LLMGenerateResult:
        """Generate a response and surface Ollama usage when the API provides it."""
        target_model = model or self.default_model

        options: dict[str, Any] = {}
        if temperature is not None:
            options["temperature"] = temperature

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
                text = str(parsed_obj)
            else:
                text = str(data.get("response", data))

            return LLMGenerateResult(
                text=text,
                prompt_tokens=_optional_nonneg_int(data.get("prompt_eval_count")),
                completion_tokens=_optional_nonneg_int(data.get("eval_count")),
            )

        except httpx.HTTPError as e:
            print(f"HTTP error occurred: {e}")
            raise
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            raise

    async def close(self) -> None:
        """Close the client connection."""
        await self.client.aclose()


def _optional_nonneg_int(value: Any) -> int | None:
    """Return a non-negative int, or None when the provider omitted/invalidated usage."""
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None
