"""Putting a filed share count on the basis of a split-adjusted price.

The price data is adjusted by the provider for every event in its split history up to its adjustment date, so a share
count must be put on the same basis. The provider's events are of two kinds that the history cannot tell apart: splits,
which change the share count, and adjustments that do not (a spin-off appears as a ratio such as 1.061 or 0.9535). Two
windows therefore apply:

- an event after the price date and not after the adjustment date was applied by the provider to the historical close
  alone, and the count of that date is untouched by it. Scaling the count undoes the provider's retroactive adjustment
  of the price, whatever the ratio;
- an event after the count's date and not after the price date happened between the two, so scaling assumes the shares
  really changed. That is true of a split and false of a spin-off. The event is applied only when its ratio is a
  recognizable split ratio (``RECOGNIZED_SPLIT_RATIOS``); any other ratio leaves the share count undetermined.

The function is pure: a count, three dates and the provider's events in, the scaled count and what was applied out.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Final

from investment_analysis_engine.data.market_data import SplitEvent

_FORWARD_NUMERATORS: Final = (2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20, 25, 30, 40, 50, 100)
_FORWARD_DENOMINATORS: Final = (1, 2, 3, 4)

RECOGNIZED_SPLIT_RATIOS: Final = frozenset(
    ratio
    for numerator in _FORWARD_NUMERATORS
    for denominator in _FORWARD_DENOMINATORS
    if numerator > denominator
    for ratio in (numerator / denominator, denominator / numerator)
)
"""The ratios (new shares per old share) the provider reports for a stock split, compared exactly.

A forward split is *p*-for-*q* with *p* in ``_FORWARD_NUMERATORS`` and *q* in ``_FORWARD_DENOMINATORS`` and *p* greater
than *q* (2-for-1, 3-for-1, 10-for-1, 3-for-2, 5-for-4, ...), and a reverse split is its reciprocal (1-for-10 is 0.1).
The ratios of the captured histories decide the rule (the 3.5.2 slice plan, W1a): NVIDIA's 10 and Walmart's 3 are in
it. A stock dividend such as Commerce Bancshares' 1.05 (21-for-20) and Honeywell's 1.00533, 1.011, 1.032, 1.061 and
0.9535 are not, and the rule is closed: a ratio that is not listed is not a split.
"""


class AdjustmentWindow(StrEnum):
    """Where an applied provider adjustment fell relative to the share count and the price."""

    COUNT_TO_PRICE = "count_to_price"
    PRICE_TO_ADJUSTMENT = "price_to_adjustment"


@dataclass(frozen=True)
class AppliedAdjustment:
    """One provider adjustment that scaled the share count, with the window it fell in.

    Attributes:
        ex_date: The event's ex-date.
        ratio: New shares per old share, as the provider reports it.
        window: ``count_to_price`` for an event between the count's date and the price date, applied because its ratio
            is a recognizable split ratio; ``price_to_adjustment`` for an event after the price date, applied to undo
            the provider's adjustment of the historical close.
    """

    ex_date: date
    ratio: float
    window: AdjustmentWindow


@dataclass(frozen=True)
class ScaledShareCount:
    """The share count on the basis of the price, or the event that leaves it undetermined.

    Attributes:
        count: The scaled count; the count as filed when ``unrecognized`` is set.
        applied: The adjustments that scaled it, in ex-date order.
        unrecognized: The first event between the count's date and the price date whose ratio is not a recognizable
            split ratio, or ``None``. When set, the count is not on the basis of the price.
    """

    count: float
    applied: tuple[AppliedAdjustment, ...]
    unrecognized: SplitEvent | None = None


def is_recognized_split_ratio(ratio: float) -> bool:
    """Return whether ``ratio`` is one of ``RECOGNIZED_SPLIT_RATIOS``."""
    return ratio in RECOGNIZED_SPLIT_RATIOS


def scale_share_count(
    count: float, after: date, price_date: date, adjustment_date: date, events: Sequence[SplitEvent]
) -> ScaledShareCount:
    """Return ``count`` on the basis of the price, scaled by the provider's events of the two windows.

    ``after`` is the filing date of the filing a year-end count was taken from, or the cover date of a cover-page
    count; it comes from the count's own provenance and is never assumed to be the anchor filing's. A filing restates
    its share counts for a split effective before it is issued, so an event on the filing date is presumed to be in the
    count already and is not applied. Events after the price date and not after ``adjustment_date`` are applied
    whatever their ratio. Events after ``after`` and not after ``price_date`` are applied when their ratio is
    recognizable; the first that is not is returned as ``unrecognized`` and the count is left as filed. When the price
    date is not after ``after`` only the first window can apply, from ``after``. Splits compound.

    Raises:
        ValueError: If the count is not finite and positive, or an event ratio is not finite and positive.
    """
    if isinstance(count, bool) or not math.isfinite(count) or count <= 0:
        raise ValueError(f"A share count must be finite and positive (received {count!r}).")
    scaled = count
    applied: list[AppliedAdjustment] = []
    for event in events:
        if not math.isfinite(event.ratio) or event.ratio <= 0:
            raise ValueError(f"A split ratio must be finite and positive (received {event.ratio!r}).")
        if not after < event.ex_date <= adjustment_date:
            continue
        if event.ex_date > price_date:
            window = AdjustmentWindow.PRICE_TO_ADJUSTMENT
        elif is_recognized_split_ratio(event.ratio):
            window = AdjustmentWindow.COUNT_TO_PRICE
        else:
            return ScaledShareCount(count, (), event)
        scaled *= event.ratio
        applied.append(AppliedAdjustment(event.ex_date, event.ratio, window))
    return ScaledShareCount(scaled, tuple(applied))
