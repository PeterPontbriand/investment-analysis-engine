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
        # Intentionally named `format` to mirror the Ollama structured-outputs
        # contract and the kwargs produced by ``src.schema.constraint``.
        format: dict[str, Any] | str | None = None,  # noqa: A002
    ) -> LLMGenerateResult:
        """Generate a response and surface Ollama usage when the API provides it.

        Args:
            prompt: Chat messages or a plain prompt string.
            model: Optional model override; falls back to the client default.
            temperature: Optional sampling temperature sent via ``options``.
            response_model: Optional Pydantic model used to parse the response.
            format: Optional Ollama structured-outputs constraint. May be the
                string ``"json"`` or a full JSON Schema object. Forwarded as a
                top-level ``format`` key, per the Ollama contract documented in
                ``src/schema/constraint.py``. Omitted from the request body when
                ``None`` to preserve existing behaviour.
        """
        target_model = model or self.default_model

        options: dict[str, Any] = {}
        if temperature is not None:
            options["temperature"] = temperature

        body: dict[str, Any] = {
            "messages": prompt,
            "target_model": target_model,
            "options": options,
        }
        if format is not None:
            body["format"] = format

        try:
            response = await self.client.post(
                "/generate",
                json=body,
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

    async def get_ollama_version(self) -> str | None:
        """Query the remote Ollama server for its version.

        Calls ``GET /api/version`` on the configured remote endpoint.
        Returns the version string (e.g. ``"0.5.4"``) or ``None`` if the
        request fails or the response is unexpected.

        Returns:
            The Ollama server version string, or None on failure.
        """
        try:
            response = await self.client.get("/api/version", timeout=5.0)
            response.raise_for_status()
            data = response.json()
            version = data.get("version")
            return version if isinstance(version, str) and version else None
        except (httpx.HTTPError, ValueError):
            return None

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
