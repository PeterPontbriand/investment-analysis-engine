"""The headline a strategy offers for the side-by-side refresh table.

Each strategy supplies one pure function from its decoded result to a :class:`Headline`: a fixed-order tuple of
cells, the fiscal period end the run used and the filing taxonomy. A cell has a stable key, a label, a kind (a number or
a text), a value, an explicit unit, the status of that cell's own value and the reason code the result carries for it.

A text cell carries no status, no reason code and no unit: the run's status is already shown beside it as the run's
outcome. A number cell with a value is ``ok``; a number cell without one carries the status that says why and, where
the result carries one, the reason code. Nothing missing becomes zero.
"""

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final

from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.metric_result import MetricStatus, ReasonCode


class CellKind(StrEnum):
    """Whether a cell holds a number or a text."""

    NUMBER = "number"
    TEXT = "text"


UNIT_PERCENT: Final = "percent"
"""The unit of a percentage."""

UNIT_POINTS: Final = "points"
"""The unit of an index on its own scale, such as the RSI."""

UNIT_MULTIPLE: Final = "multiple"
"""The unit of a ratio shown as a multiple, such as ``12.3x``."""

UNSPECIFIED_CURRENCY_PER_SHARE: Final = "currency unspecified per share"
"""The unit of a per-share amount whose currency the run did not record."""

CellStatus = CalculationStatus | MetricStatus
"""The status of a number cell's value: the run's status or the metric's own."""


def per_share_unit(currency: str | None) -> str:
    """Return ``"<currency> per share"``, or the unspecified form when the run recorded no currency."""
    return f"{currency} per share" if currency else UNSPECIFIED_CURRENCY_PER_SHARE


@dataclass(frozen=True)
class HeadlineCell:
    """One entry of a headline; see the module docstring for what each kind carries."""

    key: str
    label: str
    kind: CellKind
    value: float | str | None
    unit: str | None
    status: CellStatus | None
    reason_code: ReasonCode | None = None

    def __post_init__(self) -> None:
        """Enforce the invariants of a number cell and of a text cell."""
        if not self.key.strip() or not self.label.strip():
            raise ValueError("A headline cell needs a key and a label.")
        if self.kind is CellKind.TEXT:
            self._validate_text()
        else:
            self._validate_number()

    def _validate_text(self) -> None:
        """A text cell has a non-empty text or none, and no unit, status or reason code."""
        if self.value is not None and (not isinstance(self.value, str) or not self.value.strip()):
            raise ValueError("A text cell holds a non-empty text or no value.")
        if self.unit is not None or self.status is not None or self.reason_code is not None:
            raise ValueError("A text cell carries no unit, status or reason code.")

    def _validate_number(self) -> None:
        """A number cell has a finite number or none, a unit and a status that agrees with the value."""
        value = self.value
        if value is not None and (isinstance(value, bool) or not isinstance(value, int | float)):
            raise ValueError("A number cell holds a number or no value.")
        if value is not None and not math.isfinite(value):
            raise ValueError("A number cell never holds NaN or infinity.")
        if self.unit is None or not self.unit.strip():
            raise ValueError("A number cell has a unit.")
        if self.status is None:
            raise ValueError("A number cell has a status.")
        is_ok = self.status in (CalculationStatus.OK, MetricStatus.OK)
        if (value is not None) != is_ok:
            raise ValueError("A number cell has a value if and only if its status is ok.")
        if is_ok and self.reason_code is not None:
            raise ValueError("An ok number cell carries no reason code.")


@dataclass(frozen=True)
class Headline:
    """A strategy's cells in table order, with the fiscal period end and taxonomy the run used.

    ``period_end_label`` says what the strategy's period end is, such as the end of the earnings input's
    period; a strategy with no fiscal period has no label. The table never shows a period end under a plainer
    name than the strategy gives it.
    """

    cells: tuple[HeadlineCell, ...]
    period_end: datetime | None = None
    taxonomy: str | None = None
    period_end_label: str | None = None

    def __post_init__(self) -> None:
        """Require at least one cell, unique keys and an aware period end."""
        if not self.cells:
            raise ValueError("A headline has at least one cell.")
        keys = [cell.key for cell in self.cells]
        if len(set(keys)) != len(keys):
            raise ValueError("Headline cell keys are unique.")
        if self.period_end is not None and self.period_end.utcoffset() is None:
            raise ValueError("A headline period end is timezone-aware.")
        if self.taxonomy is not None and not self.taxonomy.strip():
            raise ValueError("A headline taxonomy is non-empty or absent.")
        if self.period_end_label is not None and not self.period_end_label.strip():
            raise ValueError("A headline period-end label is non-empty or absent.")
        if self.period_end is not None and self.period_end_label is None:
            raise ValueError("A headline period end needs the label that says what it is.")


__all__ = [
    "UNIT_MULTIPLE",
    "UNIT_PERCENT",
    "UNIT_POINTS",
    "UNSPECIFIED_CURRENCY_PER_SHARE",
    "CellKind",
    "CellStatus",
    "Headline",
    "HeadlineCell",
    "per_share_unit",
]
