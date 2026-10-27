"""The shared metric result type and the table that maps a balance-sheet absence to a reason code."""

import pytest

from investment_analysis_engine.analysis.shared.metric_evidence import (
    InputUnavailable,
    MetricEvidence,
    absence_reason_code,
    absent_input,
    missing_annual,
    unavailable,
)
from investment_analysis_engine.core.metric_result import MetricStatus, ReasonCode
from investment_analysis_engine.data.financial.facts import InstantAbsenceReason
from tests.analysis.shared._issuer_inputs import absent

# Written by hand, one line per member of the enumeration.
EXPECTED: dict[InstantAbsenceReason, ReasonCode] = {
    InstantAbsenceReason.NOT_TAGGED: ReasonCode.MISSING_FACT,
    InstantAbsenceReason.OTHER_CONCEPT: ReasonCode.MISSING_FACT,
    InstantAbsenceReason.NO_ANCHOR_FILING: ReasonCode.MISSING_FACT,
    InstantAbsenceReason.CONFLICT: ReasonCode.AMBIGUOUS_FACT,
    InstantAbsenceReason.UNSUPPORTED: ReasonCode.UNSUPPORTED_MAPPING,
    InstantAbsenceReason.AFTER_BOUNDARY: ReasonCode.NOT_AVAILABLE_AS_OF,
    InstantAbsenceReason.BASIS_MISMATCH: ReasonCode.INCOMPATIBLE_SCOPE,
}


def test_the_table_names_every_member_of_the_enumeration() -> None:
    # A new member of the enumeration fails here until it is mapped.
    assert set(EXPECTED) == set(InstantAbsenceReason)


@pytest.mark.parametrize("reason", list(InstantAbsenceReason))
def test_every_absence_reason_has_its_code(reason: InstantAbsenceReason) -> None:
    assert absence_reason_code(reason) is EXPECTED[reason]


def test_the_two_reason_codes_exist_with_their_values() -> None:
    assert ReasonCode.UNSUPPORTED_MAPPING.value == "unsupported_mapping"
    assert ReasonCode.DEBT_NOT_VISIBLE.value == "debt_not_visible"


def test_an_absent_input_is_unavailable_with_the_tables_code_and_a_reason() -> None:
    evidence = absent_input("cash", absent(InstantAbsenceReason.CONFLICT))
    assert evidence.result.status is MetricStatus.UNAVAILABLE
    assert evidence.result.reason_code is ReasonCode.AMBIGUOUS_FACT
    assert evidence.result.reason is not None
    assert "cash" in evidence.result.reason
    assert evidence.operands == ()
    assert evidence.zero_components == ()


def test_a_missing_annual_input_is_unavailable_with_missing_fact() -> None:
    evidence = missing_annual("operating_income")
    assert (evidence.result.status, evidence.result.reason_code) == (MetricStatus.UNAVAILABLE, ReasonCode.MISSING_FACT)
    assert evidence.result.reason is not None
    assert "operating_income" in evidence.result.reason


def test_unavailable_carries_the_operands_and_diagnostics_it_is_given() -> None:
    evidence = unavailable(ReasonCode.AMBIGUOUS_FACT, "why", diagnostics=("note",))
    assert evidence == MetricEvidence(result=evidence.result, diagnostics=("note",))
    assert evidence.result.value is None


def test_an_unavailable_input_needs_a_reason() -> None:
    assert InputUnavailable(ReasonCode.MISSING_FACT, "no count").reason == "no count"
    with pytest.raises(ValueError, match="non-empty reason"):
        InputUnavailable(ReasonCode.MISSING_FACT, "  ")
