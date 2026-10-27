"""Total debt and enterprise value from the balance-sheet values at one fiscal year-end.

Both functions are pure. A balance-sheet value at year-end *t* is a ``ResolvedInput`` or an ``InstantAbsence``; an
annual value is a ``ResolvedInput`` or ``None``. An absence is read as a number only where the financial math reference
allows it, and the result names the components it took as zero.

- total debt = short-term borrowings + current portion of long-term debt + noncurrent long-term debt + lease
  liabilities counted as debt;
- EV = market cap + total debt + preferred stock + noncontrolling interest - cash and equivalents - short-term
  investments. EV may be negative.

The direct long-term-debt total only reconciles with its parts. It is never added to them and never used as a value.
EV keeps the evidence of its market cap and of its total debt, so a consumer can show every component behind it.
"""

import math
from dataclasses import dataclass, field

from investment_analysis_engine.analysis.shared.market_cap import MarketCapEvidence
from investment_analysis_engine.analysis.shared.metric_evidence import (
    AnnualValue,
    BalanceSheetValue,
    MetricEvidence,
    Operand,
    absence_reason_code,
    unavailable,
)
from investment_analysis_engine.core.metric_result import MetricResult, MetricStatus, ReasonCode
from investment_analysis_engine.data.financial.facts import InstantAbsence, InstantAbsenceReason
from investment_analysis_engine.data.financial.provenance import ResolvedInput


@dataclass(frozen=True)
class EnterpriseValueEvidence:
    """Enterprise value with the market cap and total debt it used and the components it took as zero.

    Attributes:
        result: The metric's status, finite value, reason code and reason.
        market_cap: The market-cap evidence EV was given, whatever its outcome.
        total_debt: The total-debt evidence EV was given, whatever its outcome.
        operands: The resolved inputs of EV's own terms that were present: cash, preferred stock, noncontrolling
            interest and short-term investments.
        zero_components: The names of EV's own terms taken as zero because no concept is tagged for them. The
            components total debt took as zero are in ``total_debt``.
        diagnostics: Human-readable notes about how the value was reached.
    """

    result: MetricResult
    market_cap: MarketCapEvidence
    total_debt: MetricEvidence
    operands: tuple[Operand, ...] = field(default=())
    zero_components: tuple[str, ...] = field(default=())
    diagnostics: tuple[str, ...] = field(default=())


def debt_component_gap(name: str, absence: InstantAbsence) -> tuple[ReasonCode, str] | None:
    """Return why a debt component's absence cannot be read as zero, or ``None`` when it can.

    An absent debt component is zero only when no concept was tagged for it (``not_tagged``) and none of the related
    concepts recorded for it is tagged at the date. A tagged related concept means the debt exists under a concept the
    mapping does not read (``debt_not_visible``); any other absence takes the code of the shared absence table.
    """
    if absence.related_concept is not None:
        return (
            ReasonCode.DEBT_NOT_VISIBLE,
            f"{name} is absent at {absence.period_end} but the related concept {absence.related_concept} is tagged.",
        )
    if absence.reason is InstantAbsenceReason.NOT_TAGGED:
        return None
    return absence_reason_code(absence.reason), f"{name} is absent at {absence.period_end}: {absence.detail}"


def _finite(
    total: float, operands: tuple[Operand, ...], zero: tuple[str, ...], notes: tuple[str, ...]
) -> MetricEvidence:
    """Return the total as an ``ok`` result, or the overflow failure when it is not finite."""
    if not math.isfinite(total):
        return MetricEvidence(
            result=MetricResult.failure(
                MetricStatus.NOT_APPLICABLE,
                ReasonCode.INVALID_REQUEST,
                "The result overflows the finite double range for the supplied inputs.",
            ),
            operands=operands,
            zero_components=zero,
            diagnostics=notes,
        )
    return MetricEvidence(result=MetricResult.ok(total), operands=operands, zero_components=zero, diagnostics=notes)


def _direct_total_check(
    total: ResolvedInput, current: BalanceSheetValue, noncurrent: BalanceSheetValue
) -> MetricEvidence | None:
    """Return the failure of a direct total that does not equal its two parts, or ``None`` when nothing fails here.

    A part absent as ``not_tagged`` with no related concept counts as zero. A part absent for any other reason keeps
    its own outcome in the component rules, so the check then says nothing. A mismatch is ``ambiguous_fact`` when a
    part is present and ``debt_not_visible`` when neither is: the total shows debt that no part reports.
    """
    parts = (
        ("current_portion_of_long_term_debt", current),
        ("noncurrent_long_term_debt", noncurrent),
    )
    if any(isinstance(item, InstantAbsence) and debt_component_gap(name, item) is not None for name, item in parts):
        return None
    present = tuple(Operand(name, item) for name, item in parts if isinstance(item, ResolvedInput))
    parts_sum = sum(operand.input.value for operand in present)
    if total.value == parts_sum:
        return None
    if not present:
        return unavailable(
            ReasonCode.DEBT_NOT_VISIBLE,
            f"The direct long-term debt total {total.value} is reported but neither the current portion nor the "
            "noncurrent portion is, so the issuer has debt the mapping does not see.",
            diagnostics=("The direct total is never added to its parts and never used as a value.",),
        )
    return unavailable(
        ReasonCode.AMBIGUOUS_FACT,
        f"The direct long-term debt total {total.value} does not equal the current portion plus the noncurrent "
        f"portion, {parts_sum}.",
        operands=present,
        diagnostics=(
            "Affected components: current_portion_of_long_term_debt, noncurrent_long_term_debt.",
            "The direct total is never added to its parts and never used as a value.",
        ),
    )


def _no_component_present(
    components: tuple[tuple[str, InstantAbsence], ...], interest_expense: AnnualValue
) -> MetricEvidence:
    """Decide total debt when no mapped debt concept is present at the year-end.

    Precedence: an unsupported mapping, then a tagged related concept, then nonzero interest expense, then any other
    absence that cannot say there is no debt. Only when none applies is total debt zero.
    """
    unsupported = [name for name, absence in components if absence.reason is InstantAbsenceReason.UNSUPPORTED]
    if unsupported:
        return unavailable(
            ReasonCode.UNSUPPORTED_MAPPING,
            f"The mapping is unsupported for {', '.join(unsupported)}, so total debt cannot be assembled.",
        )
    gaps = [gap for name, absence in components if (gap := debt_component_gap(name, absence)) is not None]
    related = next((gap for gap in gaps if gap[0] is ReasonCode.DEBT_NOT_VISIBLE), None)
    if related is not None:
        return unavailable(*related)
    if interest_expense is not None and interest_expense.value != 0:
        return unavailable(
            ReasonCode.DEBT_NOT_VISIBLE,
            f"No mapped debt is reported but interest expense of {interest_expense.value} is, so the issuer has "
            "debt the mapping does not see.",
            operands=(Operand("interest_expense", interest_expense),),
        )
    if gaps:
        return unavailable(*gaps[0])
    return _finite(
        0.0,
        (),
        tuple(name for name, _absence in components),
        ("No reported debt: no debt concept or related concept is tagged and no interest expense is reported.",),
    )


def compute_total_debt(  # noqa: PLR0913
    *,
    short_term_borrowings: BalanceSheetValue,
    current_portion_of_long_term_debt: BalanceSheetValue,
    noncurrent_long_term_debt: BalanceSheetValue,
    lease_liabilities_as_debt: BalanceSheetValue,
    long_term_debt_total: BalanceSheetValue,
    interest_expense: AnnualValue,
) -> MetricEvidence:
    """Return total debt at year-end *t* by the total-debt table of the financial math reference.

    When the direct total is present, each long-term part absent as ``not_tagged`` with no related concept counts as
    zero and the parts must equal the total exactly: a mismatch is ``ambiguous_fact`` when a part is present and
    ``debt_not_visible`` when neither is. This check comes first, so a filer that tags only the direct total never has
    zero debt. A part absent for another reason keeps the outcome below.

    Otherwise, with at least one component present, an absent component is zero (with a diagnostic) only when it is
    ``not_tagged`` with no related concept; any other absence makes total debt ``unavailable``, with
    ``debt_not_visible`` when a related concept is tagged and the code of the absence table when not. When several
    components fail, the unsupported mapping decides, then the first in the order above. With no component present, an
    unsupported mapping gives
    ``unsupported_mapping``, a tagged related concept or nonzero interest expense gives ``debt_not_visible``, and
    otherwise total debt is zero. ``interest_expense`` is the annual figure for the year, ``None`` when none is
    reported.
    """
    if isinstance(long_term_debt_total, ResolvedInput):
        mismatch = _direct_total_check(
            long_term_debt_total, current_portion_of_long_term_debt, noncurrent_long_term_debt
        )
        if mismatch is not None:
            return mismatch
    components = (
        ("short_term_borrowings", short_term_borrowings),
        ("current_portion_of_long_term_debt", current_portion_of_long_term_debt),
        ("noncurrent_long_term_debt", noncurrent_long_term_debt),
        ("lease_liabilities_as_debt", lease_liabilities_as_debt),
    )
    present = tuple(Operand(name, item) for name, item in components if isinstance(item, ResolvedInput))
    absent = tuple((name, item) for name, item in components if isinstance(item, InstantAbsence))
    if not present:
        return _no_component_present(absent, interest_expense)
    gaps = [gap for name, item in absent if (gap := debt_component_gap(name, item)) is not None]
    if gaps:
        chosen = next((gap for gap in gaps if gap[0] is ReasonCode.UNSUPPORTED_MAPPING), gaps[0])
        return unavailable(chosen[0], chosen[1], operands=present)
    zero = tuple(name for name, _item in absent)
    notes = tuple(f"{name} is not tagged at the year-end and is taken as zero." for name in zero)
    return _finite(sum(operand.input.value for operand in present), present, zero, notes)


def _ev_result(  # noqa: PLR0913, PLR0917
    market_cap: MarketCapEvidence,
    total_debt: MetricEvidence,
    result: MetricResult,
    operands: tuple[Operand, ...] = (),
    zero: tuple[str, ...] = (),
    notes: tuple[str, ...] = (),
) -> EnterpriseValueEvidence:
    """Return EV evidence that keeps the market-cap and total-debt evidence it was given."""
    return EnterpriseValueEvidence(
        result=result,
        market_cap=market_cap,
        total_debt=total_debt,
        operands=operands,
        zero_components=zero,
        diagnostics=notes,
    )


def _ev_unavailable(
    market_cap: MarketCapEvidence, total_debt: MetricEvidence, code: ReasonCode, reason: str
) -> EnterpriseValueEvidence:
    """Return an ``unavailable`` EV that keeps the evidence it was given."""
    return _ev_result(market_cap, total_debt, MetricResult.failure(MetricStatus.UNAVAILABLE, code, reason))


def compute_enterprise_value(  # noqa: PLR0913, PLR0911
    *,
    market_cap: MarketCapEvidence,
    total_debt: MetricEvidence,
    preferred_stock: BalanceSheetValue,
    noncontrolling_interest: BalanceSheetValue,
    cash_and_equivalents: BalanceSheetValue,
    short_term_investments: BalanceSheetValue,
    current_assets: BalanceSheetValue,
) -> EnterpriseValueEvidence:
    """Return EV at year-end *t*. Market cap, total debt and cash are critical; a negative EV is a valid number.

    Preferred stock and noncontrolling interest are zero when ``not_tagged``. Short-term investments are zero when
    ``not_tagged`` only if current assets are present at the year-end, because an unclassified balance sheet's missing
    line does not show that the filer has none. Any other absence, including an unsupported mapping, makes EV
    ``unavailable`` with the code of the shared absence table. The result keeps ``market_cap`` and ``total_debt``
    whatever their outcome.
    """
    cap = market_cap.result
    debt = total_debt.result
    if cap.status is not MetricStatus.OK or cap.value is None:
        return _ev_unavailable(
            market_cap,
            total_debt,
            cap.reason_code or ReasonCode.MISSING_FACT,
            f"Market cap is {cap.status.value}: {cap.reason}",
        )
    if debt.status is not MetricStatus.OK or debt.value is None:
        return _ev_unavailable(
            market_cap,
            total_debt,
            debt.reason_code or ReasonCode.MISSING_FACT,
            f"Total debt is {debt.status.value}: {debt.reason}",
        )
    if isinstance(cash_and_equivalents, InstantAbsence):
        return _ev_unavailable(
            market_cap,
            total_debt,
            absence_reason_code(cash_and_equivalents.reason),
            f"cash_and_equivalents is absent at {cash_and_equivalents.period_end}: {cash_and_equivalents.detail}",
        )
    total = cap.value + debt.value - cash_and_equivalents.value
    operands = [Operand("cash_and_equivalents", cash_and_equivalents)]
    zero: list[str] = []
    notes = [f"Market cap {cap.value} and total debt {debt.value} are inputs."]
    classified = isinstance(current_assets, ResolvedInput)
    for name, value, sign, zero_allowed in (
        ("preferred_stock", preferred_stock, 1.0, True),
        ("noncontrolling_interest", noncontrolling_interest, 1.0, True),
        ("short_term_investments", short_term_investments, -1.0, classified),
    ):
        if isinstance(value, ResolvedInput):
            total += sign * value.value
            operands.append(Operand(name, value))
        elif value.reason is InstantAbsenceReason.NOT_TAGGED and zero_allowed:
            zero.append(name)
            notes.append(f"{name} is not tagged at the year-end and is taken as zero.")
        else:
            detail = f"{name} is absent at {value.period_end}: {value.detail}"
            if not zero_allowed:
                detail += " Current assets are not tagged, so the balance sheet is unclassified."
            return _ev_unavailable(market_cap, total_debt, absence_reason_code(value.reason), detail)
    if not math.isfinite(total):
        return _ev_result(
            market_cap,
            total_debt,
            MetricResult.failure(
                MetricStatus.NOT_APPLICABLE,
                ReasonCode.INVALID_REQUEST,
                "The result overflows the finite double range for the supplied inputs.",
            ),
            tuple(operands),
            tuple(zero),
            tuple(notes),
        )
    return _ev_result(market_cap, total_debt, MetricResult.ok(total), tuple(operands), tuple(zero), tuple(notes))
