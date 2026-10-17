"""Typed trajectory telemetry event models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class TrajectoryEventType(StrEnum):
    """Initial Step 2.1 trajectory event vocabulary."""

    RUN_START = "run_start"
    STEP_START = "step_start"
    PROMPT_SENT = "prompt_sent"
    LLM_RESPONSE = "llm_response"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    RECOVERY_ATTEMPTED = "recovery_attempted"
    STEP_END = "step_end"
    RUN_END = "run_end"


class TelemetryMode(StrEnum):
    """Supported execution modes recorded with every trajectory event."""

    LIGHT = "light"
    FULL = "full"


class TrajectoryEvent(BaseModel):
    """A single machine-readable observation belonging to one run."""

    model_config = ConfigDict(extra="forbid")

    event_id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    session_id: UUID
    sequence: int = Field(ge=1)
    timestamp: datetime
    event_type: TrajectoryEventType
    component: str
    schema_version: int = Field(default=1, ge=1)
    mode: TelemetryMode

    # Causality fields: span_id identifies the logical operation represented by
    # the event; parent_span_id identifies the operation that caused it.
    span_id: UUID
    parent_span_id: UUID | None = None

    model_tag: str | None = None
    provider: str | None = None
    step_index: int | None = Field(default=None, ge=1)
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    tool_result_summary: Any | None = None
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    latency_ms: float | None = Field(default=None, ge=0)
    payload: Any | None = None
    payload_hash: str | None = None
    error: dict[str, Any] | None = None

    def to_json_line(self) -> str:
        """Serialize the event deterministically for JSONL persistence."""
        return self.model_dump_json(exclude_none=True, by_alias=True)
