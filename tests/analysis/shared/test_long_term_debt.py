"""Long-term debt: the current portion plus the noncurrent long-term debt, by the rules of total debt."""

import math
from typing import Any

import pytest

from investment_analysis_engine.analysis.shared.enterprise_value import compute_long_term_debt, compute_total_debt
from investment_analysis_engine.analysis.shared.metric_evidence import MetricEvidence
from investment_analysis_engine.core.metric_result import MetricStatus, ReasonCode
from investment_analysis_engine.data.financial.facts import FinancialField as F
from investment_analysis_engine.data.financial.facts import InstantAbsenceReason as R
from tests.analysis.shared._issuer_inputs import absent, annual, balance, synthetic

_CLEAN = absent()
_ARGUMENTS = (
    "short_term_borrowings",
    "current_portion_of_long_term_debt",
    "noncurrent_long_term_debt",
    "lease_liabilities_as_debt",
    "long_term_debt_total",
)


def _long_term(**changes: Any) -> MetricEvidence:
    arguments: dict[str, Any] = dict.fromkeys(_ARGUMENTS, _CLEAN) | {"interest_expense": None}
    arguments.update(changes)
    return compute_long_term_debt(**arguments)


def _issuer(ticker: str) -> dict[str, Any]:
    fields = (
        F.SHORT_TERM_BORROWINGS,
        F.CURRENT_PORTION_OF_LONG_TERM_DEBT,
        F.NONCURRENT_LONG_TERM_DEBT,
        F.LEASE_LIABILITIES_AS_DEBT,
        F.LONG_TERM_DEBT_TOTAL,
    )
    arguments: dict[str, Any] = {name: balance(ticker, field) for name, field in zip(_ARGUMENTS, fields, strict=True)}
    arguments["interest_expense"] = annual(ticker, F.INTEREST_EXPENSE)
    return arguments


def _ok(evidence: MetricEvidence) -> float:
    assert evidence.result.status is MetricStatus.OK
    assert evidence.result.value is not None
    assert math.isfinite(evidence.result.value)
    assert evidence.result.reason_code is None
    return evidence.result.value


def _unavailable(evidence: MetricEvidence, code: ReasonCode) -> None:
    assert evidence.result.status is MetricStatus.UNAVAILABLE
    assert evidence.result.value is None
    assert evidence.result.reason_code is code
    assert evidence.result.reason is not None
    assert evidence.result.reason.strip()


# --- the sum of the two long-term parts --------------------------------------------------------------------------


def test_long_term_debt_is_the_current_portion_plus_the_noncurrent_debt() -> None:
    evidence = _long_term(
        current_portion_of_long_term_debt=synthetic("cp", 40.0), noncurrent_long_term_debt=synthetic("nc", 60.0)
    )
    assert _ok(evidence) == 100.0
    assert [operand.name for operand in evidence.operands] == [
        "current_portion_of_long_term_debt",
        "noncurrent_long_term_debt",
    ]
    assert evidence.zero_components == ()


def test_short_term_borrowings_and_leases_are_never_added() -> None:
    evidence = _long_term(
        short_term_borrowings=synthetic("stb", 7.0),
        current_portion_of_long_term_debt=synthetic("cp", 40.0),
        noncurrent_long_term_debt=synthetic("nc", 60.0),
        lease_liabilities_as_debt=synthetic("lease", 11.0),
    )
    assert _ok(evidence) == 100.0
    assert "short_term_borrowings" not in [operand.name for operand in evidence.operands]
    assert "lease_liabilities_as_debt" not in [operand.name for operand in evidence.operands]


def test_total_debt_is_unchanged_by_the_new_function() -> None:
    arguments: dict[str, Any] = {
        "short_term_borrowings": synthetic("stb", 7.0),
        "current_portion_of_long_term_debt": synthetic("cp", 40.0),
        "noncurrent_long_term_debt": synthetic("nc", 60.0),
        "lease_liabilities_as_debt": synthetic("lease", 11.0),
        "long_term_debt_total": _CLEAN,
        "interest_expense": None,
    }
    assert _ok(compute_total_debt(**arguments)) == 118.0
    assert _ok(compute_long_term_debt(**arguments)) == 100.0


# --- an absent part ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("present_name", "zero_name"),
    [
        ("current_portion_of_long_term_debt", "noncurrent_long_term_debt"),
        ("noncurrent_long_term_debt", "current_portion_of_long_term_debt"),
    ],
)
def test_an_untagged_part_is_zero_with_a_diagnostic_when_the_other_part_is_present(
    present_name: str, zero_name: str
) -> None:
    evidence = _long_term(**{present_name: synthetic("part", 60.0)})
    assert _ok(evidence) == 60.0
    assert evidence.zero_components == (zero_name,)
    assert len(evidence.diagnostics) == 1
    assert zero_name in evidence.diagnostics[0]


def test_both_parts_untagged_are_zero_when_short_term_borrowings_are_present() -> None:
    evidence = _long_term(short_term_borrowings=synthetic("stb", 5.0))
    assert _ok(evidence) == 0.0
    assert evidence.zero_components == ("current_portion_of_long_term_debt", "noncurrent_long_term_debt")
    assert evidence.operands == ()


def test_both_parts_untagged_are_zero_when_only_leases_are_present() -> None:
    assert _ok(_long_term(lease_liabilities_as_debt=synthetic("lease", 5.0))) == 0.0


@pytest.mark.parametrize(
    ("absence", "code"),
    [
        (absent(R.OTHER_CONCEPT), ReasonCode.MISSING_FACT),
        (absent(R.NO_ANCHOR_FILING), ReasonCode.MISSING_FACT),
        (absent(R.CONFLICT), ReasonCode.AMBIGUOUS_FACT),
        (absent(R.UNSUPPORTED), ReasonCode.UNSUPPORTED_MAPPING),
        (absent(R.AFTER_BOUNDARY), ReasonCode.NOT_AVAILABLE_AS_OF),
        (absent(R.BASIS_MISMATCH), ReasonCode.INCOMPATIBLE_SCOPE),
        (absent(R.NOT_TAGGED, related="us-gaap:DebtCurrent"), ReasonCode.DEBT_NOT_VISIBLE),
        (absent(R.OTHER_CONCEPT, related="us-gaap:DebtCurrent"), ReasonCode.DEBT_NOT_VISIBLE),
    ],
)
def test_a_part_absent_for_any_other_reason_makes_long_term_debt_unavailable_with_the_absence_table_code(
    absence: Any, code: ReasonCode
) -> None:
    evidence = _long_term(current_portion_of_long_term_debt=synthetic("cp", 40.0), noncurrent_long_term_debt=absence)
    _unavailable(evidence, code)
    assert [operand.name for operand in evidence.operands] == ["current_portion_of_long_term_debt"]


def test_an_unsupported_mapping_decides_over_an_earlier_failure() -> None:
    evidence = _long_term(
        short_term_borrowings=synthetic("stb", 5.0),
        current_portion_of_long_term_debt=absent(R.NOT_TAGGED, related="us-gaap:DebtCurrent"),
        noncurrent_long_term_debt=absent(R.UNSUPPORTED),
    )
    _unavailable(evidence, ReasonCode.UNSUPPORTED_MAPPING)


def test_without_an_unsupported_mapping_the_first_gap_in_part_order_decides() -> None:
    evidence = _long_term(
        short_term_borrowings=synthetic("stb", 5.0),
        current_portion_of_long_term_debt=absent(R.CONFLICT),
        noncurrent_long_term_debt=absent(R.OTHER_CONCEPT),
    )
    _unavailable(evidence, ReasonCode.AMBIGUOUS_FACT)


# --- a gap in short-term borrowings or leases ---------------------------------------------------------------------


@pytest.mark.parametrize("name", ["short_term_borrowings", "lease_liabilities_as_debt"])
@pytest.mark.parametrize(
    "gap",
    [
        absent(R.UNSUPPORTED),
        absent(R.CONFLICT),
        absent(R.OTHER_CONCEPT),
        absent(R.NOT_TAGGED, related="us-gaap:DebtCurrent"),
    ],
)
def test_a_gap_in_short_term_borrowings_or_leases_does_not_make_long_term_debt_unavailable(name: str, gap: Any) -> None:
    evidence = _long_term(**{name: gap}, current_portion_of_long_term_debt=synthetic("cp", 40.0))
    assert _ok(evidence) == 40.0
    assert evidence.zero_components == ("noncurrent_long_term_debt",)


# --- the direct total --------------------------------------------------------------------------------------------


def test_a_direct_total_that_equals_its_parts_reconciles_and_is_never_added() -> None:
    evidence = _long_term(
        current_portion_of_long_term_debt=synthetic("cp", 40.0),
        noncurrent_long_term_debt=synthetic("nc", 60.0),
        long_term_debt_total=synthetic("total", 100.0),
    )
    assert _ok(evidence) == 100.0
    assert "long_term_debt_total" not in [operand.name for operand in evidence.operands]


def test_a_direct_total_one_unit_off_is_ambiguous_before_any_component_rule() -> None:
    evidence = _long_term(
        short_term_borrowings=synthetic("stb", 5.0),
        current_portion_of_long_term_debt=synthetic("cp", 40.0),
        noncurrent_long_term_debt=synthetic("nc", 60.0),
        long_term_debt_total=synthetic("total", 101.0),
    )
    _unavailable(evidence, ReasonCode.AMBIGUOUS_FACT)


def test_a_direct_total_with_neither_part_reported_is_debt_not_visible_even_with_other_debt_present() -> None:
    _unavailable(
        _long_term(short_term_borrowings=synthetic("stb", 5.0), long_term_debt_total=synthetic("t", 29.0)),
        ReasonCode.DEBT_NOT_VISIBLE,
    )
    _unavailable(_long_term(long_term_debt_total=synthetic("t", 29.0)), ReasonCode.DEBT_NOT_VISIBLE)


def test_a_direct_total_equal_to_the_one_present_part_reconciles_and_the_untagged_part_is_zero() -> None:
    evidence = _long_term(
        noncurrent_long_term_debt=synthetic("nc", 60.0), long_term_debt_total=synthetic("total", 60.0)
    )
    assert _ok(evidence) == 60.0
    assert evidence.zero_components == ("current_portion_of_long_term_debt",)


def test_a_zero_direct_total_with_both_parts_untagged_reconciles_to_zero() -> None:
    assert _ok(_long_term(long_term_debt_total=synthetic("total", 0.0))) == 0.0


def test_a_part_absent_for_another_reason_keeps_its_own_outcome_beside_a_direct_total() -> None:
    evidence = _long_term(
        current_portion_of_long_term_debt=synthetic("cp", 40.0),
        noncurrent_long_term_debt=absent(R.CONFLICT),
        long_term_debt_total=synthetic("total", 100.0),
    )
    _unavailable(evidence, ReasonCode.AMBIGUOUS_FACT)


# --- none of the four debt concepts present ------------------------------------------------------------------------


def test_with_no_debt_concept_and_no_interest_expense_long_term_debt_is_zero_over_all_four_components() -> None:
    for interest in (None, synthetic("interest_expense", 0.0)):
        evidence = _long_term(interest_expense=interest)
        assert _ok(evidence) == 0.0
        assert evidence.zero_components == (
            "short_term_borrowings",
            "current_portion_of_long_term_debt",
            "noncurrent_long_term_debt",
            "lease_liabilities_as_debt",
        )
        assert evidence.diagnostics[0].startswith("No reported debt")


def test_with_no_debt_concept_positive_interest_expense_means_debt_not_visible() -> None:
    evidence = _long_term(interest_expense=synthetic("interest_expense", 12.0))
    _unavailable(evidence, ReasonCode.DEBT_NOT_VISIBLE)
    assert [operand.name for operand in evidence.operands] == ["interest_expense"]


def test_with_no_debt_concept_a_tagged_related_concept_means_debt_not_visible() -> None:
    _unavailable(
        _long_term(current_portion_of_long_term_debt=absent(R.NOT_TAGGED, related="us-gaap:DebtCurrent")),
        ReasonCode.DEBT_NOT_VISIBLE,
    )


def test_with_no_debt_concept_an_unsupported_component_makes_it_unavailable_even_in_short_term_borrowings() -> None:
    _unavailable(_long_term(short_term_borrowings=absent(R.UNSUPPORTED)), ReasonCode.UNSUPPORTED_MAPPING)
    _unavailable(_long_term(lease_liabilities_as_debt=absent(R.UNSUPPORTED)), ReasonCode.UNSUPPORTED_MAPPING)


def test_with_no_debt_concept_an_unsupported_mapping_wins_over_every_other_cause() -> None:
    evidence = _long_term(
        short_term_borrowings=absent(R.NOT_TAGGED, related="us-gaap:DebtCurrent"),
        noncurrent_long_term_debt=absent(R.UNSUPPORTED),
        interest_expense=synthetic("interest_expense", 12.0),
    )
    _unavailable(evidence, ReasonCode.UNSUPPORTED_MAPPING)


@pytest.mark.parametrize(
    ("reason", "code"),
    [
        (R.OTHER_CONCEPT, ReasonCode.MISSING_FACT),
        (R.CONFLICT, ReasonCode.AMBIGUOUS_FACT),
        (R.AFTER_BOUNDARY, ReasonCode.NOT_AVAILABLE_AS_OF),
        (R.BASIS_MISMATCH, ReasonCode.INCOMPATIBLE_SCOPE),
        (R.NO_ANCHOR_FILING, ReasonCode.MISSING_FACT),
    ],
)
def test_with_no_debt_concept_an_absence_that_cannot_say_there_is_no_debt_takes_its_code(
    reason: R, code: ReasonCode
) -> None:
    _unavailable(_long_term(lease_liabilities_as_debt=absent(reason)), code)


def test_long_term_debt_overflow_is_not_a_number() -> None:
    evidence = _long_term(
        current_portion_of_long_term_debt=synthetic("cp", 1.7e308), noncurrent_long_term_debt=synthetic("nc", 1.7e308)
    )
    assert evidence.result.status is MetricStatus.NOT_APPLICABLE
    assert evidence.result.value is None


# --- the regression issuers ---------------------------------------------------------------------------------------


def test_nutrien_and_sap_have_unsupported_noncurrent_mappings_so_long_term_debt_is_unavailable() -> None:
    _unavailable(compute_long_term_debt(**_issuer("NTR")), ReasonCode.UNSUPPORTED_MAPPING)
    _unavailable(compute_long_term_debt(**_issuer("SAP")), ReasonCode.UNSUPPORTED_MAPPING)


def test_monster_reports_no_debt_so_long_term_debt_is_zero() -> None:
    evidence = compute_long_term_debt(**_issuer("MNST"))
    assert _ok(evidence) == 0.0
    assert len(evidence.zero_components) == 4


def test_walmarts_long_term_debt_is_its_two_parts_and_equals_the_reconciled_direct_total() -> None:
    arguments = _issuer("WMT")
    evidence = compute_long_term_debt(**arguments)
    # The direct total is the same figure: the reconciliation succeeded, and it is not added.
    assert _ok(evidence) == arguments["long_term_debt_total"].value
    assert _ok(evidence) < _ok(compute_total_debt(**arguments))


def test_alphabets_direct_total_does_not_reconcile_with_its_parts() -> None:
    _unavailable(compute_long_term_debt(**_issuer("GOOGL")), ReasonCode.AMBIGUOUS_FACT)


def test_honeywell_and_deere_have_debt_in_concepts_the_mapping_does_not_read() -> None:
    _unavailable(compute_long_term_debt(**_issuer("HON")), ReasonCode.DEBT_NOT_VISIBLE)
    _unavailable(compute_long_term_debt(**_issuer("DE")), ReasonCode.DEBT_NOT_VISIBLE)
