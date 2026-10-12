"""Typed execution limits for one orchestration run."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReliabilityLimits(BaseModel):
    """Immutable execution limits applied to one orchestration run."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    max_steps: int = Field(default=10, ge=1, le=50)
    max_transient_retries: int = Field(default=3, ge=0)
    max_consecutive_schema_violations: int = Field(default=4, ge=1)
    overall_timeout_seconds: float = Field(default=300.0, gt=0)
    step_timeout_seconds: float = Field(default=180.0, gt=0)
    llm_call_timeout_seconds: float = Field(default=120.0, gt=0)
    tool_call_timeout_seconds: float = Field(default=60.0, gt=0)
    recent_diagnostic_events: int = Field(default=5, ge=1)

    @model_validator(mode="after")
    def validate_schema_retry_cap(self) -> ReliabilityLimits:
        """Keep corrective schema retries within the general retry budget."""
        schema_retries = self.max_consecutive_schema_violations - 1
        if schema_retries > self.max_transient_retries:
            raise ValueError("Schema retries cannot exceed max_transient_retries.")
        return self

    @property
    def max_schema_validation_retries(self) -> int:
        """Return corrective retries implied by the consecutive-violation cap."""
        return self.max_consecutive_schema_violations - 1
