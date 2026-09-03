"""Typed reliability policy and terminal-failure contracts for orchestration."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReliabilityTripReason(StrEnum):
    """Stable reasons for terminating an orchestration run at a reliability limit."""

    MAX_STEPS_EXCEEDED = "max_steps_exceeded"
    OVERALL_TIMEOUT = "overall_timeout"
    STEP_TIMEOUT = "step_timeout"
    LLM_TIMEOUT = "llm_timeout"
    TOOL_TIMEOUT = "tool_timeout"
    TRANSIENT_RETRY_LIMIT = "transient_retry_limit"
    SCHEMA_VIOLATION_LIMIT = "schema_violation_limit"


class CircuitState(StrEnum):
    """Request-scoped circuit state."""

    CLOSED = "closed"
    TRIPPED = "tripped"


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


class RecentEventSummary(BaseModel):
    """Sanitized trajectory metadata safe to include in terminal diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=1)
    event_type: str = Field(min_length=1)
    component: str = Field(min_length=1)
    step_index: int | None = Field(default=None, ge=1)


class ReliabilityFailure(BaseModel):
    """Structured terminal outcome produced when a reliability limit trips."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    reason: ReliabilityTripReason
    message: str = Field(min_length=1)
    run_id: UUID
    final_step: int | None = Field(default=None, ge=1)
    configured_limit: int | float = Field(ge=0)
    observed_value: int | float = Field(ge=0)
    recent_events: tuple[RecentEventSummary, ...] = ()
    cancellation_confirmed: bool | None = None


class CircuitSnapshot(BaseModel):
    """Immutable observable state for the request-scoped reliability controller."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    state: CircuitState = CircuitState.CLOSED
    trip_reason: ReliabilityTripReason | None = None
    transient_retries: int = Field(default=0, ge=0)
    consecutive_schema_violations: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_trip_reason(self) -> CircuitSnapshot:
        """Require a reason exactly when the circuit is tripped."""
        if self.state is CircuitState.TRIPPED and self.trip_reason is None:
            raise ValueError("A tripped circuit requires a trip_reason.")
        if self.state is CircuitState.CLOSED and self.trip_reason is not None:
            raise ValueError("A closed circuit cannot have a trip_reason.")
        return self


class MonotonicClock(Protocol):
    """Clock seam used to make deadline behavior deterministic in tests."""

    def now(self) -> float:
        """Return a monotonic time value in seconds."""
        ...


class SystemMonotonicClock:
    """Production monotonic clock."""

    def now(self) -> float:
        """Return the current monotonic time in seconds."""
        return time.monotonic()


@dataclass(frozen=True, slots=True)
class TimeoutBudget:
    """Effective timeout selected from operation, step, and run deadlines."""

    seconds: float
    reason: ReliabilityTripReason
    configured_limit: float


class ReliabilityLimitReachedError(Exception):
    """Internal control signal raised when the request-scoped circuit trips."""

    def __init__(
        self,
        reason: ReliabilityTripReason,
        *,
        configured_limit: int | float,
        observed_value: int | float,
        cancellation_confirmed: bool | None = None,
    ) -> None:
        """Initialize one classified reliability trip."""
        super().__init__(reason.value)
        self.reason = reason
        self.configured_limit = configured_limit
        self.observed_value = observed_value
        self.cancellation_confirmed = cancellation_confirmed


class CircuitBreaker:
    """Request-scoped monotonic deadlines and reliability counters."""

    def __init__(
        self,
        limits: ReliabilityLimits,
        clock: MonotonicClock | None = None,
    ) -> None:
        """Start a closed circuit and its overall monotonic deadline."""
        self.limits = limits
        self.clock = clock or SystemMonotonicClock()
        self._run_started_at = self.clock.now()
        self._overall_deadline = self._run_started_at + limits.overall_timeout_seconds
        self._step_started_at: float | None = None
        self._step_deadline: float | None = None
        self._state = CircuitState.CLOSED
        self._trip_reason: ReliabilityTripReason | None = None
        self._transient_retries = 0
        self._consecutive_schema_violations = 0

    @property
    def snapshot(self) -> CircuitSnapshot:
        """Return immutable observable circuit state."""
        return CircuitSnapshot(
            state=self._state,
            trip_reason=self._trip_reason,
            transient_retries=self._transient_retries,
            consecutive_schema_violations=self._consecutive_schema_violations,
        )

    def begin_step(self, step: int) -> None:
        """Check run/step limits and start the step deadline."""
        self._ensure_closed()
        now = self.clock.now()
        if now >= self._overall_deadline:
            self._raise_timeout(ReliabilityTripReason.OVERALL_TIMEOUT, now)
        if step > self.limits.max_steps:
            self.trip(
                ReliabilityTripReason.MAX_STEPS_EXCEEDED,
                configured_limit=self.limits.max_steps,
                observed_value=step,
            )
        self._step_started_at = now
        self._step_deadline = now + self.limits.step_timeout_seconds

    def timeout_budget(self, operation_reason: ReliabilityTripReason) -> TimeoutBudget:
        """Return the earliest applicable operation, step, or overall timeout."""
        self._ensure_closed()
        now = self.clock.now()
        if now >= self._overall_deadline:
            self._raise_timeout(ReliabilityTripReason.OVERALL_TIMEOUT, now)
        if self._step_deadline is not None and now >= self._step_deadline:
            self._raise_timeout(ReliabilityTripReason.STEP_TIMEOUT, now)

        operation_limit = self._operation_limit(operation_reason)
        candidates = [
            (self._overall_deadline, ReliabilityTripReason.OVERALL_TIMEOUT, self.limits.overall_timeout_seconds),
            (now + operation_limit, operation_reason, operation_limit),
        ]
        if self._step_deadline is not None:
            candidates.append(
                (self._step_deadline, ReliabilityTripReason.STEP_TIMEOUT, self.limits.step_timeout_seconds)
            )
        deadline, reason, configured_limit = min(candidates, key=lambda candidate: candidate[0])
        return TimeoutBudget(
            seconds=max(deadline - now, 0.0),
            reason=reason,
            configured_limit=configured_limit,
        )

    def check_deadlines(self) -> None:
        """Trip if the current step or run deadline has elapsed."""
        self._ensure_closed()
        now = self.clock.now()
        if now >= self._overall_deadline:
            self._raise_timeout(ReliabilityTripReason.OVERALL_TIMEOUT, now)
        if self._step_deadline is not None and now >= self._step_deadline:
            self._raise_timeout(ReliabilityTripReason.STEP_TIMEOUT, now)

    def trip_timeout(self, budget: TimeoutBudget, *, cancellation_confirmed: bool) -> None:
        """Trip using the deadline selected for a timed operation."""
        now = self.clock.now()
        observed_value = self._elapsed_for(budget.reason, now)
        self.trip(
            budget.reason,
            configured_limit=budget.configured_limit,
            observed_value=observed_value,
            cancellation_confirmed=cancellation_confirmed,
        )

    def authorize_transient_retry(self) -> int:
        """Consume and return the next retry number or trip on exhaustion."""
        self._ensure_closed()
        if self._transient_retries >= self.limits.max_transient_retries:
            self.trip(
                ReliabilityTripReason.TRANSIENT_RETRY_LIMIT,
                configured_limit=self.limits.max_transient_retries,
                observed_value=self._transient_retries,
            )
        self._transient_retries += 1
        return self._transient_retries

    def reset_transient_retries(self) -> None:
        """Reset the per-operation transient retry counter after success."""
        self._transient_retries = 0

    def record_schema_violation(self) -> int:
        """Increment consecutive schema violations and trip at the configured cap."""
        self._ensure_closed()
        self._consecutive_schema_violations += 1
        if self._consecutive_schema_violations >= self.limits.max_consecutive_schema_violations:
            self.trip(
                ReliabilityTripReason.SCHEMA_VIOLATION_LIMIT,
                configured_limit=self.limits.max_consecutive_schema_violations,
                observed_value=self._consecutive_schema_violations,
            )
        return self._consecutive_schema_violations

    def reset_schema_violations(self) -> None:
        """Reset the consecutive counter only after a valid schema response."""
        self._consecutive_schema_violations = 0

    def trip(
        self,
        reason: ReliabilityTripReason,
        *,
        configured_limit: int | float,
        observed_value: int | float,
        cancellation_confirmed: bool | None = None,
    ) -> None:
        """Trip idempotently and raise the authoritative internal control signal."""
        if self._state is CircuitState.CLOSED:
            self._state = CircuitState.TRIPPED
            self._trip_reason = reason
        authoritative_reason = self._trip_reason or reason
        raise ReliabilityLimitReachedError(
            authoritative_reason,
            configured_limit=configured_limit,
            observed_value=observed_value,
            cancellation_confirmed=cancellation_confirmed,
        )

    def _ensure_closed(self) -> None:
        if self._state is CircuitState.TRIPPED:
            self.trip(
                self._trip_reason or ReliabilityTripReason.MAX_STEPS_EXCEEDED,
                configured_limit=0,
                observed_value=0,
            )

    def _raise_timeout(self, reason: ReliabilityTripReason, now: float) -> None:
        configured_limit = self._configured_timeout(reason)
        self.trip(
            reason,
            configured_limit=configured_limit,
            observed_value=self._elapsed_for(reason, now),
        )

    def _elapsed_for(self, reason: ReliabilityTripReason, now: float) -> float:
        if reason is ReliabilityTripReason.OVERALL_TIMEOUT:
            return max(now - self._run_started_at, 0.0)
        if reason is ReliabilityTripReason.STEP_TIMEOUT and self._step_started_at is not None:
            return max(now - self._step_started_at, 0.0)
        return self._operation_limit(reason)

    def _configured_timeout(self, reason: ReliabilityTripReason) -> float:
        if reason is ReliabilityTripReason.OVERALL_TIMEOUT:
            return self.limits.overall_timeout_seconds
        if reason is ReliabilityTripReason.STEP_TIMEOUT:
            return self.limits.step_timeout_seconds
        return self._operation_limit(reason)

    def _operation_limit(self, reason: ReliabilityTripReason) -> float:
        if reason is ReliabilityTripReason.LLM_TIMEOUT:
            return self.limits.llm_call_timeout_seconds
        if reason is ReliabilityTripReason.TOOL_TIMEOUT:
            return self.limits.tool_call_timeout_seconds
        raise ValueError(f"Unsupported operation timeout reason: {reason.value}")
