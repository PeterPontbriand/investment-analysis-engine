"""Scaling a filed share count onto the basis of a split-adjusted price."""

import json
import math
from datetime import date
from typing import Any

import pytest

from investment_analysis_engine.analysis.shared.split_adjustment import (
    RECOGNIZED_SPLIT_RATIOS,
    AdjustmentWindow,
    AppliedAdjustment,
    is_recognized_split_ratio,
    scale_share_count,
)
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
_PRICE = _ADJUSTED
_FILED = date(2024, 2, 21)
_SPLIT = SplitEvent(date(2024, 6, 10), 10.0)


def _scaled(count: float, after: date, events: tuple[SplitEvent, ...], *, price: date = _PRICE) -> float:
    return scale_share_count(count, after, price, _ADJUSTED, events).count


def test_a_split_after_the_filing_date_scales_the_count() -> None:
    assert _scaled(2_464_000_000, _FILED, (_SPLIT,)) == 24_640_000_000


def test_a_split_before_or_on_the_filing_date_does_not() -> None:
    assert _scaled(100.0, date(2024, 6, 11), (_SPLIT,)) == 100.0
    assert _scaled(100.0, date(2024, 6, 10), (_SPLIT,)) == 100.0
    assert _scaled(100.0, date(2024, 6, 9), (_SPLIT,)) == 1000.0


def test_two_splits_compound_and_a_split_after_the_adjustment_date_is_not_applied() -> None:
    events = (SplitEvent(date(2021, 7, 20), 4.0), _SPLIT, SplitEvent(date(2027, 1, 4), 2.0))
    assert _scaled(10.0, date(2021, 1, 1), events) == 400.0
    assert _scaled(10.0, date(2021, 7, 20), events) == 100.0
    assert scale_share_count(10.0, date(2021, 1, 1), _PRICE, date(2027, 1, 4), events).count == 800.0


def test_each_event_records_the_window_it_fell_in() -> None:
    events = (SplitEvent(date(2024, 6, 10), 10.0), SplitEvent(date(2026, 9, 1), 2.0))
    result = scale_share_count(1.0, date(2024, 1, 1), date(2025, 1, 1), _ADJUSTED, events)
    assert result.applied == (
        AppliedAdjustment(date(2024, 6, 10), 10.0, AdjustmentWindow.COUNT_TO_PRICE),
        AppliedAdjustment(date(2026, 9, 1), 2.0, AdjustmentWindow.PRICE_TO_ADJUSTMENT),
    )
    assert result.count == 20.0
    assert result.unrecognized is None


def test_an_event_on_the_price_date_is_in_the_first_window_and_the_day_after_in_the_second() -> None:
    on_the_day = scale_share_count(1.0, date(2024, 1, 1), date(2024, 6, 10), _ADJUSTED, (_SPLIT,))
    assert [item.window for item in on_the_day.applied] == [AdjustmentWindow.COUNT_TO_PRICE]
    day_before = scale_share_count(1.0, date(2024, 1, 1), date(2024, 6, 9), _ADJUSTED, (_SPLIT,))
    assert [item.window for item in day_before.applied] == [AdjustmentWindow.PRICE_TO_ADJUSTMENT]


def test_an_event_after_the_price_date_is_applied_whatever_its_ratio() -> None:
    for ratio in (1.061, 0.9535, 1.05, 3.7):
        event = SplitEvent(date(2026, 1, 5), ratio)
        result = scale_share_count(100.0, date(2024, 1, 1), date(2025, 1, 1), _ADJUSTED, (event,))
        assert result.count == pytest.approx(100.0 * ratio)
        assert result.unrecognized is None


def test_an_unrecognized_ratio_between_the_count_and_the_price_leaves_the_count_undetermined() -> None:
    first, second = SplitEvent(date(2025, 3, 1), 1.061), SplitEvent(date(2025, 9, 1), 0.9535)
    result = scale_share_count(100.0, date(2025, 1, 1), _PRICE, _ADJUSTED, (_SPLIT, first, second))
    assert result.unrecognized == first
    assert result.count == 100.0
    assert result.applied == ()


def test_when_the_price_precedes_the_count_only_events_after_the_count_are_applied() -> None:
    event = SplitEvent(date(2024, 6, 1), 2.0)
    result = scale_share_count(100.0, date(2025, 1, 1), date(2024, 1, 1), _ADJUSTED, (event,))
    assert result.count == 100.0
    assert result.applied == ()


def test_the_captured_ratios_and_their_outcomes() -> None:
    outcomes = {
        ("nvda", 10.0): True,
        ("wmt", 3.0): True,
        ("cbsh", 1.05): False,
        ("hon", 1.0053282396702523): False,
        ("hon", 1.011): False,
        ("hon", 1.032): False,
        ("hon", 1.061): False,
        ("hon", 0.9535): False,
    }
    captured = {(name, ratio) for name in ("nvda", "wmt", "cbsh", "hon") for _, ratio in _fixture(name)["events"]}
    assert captured == set(outcomes)
    for (_, ratio), expected in outcomes.items():
        assert is_recognized_split_ratio(ratio) is expected


def test_the_rule_is_a_closed_set_of_forward_and_reverse_split_ratios() -> None:
    for recognized in (2.0, 3.0, 4.0, 10.0, 1.5, 1.25, 0.5, 0.1, 0.25, 2 / 3):
        assert recognized in RECOGNIZED_SPLIT_RATIOS
    for refused in (1.0, 1.03, 1.05, 1.1, 0.95, 0.9535, 1.061, 11.0, 2.0000001):
        assert not is_recognized_split_ratio(refused)


def test_no_events_leave_the_count_unchanged() -> None:
    assert _scaled(7.0, _FILED, ()) == 7.0


def test_a_count_or_ratio_that_is_not_finite_and_positive_is_refused() -> None:
    for count in (0.0, -1.0, math.inf, math.nan, True):
        with pytest.raises(ValueError, match="share count"):
            _scaled(count, _FILED, ())
    bad = object.__new__(SplitEvent)
    for ratio in (0.0, -2.0, math.inf):
        object.__setattr__(bad, "ex_date", date(2025, 1, 2))
        object.__setattr__(bad, "ratio", ratio)
        with pytest.raises(ValueError, match="split ratio"):
            _scaled(1.0, _FILED, (bad,))
    with pytest.raises(ValueError, match="split ratio"):
        SplitEvent(date(2025, 1, 2), 0.0)
    with pytest.raises(ValueError, match="calendar date"):
        SplitEvent("2025-01-02", 2.0)  # type: ignore[arg-type]


def test_nvidia_the_fiscal_2024_count_scaled_by_the_june_split_gives_the_same_market_cap() -> None:
    events = _events("nvda")
    assert events == (_SPLIT,)
    count = scale_share_count(
        2_464_000_000, _FILED, date(2024, 4, 30), date.fromisoformat(_fixture("nvda")["adjustment_date"]), events
    ).count
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
    assert _scaled(restated, filed_after_the_split, events) == restated
    # Scaling from the fiscal year-end instead would count the split twice and give a result three times larger.
    assert _scaled(restated, date(2024, 1, 31), events) == 3 * restated


def test_a_later_filings_restated_comparative_is_not_scaled_by_the_june_split() -> None:
    # NVIDIA's fiscal 2025 filing (filed 2025-02-26) restates the count at 2024-01-28 as 24,643,000,000.
    restated = 24_643_000_000.0
    assert _scaled(restated, date(2025, 2, 26), _events("nvda")) == restated


def test_a_split_after_the_requested_boundary_still_scales_the_count_because_the_price_is_adjusted_for_it() -> None:
    # The close of 2024-04-30 is already divided by the split of 2024-06-10; the count must be multiplied by it.
    as_of_close = _close("nvda", "2024-04-30")
    scaled = _scaled(1_000.0, _FILED, _events("nvda"), price=date(2024, 4, 30))
    assert scaled == 10_000.0
    assert as_of_close * scaled == pytest.approx(as_of_close * 10 * 1_000.0)


def test_commerce_bancshares_stock_dividend_is_refused_between_the_count_and_the_price_and_applied_after_it() -> None:
    # W1: a 5% stock dividend (1.05) is not a recognizable split ratio. This reverses F7 inside the second window.
    events = _events("cbsh")
    assert events == (SplitEvent(date(2025, 12, 2), 1.05),)
    between = scale_share_count(1_000.0, date(2025, 11, 1), _PRICE, _ADJUSTED, events)
    assert between.unrecognized == events[0]
    after_the_price = scale_share_count(1_000.0, date(2025, 11, 1), date(2025, 11, 28), _ADJUSTED, events)
    assert after_the_price.count == pytest.approx(1_050.0)
    assert _scaled(1_000.0, date(2025, 12, 2), events) == 1_000.0
