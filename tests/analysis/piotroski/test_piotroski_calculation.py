"""The Piotroski F-Score calculation: the arithmetic oracle, every strict comparison and every unavailable case.

Expected values are written here as ``Fraction`` or literal outcomes. The calculator never produces them.
"""

import math
from dataclasses import replace
from fractions import Fraction
from typing import Any

import pytest

from investment_analysis_engine.analysis.shared.metric_evidence import InputUnavailable, MetricEvidence, Operand
from investment_analysis_engine.analysis.shared.metric_inputs import ShareCountPath, YearEndShareCount
from investment_analysis_engine.core.metric_result import MetricResult, MetricStatus, ReasonCode
from investment_analysis_engine.data.financial.provenance import ComponentLineage, ResolvedInput, SourceKind
from investment_analysis_engine.data.sec_edgar.financial_facts import _SEC_DERIVED_COMMON_SHARES_FIELD
from investment_analysis_engine.strategies.piotroski_calculation import (
    CheckOutcome,
    Completeness,
    NamedMetric,
    PiotroskiInputs,
    PiotroskiScoreResult,
    PiotroskiTestResult,
    calculate_f_score,
)
from tests._sec_instants import NOW
from tests.analysis.shared._issuer_inputs import synthetic

ACCESSION = "0000000000-25-000001"
PASS, FAIL, UNAVAILABLE = CheckOutcome.PASS, CheckOutcome.FAIL, CheckOutcome.UNAVAILABLE

# Base case of the arithmetic oracle: all nine tests pass.
BASE: dict[str, float] = {
    "total_assets_t2": 80,
    "total_assets_t1": 100,
    "total_assets_t": 120,
    "net_income_t1": 4,
    "net_income_t": 8,
    "operating_cash_flow_t": 10,
    "sales_t1": 80,
    "sales_t": 120,
    "gross_profit_t1": 24,
    "gross_profit_t": 42,
    "long_term_debt_t1": 20,
    "long_term_debt_t": 18,
    "current_assets_t1": 40,
    "current_assets_t": 54,
    "current_liabilities_t1": 20,
    "current_liabilities_t": 24,
    "shares_t1": 100,
    "shares_t": 100,
}


def fact(name: str, value: float, *, currency: str | None = "USD", field: str | None = None) -> ResolvedInput:
    """Return a resolved input of ``value``, under us-gaap unless ``field`` names another concept."""
    return replace(
        synthetic(name, float(value)),
        currency=currency,
        provider_field=field if field else "us-gaap:" + "".join(word.capitalize() for word in name.split("_")),
    )


def evidence(name: str, value: float) -> MetricEvidence:
    """Return ok shared-metric evidence of ``value`` with one operand."""
    return MetricEvidence(MetricResult.ok(float(value)), operands=(Operand(name, fact(name, value)),))


def share_count(
    name: str, value: float, *, accession: str = ACCESSION, path: ShareCountPath = ShareCountPath.DIRECT
) -> YearEndShareCount:
    """Return a share count of ``value`` taken from ``accession`` by ``path``."""
    return YearEndShareCount(fact(name, value, currency=None), accession, path)


def _build(name: str, value: Any) -> Any:
    """Return the operand for a number, or ``value`` itself when it is already an operand."""
    if not isinstance(value, (int, float)):
        return value
    if name.startswith("shares_"):
        return share_count(name, value)
    if name.startswith(("gross_profit_", "long_term_debt_")):
        return evidence(name, value)
    return fact(name, value)


def make(**changes: Any) -> PiotroskiInputs:
    """Return the base-case inputs with ``changes`` applied; a number becomes an operand."""
    merged: dict[str, Any] = {**BASE, **changes}
    return PiotroskiInputs(**{name: _build(name, value) for name, value in merged.items()})


def missing(code: ReasonCode = ReasonCode.MISSING_FACT) -> InputUnavailable:
    """Return an unavailable input."""
    return InputUnavailable(code, "synthetic gap")


def outcomes(result: PiotroskiScoreResult) -> tuple[CheckOutcome, ...]:
    """Return the nine outcomes in order."""
    return tuple(item.outcome for item in result.tests)


def ratio(result: PiotroskiScoreResult, number: int, name: str) -> float:
    """Return the value of the ratio ``name`` of test ``number``."""
    for item in result.tests[number - 1].ratios:
        if item.name == name:
            assert item.result.value is not None
            return item.result.value
    raise AssertionError(f"test {number} has no ratio {name}")


def assert_score(result: PiotroskiScoreResult, value: float | None, completeness: Completeness | None) -> None:
    """Assert the score, its completeness and, when unavailable, its code."""
    assert result.completeness is completeness
    if value is None:
        assert result.score.status is MetricStatus.UNAVAILABLE
        assert result.score.reason_code is ReasonCode.INSUFFICIENT_TESTS
        assert result.score.value is None
    else:
        assert result.score.status is MetricStatus.OK
        assert result.score.value == value


def unavailable_numbers(result: PiotroskiScoreResult) -> tuple[int, ...]:
    """Return the numbers of the unavailable tests."""
    return tuple(item.number for item in result.tests if item.outcome is UNAVAILABLE)


# ---------------------------------------------------------------------------
# The arithmetic oracle
# ---------------------------------------------------------------------------


def test_the_base_case_passes_all_nine_tests_with_the_oracle_ratios() -> None:
    result = calculate_f_score(make())
    assert outcomes(result) == (PASS,) * 9
    assert_score(result, 9.0, Completeness.COMPLETE)
    assert result.available_count == 9
    assert result.unavailable_tests == ()
    expected = {
        (1, "roa_t"): Fraction(2, 25),
        (2, "cfo_over_assets_t"): Fraction(1, 10),
        (3, "roa_t"): Fraction(2, 25),
        (3, "roa_t1"): Fraction(1, 20),
        (5, "leverage_t"): Fraction(9, 55),
        (5, "leverage_t1"): Fraction(2, 9),
        (6, "current_ratio_t"): Fraction(9, 4),
        (6, "current_ratio_t1"): Fraction(2),
        (8, "gross_margin_t"): Fraction(7, 20),
        (8, "gross_margin_t1"): Fraction(3, 10),
        (9, "turnover_t"): Fraction(6, 5),
        (9, "turnover_t1"): Fraction(1),
    }
    for (number, name), exact in expected.items():
        assert ratio(result, number, name) == float(exact)


def test_the_tests_are_numbered_named_and_grouped_in_the_fixed_order() -> None:
    result = calculate_f_score(make())
    assert [(item.number, item.name, item.group) for item in result.tests] == [
        (1, "Positive ROA", "Profitability"),
        (2, "Positive CFO", "Profitability"),
        (3, "Improving ROA", "Profitability"),
        (4, "Cash exceeds income", "Profitability"),
        (5, "Falling leverage", "Leverage and liquidity"),
        (6, "Improving liquidity", "Leverage and liquidity"),
        (7, "No dilution", "Leverage and liquidity"),
        (8, "Improving margin", "Efficiency"),
        (9, "Improving turnover", "Efficiency"),
    ]


def test_turnover_uses_beginning_of_year_assets_not_average_assets() -> None:
    result = calculate_f_score(make(total_assets_t=200))
    assert outcomes(result) == (PASS,) * 9
    assert ratio(result, 9, "turnover_t") == float(Fraction(6, 5))
    assert ratio(result, 9, "turnover_t1") == 1.0


def test_one_more_share_fails_only_the_dilution_test() -> None:
    result = calculate_f_score(make(shares_t=101))
    assert outcomes(result) == (PASS,) * 6 + (FAIL,) + (PASS,) * 2
    assert_score(result, 8.0, Completeness.COMPLETE)


def test_missing_total_assets_two_years_back_leaves_exactly_tests_3_5_and_9_unavailable() -> None:
    result = calculate_f_score(make(total_assets_t2=missing()))
    assert unavailable_numbers(result) == (3, 5, 9)
    assert result.available_count == 6
    assert_score(result, 6.0, Completeness.PARTIAL)
    assert all(result.tests[number - 1].reason_code is ReasonCode.MISSING_FACT for number in (3, 5, 9))


def test_five_available_tests_give_an_unavailable_score() -> None:
    result = calculate_f_score(make(total_assets_t2=missing(), gross_profit_t=missing()))
    assert unavailable_numbers(result) == (3, 5, 8, 9)
    assert result.available_count == 5
    assert_score(result, None, None)


def test_the_equality_case_scores_three() -> None:
    result = calculate_f_score(
        make(
            total_assets_t2=100,
            total_assets_t1=100,
            total_assets_t=100,
            net_income_t1=10,
            net_income_t=10,
            operating_cash_flow_t=10,
            sales_t1=100,
            sales_t=100,
            gross_profit_t1=30,
            gross_profit_t=30,
            long_term_debt_t1=20,
            long_term_debt_t=20,
            current_assets_t1=40,
            current_assets_t=40,
            current_liabilities_t1=20,
            current_liabilities_t=20,
            shares_t1=100,
            shares_t=100,
        )
    )
    assert outcomes(result) == (PASS, PASS, FAIL, FAIL, FAIL, FAIL, PASS, FAIL, FAIL)
    assert_score(result, 3.0, Completeness.COMPLETE)


def test_the_equality_case_with_zero_debt_in_both_years_scores_four() -> None:
    result = calculate_f_score(
        make(
            total_assets_t2=100,
            total_assets_t1=100,
            total_assets_t=100,
            net_income_t1=10,
            net_income_t=10,
            operating_cash_flow_t=10,
            sales_t1=100,
            sales_t=100,
            gross_profit_t1=30,
            gross_profit_t=30,
            long_term_debt_t1=0,
            long_term_debt_t=0,
            current_assets_t1=40,
            current_assets_t=40,
            current_liabilities_t1=20,
            current_liabilities_t=20,
        )
    )
    assert outcomes(result) == (PASS, PASS, FAIL, FAIL, PASS, FAIL, PASS, FAIL, FAIL)
    assert_score(result, 4.0, Completeness.COMPLETE)


def test_the_all_fail_case_is_a_complete_score_of_zero() -> None:
    result = calculate_f_score(
        make(
            total_assets_t2=100,
            total_assets_t1=100,
            total_assets_t=100,
            net_income_t1=-1,
            net_income_t=-2,
            operating_cash_flow_t=-3,
            sales_t1=100,
            sales_t=90,
            gross_profit_t1=30,
            gross_profit_t=18,
            long_term_debt_t1=10,
            long_term_debt_t=20,
            current_assets_t1=40,
            current_assets_t=30,
            current_liabilities_t1=20,
            current_liabilities_t=20,
            shares_t1=100,
            shares_t=101,
        )
    )
    assert outcomes(result) == (FAIL,) * 9
    assert_score(result, 0.0, Completeness.COMPLETE)
    assert result.available_count == 9


# ---------------------------------------------------------------------------
# Strict comparisons, each at equality and on either side
# ---------------------------------------------------------------------------

# (test number, the change that puts the current value above, at and below the threshold or the prior value)
_COMPARISONS = [
    (1, "net_income_t", (1, 0, -1)),
    (2, "operating_cash_flow_t", (1, 0, -1)),
    (3, "net_income_t", (6, 5, 4)),
    (4, "operating_cash_flow_t", (9, 8, 7)),
    (6, "current_assets_t", (49, 48, 47)),
    (8, "gross_profit_t", (37, 36, 35)),
    (9, "sales_t", (101, 100, 99)),
]


@pytest.mark.parametrize(("number", "field", "values"), _COMPARISONS)
def test_a_strict_greater_than_test_passes_only_above_the_threshold(
    number: int, field: str, values: tuple[float, float, float]
) -> None:
    above, equal, below = (calculate_f_score(make(**{field: value})).tests[number - 1].outcome for value in values)
    assert (above, equal, below) == (PASS, FAIL, FAIL)


def test_falling_leverage_passes_only_below_the_prior_ratio() -> None:
    # Prior: 20 over the average of 100 and 100. Current: long-term debt over the average of 120 and 100, which is 110.
    above, equal, below = (
        calculate_f_score(make(total_assets_t2=100, long_term_debt_t=value)).tests[4].outcome for value in (23, 22, 21)
    )
    assert (above, equal, below) == (FAIL, FAIL, PASS)


def test_no_dilution_passes_when_the_count_is_unchanged_or_lower() -> None:
    more, same, fewer = (calculate_f_score(make(shares_t=value)).tests[6].outcome for value in (101, 100, 99))
    assert (more, same, fewer) == (FAIL, PASS, PASS)


def test_ratios_equal_in_exact_arithmetic_are_equal_however_the_floats_round() -> None:
    result = calculate_f_score(make(net_income_t=0.1, total_assets_t1=0.3, net_income_t1=0.2, total_assets_t2=0.6))
    assert result.tests[2].outcome is FAIL


# ---------------------------------------------------------------------------
# Denominators
# ---------------------------------------------------------------------------

_DENOMINATORS = [
    ("total_assets_t1", (1, 2, 3, 5, 9)),
    ("total_assets_t2", (3, 5, 9)),
    ("total_assets_t", (5,)),
    ("current_liabilities_t", (6,)),
    ("current_liabilities_t1", (6,)),
    ("sales_t", (8,)),
    ("sales_t1", (8,)),
]


@pytest.mark.parametrize(("field", "affected"), _DENOMINATORS)
@pytest.mark.parametrize("value", [0, -1])
def test_a_denominator_that_is_not_positive_makes_exactly_its_tests_unavailable(
    field: str, affected: tuple[int, ...], value: float
) -> None:
    result = calculate_f_score(make(**{field: value}))
    assert unavailable_numbers(result) == tuple(sorted(set(affected)))
    for number in affected:
        item = result.tests[number - 1]
        assert item.reason_code is ReasonCode.NONPOSITIVE_DENOMINATOR
        assert item.reason is not None
        assert field in item.reason


def test_a_non_finite_ratio_makes_its_test_unavailable_and_nothing_is_non_finite() -> None:
    result = calculate_f_score(make(net_income_t=1e308, total_assets_t1=1e-300))
    assert result.tests[0].outcome is UNAVAILABLE
    assert result.tests[0].reason_code is ReasonCode.INVALID_REQUEST
    assert result.tests[2].outcome is UNAVAILABLE
    for item in result.tests:
        assert all(math.isfinite(metric.result.value or 0.0) for metric in item.ratios)


# ---------------------------------------------------------------------------
# Missing inputs
# ---------------------------------------------------------------------------


def test_a_missing_newest_year_never_scores_an_older_year() -> None:
    newest = {
        name: missing()
        for name in (
            "total_assets_t",
            "net_income_t",
            "operating_cash_flow_t",
            "sales_t",
            "gross_profit_t",
            "long_term_debt_t",
            "current_assets_t",
            "current_liabilities_t",
            "shares_t",
        )
    }
    result = calculate_f_score(make(**newest))
    assert unavailable_numbers(result) == tuple(range(1, 10))
    assert result.available_count == 0
    assert_score(result, None, None)


def test_an_unavailable_operand_hands_its_reason_code_to_the_test() -> None:
    result = calculate_f_score(make(net_income_t=missing(ReasonCode.NOT_AVAILABLE_AS_OF)))
    assert unavailable_numbers(result) == (1, 3, 4)
    assert result.tests[0].reason_code is ReasonCode.NOT_AVAILABLE_AS_OF
    assert "net_income_t" in (result.tests[0].reason or "")


def test_gross_profit_evidence_that_is_not_ok_makes_the_margin_test_unavailable_with_its_code() -> None:
    failed = MetricEvidence(MetricResult.failure(MetricStatus.UNAVAILABLE, ReasonCode.MISSING_FACT, "no gross profit"))
    result = calculate_f_score(make(gross_profit_t1=failed))
    assert unavailable_numbers(result) == (8,)
    assert result.tests[7].reason_code is ReasonCode.MISSING_FACT
    assert "no gross profit" in (result.tests[7].reason or "")


def test_derived_gross_profit_keeps_both_inputs_and_its_diagnostic() -> None:
    derived = MetricEvidence(
        MetricResult.ok(42.0),
        operands=(Operand("sales", fact("sales", 100)), Operand("cost_of_revenue", fact("cost_of_revenue", 58))),
        diagnostics=("Gross profit is not reported; derived as sales minus cost of revenue.",),
    )
    item = calculate_f_score(make(gross_profit_t=derived)).tests[7]
    assert item.outcome is PASS
    assert [operand.name for operand in item.operands] == [
        "gross_profit_t:sales",
        "gross_profit_t:cost_of_revenue",
        "sales_t",
        "gross_profit_t1:gross_profit_t1",
        "sales_t1",
    ]
    assert "Gross profit is not reported; derived as sales minus cost of revenue." in item.diagnostics


# ---------------------------------------------------------------------------
# Zero debt
# ---------------------------------------------------------------------------


def test_zero_debt_in_both_years_passes_even_without_total_assets_two_years_back() -> None:
    result = calculate_f_score(make(long_term_debt_t1=0, long_term_debt_t=0, total_assets_t2=missing()))
    assert result.tests[4].outcome is PASS
    assert unavailable_numbers(result) == (3, 9)
    assert any("zero in both years" in note for note in result.tests[4].diagnostics)


def test_zero_debt_in_both_years_passes_whatever_the_assets() -> None:
    result = calculate_f_score(
        make(long_term_debt_t1=0, long_term_debt_t=0, total_assets_t=-5, total_assets_t1=0, total_assets_t2=missing())
    )
    assert result.tests[4].outcome is PASS


def test_debt_that_falls_to_zero_needs_the_assets_to_compare() -> None:
    assert calculate_f_score(make(long_term_debt_t=0)).tests[4].outcome is PASS
    result = calculate_f_score(make(long_term_debt_t=0, total_assets_t2=missing()))
    assert result.tests[4].outcome is UNAVAILABLE
    assert result.tests[4].reason_code is ReasonCode.MISSING_FACT


def test_debt_that_rises_from_zero_fails() -> None:
    assert calculate_f_score(make(long_term_debt_t1=0, long_term_debt_t=5)).tests[4].outcome is FAIL


def test_long_term_debt_that_is_unavailable_in_one_year_makes_test_5_unavailable_with_its_code() -> None:
    failed = MetricEvidence(
        MetricResult.failure(MetricStatus.UNAVAILABLE, ReasonCode.DEBT_NOT_VISIBLE, "debt the mapping cannot see")
    )
    result = calculate_f_score(make(long_term_debt_t=failed, long_term_debt_t1=0))
    assert unavailable_numbers(result) == (5,)
    assert result.tests[4].reason_code is ReasonCode.DEBT_NOT_VISIBLE
    unsupported = InputUnavailable(ReasonCode.UNSUPPORTED_MAPPING, "unsupported for ifrs-full")
    assert calculate_f_score(make(long_term_debt_t1=unsupported)).tests[4].reason_code is (
        ReasonCode.UNSUPPORTED_MAPPING
    )


# ---------------------------------------------------------------------------
# Currency and taxonomy, per test
# ---------------------------------------------------------------------------


def test_operands_in_different_currencies_make_only_the_tests_that_combine_them_unavailable() -> None:
    result = calculate_f_score(make(net_income_t=fact("net_income_t", 8, currency="EUR")))
    assert unavailable_numbers(result) == (1, 3, 4)
    assert all(result.tests[number - 1].reason_code is ReasonCode.INCOMPATIBLE_CURRENCY for number in (1, 3, 4))
    assert_score(result, 6.0, Completeness.PARTIAL)


def test_a_monetary_operand_with_no_currency_makes_its_tests_unavailable() -> None:
    result = calculate_f_score(make(operating_cash_flow_t=fact("operating_cash_flow_t", 10, currency=None)))
    assert unavailable_numbers(result) == (2, 4)
    assert result.tests[1].reason_code is ReasonCode.INCOMPATIBLE_CURRENCY


def test_a_currency_that_differs_inside_shared_metric_evidence_is_found() -> None:
    mixed = MetricEvidence(MetricResult.ok(18.0), operands=(Operand("x", fact("x", 18, currency="EUR")),))
    result = calculate_f_score(make(long_term_debt_t=mixed))
    assert unavailable_numbers(result) == (5,)
    assert result.tests[4].reason_code is ReasonCode.INCOMPATIBLE_CURRENCY


def test_a_us_gaap_and_ifrs_full_mix_makes_the_affected_tests_unavailable() -> None:
    result = calculate_f_score(make(total_assets_t2=fact("total_assets_t2", 80, field="ifrs-full:Assets")))
    assert unavailable_numbers(result) == (3, 5, 9)
    assert all(result.tests[number - 1].reason_code is ReasonCode.INCOMPATIBLE_SCOPE for number in (3, 5, 9))


def test_share_counts_on_different_taxonomies_make_the_dilution_test_unavailable() -> None:
    ifrs = YearEndShareCount(
        fact("shares_t", 100, currency=None, field="ifrs-full:NumberOfSharesOutstanding"),
        ACCESSION,
        ShareCountPath.DIRECT,
    )
    result = calculate_f_score(make(shares_t=ifrs))
    assert unavailable_numbers(result) == (7,)
    assert result.tests[6].reason_code is ReasonCode.INCOMPATIBLE_SCOPE


def test_an_operand_with_no_supported_taxonomy_makes_its_tests_unavailable() -> None:
    result = calculate_f_score(make(net_income_t=synthetic("net_income_t", 8.0)))
    assert unavailable_numbers(result) == (1, 3, 4)
    assert result.tests[0].reason_code is ReasonCode.INCOMPATIBLE_SCOPE


def _derived_count(name: str, provider_field: str | None) -> YearEndShareCount:
    """Return an issued-less-treasury count labelled as the adapter labels one, or with ``provider_field`` instead."""
    issued, treasury = fact("issued", 120, currency=None), fact("treasury", 20, currency=None)
    derived = replace(
        synthetic(name, 100.0),
        source_kind=SourceKind.DERIVED,
        currency=None,
        provider_field=provider_field,
        lineage=ComponentLineage("issued less treasury", (issued, treasury)),
        resolved_at=NOW,
    )
    return YearEndShareCount(derived, ACCESSION, ShareCountPath.ISSUED_LESS_TREASURY)


def test_a_derived_share_count_with_the_adapters_provider_field_has_a_taxonomy() -> None:
    result = calculate_f_score(
        make(
            shares_t=_derived_count("shares_t", _SEC_DERIVED_COMMON_SHARES_FIELD),
            shares_t1=_derived_count("shares_t1", _SEC_DERIVED_COMMON_SHARES_FIELD),
        )
    )
    assert result.tests[6].outcome is PASS


def test_a_derived_share_count_against_a_direct_one_is_a_path_conflict_not_a_taxonomy_conflict() -> None:
    result = calculate_f_score(make(shares_t=_derived_count("shares_t", _SEC_DERIVED_COMMON_SHARES_FIELD)))
    assert result.tests[6].reason_code is ReasonCode.AMBIGUOUS_FACT


def test_a_derived_share_count_on_mixed_taxonomies_is_a_scope_conflict() -> None:
    mixed = "derived:us-gaap:CommonStockSharesIssued-ifrs-full:TreasuryShares"
    result = calculate_f_score(
        make(shares_t=_derived_count("shares_t", mixed), shares_t1=_derived_count("shares_t1", mixed))
    )
    assert result.tests[6].reason_code is ReasonCode.INCOMPATIBLE_SCOPE


def test_an_input_with_no_provider_field_takes_its_taxonomy_from_its_components() -> None:
    result = calculate_f_score(
        make(shares_t=_derived_count("shares_t", None), shares_t1=_derived_count("shares_t1", None))
    )
    assert result.tests[6].outcome is PASS
    foreign = fact("treasury", 20, currency=None, field="ifrs-full:TreasuryShares")
    count = _derived_count("shares_t", None)
    mixed = replace(
        count.count, lineage=ComponentLineage("issued less treasury", (fact("issued", 120, currency=None), foreign))
    )
    scope = calculate_f_score(
        make(shares_t=YearEndShareCount(mixed, ACCESSION, count.path), shares_t1=_derived_count("shares_t1", None))
    )
    assert scope.tests[6].reason_code is ReasonCode.INCOMPATIBLE_SCOPE


def test_an_input_with_neither_a_provider_field_nor_components_has_no_taxonomy() -> None:
    bare = replace(synthetic("net_income_t", 8.0), provider_field=None)
    result = calculate_f_score(make(net_income_t=bare))
    assert result.tests[0].reason_code is ReasonCode.INCOMPATIBLE_SCOPE


# ---------------------------------------------------------------------------
# Dilution
# ---------------------------------------------------------------------------


def test_counts_from_different_filings_make_the_dilution_test_unavailable() -> None:
    result = calculate_f_score(make(shares_t1=share_count("shares_t1", 100, accession="0000000000-24-000002")))
    assert unavailable_numbers(result) == (7,)
    assert result.tests[6].reason_code is ReasonCode.AMBIGUOUS_FACT


def test_counts_on_different_paths_make_the_dilution_test_unavailable() -> None:
    result = calculate_f_score(make(shares_t1=share_count("shares_t1", 100, path=ShareCountPath.ISSUED_LESS_TREASURY)))
    assert unavailable_numbers(result) == (7,)
    assert result.tests[6].reason_code is ReasonCode.AMBIGUOUS_FACT


def test_an_unavailable_share_count_hands_its_reason_code_to_the_dilution_test() -> None:
    result = calculate_f_score(make(shares_t1=missing(ReasonCode.AMBIGUOUS_FACT)))
    assert unavailable_numbers(result) == (7,)
    assert result.tests[6].reason_code is ReasonCode.AMBIGUOUS_FACT


# ---------------------------------------------------------------------------
# Scores
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("changes", "unavailable", "score"),
    [
        ({"gross_profit_t": missing()}, (8,), 8.0),
        ({"gross_profit_t": missing(), "current_liabilities_t": missing()}, (6, 8), 7.0),
        ({"total_assets_t2": missing()}, (3, 5, 9), 6.0),
    ],
)
def test_a_partial_score_is_the_number_passed_over_six_to_eight_available_tests(
    changes: dict[str, Any], unavailable: tuple[int, ...], score: float
) -> None:
    result = calculate_f_score(make(**changes))
    assert unavailable_numbers(result) == unavailable
    assert_score(result, score, Completeness.PARTIAL)
    assert result.available_count == 9 - len(unavailable)


def test_an_unavailable_test_is_never_counted_as_a_fail() -> None:
    result = calculate_f_score(make(gross_profit_t=missing()))
    assert sum(1 for item in result.tests if item.outcome is FAIL) == 0
    assert_score(result, 8.0, Completeness.PARTIAL)


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------

_SCENARIOS = [
    {},
    {"shares_t": 101},
    {"total_assets_t2": missing()},
    {"total_assets_t2": missing(), "gross_profit_t": missing()},
    {"net_income_t": -3, "operating_cash_flow_t": -1},
    {"long_term_debt_t1": 0, "long_term_debt_t": 0},
]


@pytest.mark.parametrize("changes", _SCENARIOS)
def test_every_result_holds_nine_ordered_tests_with_consistent_points_and_finite_numbers(
    changes: dict[str, Any],
) -> None:
    result = calculate_f_score(make(**changes))
    assert [item.number for item in result.tests] == list(range(1, 10))
    passed = sum(1 for item in result.tests if item.outcome is PASS)
    if result.score.status is MetricStatus.OK:
        assert result.score.value == float(passed)
    for item in result.tests:
        assert (item.reason_code is not None) == (item.outcome is UNAVAILABLE)
        for metric in item.ratios:
            assert metric.result.status is MetricStatus.OK
            assert metric.result.value is not None
            assert math.isfinite(metric.result.value)
        assert all(math.isfinite(operand.input.value) for operand in item.operands)


def test_the_same_inputs_give_the_same_result() -> None:
    assert calculate_f_score(make()) == calculate_f_score(make())


def _tests_of(result: PiotroskiScoreResult) -> list[PiotroskiTestResult]:
    return list(result.tests)


def test_a_result_refuses_a_duplicated_or_reordered_test() -> None:
    result = calculate_f_score(make())
    tests = _tests_of(result)
    duplicated = (*tests[:8], tests[0])
    reordered = (tests[1], tests[0], *tests[2:])
    for bad in (duplicated, reordered, tuple(tests[:8])):
        with pytest.raises(ValueError, match="nine tests"):
            PiotroskiScoreResult(bad, result.score, result.completeness, 9, ())


def test_a_result_refuses_a_score_or_counts_that_disagree_with_its_tests() -> None:
    result = calculate_f_score(make(gross_profit_t=missing()))
    tests = result.tests
    with pytest.raises(ValueError, match="available count"):
        PiotroskiScoreResult(tests, result.score, result.completeness, 9, (8,))
    with pytest.raises(ValueError, match="unavailable tests"):
        PiotroskiScoreResult(tests, result.score, result.completeness, 8, ())
    with pytest.raises(ValueError, match="score must equal"):
        PiotroskiScoreResult(tests, MetricResult.ok(3.0), result.completeness, 8, (8,))
    with pytest.raises(ValueError, match="Completeness"):
        PiotroskiScoreResult(tests, result.score, Completeness.COMPLETE, 8, (8,))
    few = calculate_f_score(make(total_assets_t2=missing(), gross_profit_t=missing()))
    with pytest.raises(ValueError, match="Fewer than six"):
        PiotroskiScoreResult(few.tests, MetricResult.ok(4.0), None, 5, few.unavailable_tests)
    with pytest.raises(ValueError, match="Fewer than six"):
        PiotroskiScoreResult(few.tests, few.score, Completeness.PARTIAL, 5, few.unavailable_tests)


def test_a_test_result_refuses_an_inconsistent_reason_or_ratio() -> None:
    with pytest.raises(ValueError, match="reason"):
        PiotroskiTestResult(1, "Positive ROA", "Profitability", UNAVAILABLE)
    with pytest.raises(ValueError, match="reason"):
        PiotroskiTestResult(1, "Positive ROA", "Profitability", PASS, reason_code=ReasonCode.MISSING_FACT, reason="x")
    with pytest.raises(ValueError, match="no ratios"):
        PiotroskiTestResult(
            1,
            "Positive ROA",
            "Profitability",
            UNAVAILABLE,
            ratios=(NamedMetric("roa_t", MetricResult.ok(1.0)),),
            reason_code=ReasonCode.MISSING_FACT,
            reason="x",
        )
    failed = NamedMetric("roa_t", MetricResult.failure(MetricStatus.UNAVAILABLE, ReasonCode.MISSING_FACT, "x"))
    with pytest.raises(ValueError, match="only ratios"):
        PiotroskiTestResult(1, "Positive ROA", "Profitability", PASS, ratios=(failed,))
