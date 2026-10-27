"""The result type every shared metric returns, and the mapping from a balance-sheet absence to a reason code.

A shared metric is a pure function over resolved inputs. It returns a ``MetricEvidence``: the ``MetricResult``, the
named operands it used with their provenance, the components it took as zero, and diagnostic messages. Market
capitalization has its own result type (``analysis/shared/market_cap.py``) because it also records a share count, a
price and the splits applied.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from investment_analysis_engine.core.metric_result import MetricResult, MetricStatus, ReasonCode
from investment_analysis_engine.data.financial.facts import InstantAbsence, InstantAbsenceReason
from investment_analysis_engine.data.financial.provenance import ResolvedInput

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
