"""Shared typed outcome contract for deterministic numeric metrics."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final


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
    STALE_ANCHOR = "stale_anchor"
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
    INSTRUMENT_KIND_NOT_APPLICABLE = "instrument_kind_not_applicable"
    INDUSTRY_CLASS_NOT_APPLICABLE = "industry_class_not_applicable"
    INDUSTRY_CLASS_UNKNOWN = "industry_class_unknown"
    UNSUPPORTED_MAPPING = "unsupported_mapping"
    DEBT_NOT_VISIBLE = "debt_not_visible"
    NONPOSITIVE_DENOMINATOR = "nonpositive_denominator"
    INSUFFICIENT_TESTS = "insufficient_tests"


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


METRIC_STATUS_TERMS: Final[Mapping[str, str]] = MappingProxyType(
    {
        MetricStatus.OK.value: "status-ok",
        MetricStatus.UNAVAILABLE.value: "status-unavailable",
        MetricStatus.NOT_APPLICABLE.value: "not-applicable",
    }
)
"""The glossary term that explains each metric status; a value a calculation status shares maps to the same term."""


REASON_CODE_TERMS: Final[Mapping[str, str]] = MappingProxyType(
    {
        ReasonCode.INSUFFICIENT_HISTORY.value: "reason-insufficient-history",
        ReasonCode.NON_CONTIGUOUS_HISTORY.value: "reason-insufficient-history",
        ReasonCode.MISSING_FACT.value: "reason-missing-input",
        ReasonCode.INCOMPATIBLE_PERIOD.value: "reason-incompatible-inputs",
        ReasonCode.INCOMPATIBLE_UNITS.value: "reason-incompatible-inputs",
        ReasonCode.INCOMPATIBLE_CURRENCY.value: "reason-incompatible-inputs",
        ReasonCode.INCOMPATIBLE_SCOPE.value: "reason-incompatible-inputs",
        ReasonCode.AMBIGUOUS_FACT.value: "reason-ambiguous-fact",
        ReasonCode.NOT_AVAILABLE_AS_OF.value: "reason-not-available-as-of",
        ReasonCode.STALE_ANCHOR.value: "reason-stale-anchor",
        ReasonCode.NONPOSITIVE_BEGINNING.value: "reason-growth-not-meaningful",
        ReasonCode.NONPOSITIVE_ENDING.value: "reason-growth-not-meaningful",
        ReasonCode.SIGN_CHANGE.value: "reason-growth-not-meaningful",
        ReasonCode.FCF_NOT_GROWING.value: "reason-not-growing",
        ReasonCode.EPS_NOT_GROWING.value: "reason-not-growing",
        ReasonCode.FCF_AND_EPS_NOT_GROWING.value: "reason-not-growing",
        ReasonCode.FORWARD_GROWTH_NOT_CONFIRMED.value: "reason-forward-not-confirmed",
        ReasonCode.CONSENSUS_UNAVAILABLE.value: "reason-missing-input",
        ReasonCode.MARKET_CAP_UNAVAILABLE.value: "reason-missing-input",
        ReasonCode.PROVIDER_ERROR.value: "status-provider-error",
        ReasonCode.INVALID_REQUEST.value: "reason-invalid-request",
        ReasonCode.INSTRUMENT_KIND_NOT_APPLICABLE.value: "reason-security-not-applicable",
        ReasonCode.INDUSTRY_CLASS_NOT_APPLICABLE.value: "reason-security-not-applicable",
        ReasonCode.INDUSTRY_CLASS_UNKNOWN.value: "reason-industry-class-unknown",
        ReasonCode.UNSUPPORTED_MAPPING.value: "reason-debt-not-visible",
        ReasonCode.DEBT_NOT_VISIBLE.value: "reason-debt-not-visible",
        ReasonCode.NONPOSITIVE_DENOMINATOR.value: "reason-growth-not-meaningful",
        ReasonCode.INSUFFICIENT_TESTS.value: "reason-insufficient-tests",
    }
)
"""The glossary term that explains each metric reason code; codes that differ only in detail share a term."""
