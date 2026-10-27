"""Total debt and enterprise value."""

import math
from datetime import date
from typing import Any

import pytest

from investment_analysis_engine.analysis.shared.enterprise_value import (
    EnterpriseValueEvidence,
    compute_enterprise_value,
    compute_total_debt,
)
from investment_analysis_engine.analysis.shared.market_cap import MarketCapEvidence, ShareCountBasis
from investment_analysis_engine.analysis.shared.metric_evidence import MetricEvidence, Operand
from investment_analysis_engine.core.metric_result import MetricResult, MetricStatus, ReasonCode
from investment_analysis_engine.data.financial.facts import FinancialField as F
from investment_analysis_engine.data.financial.facts import InstantAbsenceReason as R
from tests.analysis.shared._issuer_inputs import absent, annual, balance, synthetic

_CLEAN = absent()


def _debt(ticker: str) -> MetricEvidence:
    return compute_total_debt(
        short_term_borrowings=balance(ticker, F.SHORT_TERM_BORROWINGS),
        current_portion_of_long_term_debt=balance(ticker, F.CURRENT_PORTION_OF_LONG_TERM_DEBT),
        noncurrent_long_term_debt=balance(ticker, F.NONCURRENT_LONG_TERM_DEBT),
        lease_liabilities_as_debt=balance(ticker, F.LEASE_LIABILITIES_AS_DEBT),
        long_term_debt_total=balance(ticker, F.LONG_TERM_DEBT_TOTAL),
        interest_expense=annual(ticker, F.INTEREST_EXPENSE),
    )


def _synthetic_debt(**changes: Any) -> MetricEvidence:
    arguments: dict[str, Any] = {
        "short_term_borrowings": _CLEAN,
        "current_portion_of_long_term_debt": _CLEAN,
        "noncurrent_long_term_debt": _CLEAN,
        "lease_liabilities_as_debt": _CLEAN,
        "long_term_debt_total": _CLEAN,
        "interest_expense": None,
    }
    arguments.update(changes)
    return compute_total_debt(**arguments)


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


# --- total debt: the issuers --------------------------------------------------------------------------------------


def test_alphabets_direct_total_does_not_reconcile_with_its_parts() -> None:
    evidence = _debt("GOOGL")
    _unavailable(evidence, ReasonCode.AMBIGUOUS_FACT)
    # 1,996 million + 46,547 million = 48,543 million, against a direct total of 49,085 million.
    assert [operand.name for operand in evidence.operands] == [
        "current_portion_of_long_term_debt",
        "noncurrent_long_term_debt",
    ]
    assert any(
        "Affected components: current_portion_of_long_term_debt, noncurrent_long_term_debt" in d
        for d in evidence.diagnostics
    )


def test_honeywell_has_debt_in_concepts_the_mapping_does_not_read() -> None:
    evidence = _debt("HON")
    _unavailable(evidence, ReasonCode.DEBT_NOT_VISIBLE)
    assert evidence.result.reason is not None
    assert "LongTermDebtAndCapitalLeaseObligationsCurrent" in evidence.result.reason


def test_monster_reports_no_debt_and_interest_expense_is_not_tagged() -> None:
    assert annual("MNST", F.INTEREST_EXPENSE) is None
    evidence = _debt("MNST")
    assert _ok(evidence) == 0.0
    assert evidence.zero_components == (
        "short_term_borrowings",
        "current_portion_of_long_term_debt",
        "noncurrent_long_term_debt",
        "lease_liabilities_as_debt",
    )
    assert evidence.operands == ()
    assert evidence.diagnostics[0].startswith("No reported debt")


def test_nutriens_ifrs_noncurrent_debt_is_unsupported_so_total_debt_is_too() -> None:
    _unavailable(_debt("NTR"), ReasonCode.UNSUPPORTED_MAPPING)
    _unavailable(_debt("SAP"), ReasonCode.UNSUPPORTED_MAPPING)


def test_walmart_sums_its_four_components_and_the_reconciled_total_is_not_added() -> None:
    evidence = _debt("WMT")
    # 6,596 + 3,542 + 34,624 + 6,761 million; the direct total of 38,166 million equals the two long-term parts.
    assert _ok(evidence) == 51_523_000_000.0
    assert evidence.zero_components == ()
    assert len(evidence.operands) == 4


def test_deere_tags_a_combined_current_debt_the_mapping_does_not_read() -> None:
    _unavailable(_debt("DE"), ReasonCode.DEBT_NOT_VISIBLE)


# --- total debt: the total-debt table of the financial math reference ---------------------------------------------


def test_with_one_component_present_the_clean_absences_are_zero_with_a_diagnostic() -> None:
    evidence = _synthetic_debt(short_term_borrowings=synthetic("stb", 100.0))
    assert _ok(evidence) == 100.0
    assert evidence.zero_components == (
        "current_portion_of_long_term_debt",
        "noncurrent_long_term_debt",
        "lease_liabilities_as_debt",
    )
    assert len(evidence.diagnostics) == 3


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
def test_with_one_component_present_any_other_absence_makes_total_debt_unavailable(
    absence: Any, code: ReasonCode
) -> None:
    evidence = _synthetic_debt(short_term_borrowings=synthetic("stb", 100.0), noncurrent_long_term_debt=absence)
    _unavailable(evidence, code)
    assert [operand.name for operand in evidence.operands] == ["short_term_borrowings"]


def test_with_one_component_present_an_unsupported_mapping_decides_over_an_earlier_failure() -> None:
    evidence = _synthetic_debt(
        short_term_borrowings=synthetic("stb", 100.0),
        current_portion_of_long_term_debt=absent(R.NOT_TAGGED, related="us-gaap:DebtCurrent"),
        noncurrent_long_term_debt=absent(R.UNSUPPORTED),
    )
    _unavailable(evidence, ReasonCode.UNSUPPORTED_MAPPING)


def test_with_no_component_and_no_interest_expense_total_debt_is_zero() -> None:
    for interest in (None, synthetic("interest_expense", 0.0)):
        evidence = _synthetic_debt(interest_expense=interest)
        assert _ok(evidence) == 0.0
        assert len(evidence.zero_components) == 4


def test_with_no_component_positive_interest_expense_means_debt_not_visible() -> None:
    evidence = _synthetic_debt(interest_expense=synthetic("interest_expense", 12.0))
    _unavailable(evidence, ReasonCode.DEBT_NOT_VISIBLE)
    assert [operand.name for operand in evidence.operands] == ["interest_expense"]


def test_with_no_component_a_tagged_related_concept_means_debt_not_visible() -> None:
    evidence = _synthetic_debt(current_portion_of_long_term_debt=absent(R.NOT_TAGGED, related="us-gaap:DebtCurrent"))
    _unavailable(evidence, ReasonCode.DEBT_NOT_VISIBLE)


def test_with_no_component_an_unsupported_mapping_wins_over_every_other_cause() -> None:
    evidence = _synthetic_debt(
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
def test_with_no_component_an_absence_that_cannot_say_there_is_no_debt_takes_its_code(
    reason: R, code: ReasonCode
) -> None:
    _unavailable(_synthetic_debt(lease_liabilities_as_debt=absent(reason)), code)


# --- total debt: the direct total ---------------------------------------------------------------------------------


def test_a_direct_total_that_equals_its_parts_reconciles_and_is_never_added() -> None:
    evidence = _synthetic_debt(
        current_portion_of_long_term_debt=synthetic("cp", 40.0),
        noncurrent_long_term_debt=synthetic("nc", 60.0),
        long_term_debt_total=synthetic("total", 100.0),
    )
    assert _ok(evidence) == 100.0
    assert "long_term_debt_total" not in [operand.name for operand in evidence.operands]


def test_a_direct_total_one_unit_off_is_ambiguous_with_no_tolerance() -> None:
    evidence = _synthetic_debt(
        current_portion_of_long_term_debt=synthetic("cp", 40.0),
        noncurrent_long_term_debt=synthetic("nc", 60.0),
        long_term_debt_total=synthetic("total", 101.0),
    )
    _unavailable(evidence, ReasonCode.AMBIGUOUS_FACT)


def test_where_the_parts_carry_related_concepts_their_own_absences_decide() -> None:
    # Honeywell's shape: a direct total, short-term borrowings, and parts that carry related concepts.
    total = synthetic("total", 29_046.0)
    related = absent(R.NOT_TAGGED, related="us-gaap:LongTermDebtAndCapitalLeaseObligations")
    _unavailable(
        _synthetic_debt(
            short_term_borrowings=synthetic("stb", 5.0),
            noncurrent_long_term_debt=related,
            long_term_debt_total=total,
        ),
        ReasonCode.DEBT_NOT_VISIBLE,
    )


def test_a_part_absent_for_another_reason_keeps_its_own_outcome_beside_a_direct_total() -> None:
    evidence = _synthetic_debt(
        current_portion_of_long_term_debt=synthetic("cp", 40.0),
        noncurrent_long_term_debt=absent(R.CONFLICT),
        long_term_debt_total=synthetic("total", 100.0),
    )
    _unavailable(evidence, ReasonCode.AMBIGUOUS_FACT)
    assert [operand.name for operand in evidence.operands] == ["current_portion_of_long_term_debt"]


def test_a_direct_total_with_both_parts_absent_and_clean_is_debt_not_visible() -> None:
    evidence = _synthetic_debt(short_term_borrowings=synthetic("stb", 5.0), long_term_debt_total=synthetic("t", 29.0))
    _unavailable(evidence, ReasonCode.DEBT_NOT_VISIBLE)
    # Even when nothing else is reported, a filer that tags only the direct total never has zero debt.
    _unavailable(_synthetic_debt(long_term_debt_total=synthetic("t", 29.0)), ReasonCode.DEBT_NOT_VISIBLE)


def test_a_direct_total_equal_to_the_one_present_part_reconciles_and_the_clean_part_is_zero() -> None:
    evidence = _synthetic_debt(
        noncurrent_long_term_debt=synthetic("nc", 60.0), long_term_debt_total=synthetic("total", 60.0)
    )
    assert _ok(evidence) == 60.0
    assert "current_portion_of_long_term_debt" in evidence.zero_components
    assert [operand.name for operand in evidence.operands] == ["noncurrent_long_term_debt"]


def test_a_direct_total_unequal_to_the_one_present_part_is_ambiguous_with_that_part_named() -> None:
    evidence = _synthetic_debt(
        current_portion_of_long_term_debt=synthetic("cp", 40.0), long_term_debt_total=synthetic("total", 60.0)
    )
    _unavailable(evidence, ReasonCode.AMBIGUOUS_FACT)
    assert [operand.name for operand in evidence.operands] == ["current_portion_of_long_term_debt"]
    assert any("Affected components" in note for note in evidence.diagnostics)


def test_a_zero_direct_total_with_both_parts_clean_reconciles_to_zero() -> None:
    evidence = _synthetic_debt(long_term_debt_total=synthetic("total", 0.0))
    assert _ok(evidence) == 0.0
    assert len(evidence.zero_components) == 4


def test_total_debt_overflow_is_not_a_number() -> None:
    evidence = _synthetic_debt(
        short_term_borrowings=synthetic("stb", 1.7e308), lease_liabilities_as_debt=synthetic("lease", 1.7e308)
    )
    assert evidence.result.status is MetricStatus.NOT_APPLICABLE
    assert evidence.result.value is None


# --- enterprise value ---------------------------------------------------------------------------------------------

_YEAR_END = date(2025, 12, 31)


def _cap_evidence(result: MetricResult) -> MarketCapEvidence:
    return MarketCapEvidence(
        result=result,
        share_count=synthetic("common_shares_outstanding", 3_000_000_000.0),
        share_count_basis=ShareCountBasis.YEAR_END,
        share_count_date=_YEAR_END,
        scaled_share_count=3_000_000_000.0,
        price=200.0,
        price_date=_YEAR_END,
        form="10-K",
        filing_currency="USD",
        quote_currency="USD",
    )


def _debt_evidence(result: MetricResult) -> MetricEvidence:
    return MetricEvidence(result=result, operands=(Operand("short_term_borrowings", synthetic("stb", 1.0)),))


_MARKET_CAP = _cap_evidence(MetricResult.ok(600_000_000_000.0))
_DEBT = _debt_evidence(MetricResult.ok(51_523_000_000.0))


def _ev(**changes: Any) -> EnterpriseValueEvidence:
    arguments: dict[str, Any] = {
        "market_cap": _MARKET_CAP,
        "total_debt": _DEBT,
        "preferred_stock": _CLEAN,
        "noncontrolling_interest": synthetic("nci", 6_270_000_000.0),
        "cash_and_equivalents": synthetic("cash", 10_727_000_000.0),
        "short_term_investments": _CLEAN,
        "current_assets": synthetic("ca", 84_874_000_000.0),
    }
    arguments.update(changes)
    return compute_enterprise_value(**arguments)


def _ev_ok(evidence: EnterpriseValueEvidence) -> float:
    assert evidence.result.status is MetricStatus.OK
    assert evidence.result.value is not None
    assert math.isfinite(evidence.result.value)
    return evidence.result.value


def _ev_unavailable_with(evidence: EnterpriseValueEvidence, code: ReasonCode) -> None:
    assert evidence.result.status is MetricStatus.UNAVAILABLE
    assert evidence.result.value is None
    assert evidence.result.reason_code is code
    assert evidence.result.reason is not None
    assert evidence.result.reason.strip()


def test_ev_keeps_the_market_cap_and_total_debt_evidence_it_used() -> None:
    evidence = _ev()
    assert evidence.market_cap is _MARKET_CAP
    assert evidence.total_debt is _DEBT
    assert evidence.market_cap.share_count is not None
    assert (evidence.market_cap.scaled_share_count, evidence.market_cap.price) == (3_000_000_000.0, 200.0)
    assert [operand.name for operand in evidence.total_debt.operands] == ["short_term_borrowings"]


def test_ev_keeps_the_evidence_when_it_is_unavailable_too() -> None:
    refused_cap = _cap_evidence(MetricResult.failure(MetricStatus.UNAVAILABLE, ReasonCode.INCOMPATIBLE_SCOPE, "20-F"))
    evidence = _ev(market_cap=refused_cap)
    _ev_unavailable_with(evidence, ReasonCode.INCOMPATIBLE_SCOPE)
    assert evidence.market_cap is refused_cap
    assert evidence.total_debt is _DEBT
    assert evidence.market_cap.price == 200.0


def test_ev_shows_the_zero_components_of_debt_and_its_own_apart() -> None:
    debt = _synthetic_debt(short_term_borrowings=synthetic("stb", 100.0))
    evidence = _ev(total_debt=debt)
    assert evidence.total_debt.zero_components == (
        "current_portion_of_long_term_debt",
        "noncurrent_long_term_debt",
        "lease_liabilities_as_debt",
    )
    assert evidence.zero_components == ("preferred_stock", "short_term_investments")


def test_walmart_ev_with_absent_preferred_stock_and_short_term_investments_taken_as_zero() -> None:
    evidence = compute_enterprise_value(
        market_cap=_MARKET_CAP,
        total_debt=_debt("WMT"),
        preferred_stock=balance("WMT", F.PREFERRED_STOCK),
        noncontrolling_interest=balance("WMT", F.NONCONTROLLING_INTEREST),
        cash_and_equivalents=balance("WMT", F.CASH_AND_EQUIVALENTS),
        short_term_investments=balance("WMT", F.SHORT_TERM_INVESTMENTS),
        current_assets=balance("WMT", F.CURRENT_ASSETS),
    )
    # 600,000 + 51,523 + 0 + 6,270 - 10,727 - 0 million.
    assert _ev_ok(evidence) == 647_066_000_000.0
    assert evidence.total_debt.result.value == 51_523_000_000.0
    assert evidence.zero_components == ("preferred_stock", "short_term_investments")
    assert [operand.name for operand in evidence.operands] == ["cash_and_equivalents", "noncontrolling_interest"]


def test_honeywell_classified_balance_sheet_reads_an_absent_short_term_investments_line_as_zero() -> None:
    # Honeywell tags current assets, so a classified balance sheet; its own short-term investments line is tagged,
    # so the absence is the one Walmart shows above, and Honeywell's tagged figure is subtracted.
    evidence = _ev(
        short_term_investments=balance("HON", F.SHORT_TERM_INVESTMENTS),
        current_assets=balance("HON", F.CURRENT_ASSETS),
    )
    assert _ev_ok(evidence) == 600_000e6 + 51_523e6 + 6_270e6 - 10_727e6 - 443e6
    # The same classified current assets with the line absent give zero.
    assert "short_term_investments" in _ev(current_assets=balance("HON", F.CURRENT_ASSETS)).zero_components


def test_deeres_unclassified_balance_sheet_makes_short_term_investments_and_so_ev_unavailable() -> None:
    evidence = _ev(
        short_term_investments=balance("DE", F.SHORT_TERM_INVESTMENTS),
        current_assets=balance("DE", F.CURRENT_ASSETS),
        cash_and_equivalents=balance("DE", F.CASH_AND_EQUIVALENTS),
    )
    _ev_unavailable_with(evidence, ReasonCode.MISSING_FACT)
    assert evidence.result.reason is not None
    assert "unclassified" in evidence.result.reason


def test_deeres_ev_is_unavailable_through_total_debt_as_well() -> None:
    evidence = compute_enterprise_value(
        market_cap=_MARKET_CAP,
        total_debt=_debt("DE"),
        preferred_stock=balance("DE", F.PREFERRED_STOCK),
        noncontrolling_interest=balance("DE", F.NONCONTROLLING_INTEREST),
        cash_and_equivalents=balance("DE", F.CASH_AND_EQUIVALENTS),
        short_term_investments=balance("DE", F.SHORT_TERM_INVESTMENTS),
        current_assets=balance("DE", F.CURRENT_ASSETS),
    )
    _ev_unavailable_with(evidence, ReasonCode.DEBT_NOT_VISIBLE)
    assert evidence.total_debt.result.reason_code is ReasonCode.DEBT_NOT_VISIBLE


def test_nutriens_ev_is_unavailable_with_an_unsupported_mapping() -> None:
    evidence = compute_enterprise_value(
        market_cap=_MARKET_CAP,
        total_debt=_debt("NTR"),
        preferred_stock=balance("NTR", F.PREFERRED_STOCK),
        noncontrolling_interest=balance("NTR", F.NONCONTROLLING_INTEREST),
        cash_and_equivalents=balance("NTR", F.CASH_AND_EQUIVALENTS),
        short_term_investments=balance("NTR", F.SHORT_TERM_INVESTMENTS),
        current_assets=balance("NTR", F.CURRENT_ASSETS),
    )
    _ev_unavailable_with(evidence, ReasonCode.UNSUPPORTED_MAPPING)


def test_ev_may_be_negative() -> None:
    evidence = _ev(market_cap=_cap_evidence(MetricResult.ok(1.0)), total_debt=_debt_evidence(MetricResult.ok(0.0)))
    assert _ev_ok(evidence) == 1.0 + 6_270e6 - 10_727e6
    assert _ev_ok(evidence) < 0


@pytest.mark.parametrize("name", ["market_cap", "total_debt"])
def test_ev_needs_market_cap_and_total_debt(name: str) -> None:
    failed = MetricResult.failure(MetricStatus.UNAVAILABLE, ReasonCode.MISSING_FACT, "nothing")
    wrap = _cap_evidence if name == "market_cap" else _debt_evidence
    _ev_unavailable_with(_ev(**{name: wrap(failed)}), ReasonCode.MISSING_FACT)


def test_ev_needs_cash_with_the_tables_code() -> None:
    _ev_unavailable_with(_ev(cash_and_equivalents=absent(R.CONFLICT)), ReasonCode.AMBIGUOUS_FACT)
    _ev_unavailable_with(_ev(cash_and_equivalents=absent(R.NOT_TAGGED)), ReasonCode.MISSING_FACT)


@pytest.mark.parametrize("name", ["preferred_stock", "noncontrolling_interest", "short_term_investments"])
@pytest.mark.parametrize(
    ("reason", "code"),
    [
        (R.UNSUPPORTED, ReasonCode.UNSUPPORTED_MAPPING),
        (R.OTHER_CONCEPT, ReasonCode.MISSING_FACT),
        (R.CONFLICT, ReasonCode.AMBIGUOUS_FACT),
    ],
)
def test_an_optional_component_is_zero_only_for_not_tagged(name: str, reason: R, code: ReasonCode) -> None:
    _ev_unavailable_with(_ev(**{name: absent(reason)}), code)


def test_a_not_tagged_optional_component_is_zero_with_a_diagnostic() -> None:
    evidence = _ev(noncontrolling_interest=absent())
    assert evidence.zero_components == ("preferred_stock", "noncontrolling_interest", "short_term_investments")
    assert any("noncontrolling_interest is not tagged" in note for note in evidence.diagnostics)


def test_ev_overflow_is_not_a_number() -> None:
    evidence = _ev(
        market_cap=_cap_evidence(MetricResult.ok(1.7e308)), total_debt=_debt_evidence(MetricResult.ok(1.7e308))
    )
    assert evidence.result.status is MetricStatus.NOT_APPLICABLE
    assert evidence.market_cap.result.value == 1.7e308
