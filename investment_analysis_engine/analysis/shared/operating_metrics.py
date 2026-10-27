"""Gross profit, EBIT, depreciation and amortization, and EBITDA from reported annual figures.

Each function is pure and takes the annual inputs of one fiscal year: a ``ResolvedInput``, or ``None`` when the filings
report none for that year. None of them rebuilds a figure from another line: gross profit is never taken from operating
income, and EBIT is never rebuilt from pretax income plus interest.

- gross profit = the reported gross profit, else sales - cost of revenue when both are reported;
- EBIT = reported operating income, which may be negative;
- EBITDA = EBIT + depreciation and amortization.
"""

import math

from investment_analysis_engine.analysis.shared.metric_evidence import (
    AnnualValue,
    MetricEvidence,
    Operand,
    missing_annual,
    unavailable,
)
from investment_analysis_engine.core.metric_result import MetricResult, MetricStatus, ReasonCode


def _finite(value: float, operands: tuple[Operand, ...], description: str) -> MetricEvidence:
    """Return ``value`` as an ``ok`` result, or the overflow failure when it is not finite."""
    if not math.isfinite(value):
        return MetricEvidence(
            result=MetricResult.failure(
                MetricStatus.NOT_APPLICABLE,
                ReasonCode.INVALID_REQUEST,
                f"{description} overflows the finite double range for the supplied inputs.",
            ),
            operands=operands,
        )
    return MetricEvidence(result=MetricResult.ok(value), operands=operands)


def compute_gross_profit(gross_profit: AnnualValue, sales: AnnualValue, cost_of_revenue: AnnualValue) -> MetricEvidence:
    """Return the reported gross profit; otherwise sales minus cost of revenue, keeping both operands' provenance.

    A filer that reports neither form has none: the result is ``unavailable`` with ``missing_fact``.
    """
    if gross_profit is not None:
        return _finite(gross_profit.value, (Operand("gross_profit", gross_profit),), "Gross profit")
    if sales is None or cost_of_revenue is None:
        absent = [name for name, item in (("sales", sales), ("cost_of_revenue", cost_of_revenue)) if item is None]
        return unavailable(
            ReasonCode.MISSING_FACT,
            f"Gross profit is not reported, and cannot be derived without {' and '.join(absent)}.",
        )
    result = _finite(
        sales.value - cost_of_revenue.value,
        (Operand("sales", sales), Operand("cost_of_revenue", cost_of_revenue)),
        "Gross profit",
    )
    return MetricEvidence(
        result=result.result,
        operands=result.operands,
        diagnostics=("Gross profit is not reported; derived as sales minus cost of revenue.",),
    )


def compute_ebit(operating_income: AnnualValue) -> MetricEvidence:
    """Return the reported operating income as EBIT; a negative value is a valid number."""
    if operating_income is None:
        return missing_annual("operating_income")
    return _finite(operating_income.value, (Operand("operating_income", operating_income),), "EBIT")


def compute_depreciation_and_amortization(depreciation_and_amortization: AnnualValue) -> MetricEvidence:
    """Return the reported depreciation, depletion and amortization of the cash-flow statement."""
    if depreciation_and_amortization is None:
        return missing_annual("depreciation_and_amortization")
    return _finite(
        depreciation_and_amortization.value,
        (Operand("depreciation_and_amortization", depreciation_and_amortization),),
        "Depreciation and amortization",
    )


def compute_ebitda(operating_income: AnnualValue, depreciation_and_amortization: AnnualValue) -> MetricEvidence:
    """Return EBIT plus depreciation and amortization; either one missing makes EBITDA ``unavailable``."""
    absent = [
        name
        for name, item in (
            ("operating_income", operating_income),
            ("depreciation_and_amortization", depreciation_and_amortization),
        )
        if item is None
    ]
    if operating_income is None or depreciation_and_amortization is None:
        return unavailable(ReasonCode.MISSING_FACT, f"EBITDA needs {' and '.join(absent)}, which is not reported.")
    return _finite(
        operating_income.value + depreciation_and_amortization.value,
        (
            Operand("operating_income", operating_income),
            Operand("depreciation_and_amortization", depreciation_and_amortization),
        ),
        "EBITDA",
    )
