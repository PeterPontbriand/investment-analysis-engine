"""Gross profit, EBIT, depreciation and amortization, and EBITDA."""

import math

import pytest

from investment_analysis_engine.analysis.shared.metric_evidence import MetricEvidence
from investment_analysis_engine.analysis.shared.operating_metrics import (
    compute_depreciation_and_amortization,
    compute_ebit,
    compute_ebitda,
    compute_gross_profit,
)
from investment_analysis_engine.core.metric_result import MetricStatus, ReasonCode
from investment_analysis_engine.data.financial.facts import FinancialField as F
from tests.analysis.shared._issuer_inputs import annual, synthetic


def _value(evidence: MetricEvidence) -> float:
    assert evidence.result.status is MetricStatus.OK
    assert evidence.result.value is not None
    assert math.isfinite(evidence.result.value)
    return evidence.result.value


def _unavailable(evidence: MetricEvidence, code: ReasonCode) -> None:
    assert evidence.result.status is MetricStatus.UNAVAILABLE
    assert evidence.result.value is None
    assert evidence.result.reason_code is code
    assert evidence.result.reason is not None
    assert evidence.result.reason.strip()


def test_monster_reports_gross_profit_and_it_is_used_as_reported() -> None:
    reported = annual("MNST", F.GROSS_PROFIT)
    evidence = compute_gross_profit(reported, annual("MNST", F.SALES), annual("MNST", F.COST_OF_REVENUE))
    assert reported is not None
    assert _value(evidence) == reported.value == 4_632_195_000.0
    assert [operand.name for operand in evidence.operands] == ["gross_profit"]
    assert evidence.diagnostics == ()


def test_walmart_derives_gross_profit_from_sales_and_cost_with_both_provenances() -> None:
    sales, cost = annual("WMT", F.SALES), annual("WMT", F.COST_OF_REVENUE)
    assert annual("WMT", F.GROSS_PROFIT) is None
    evidence = compute_gross_profit(None, sales, cost)
    assert _value(evidence) == 177_768_000_000.0
    assert [(operand.name, operand.input) for operand in evidence.operands] == [
        ("sales", sales),
        ("cost_of_revenue", cost),
    ]
    assert evidence.diagnostics == ("Gross profit is not reported; derived as sales minus cost of revenue.",)


def test_a_reported_gross_profit_wins_over_the_difference() -> None:
    evidence = compute_gross_profit(synthetic("gp", 50.0), synthetic("sales", 100.0), synthetic("cost", 10.0))
    assert _value(evidence) == 50.0


@pytest.mark.parametrize(
    ("sales", "cost", "named"),
    [(None, 10.0, "sales"), (100.0, None, "cost_of_revenue"), (None, None, "sales and cost_of_revenue")],
)
def test_one_of_the_two_missing_is_unavailable_and_operating_income_is_never_used(
    sales: float | None, cost: float | None, named: str
) -> None:
    evidence = compute_gross_profit(
        None,
        None if sales is None else synthetic("sales", sales),
        None if cost is None else synthetic("cost", cost),
    )
    _unavailable(evidence, ReasonCode.MISSING_FACT)
    assert evidence.result.reason is not None
    assert named in evidence.result.reason


def test_deere_reports_no_cost_of_revenue_so_it_has_no_gross_profit() -> None:
    evidence = compute_gross_profit(
        annual("DE", F.GROSS_PROFIT), annual("DE", F.SALES), annual("DE", F.COST_OF_REVENUE)
    )
    _unavailable(evidence, ReasonCode.MISSING_FACT)


def test_gross_profit_overflow_is_not_a_number() -> None:
    evidence = compute_gross_profit(None, synthetic("sales", 1.7e308), synthetic("cost", -1.7e308))
    assert evidence.result.status is MetricStatus.NOT_APPLICABLE
    assert evidence.result.reason_code is ReasonCode.INVALID_REQUEST


def test_ebit_is_the_reported_operating_income_and_may_be_negative() -> None:
    income = annual("HON", F.OPERATING_INCOME)
    assert _value(compute_ebit(income)) == 8_127_000_000.0
    loss = compute_ebit(synthetic("operating_income", -250.0))
    assert _value(loss) == -250.0
    assert [operand.name for operand in loss.operands] == ["operating_income"]


def test_ebit_is_unavailable_without_operating_income_and_is_not_rebuilt_from_pretax_income() -> None:
    _unavailable(compute_ebit(None), ReasonCode.MISSING_FACT)


def test_depreciation_and_amortization_is_the_reported_figure() -> None:
    assert _value(compute_depreciation_and_amortization(annual("HON", F.DEPRECIATION_AND_AMORTIZATION))) == 1_388e6
    _unavailable(
        compute_depreciation_and_amortization(annual("GOOGL", F.DEPRECIATION_AND_AMORTIZATION)), ReasonCode.MISSING_FACT
    )


def test_ebitda_is_ebit_plus_depreciation_and_amortization() -> None:
    evidence = compute_ebitda(annual("HON", F.OPERATING_INCOME), annual("HON", F.DEPRECIATION_AND_AMORTIZATION))
    assert _value(evidence) == 9_515_000_000.0
    assert [operand.name for operand in evidence.operands] == ["operating_income", "depreciation_and_amortization"]


def test_ebitda_with_a_negative_ebit_is_a_valid_number() -> None:
    assert _value(compute_ebitda(synthetic("oi", -300.0), synthetic("da", 100.0))) == -200.0


@pytest.mark.parametrize(
    ("income", "depreciation", "named"),
    [(None, 5.0, "operating_income"), (5.0, None, "depreciation_and_amortization")],
)
def test_ebitda_needs_both(income: float | None, depreciation: float | None, named: str) -> None:
    evidence = compute_ebitda(
        None if income is None else synthetic("oi", income),
        None if depreciation is None else synthetic("da", depreciation),
    )
    _unavailable(evidence, ReasonCode.MISSING_FACT)
    assert evidence.result.reason is not None
    assert named in evidence.result.reason
    assert evidence.result.reason.endswith("which is not reported.")


def test_ebitda_with_both_inputs_missing_says_which_are_not_reported() -> None:
    evidence = compute_ebitda(None, None)
    _unavailable(evidence, ReasonCode.MISSING_FACT)
    assert evidence.result.reason == (
        "EBITDA needs operating_income and depreciation_and_amortization, which are not reported."
    )


def test_google_has_operating_income_but_no_depreciation_so_no_ebitda() -> None:
    evidence = compute_ebitda(annual("GOOGL", F.OPERATING_INCOME), annual("GOOGL", F.DEPRECIATION_AND_AMORTIZATION))
    _unavailable(evidence, ReasonCode.MISSING_FACT)


def test_ebitda_overflow_is_not_a_number() -> None:
    evidence = compute_ebitda(synthetic("oi", 1.7e308), synthetic("da", 1.7e308))
    assert evidence.result.status is MetricStatus.NOT_APPLICABLE
    assert evidence.result.value is None
