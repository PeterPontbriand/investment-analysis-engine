"""The result type every shared metric returns, and the mapping from a balance-sheet absence to a reason code.

A shared metric is a pure function over resolved inputs. It returns a ``MetricEvidence``: the ``MetricResult``, the
named operands it used with their provenance, the components it took as zero, and diagnostic messages. Market
capitalization has its own result type (``analysis/shared/market_cap.py``) because it also records a share count, a
price and the splits applied.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from investment_analysis_engine.core.metric_result import MetricResult, MetricStatus, ReasonCode
from investment_analysis_engine.data.financial.facts import InstantAbsence, InstantAbsenceReason
from investment_analysis_engine.data.financial.provenance import ResolvedInput
from investment_analysis_engine.data.financial.resolver import LeftOutObservation, LeftOutReason

# A balance-sheet value at a fiscal year-end *t*: what the instant series reports, or why it reports none.
BalanceSheetValue = ResolvedInput | InstantAbsence

# An annual value for year *t*: the resolved input, or ``None`` for "the filings report none for year *t*".
AnnualValue = ResolvedInput | None

_ABSENCE_REASON_CODES: Mapping[InstantAbsenceReason, ReasonCode] = {
    InstantAbsenceReason.NOT_TAGGED: ReasonCode.MISSING_FACT,
    InstantAbsenceReason.OTHER_CONCEPT: ReasonCode.MISSING_FACT,
    InstantAbsenceReason.NO_ANCHOR_FILING: ReasonCode.MISSING_FACT,
    InstantAbsenceReason.CONFLICT: ReasonCode.AMBIGUOUS_FACT,
    InstantAbsenceReason.UNSUPPORTED: ReasonCode.UNSUPPORTED_MAPPING,
    InstantAbsenceReason.AFTER_BOUNDARY: ReasonCode.NOT_AVAILABLE_AS_OF,
    InstantAbsenceReason.BASIS_MISMATCH: ReasonCode.INCOMPATIBLE_SCOPE,
}


def absence_reason_code(reason: InstantAbsenceReason) -> ReasonCode:
    """Return the reason code every metric gives an input that is absent for ``reason``."""
    return _ABSENCE_REASON_CODES[reason]


@dataclass(frozen=True)
class InputUnavailable:
    """An input a metric needs that is unavailable for a reason other than a balance-sheet absence.

    Examples are no share count, conflicting or per-class share counts, and no price.

    Attributes:
        reason_code: The code the dependent metric reports.
        reason: A non-empty explanation.
    """

    reason_code: ReasonCode
    reason: str

    def __post_init__(self) -> None:
        """Require an explanation."""
        if not self.reason.strip():
            raise ValueError("An unavailable input requires a non-empty reason.")


@dataclass(frozen=True)
class Operand:
    """One input a metric used, under the name the metric gives it."""

    name: str
    input: ResolvedInput


@dataclass(frozen=True)
class MetricEvidence:
    """A shared metric's result with the inputs behind it.

    Attributes:
        result: The metric's status, finite value, reason code and reason.
        operands: Every resolved input used, in the order the metric reads them.
        zero_components: The names of the components taken as zero because the filing reports none.
        diagnostics: Messages that explain a zero component, a derivation or an affected component.
    """

    result: MetricResult
    operands: tuple[Operand, ...] = ()
    zero_components: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()


def unavailable(
    reason_code: ReasonCode,
    reason: str,
    *,
    operands: tuple[Operand, ...] = (),
    diagnostics: tuple[str, ...] = (),
) -> MetricEvidence:
    """Return an ``unavailable`` result carrying ``reason_code`` and ``reason``."""
    return MetricEvidence(
        result=MetricResult.failure(MetricStatus.UNAVAILABLE, reason_code, reason),
        operands=operands,
        diagnostics=diagnostics,
    )


def absent_input(name: str, absence: InstantAbsence) -> MetricEvidence:
    """Return the ``unavailable`` result of a metric whose input ``name`` is absent, with the table's reason code."""
    return unavailable(
        absence_reason_code(absence.reason),
        f"{name} is absent at {absence.period_end}: {absence.detail}",
    )


def missing_annual(name: str) -> MetricEvidence:
    """Return the ``unavailable`` result of a metric whose annual input ``name`` is reported as none."""
    return unavailable(ReasonCode.MISSING_FACT, f"{name} is not reported for the fiscal year.")


@dataclass(frozen=True)
class LeftOutYear:
    """One fiscal year of one field that was left out of the series, with the reason.

    Attributes:
        field: The field's name, such as ``eps``.
        fiscal_year: The calendar year containing the period end, which is how a fiscal year is labelled.
        period_end: The end of the period that was left out.
        reason_code: The served reason code: ``earlier_basis``, or ``ambiguous_fact`` for a year whose filings
            filed together give different values.
        reason: The explanation.
    """

    field: str
    fiscal_year: int
    period_end: date
    reason_code: ReasonCode
    reason: str

    def __post_init__(self) -> None:
        """Require the fiscal year to be the year of the period end."""
        if self.fiscal_year != self.period_end.year:
            raise ValueError("A left-out year's fiscal year is the year of its period end.")


_LEFT_OUT_CODES: Mapping[LeftOutReason, ReasonCode] = {
    LeftOutReason.EARLIER_BASIS: ReasonCode.EARLIER_BASIS,
    LeftOutReason.CONFLICTING_VERSIONS: ReasonCode.AMBIGUOUS_FACT,
}


def left_out_years_of(field: str, left_out: Sequence[LeftOutObservation]) -> tuple[LeftOutYear, ...]:
    """Return the years of ``field`` left out as earlier-basis or conflicting, oldest first.

    An observation left out for another reason (after the boundary, or failing a quality check) is not a left-out
    year: its reason is not a served code of this record.
    """
    years = [
        LeftOutYear(
            field=field,
            fiscal_year=item.observation_period_end.year,
            period_end=item.observation_period_end.date(),
            reason_code=_LEFT_OUT_CODES[item.why],
            reason=item.reason,
        )
        for item in left_out
        if item.why in _LEFT_OUT_CODES and item.observation_period_end is not None
    ]
    return tuple(sorted(years, key=lambda year: year.period_end))
