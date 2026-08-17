"""Pydantic models for LLM structured output.

These models define the expected shape of responses from Ollama when
native schema constraints are applied. They serve as both the source
for JSON Schema generation and the second-line validation layer.

All models use extra="forbid" so that unexpected fields are rejected
during Pydantic validation (aligning with additionalProperties: false
in the emitted JSON Schema).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ToolCallStatus(StrEnum):
    """Status of a tool call execution."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"


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


class PlanStep(BaseModel):
    """A single step in an execution plan."""

    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(..., description="Unique identifier for this step")
    description: str = Field(..., description="Human-readable description")
    tool_name: str | None = Field(None, description="Tool to execute, if any")
    dependencies: list[str] = Field(
        default_factory=list,
        description="Step IDs that must complete before this step",
    )


class PlanResponse(BaseModel):
    """Structured response for planning output.

    Used when the LLM generates a multi-step execution plan.
    """

    model_config = ConfigDict(extra="forbid")

    goal: str = Field(..., description="Overall goal of the plan")
    steps: list[PlanStep] = Field(..., description="Ordered steps to execute")
    estimated_duration_seconds: int | None = Field(
        None,
        description="Estimated duration in seconds",
    )

    @field_validator("steps")
    @classmethod
    def validate_steps_non_empty(cls, v: list[PlanStep]) -> list[PlanStep]:
        """Ensure at least one step is present."""
        if not v:
            raise ValueError("Plan must contain at least one step")
        return v


class SynthesisResponse(BaseModel):
    """Structured response for final synthesis/narrative output.

    Used when the LLM produces the final investment analysis synthesis.
    """

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(..., description="Executive summary")
    key_findings: list[str] = Field(
        default_factory=list,
        description="Key findings from the analysis",
    )
    recommendation: str | None = Field(None, description="Recommended action")
    confidence_score: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0 and 1",
    )
    metrics: dict[str, float | int | str] = Field(
        default_factory=dict,
        description="Quantitative metrics from the analysis",
    )

    @field_validator("confidence_score")
    @classmethod
    def validate_confidence(cls, v: float | None) -> float | None:
        """Ensure confidence score is within valid range."""
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("confidence_score must be between 0 and 1")
        return v


# Prefer concrete models; keep the structured-output contract strong.
StructuredResponse = ToolCallResponse | PlanResponse | SynthesisResponse


def model_to_json_schema(model_class: type[BaseModel]) -> dict[str, Any]:
    """Convert a Pydantic model to JSON Schema format.

    Uses the default mode so that $defs / $ref are emitted when needed.
    Ollama's structured-output path accepts schemas that contain $defs.
    """
    return model_class.model_json_schema()
