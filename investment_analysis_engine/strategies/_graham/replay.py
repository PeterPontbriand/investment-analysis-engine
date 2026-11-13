"""Replay code the two Graham strategies share."""

from investment_analysis_engine.analysis.shared.financial_resolution import PriceComparison
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.metric_result import MetricStatus, ReasonCode
from investment_analysis_engine.reporting.headline import CellKind, CellUnit, HeadlineCell

EARNINGS_PERIOD_END_LABEL = "earnings input period end"
"""What a Graham strategy's period end is: the observation period end of the earnings (EPS) input.

Book value can come from another period; no code compares them, so the label never calls it the period end of the run.
"""


def price_cell(  # noqa: PLR0913
    *,
    key: str,
    label: str,
    term: str,
    value: float | None,
    status: CalculationStatus,
    reason_code: ReasonCode | None,
    currency: str | None,
) -> HeadlineCell:
    """Return a Graham strategy's per-share cell: its value, the strategy's own status and the run's currency.

    The cell carries the analysis's reason code, which is ``None`` exactly when the status is ``ok``. The currency is
    the one the run recorded, or none when the run recorded none.
    """
    return HeadlineCell(
        key, label, term, CellKind.NUMBER, value, CellUnit.PER_SHARE, status, reason_code, currency=currency or None
    )


def margin_cell(
    *, term: str, comparison: PriceComparison | None, percent: float | None, native_status: CalculationStatus
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
    return HeadlineCell("margin_of_safety", "Margin", term, CellKind.NUMBER, value, CellUnit.PERCENT, status)
