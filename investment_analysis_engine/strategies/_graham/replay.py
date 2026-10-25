"""Replay code the two Graham strategies share."""

from dataclasses import replace

from investment_analysis_engine.analysis.shared.financial_resolution import PriceComparison
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.metric_result import MetricStatus
from investment_analysis_engine.reporting.evidence_presentation import friendly_valuation_failure
from investment_analysis_engine.reporting.headline import UNIT_PERCENT, CellKind, HeadlineCell, per_share_unit
from investment_analysis_engine.strategies.graham_growth.calculation import GrowthValueInputAssembly
from investment_analysis_engine.strategies.graham_number.calculation import GrahamNumberInputAssembly

# Statuses whose stored `assembly.reason`/`result.reason` is already investor-facing
# (a successful calculation, or a method-level inapplicability message authored at
# the source); every other non-OK status carries a raw resolver reason that the live
# commands only ever show after `friendly_valuation_failure` normalizes it.
_REASON_ALREADY_SAFE = (CalculationStatus.OK, CalculationStatus.NOT_APPLICABLE)


def friendly_graham_assembly[AssemblyT: (GrahamNumberInputAssembly, GrowthValueInputAssembly)](
    ticker: str, assembly: AssemblyT
) -> AssemblyT:
    """Replace a genuine failure's raw reason with the live command's investor-facing text.

    Mirrors the Graham commands' failure output exactly: a successful or NOT_APPLICABLE assembly's reason is
    already safe to show verbatim (or, for OK, is None); any other status carries a raw resolver reason at
    capture time that the live command only ever displays after `friendly_valuation_failure` normalizes it.
    """
    if assembly.status in _REASON_ALREADY_SAFE:
        return assembly
    return replace(assembly, reason=friendly_valuation_failure(ticker, assembly.status, assembly.reason))


EARNINGS_PERIOD_END_LABEL = "earnings input period end"
"""What a Graham strategy's period end is: the observation period end of the earnings (EPS) input.

Book value can come from another period; no code compares them, so the label never calls it the period end of the run.
"""


def price_cell(
    *, key: str, label: str, value: float | None, status: CalculationStatus, currency: str | None
) -> HeadlineCell:
    """Return a Graham strategy's per-share cell: its value, the strategy's own status and the run's currency.

    The Graham results carry text reasons only, so the cell has no reason code. The currency is the one the run
    recorded, or none, which the unit then says.
    """
    return HeadlineCell(key, label, CellKind.NUMBER, value, per_share_unit(currency), status)


def margin_cell(
    *, comparison: PriceComparison | None, percent: float | None, native_status: CalculationStatus
) -> HeadlineCell:
    """Return the margin-of-safety cell: the comparison's percent, with its status mapped to a cell status.

    ``available`` is ``ok`` and ``unavailable`` is ``unavailable``. When no comparison exists the cell takes the
    run's status, or ``unavailable`` when that status is ``ok`` yet no comparison was made.
    """
    if comparison is not None:
        status: CalculationStatus | MetricStatus = (
            MetricStatus.OK if comparison.status == "available" else MetricStatus.UNAVAILABLE
        )
        value = percent if comparison.status == "available" else None
    else:
        status = MetricStatus.UNAVAILABLE if native_status is CalculationStatus.OK else native_status
        value = None
    return HeadlineCell("margin_of_safety", "Margin", CellKind.NUMBER, value, UNIT_PERCENT, status)
