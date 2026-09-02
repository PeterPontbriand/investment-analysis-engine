"""Typed models for the free-cash-flow & earnings-growth strategy (Slice B).

Defines the normative strategy enums, the typed policy, the invariant-checked
shared ``MetricResult`` and strategy-specific ``ForwardEvidence`` containers, the annual observation
record, and the fixed-identifier ``FCFEarningsGrowthResult`` result type
required by ``docs/project/milestones/v0.2/step-2.4/STEP_2_4_FCF_EARNINGS_GROWTH_DESIGN.md``.

All models are frozen.  All ``datetime`` fields, when present, must be
timezone-aware (inherited from the shared provenance contract).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from src.core.analysis_status import CalculationStatus
from src.core.metric_result import MetricResult, MetricStatus, ReasonCode
from src.data.financial.provenance import ResolvedInput
from src.data.financial.resolution_trace import ResolutionTrace
from src.data.instrument_profile import InstrumentProfile

__all__ = ["MetricResult", "MetricStatus", "ReasonCode"]

# ---------------------------------------------------------------------------
# Fixed identifiers (method_version = 1 / schema_version = 1)
# ---------------------------------------------------------------------------

STRATEGY_ID = "fcf_earnings_growth"
METHOD_ID = "reported_fcf_eps_cagr"
METHOD_VERSION = 2
SCHEMA_VERSION = 3


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class HistoricalHorizon(StrEnum):
    """Requested historical elapsed-year horizon for classification."""

    LONGEST_AVAILABLE = "longest_available"
    THREE_YEARS = "3"
    FOUR_YEARS = "4"
    FIVE_YEARS = "5"


class ForwardPolicy(StrEnum):
    """How forward consensus evidence affects the headline result."""

    DISPLAY_ONLY = "display_only"
    CONFIRMATION = "confirmation"
    HARD_GATE = "hard_gate"


class FCFClassificationBasis(StrEnum):
    """Free-cash-flow measure controlling classification."""

    TOTAL_FCF = "total_fcf"
    FCF_PER_SHARE = "fcf_per_share"


class Classification(StrEnum):
    """Headline historical screening conclusion."""

    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


class TrendClassification(StrEnum):
    """Historical relationship between FCF and earnings growth (evidence, not a score)."""

    BOTH_GROWING = "both_growing"
    FCF_GROWING_EARNINGS_NOT = "fcf_growing_earnings_not"
    EARNINGS_GROWING_FCF_NOT = "earnings_growing_fcf_not"
    NEITHER_GROWING = "neither_growing"
    INSUFFICIENT_OR_NONMEANINGFUL_GROWTH = "insufficient_or_nonmeaningful_growth"


class ForwardEvidenceStatus(StrEnum):
    """Completeness of the forward consensus evidence block."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FCFEarningsGrowthPolicy:
    """Investor-selectable controls for one analysis run.

    The minimum automatic horizon is fixed at three elapsed years and is not
    configurable in ``method_version = 1``.

    Attributes:
        historical_horizon: Requested elapsed-year horizon.
        forward_policy: How forward consensus evidence affects the headline.
        include_fcf_yield: Whether the optional informational FCF yield is computed.
    """

    historical_horizon: HistoricalHorizon = HistoricalHorizon.LONGEST_AVAILABLE
    classification_basis: FCFClassificationBasis = FCFClassificationBasis.TOTAL_FCF
    forward_policy: ForwardPolicy = ForwardPolicy.DISPLAY_ONLY
    include_fcf_yield: bool = True


# ---------------------------------------------------------------------------
# Metric result
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Forward evidence
# ---------------------------------------------------------------------------


def _expected_confirms_positive(actual_to_fy1: MetricResult, fy1_to_fy2: MetricResult) -> bool | None:
    """Compute the only permitted ``confirms_positive_growth`` value."""
    if actual_to_fy1.status is not MetricStatus.OK or fy1_to_fy2.status is not MetricStatus.OK:
        return None
    if actual_to_fy1.value is None or fy1_to_fy2.value is None:
        return None
    return actual_to_fy1.value > 0 and fy1_to_fy2.value > 0


def _growth_ok(growth: MetricResult) -> bool:
    """Return whether *growth* is a successfully calculated metric."""
    return growth.status is MetricStatus.OK and growth.value is not None


@dataclass(frozen=True, kw_only=True)
class ForwardEvidence:
    """Analyst-consensus forward evidence block for FY1 and FY2.

    Invariants (normative contract):
        - ``complete`` requires all three EPS values and both growth metrics ok.
        - ``partial`` requires at least one consensus estimate without the full
          two-interval evaluation.
        - ``unavailable`` requires no usable consensus estimate.
        - ``confirms_positive_growth`` is ``True`` only when both growth metrics
          are positive, ``False`` when both are meaningful and at least one is
          nonpositive, and ``None`` otherwise.

    Attributes:
        status: Completeness discriminator.
        latest_actual_eps: Latest completed fiscal-year actual diluted EPS.
        fy1_consensus_eps: Consensus diluted EPS for the next fiscal year.
        fy2_consensus_eps: Consensus diluted EPS for the following fiscal year.
        actual_to_fy1_growth: Growth percent from the latest actual to FY1.
        fy1_to_fy2_growth: Growth percent from FY1 to FY2.
        confirms_positive_growth: Whether both forward intervals confirm positive growth.
    """

    status: ForwardEvidenceStatus
    latest_actual_eps: ResolvedInput | None
    fy1_consensus_eps: ResolvedInput | None
    fy2_consensus_eps: ResolvedInput | None
    actual_to_fy1_growth: MetricResult
    fy1_to_fy2_growth: MetricResult
    confirms_positive_growth: bool | None

    def __post_init__(self) -> None:
        """Enforce status completeness and confirms_positive_growth semantics."""
        both_growth_ok = _growth_ok(self.actual_to_fy1_growth) and _growth_ok(self.fy1_to_fy2_growth)
        all_values_present = (
            self.latest_actual_eps is not None
            and self.fy1_consensus_eps is not None
            and self.fy2_consensus_eps is not None
        )
        any_estimate = self.fy1_consensus_eps is not None or self.fy2_consensus_eps is not None

        if self.status is ForwardEvidenceStatus.COMPLETE:
            if not (all_values_present and both_growth_ok):
                msg = "ForwardEvidence.status=complete requires all three EPS values and both growth metrics to be ok."
                raise ValueError(msg)
        elif self.status is ForwardEvidenceStatus.PARTIAL:
            if not any_estimate:
                msg = "ForwardEvidence.status=partial requires at least one consensus estimate."
                raise ValueError(msg)
            if all_values_present and both_growth_ok:
                msg = "ForwardEvidence with both complete intervals must have status=complete."
                raise ValueError(msg)
        elif any_estimate:
            msg = "ForwardEvidence.status=unavailable requires no usable consensus estimate."
            raise ValueError(msg)

        expected = _expected_confirms_positive(self.actual_to_fy1_growth, self.fy1_to_fy2_growth)
        if self.confirms_positive_growth is not expected:
            msg = f"confirms_positive_growth must be {expected!r} for these growth metrics."
            raise ValueError(msg)


# ---------------------------------------------------------------------------
# Annual observation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AnnualGrowthObservation:
    """One completed-fiscal-year observation with fully provenanced components.

    Attributes:
        fiscal_year: Fiscal-year label for the completed period.
        period_start: Timezone-aware fiscal-year start.
        period_end: Timezone-aware fiscal-year end.
        operating_cash_flow: Resolved operating cash flow for the fiscal year.
        normalized_capital_expenditures: Positive normalized CapEx for the fiscal year.
        free_cash_flow: Derived free cash flow (``operating cash flow - normalized CapEx``).
        diluted_eps: Resolved diluted earnings per share.
    """

    fiscal_year: int
    period_start: datetime
    period_end: datetime
    operating_cash_flow: ResolvedInput
    normalized_capital_expenditures: ResolvedInput
    free_cash_flow: ResolvedInput
    diluted_eps: ResolvedInput
    weighted_average_diluted_shares: ResolvedInput | None = None
    free_cash_flow_per_diluted_share: ResolvedInput | None = None

    def __post_init__(self) -> None:
        """Validate the fiscal-year span and derived free-cash-flow identity."""
        if self.fiscal_year < 1:
            msg = f"fiscal_year must be a positive year label (received {self.fiscal_year})."
            raise ValueError(msg)
        if (self.weighted_average_diluted_shares is None) is not (self.free_cash_flow_per_diluted_share is None):
            raise ValueError("Diluted shares and derived FCF/share must be present or absent together.")
        if self.weighted_average_diluted_shares is not None:
            if self.weighted_average_diluted_shares.value <= 0:
                raise ValueError("weighted_average_diluted_shares must be strictly positive.")
            expected_per_share = self.free_cash_flow.value / self.weighted_average_diluted_shares.value
            assert self.free_cash_flow_per_diluted_share is not None
            if not math.isclose(self.free_cash_flow_per_diluted_share.value, expected_per_share):
                raise ValueError("free_cash_flow_per_diluted_share has an inconsistent derived value.")
        if self.period_start > self.period_end:
            msg = "period_start must not be after period_end."
            raise ValueError(msg)
        expected_fcf = self.operating_cash_flow.value - self.normalized_capital_expenditures.value
        if self.free_cash_flow.value != expected_fcf:
            msg = (
                "free_cash_flow must equal operating_cash_flow minus "
                f"normalized_capital_expenditures (expected {expected_fcf})."
            )
            raise ValueError(msg)


# ---------------------------------------------------------------------------
# Classification decision
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClassificationDecision:
    """Outcome of the pure historical/forward classification function.

    Invariants:
        - ``PASS`` has no classification reason.
        - ``FAIL`` and ``INDETERMINATE`` have both reason fields present.

    Attributes:
        classification: PASS / FAIL / INDETERMINATE conclusion.
        trend_classification: Historical relationship description (evidence only).
        reason_code: Machine-readable classification reason (``None`` for PASS).
        reason: Human-readable classification reason (``None`` for PASS).
    """

    classification: Classification
    trend_classification: TrendClassification
    reason_code: ReasonCode | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        """Enforce the reason-presence invariants."""
        if self.classification is Classification.PASS:
            if self.reason_code is not None or self.reason is not None:
                msg = "A PASS classification must not carry a classification reason."
                raise ValueError(msg)
        elif self.reason_code is None or self.reason is None or not self.reason.strip():
            msg = f"A {self.classification.value} classification requires reason_code and a non-empty reason."
            raise ValueError(msg)


# ---------------------------------------------------------------------------
# Final result
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class FCFEarningsGrowthResult:
    """Complete typed result for one free-cash-flow & earnings-growth analysis.

    ``strategy_id``, ``method_id``, ``method_version`` and ``schema_version``
    are fixed for ``method_version = 1`` and are not constructor arguments;
    changing them requires a schema or method version increment per the
    design contract.

    Invariants enforced at construction:
        - ``selected_observation_count`` equals the number of annual observations.
        - A selected horizon of ``N`` years has exactly ``N + 1`` observations.
        - ``used_horizon_fallback`` is only true for ``longest_available`` with
          fewer than five elapsed years selected.
        - A successful PASS has ``execution_status = ok``, both historical
          metrics ok, non-null period fields, and no classification reason.
        - FAIL and INDETERMINATE carry both classification-reason fields.
        - ``include_fcf_yield = false`` forces a not_applicable/not_requested
          FCF yield metric.

    Attributes:
        schema_version: Machine-readable result schema version (fixed at 1).
        strategy_id: Stable analysis-family identifier.
        method_id: Financial-method identifier.
        method_version: Method semantics version (fixed at 1).
        ticker: Requested security identifier.
        requested_as_of: Timezone-aware requested analysis boundary, if any.
        effective_as_of: Timezone-aware effective analysis boundary used.
        policy: Investor-selected policy for this run.
        execution_status: Software execution outcome, independent of classification.
        classification: PASS / FAIL / INDETERMINATE headline conclusion.
        classification_reason_code: Machine-readable classification reason.
        classification_reason: Human-readable classification reason.
        selected_horizon_years: Elapsed years actually selected (3, 4, or 5; None when indeterminate).
        selected_observation_count: Number of annual observations used.
        used_horizon_fallback: True when automatic selection fell back below five years.
        period_start: Timezone-aware start of the selected span, if any.
        period_end: Timezone-aware end of the selected span, if any.
        annual_observations: Raw annual observations preserving every value.
        fcf_cagr: Free-cash-flow compound annual growth (percent).
        eps_cagr: Diluted-EPS compound annual growth (percent).
        trend_classification: Historical relationship description.
        market_capitalization: Current market capitalization fact, when resolved.
        fcf_yield: Informational free-cash-flow yield (percent); never affects classification.
        forward_evidence: Forward consensus evidence block.
        warnings: Material data-quality warnings for the run.
        diagnostics: Ordered resolver trace for investor-facing diagnostics.
    """

    schema_version: int = field(init=False, default=SCHEMA_VERSION)
    strategy_id: str = field(init=False, default=STRATEGY_ID)
    method_id: str = field(init=False, default=METHOD_ID)
    method_version: int = field(init=False, default=METHOD_VERSION)
    ticker: str
    requested_as_of: datetime | None = None
    effective_as_of: datetime
    policy: FCFEarningsGrowthPolicy
    instrument_profile: InstrumentProfile | None = None
    execution_status: CalculationStatus
    classification: Classification
    classification_reason_code: ReasonCode | None = None
    classification_reason: str | None = None
    selected_horizon_years: int | None = None
    selected_observation_count: int = 0
    used_horizon_fallback: bool = False
    period_start: datetime | None = None
    period_end: datetime | None = None
    annual_observations: tuple[AnnualGrowthObservation, ...] = ()
    fcf_cagr: MetricResult
    fcf_per_share_cagr: MetricResult
    eps_cagr: MetricResult
    trend_classification: TrendClassification
    market_capitalization: ResolvedInput | None = None
    fcf_yield: MetricResult
    forward_evidence: ForwardEvidence
    warnings: tuple[str, ...] = ()
    diagnostics: ResolutionTrace = ResolutionTrace()

    def __post_init__(self) -> None:
        """Enforce the result-level invariants from the strategy contract."""
        if not self.ticker.strip():
            msg = "FCFEarningsGrowthResult.ticker must be non-empty."
            raise ValueError(msg)
        if self.selected_horizon_years is not None and self.selected_horizon_years not in (3, 4, 5):
            msg = f"selected_horizon_years must be 3, 4, or 5 (received {self.selected_horizon_years})."
            raise ValueError(msg)
        if self.selected_observation_count != len(self.annual_observations):
            msg = "selected_observation_count must equal the number of annual_observations."
            raise ValueError(msg)
        if self.selected_horizon_years is not None and self.selected_observation_count != (
            self.selected_horizon_years + 1
        ):
            msg = f"A selected horizon of {self.selected_horizon_years} years requires exactly N + 1 observations."
            raise ValueError(msg)
        if self.used_horizon_fallback:
            if self.policy.historical_horizon is not HistoricalHorizon.LONGEST_AVAILABLE:
                msg = "used_horizon_fallback is only valid under the longest_available horizon."
                raise ValueError(msg)
            if self.selected_horizon_years not in (3, 4):
                msg = "used_horizon_fallback requires a selected horizon of exactly 3 or 4 years."
                raise ValueError(msg)
        if self.policy.include_fcf_yield is False and (
            self.fcf_yield.status is not MetricStatus.NOT_APPLICABLE
            or self.fcf_yield.reason_code is not ReasonCode.NOT_REQUESTED
        ):
            msg = "include_fcf_yield=false requires fcf_yield to be not_applicable/not_requested."
            raise ValueError(msg)

        if self.instrument_profile is not None and self.instrument_profile.ticker != self.ticker.strip().upper():
            msg = "Instrument profile ticker does not match the FCF & Earnings Growth result ticker."
            raise ValueError(msg)
        self._validate_not_applicable_result()

        if self.classification in (Classification.PASS, Classification.FAIL) and (
            self.execution_status is not CalculationStatus.OK
            or (
                self.fcf_cagr.status
                if self.policy.classification_basis is FCFClassificationBasis.TOTAL_FCF
                else self.fcf_per_share_cagr.status
            )
            is not MetricStatus.OK
            or self.eps_cagr.status is not MetricStatus.OK
            or self.period_start is None
            or self.period_end is None
        ):
            msg = (
                f"A {self.classification.value} classification requires execution_status=ok, both "
                "historical metrics ok, and non-null period fields."
            )
            raise ValueError(msg)
        if self.classification is Classification.PASS and (
            self.classification_reason_code is not None or self.classification_reason is not None
        ):
            msg = "A PASS classification must not carry a classification reason."
            raise ValueError(msg)
        if self.classification is not Classification.PASS and (
            self.classification_reason_code is None
            or self.classification_reason is None
            or not self.classification_reason.strip()
        ):
            msg = (
                f"A {self.classification.value} classification requires "
                "classification_reason_code and a non-empty classification_reason."
            )
            raise ValueError(msg)

    def _validate_not_applicable_result(self) -> None:
        """Require a coherent empty company-history result for inapplicable instruments."""
        if self.execution_status is not CalculationStatus.NOT_APPLICABLE:
            return
        if (
            self.classification is not Classification.INDETERMINATE
            or self.annual_observations
            or self.selected_horizon_years is not None
            or self.selected_observation_count != 0
            or self.fcf_cagr.status is not MetricStatus.NOT_APPLICABLE
            or self.fcf_per_share_cagr.status is not MetricStatus.NOT_APPLICABLE
            or self.eps_cagr.status is not MetricStatus.NOT_APPLICABLE
        ):
            msg = (
                "execution_status=not_applicable requires an indeterminate classification, no selected history, "
                "and not-applicable historical metrics."
            )
            raise ValueError(msg)
