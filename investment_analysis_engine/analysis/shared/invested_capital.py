"""Invested capital from the balance-sheet values at one fiscal year-end (Greenblatt's tangible capital employed).

The function is pure. A balance-sheet value at year-end *t* is a ``ResolvedInput`` or an ``InstantAbsence``.

- invested capital = (current assets - cash - short-term investments)
  - (current liabilities - short-term borrowings - current portion of long-term debt) + net PP&E.

Current assets, current liabilities, net PP&E and cash are critical. Short-term investments are zero when ``not_tagged``
(current assets are present, because they are critical). Short-term borrowings and the current portion follow the
debt-component rule of ``enterprise_value.debt_component_gap``. Invested capital at or below zero is an ``ok`` value:
the metric that divides by it decides what that means.
"""

import math

from investment_analysis_engine.analysis.shared.enterprise_value import debt_component_gap
from investment_analysis_engine.analysis.shared.metric_evidence import (
    BalanceSheetValue,
    MetricEvidence,
    Operand,
    absent_input,
    unavailable,
)
from investment_analysis_engine.core.metric_result import MetricResult, MetricStatus, ReasonCode
from investment_analysis_engine.data.financial.facts import InstantAbsence, InstantAbsenceReason
from investment_analysis_engine.data.financial.provenance import ResolvedInput


def compute_invested_capital(  # noqa: PLR0913
    *,
    current_assets: BalanceSheetValue,
    current_liabilities: BalanceSheetValue,
    net_ppe: BalanceSheetValue,
    cash_and_equivalents: BalanceSheetValue,
    short_term_investments: BalanceSheetValue,
    short_term_borrowings: BalanceSheetValue,
    current_portion_of_long_term_debt: BalanceSheetValue,
) -> MetricEvidence:
    """Return invested capital at year-end *t*, or why it is ``unavailable``.

    A missing critical input makes the result ``unavailable`` with the code of the shared absence table. An absent
    debt component that is not zero by the debt-component rule makes it ``unavailable`` with that rule's code.
    """
    critical = (
        ("current_assets", current_assets),
        ("current_liabilities", current_liabilities),
        ("net_ppe", net_ppe),
        ("cash_and_equivalents", cash_and_equivalents),
    )
    operands: list[Operand] = []
    for name, value in critical:
        if isinstance(value, InstantAbsence):
            return absent_input(name, value)
        operands.append(Operand(name, value))
    values = {operand.name: operand.input.value for operand in operands}
    zero: list[str] = []
    notes: list[str] = []
    capital = (
        values["current_assets"] - values["cash_and_equivalents"] + values["net_ppe"] - values["current_liabilities"]
    )
    if isinstance(short_term_investments, ResolvedInput):
        operands.append(Operand("short_term_investments", short_term_investments))
        capital -= short_term_investments.value
    elif short_term_investments.reason is InstantAbsenceReason.NOT_TAGGED:
        zero.append("short_term_investments")
        notes.append("short_term_investments is not tagged at the year-end and is taken as zero.")
    else:
        return absent_input("short_term_investments", short_term_investments)
    for name, debt in (
        ("short_term_borrowings", short_term_borrowings),
        ("current_portion_of_long_term_debt", current_portion_of_long_term_debt),
    ):
        if isinstance(debt, ResolvedInput):
            operands.append(Operand(name, debt))
            capital += debt.value
            continue
        gap = debt_component_gap(name, debt)
        if gap is not None:
            return unavailable(gap[0], gap[1])
        zero.append(name)
        notes.append(f"{name} is not tagged at the year-end and is taken as zero.")
    if not math.isfinite(capital):
        return MetricEvidence(
            result=MetricResult.failure(
                MetricStatus.NOT_APPLICABLE,
                ReasonCode.INVALID_REQUEST,
                "Invested capital overflows the finite double range for the supplied inputs.",
            ),
            operands=tuple(operands),
        )
    return MetricEvidence(
        result=MetricResult.ok(capital),
        operands=tuple(operands),
        zero_components=tuple(zero),
        diagnostics=tuple(notes),
    )
