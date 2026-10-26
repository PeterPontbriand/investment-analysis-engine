"""Putting a filed share count on the basis of a split-adjusted price.

The price data is adjusted by the provider for every split up to its adjustment date, so a share count must be scaled by
the splits after the date the count was taken, up to the same adjustment date, to be on the same basis. The function is
pure: a count, a starting date, an adjustment date and the split events in, a scaled count out.
"""

import math
from collections.abc import Sequence
from datetime import date

from investment_analysis_engine.data.market_data import SplitEvent


def scale_share_count(count: float, after: date, adjustment_date: date, events: Sequence[SplitEvent]) -> float:
    """Return ``count`` scaled by every split whose ex-date is after ``after`` and not after ``adjustment_date``.

    ``after`` is the filing date of the filing a year-end count was taken from, or the cover date of a cover-page
    count; it comes from the count's own provenance and is never assumed to be the anchor filing's. A filing restates
    its share counts for a split effective before it is issued, so a split on the filing date is presumed to be in
    the count already and is not applied. Splits compound, a fractional ratio (a stock dividend, 1.05) scales the count
    as a split does and is not issuance, and no events leave the count unchanged.

    Raises:
        ValueError: If the count is not finite and positive, or an event ratio is not finite and positive.
    """
    if isinstance(count, bool) or not math.isfinite(count) or count <= 0:
        raise ValueError(f"A share count must be finite and positive (received {count!r}).")
    scaled = count
    for event in events:
        if not math.isfinite(event.ratio) or event.ratio <= 0:
            raise ValueError(f"A split ratio must be finite and positive (received {event.ratio!r}).")
        if after < event.ex_date <= adjustment_date:
            scaled *= event.ratio
    return scaled
