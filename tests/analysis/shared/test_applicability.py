"""Industry class from a SIC code and the applicability matrix of the Step 3.5 shared definitions."""

import pytest

from investment_analysis_engine.analysis.shared.applicability import (
    Applicability,
    ApplicabilityOutcome,
    IndustryClass,
    SectorGate,
    applicability_of,
    industry_class_of_sic,
)
from investment_analysis_engine.core.metric_result import MetricResult, MetricStatus, ReasonCode


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (1, IndustryClass.OTHER),
        (100, IndustryClass.OTHER),
        (1999, IndustryClass.OTHER),
        (2000, IndustryClass.MANUFACTURER),
        (3571, IndustryClass.MANUFACTURER),
        (3999, IndustryClass.MANUFACTURER),
        (4000, IndustryClass.OTHER),
        (4899, IndustryClass.OTHER),
        (4900, IndustryClass.UTILITY),
        (4931, IndustryClass.UTILITY),
        (4999, IndustryClass.UTILITY),
        (5000, IndustryClass.OTHER),
        (5999, IndustryClass.OTHER),
        (6000, IndustryClass.FINANCIAL),
        (6021, IndustryClass.FINANCIAL),
        (6798, IndustryClass.FINANCIAL),
        (6799, IndustryClass.FINANCIAL),
        (6800, IndustryClass.OTHER),
        (7372, IndustryClass.OTHER),
        (9999, IndustryClass.OTHER),
    ],
)
def test_every_range_edge_lands_in_its_class(code: int, expected: IndustryClass) -> None:
    assert industry_class_of_sic(code) is expected


@pytest.mark.parametrize("code", [0, -1, 10000])
def test_a_code_outside_four_digits_is_refused(code: int) -> None:
    with pytest.raises(ValueError, match="SIC code"):
        industry_class_of_sic(code)


# The three gate shapes of the Shared definitions §1 matrix, built here: a strategy declares its own gate.
_FINANCIAL = frozenset({IndustryClass.FINANCIAL})
_FINANCIAL_AND_UTILITY = frozenset({IndustryClass.FINANCIAL, IndustryClass.UTILITY})
_SHAPES = {
    "ungated, warning for financial issuers": (SectorGate(gated=False, warn=_FINANCIAL), False, set(), _FINANCIAL),
    "gated, financial issuers refused": (SectorGate(gated=True, not_applicable=_FINANCIAL), True, _FINANCIAL, set()),
    "gated, financial issuers and utilities refused": (
        SectorGate(gated=True, not_applicable=_FINANCIAL_AND_UTILITY),
        True,
        _FINANCIAL_AND_UTILITY,
        set(),
    ),
}


@pytest.mark.parametrize("shape", sorted(_SHAPES))
@pytest.mark.parametrize("industry", list(IndustryClass))
def test_each_gate_shape_of_the_matrix_decides_every_class(shape: str, industry: IndustryClass) -> None:
    gate, gated, refused, warned = _SHAPES[shape]
    assert gate.gated is gated
    outcome = applicability_of(gate, industry)
    assert outcome.industry_class is industry
    if industry in refused:
        assert (outcome.outcome, outcome.reason_code) == (
            Applicability.NOT_APPLICABLE,
            ReasonCode.INDUSTRY_CLASS_NOT_APPLICABLE,
        )
    elif industry in warned:
        assert (outcome.outcome, outcome.reason_code) == (Applicability.APPLIES_WITH_WARNING, None)
    else:
        assert (outcome.outcome, outcome.reason_code) == (Applicability.APPLIES, None)


@pytest.mark.parametrize("shape", [name for name, (_, gated, _, _) in sorted(_SHAPES.items()) if gated])
def test_a_gated_gate_with_an_unknown_class_is_unavailable(shape: str) -> None:
    outcome = applicability_of(_SHAPES[shape][0], None)
    assert outcome == ApplicabilityOutcome(Applicability.UNAVAILABLE, ReasonCode.INDUSTRY_CLASS_UNKNOWN, None)


def test_an_ungated_gate_runs_with_the_class_still_unknown() -> None:
    gate = _SHAPES["ungated, warning for financial issuers"][0]
    assert applicability_of(gate, None) == ApplicabilityOutcome(Applicability.APPLIES, None, None)


def test_a_custom_gate_follows_its_own_sets() -> None:
    gate = SectorGate(gated=False, not_applicable=frozenset({IndustryClass.OTHER}))
    assert applicability_of(gate, IndustryClass.OTHER).outcome is Applicability.NOT_APPLICABLE
    assert applicability_of(gate, None).outcome is Applicability.APPLIES


def test_a_class_cannot_be_both_refused_and_warned() -> None:
    both = frozenset({IndustryClass.UTILITY})
    with pytest.raises(ValueError, match="both"):
        SectorGate(gated=True, not_applicable=both, warn=both)


def test_an_outcome_carries_a_reason_code_exactly_when_it_stops_the_strategy() -> None:
    with pytest.raises(ValueError, match="reason code"):
        ApplicabilityOutcome(Applicability.NOT_APPLICABLE, None, IndustryClass.FINANCIAL)
    with pytest.raises(ValueError, match="reason code"):
        ApplicabilityOutcome(Applicability.APPLIES, ReasonCode.INDUSTRY_CLASS_UNKNOWN, None)


def test_the_two_reason_codes_exist_and_make_valid_metric_results() -> None:
    assert ReasonCode("industry_class_not_applicable") is ReasonCode.INDUSTRY_CLASS_NOT_APPLICABLE
    assert ReasonCode("industry_class_unknown") is ReasonCode.INDUSTRY_CLASS_UNKNOWN
    refused = MetricResult(
        MetricStatus.NOT_APPLICABLE, reason_code=ReasonCode.INDUSTRY_CLASS_NOT_APPLICABLE, reason="x"
    )
    unknown = MetricResult(MetricStatus.UNAVAILABLE, reason_code=ReasonCode.INDUSTRY_CLASS_UNKNOWN, reason="y")
    assert (refused.status, unknown.status) == (MetricStatus.NOT_APPLICABLE, MetricStatus.UNAVAILABLE)
