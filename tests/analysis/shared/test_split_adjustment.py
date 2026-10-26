"""Scaling a filed share count onto the basis of a split-adjusted price."""

import json
import math
from datetime import date
from typing import Any

import pytest

from investment_analysis_engine.analysis.shared.split_adjustment import scale_share_count
from investment_analysis_engine.core.package_root import PACKAGE_ROOT
from investment_analysis_engine.data.market_data import SplitEvent

FIXTURES = PACKAGE_ROOT / "evaluation" / "fixtures" / "sec_edgar" / "split_history"


def _fixture(name: str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return document


def _events(name: str) -> tuple[SplitEvent, ...]:
    return tuple(SplitEvent(date.fromisoformat(day), ratio) for day, ratio in _fixture(name)["events"])


def _close(name: str, day: str) -> float:
    return float(dict(_fixture(name)["close"])[day])


_ADJUSTED = date(2026, 10, 26)
_FILED = date(2024, 2, 21)
_SPLIT = SplitEvent(date(2024, 6, 10), 10.0)


def test_a_split_after_the_filing_date_scales_the_count() -> None:
    assert scale_share_count(2_464_000_000, _FILED, _ADJUSTED, (_SPLIT,)) == 24_640_000_000


def test_a_split_before_or_on_the_filing_date_does_not() -> None:
    assert scale_share_count(100.0, date(2024, 6, 11), _ADJUSTED, (_SPLIT,)) == 100.0
    assert scale_share_count(100.0, date(2024, 6, 10), _ADJUSTED, (_SPLIT,)) == 100.0
    assert scale_share_count(100.0, date(2024, 6, 9), _ADJUSTED, (_SPLIT,)) == 1000.0


def test_two_splits_compound_and_a_split_after_the_adjustment_date_is_not_applied() -> None:
    events = (SplitEvent(date(2021, 7, 20), 4.0), _SPLIT, SplitEvent(date(2027, 1, 4), 2.0))
    assert scale_share_count(10.0, date(2021, 1, 1), _ADJUSTED, events) == 400.0
    assert scale_share_count(10.0, date(2021, 7, 20), _ADJUSTED, events) == 100.0
    assert scale_share_count(10.0, date(2021, 1, 1), date(2027, 1, 4), events) == 800.0


def test_a_fractional_ratio_scales_the_count_like_a_split_and_is_not_issuance() -> None:
    # Commerce Bancshares' 5% stock dividend appears as a split of 1.05.
    events = _events("cbsh")
    assert events == (SplitEvent(date(2025, 12, 2), 1.05),)
    assert scale_share_count(1_000.0, date(2025, 11, 1), _ADJUSTED, events) == pytest.approx(1_050.0)
    assert scale_share_count(1_000.0, date(2025, 12, 2), _ADJUSTED, events) == 1_000.0


def test_no_events_leave_the_count_unchanged() -> None:
    assert scale_share_count(7.0, _FILED, _ADJUSTED, ()) == 7.0


def test_a_count_or_ratio_that_is_not_finite_and_positive_is_refused() -> None:
    for count in (0.0, -1.0, math.inf, math.nan, True):
        with pytest.raises(ValueError, match="share count"):
            scale_share_count(count, _FILED, _ADJUSTED, ())
    bad = object.__new__(SplitEvent)
    for ratio in (0.0, -2.0, math.inf):
        object.__setattr__(bad, "ex_date", date(2025, 1, 2))
        object.__setattr__(bad, "ratio", ratio)
        with pytest.raises(ValueError, match="split ratio"):
            scale_share_count(1.0, _FILED, _ADJUSTED, (bad,))
    with pytest.raises(ValueError, match="split ratio"):
        SplitEvent(date(2025, 1, 2), 0.0)
    with pytest.raises(ValueError, match="calendar date"):
        SplitEvent("2025-01-02", 2.0)  # type: ignore[arg-type]


def test_nvidia_the_fiscal_2024_count_scaled_by_the_june_split_gives_the_same_market_cap() -> None:
    events = _events("nvda")
    assert events == (_SPLIT,)
    count = scale_share_count(2_464_000_000, _FILED, date.fromisoformat(_fixture("nvda")["adjustment_date"]), events)
    assert count == 24_640_000_000
    adjusted_close = _close("nvda", "2024-04-30")
    assert adjusted_close == pytest.approx(86.402, abs=1e-3)
    traded = adjusted_close * 10
    assert traded == pytest.approx(864.02, abs=1e-2)
    assert adjusted_close * count == pytest.approx(traded * 2_464_000_000, rel=1e-9)
    assert adjusted_close * count == pytest.approx(2_128_945_280_000, rel=1e-6)


def test_walmart_fiscal_2024_the_count_from_the_filing_after_the_split_is_not_scaled_again() -> None:
    events = _events("wmt")
    assert events == (SplitEvent(date(2024, 2, 26), 3.0),)
    filed_after_the_split = date(2024, 3, 15)
    restated = 2_690_000_000.0 * 3
    assert scale_share_count(restated, filed_after_the_split, _ADJUSTED, events) == restated
    # Scaling from the fiscal year-end instead would count the split twice and give a result three times larger.
    assert scale_share_count(restated, date(2024, 1, 31), _ADJUSTED, events) == 3 * restated


def test_a_later_filings_restated_comparative_is_not_scaled_by_the_june_split() -> None:
    # NVIDIA's fiscal 2025 filing (filed 2025-02-26) restates the count at 2024-01-28 as 24,643,000,000.
    restated = 24_643_000_000.0
    assert scale_share_count(restated, date(2025, 2, 26), _ADJUSTED, _events("nvda")) == restated


def test_a_split_after_the_requested_boundary_still_scales_the_count_because_the_price_is_adjusted_for_it() -> None:
    # The close of 2024-04-30 is already divided by the split of 2024-06-10; the count must be multiplied by it.
    as_of_close = _close("nvda", "2024-04-30")
    scaled = scale_share_count(1_000.0, _FILED, _ADJUSTED, _events("nvda"))
    assert scaled == 10_000.0
    assert as_of_close * scaled == pytest.approx(as_of_close * 10 * 1_000.0)
