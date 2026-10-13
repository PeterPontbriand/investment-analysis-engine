"""Sanitized recent-event summary that the trajectory recorder produces."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RecentEventSummary(BaseModel):
    """Sanitized trajectory metadata safe to include in terminal diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=1)
    event_type: str = Field(min_length=1)
    component: str = Field(min_length=1)
    step_index: int | None = Field(default=None, ge=1)
