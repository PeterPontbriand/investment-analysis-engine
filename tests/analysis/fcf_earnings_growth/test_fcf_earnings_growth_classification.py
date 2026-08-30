"""Tests for the pure FCF & earnings-growth classification function."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.analysis.fcf_earnings_growth.calculators import classify_fcf_earnings_growth
from src.analysis.fcf_earnings_growth.models import (
    Classification,
    ClassificationDecision,
    FCFClassificationBasis,
    FCFEarningsGrowthPolicy,
    ForwardEvidence,
    ForwardEvidenceStatus,
    ForwardPolicy,
    MetricResult,
    MetricStatus,
    ReasonCode,
    TrendClassification,
)
from src.data.financial.provenance import ResolvedInput, SourceKind

RESOLVED_AT = datetime(2025, 12, 31, tzinfo=UTC)


def _eps(name: str, value: float) -> ResolvedInput:
    return ResolvedInput(
        field_name=name,
        value=value,
        source_kind=SourceKind.PROVIDER,
        resolved_at=RESOLVED_AT,
        provider_id="fixture",
    )


def _complete_forward(*, actual_to_fy1: float, fy1_to_fy2: float) -> ForwardEvidence:
    """Build a complete forward evidence block with ok growth on both intervals."""
    return ForwardEvidence(
        status=ForwardEvidenceStatus.COMPLETE,
        latest_actual_eps=_eps("latest_actual_eps", 5.0),
        fy1_consensus_eps=_eps("fy1_consensus_eps", 6.0),
        fy2_consensus_eps=_eps("fy2_consensus_eps", 7.0),
        actual_to_fy1_growth=MetricResult.ok(actual_to_fy1),
        fy1_to_fy2_growth=MetricResult.ok(fy1_to_fy2),
        confirms_positive_growth=actual_to_fy1 > 0 and fy1_to_fy2 > 0,
    )


def _unavailable_forward() -> ForwardEvidence:
    """Build a forward evidence block with no usable consensus estimate."""
    return ForwardEvidence(
        status=ForwardEvidenceStatus.UNAVAILABLE,
        latest_actual_eps=None,
        fy1_consensus_eps=None,
        fy2_consensus_eps=None,
        actual_to_fy1_growth=MetricResult.failure(
            MetricStatus.UNAVAILABLE, ReasonCode.MISSING_FACT, "No FY1 consensus estimate was available."
        ),
        fy1_to_fy2_growth=MetricResult.failure(
            MetricStatus.UNAVAILABLE, ReasonCode.MISSING_FACT, "No FY2 consensus estimate was available."
        ),
        confirms_positive_growth=None,
    )


def _partial_forward() -> ForwardEvidence:
    """Build a forward evidence block with a single declining FY1 interval."""
    return ForwardEvidence(
        status=ForwardEvidenceStatus.PARTIAL,
        latest_actual_eps=_eps("latest_actual_eps", 5.0),
        fy1_consensus_eps=_eps("fy1_consensus_eps", 4.0),
        fy2_consensus_eps=None,
        actual_to_fy1_growth=MetricResult.ok(-20.0),
        fy1_to_fy2_growth=MetricResult.failure(
            MetricStatus.UNAVAILABLE, ReasonCode.MISSING_FACT, "No FY2 consensus estimate was available."
        ),
        confirms_positive_growth=None,
    )


def _classify(
    *,
    policy: FCFEarningsGrowthPolicy,
    fcf_cagr: MetricResult,
    eps_cagr: MetricResult,
    forward_evidence: ForwardEvidence,
) -> ClassificationDecision:
    return classify_fcf_earnings_growth(
        policy=policy, fcf_cagr=fcf_cagr, eps_cagr=eps_cagr, forward_evidence=forward_evidence
    )


class TestHistoricalGates:
    """PASS/FAIL on the selected historical CAGR span (display-only forward)."""

    POLICY = FCFEarningsGrowthPolicy(forward_policy=ForwardPolicy.DISPLAY_ONLY)

    def test_explicit_per_share_basis_controls_classification(self) -> None:
        decision = classify_fcf_earnings_growth(
            policy=FCFEarningsGrowthPolicy(classification_basis=FCFClassificationBasis.FCF_PER_SHARE),
            fcf_cagr=MetricResult.ok(8.0),
            fcf_per_share_cagr=MetricResult.ok(-1.0),
            eps_cagr=MetricResult.ok(4.0),
            forward_evidence=_unavailable_forward(),
        )
        assert decision.classification is Classification.FAIL
        assert decision.reason_code is ReasonCode.FCF_NOT_GROWING

    def test_missing_selected_per_share_evidence_is_indeterminate(self) -> None:
        unavailable = MetricResult.failure(
            MetricStatus.UNAVAILABLE, ReasonCode.MISSING_FACT, "FCF/share evidence is unavailable."
        )
        decision = classify_fcf_earnings_growth(
            policy=FCFEarningsGrowthPolicy(classification_basis=FCFClassificationBasis.FCF_PER_SHARE),
            fcf_cagr=MetricResult.ok(8.0),
            fcf_per_share_cagr=unavailable,
            eps_cagr=MetricResult.ok(4.0),
            forward_evidence=_unavailable_forward(),
        )
        assert decision.classification is Classification.INDETERMINATE
        assert decision.reason_code is ReasonCode.MISSING_FACT

    def test_pass_when_both_series_grow(self) -> None:
        decision = _classify(
            policy=self.POLICY,
            fcf_cagr=MetricResult.ok(12.0),
            eps_cagr=MetricResult.ok(6.0),
            forward_evidence=_unavailable_forward(),
        )
        assert decision.classification is Classification.PASS
        assert decision.trend_classification is TrendClassification.BOTH_GROWING
        assert decision.reason_code is None
        assert decision.reason is None

    @pytest.mark.parametrize(
        ("fcf", "eps", "reason_code", "trend"),
        [
            (10.0, -2.0, ReasonCode.EPS_NOT_GROWING, TrendClassification.FCF_GROWING_EARNINGS_NOT),
            (-3.0, 8.0, ReasonCode.FCF_NOT_GROWING, TrendClassification.EARNINGS_GROWING_FCF_NOT),
            (-1.0, -2.0, ReasonCode.FCF_AND_EPS_NOT_GROWING, TrendClassification.NEITHER_GROWING),
            (0.0, 5.0, ReasonCode.FCF_NOT_GROWING, TrendClassification.EARNINGS_GROWING_FCF_NOT),
            (5.0, 0.0, ReasonCode.EPS_NOT_GROWING, TrendClassification.FCF_GROWING_EARNINGS_NOT),
        ],
        ids=["eps-only", "fcf-only", "both", "fcf-zero", "eps-zero"],
    )
    def test_fail_when_either_series_is_not_positive(
        self,
        fcf: float,
        eps: float,
        reason_code: ReasonCode,
        trend: TrendClassification,
    ) -> None:
        decision = _classify(
            policy=self.POLICY,
            fcf_cagr=MetricResult.ok(fcf),
            eps_cagr=MetricResult.ok(eps),
            forward_evidence=_unavailable_forward(),
        )
        assert decision.classification is Classification.FAIL
        assert decision.reason_code is reason_code
        assert decision.reason is not None
        assert decision.reason.strip()
        assert decision.trend_classification is trend

    def test_indeterminate_propagates_fcf_failure(self) -> None:
        decision = _classify(
            policy=self.POLICY,
            fcf_cagr=MetricResult.failure(
                MetricStatus.UNAVAILABLE, ReasonCode.NONPOSITIVE_BEGINNING, "Beginning FCF was nonpositive."
            ),
            eps_cagr=MetricResult.ok(5.0),
            forward_evidence=_unavailable_forward(),
        )
        assert decision.classification is Classification.INDETERMINATE
        assert decision.reason_code is ReasonCode.NONPOSITIVE_BEGINNING
        assert decision.reason == "Beginning FCF was nonpositive."
        assert decision.trend_classification is TrendClassification.INSUFFICIENT_OR_NONMEANINGFUL_GROWTH

    def test_indeterminate_propagates_eps_failure_when_fcf_ok(self) -> None:
        decision = _classify(
            policy=self.POLICY,
            fcf_cagr=MetricResult.ok(5.0),
            eps_cagr=MetricResult.failure(
                MetricStatus.UNAVAILABLE, ReasonCode.MISSING_FACT, "Latest diluted EPS was missing."
            ),
            forward_evidence=_unavailable_forward(),
        )
        assert decision.classification is Classification.INDETERMINATE
        assert decision.reason_code is ReasonCode.MISSING_FACT
        assert decision.reason == "Latest diluted EPS was missing."

    def test_nonmeaningful_growth_precedes_hard_gate(self) -> None:
        """Historical nonmeaningfulness outranks the forward consensus gate."""
        decision = _classify(
            policy=FCFEarningsGrowthPolicy(forward_policy=ForwardPolicy.HARD_GATE),
            fcf_cagr=MetricResult.failure(
                MetricStatus.UNAVAILABLE, ReasonCode.INSUFFICIENT_HISTORY, "Only two fiscal years were available."
            ),
            eps_cagr=MetricResult.ok(5.0),
            forward_evidence=_complete_forward(actual_to_fy1=10.0, fy1_to_fy2=20.0),
        )
        assert decision.classification is Classification.INDETERMINATE
        assert decision.reason_code is ReasonCode.INSUFFICIENT_HISTORY
        assert decision.trend_classification is TrendClassification.INSUFFICIENT_OR_NONMEANINGFUL_GROWTH


class TestForwardPolicies:
    """How the selected forward policy affects the headline result."""

    POSITIVE = (MetricResult.ok(12.0), MetricResult.ok(6.0))

    def test_display_only_ignores_unavailable_consensus(self) -> None:
        fcf, eps = self.POSITIVE
        decision = _classify(
            policy=FCFEarningsGrowthPolicy(forward_policy=ForwardPolicy.DISPLAY_ONLY),
            fcf_cagr=fcf,
            eps_cagr=eps,
            forward_evidence=_unavailable_forward(),
        )
        assert decision.classification is Classification.PASS

    def test_confirmation_is_informational_in_method_v1(self) -> None:
        """Only ``hard_gate`` affects the headline; confirmation stays display-only."""
        fcf, eps = self.POSITIVE
        decision = _classify(
            policy=FCFEarningsGrowthPolicy(forward_policy=ForwardPolicy.CONFIRMATION),
            fcf_cagr=fcf,
            eps_cagr=eps,
            forward_evidence=_partial_forward(),
        )
        assert decision.classification is Classification.PASS
        assert decision.reason_code is None

    @pytest.mark.parametrize("evidence", [_partial_forward(), _unavailable_forward()], ids=["partial", "unavailable"])
    def test_hard_gate_requires_complete_evidence(self, evidence: ForwardEvidence) -> None:
        fcf, eps = self.POSITIVE
        decision = _classify(
            policy=FCFEarningsGrowthPolicy(forward_policy=ForwardPolicy.HARD_GATE),
            fcf_cagr=fcf,
            eps_cagr=eps,
            forward_evidence=evidence,
        )
        assert decision.classification is Classification.INDETERMINATE
        assert decision.reason_code is ReasonCode.CONSENSUS_UNAVAILABLE
        assert decision.trend_classification is TrendClassification.BOTH_GROWING

    def test_hard_gate_fails_on_declining_fy1_interval(self) -> None:
        fcf, eps = self.POSITIVE
        decision = _classify(
            policy=FCFEarningsGrowthPolicy(forward_policy=ForwardPolicy.HARD_GATE),
            fcf_cagr=fcf,
            eps_cagr=eps,
            forward_evidence=_complete_forward(actual_to_fy1=-20.0, fy1_to_fy2=5.0),
        )
        assert decision.classification is Classification.FAIL
        assert decision.reason_code is ReasonCode.FORWARD_GROWTH_NOT_CONFIRMED

    def test_hard_gate_fails_on_declining_fy2_interval(self) -> None:
        fcf, eps = self.POSITIVE
        decision = _classify(
            policy=FCFEarningsGrowthPolicy(forward_policy=ForwardPolicy.HARD_GATE),
            fcf_cagr=fcf,
            eps_cagr=eps,
            forward_evidence=_complete_forward(actual_to_fy1=20.0, fy1_to_fy2=-5.0),
        )
        assert decision.classification is Classification.FAIL
        assert decision.reason_code is ReasonCode.FORWARD_GROWTH_NOT_CONFIRMED

    def test_hard_gate_fails_on_flat_interval(self) -> None:
        fcf, eps = self.POSITIVE
        decision = _classify(
            policy=FCFEarningsGrowthPolicy(forward_policy=ForwardPolicy.HARD_GATE),
            fcf_cagr=fcf,
            eps_cagr=eps,
            forward_evidence=_complete_forward(actual_to_fy1=20.0, fy1_to_fy2=0.0),
        )
        assert decision.classification is Classification.FAIL
        assert decision.reason_code is ReasonCode.FORWARD_GROWTH_NOT_CONFIRMED

    def test_hard_gate_passes_when_both_intervals_positive(self) -> None:
        fcf, eps = self.POSITIVE
        decision = _classify(
            policy=FCFEarningsGrowthPolicy(forward_policy=ForwardPolicy.HARD_GATE),
            fcf_cagr=fcf,
            eps_cagr=eps,
            forward_evidence=_complete_forward(actual_to_fy1=20.0, fy1_to_fy2=16.67),
        )
        assert decision.classification is Classification.PASS
        assert decision.reason_code is None
        assert decision.trend_classification is TrendClassification.BOTH_GROWING

    def test_hard_gate_fail_keeps_historical_trend(self) -> None:
        """The trend description is evidence and survives a forward FAIL."""
        fcf, eps = self.POSITIVE
        decision = _classify(
            policy=FCFEarningsGrowthPolicy(forward_policy=ForwardPolicy.HARD_GATE),
            fcf_cagr=fcf,
            eps_cagr=eps,
            forward_evidence=_unavailable_forward(),
        )
        assert decision.classification is Classification.INDETERMINATE
        assert decision.trend_classification is TrendClassification.BOTH_GROWING

    def test_ok_status_with_missing_value_is_defensive_failure(self) -> None:
        """An ok metric without a value must never classify, even if constructed by bypass."""
        bad = object.__new__(MetricResult)
        bad.__dict__.update(
            {
                "status": MetricStatus.OK,
                "value": None,
                "reason_code": None,
                "reason": None,
            }
        )
        with pytest.raises(ValueError, match="must carry a finite value"):
            _classify(
                policy=FCFEarningsGrowthPolicy(forward_policy=ForwardPolicy.DISPLAY_ONLY),
                fcf_cagr=bad,
                eps_cagr=MetricResult.ok(6.0),
                forward_evidence=_unavailable_forward(),
            )
