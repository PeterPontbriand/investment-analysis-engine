"""Shared typed outcome contract for deterministic numeric metrics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum


class MetricStatus(StrEnum):
    """Outcome of one calculated metric."""

    OK = "ok"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"


class ReasonCode(StrEnum):
    """Machine-readable reasons shared by deterministic metric results."""

    INSUFFICIENT_HISTORY = "insufficient_history"
    NON_CONTIGUOUS_HISTORY = "non_contiguous_history"
    MISSING_FACT = "missing_fact"
    INCOMPATIBLE_PERIOD = "incompatible_period"
    INCOMPATIBLE_UNITS = "incompatible_units"
    INCOMPATIBLE_CURRENCY = "incompatible_currency"
    INCOMPATIBLE_SCOPE = "incompatible_scope"
    AMBIGUOUS_FACT = "ambiguous_fact"
    NOT_AVAILABLE_AS_OF = "not_available_as_of"
    NONPOSITIVE_BEGINNING = "nonpositive_beginning"
    NONPOSITIVE_ENDING = "nonpositive_ending"
    SIGN_CHANGE = "sign_change"
    FCF_NOT_GROWING = "fcf_not_growing"
    EPS_NOT_GROWING = "eps_not_growing"
    FCF_AND_EPS_NOT_GROWING = "fcf_and_eps_not_growing"
    FORWARD_GROWTH_NOT_CONFIRMED = "forward_growth_not_confirmed"
    CONSENSUS_UNAVAILABLE = "consensus_unavailable"
    MARKET_CAP_UNAVAILABLE = "market_cap_unavailable"
    PROVIDER_ERROR = "provider_error"
    INVALID_REQUEST = "invalid_request"
    NOT_REQUESTED = "not_requested"


@dataclass(frozen=True)
class MetricResult:
    """Typed outcome of one calculated metric, never ``NaN`` or ``Inf``."""

    status: MetricStatus
    value: float | None = None
    reason_code: ReasonCode | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        """Enforce the success/failure field invariants."""
        if self.status is MetricStatus.OK:
            if self.value is None or not math.isfinite(self.value):
                raise ValueError("MetricResult with status=ok requires a finite numeric value.")
            if self.reason_code is not None or self.reason is not None:
                raise ValueError("MetricResult with status=ok requires both reason fields to be None.")
        else:
            if self.value is not None:
                raise ValueError(f"MetricResult with status={self.status.value} requires value to be None.")
            if self.reason_code is None:
                raise ValueError(f"MetricResult with status={self.status.value} requires a reason_code.")
            if self.reason is None or not self.reason.strip():
                raise ValueError(f"MetricResult with status={self.status.value} requires a non-empty reason string.")

    @classmethod
    def ok(cls, value: float) -> MetricResult:
        """Build a successful metric result for a finite value."""
        return cls(status=MetricStatus.OK, value=value)

    @classmethod
    def failure(cls, status: MetricStatus, reason_code: ReasonCode, reason: str) -> MetricResult:
        """Build a non-success result with a machine code and human reason."""
        if status is MetricStatus.OK:
            raise ValueError("MetricResult.failure requires a non-ok status.")
        return cls(status=status, reason_code=reason_code, reason=reason)
