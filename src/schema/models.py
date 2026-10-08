"""Pydantic models for LLM structured output.

These models define the expected shape of responses from Ollama when
native schema constraints are applied. They serve as both the source
for JSON Schema generation and the second-line validation layer.

All models use extra="forbid" so that unexpected fields are rejected
during Pydantic validation (aligning with additionalProperties: false
in the emitted JSON Schema).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ToolCallResponse(BaseModel):
    """Structured response for tool call extraction.

    Used when the LLM is asked to select and parameterize a tool call.
    """

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(..., description="Name of the tool to call")
    tool_args: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments to pass to the tool",
    )
    reasoning: str | None = Field(
        None,
        description="Reasoning behind the tool selection",
    )

    @field_validator("tool_name")
    @classmethod
    def validate_tool_name(cls, v: str) -> str:
        """Ensure tool name is non-empty and reasonably formatted."""
        if not v or not v.strip():
            raise ValueError("tool_name must be non-empty")
        if not v.replace("_", "").isalnum():
            raise ValueError("tool_name must be alphanumeric with underscores")
        return v.strip()


def model_to_json_schema(model_class: type[BaseModel]) -> dict[str, Any]:
    """Convert a Pydantic model to JSON Schema format.

    Uses the default mode so that $defs / $ref are emitted when needed.
    Ollama's structured-output path accepts schemas that contain $defs.
    """
    return model_class.model_json_schema()
