"""Momentum's point-in-time boundary (ESC-21, Momentum half).

Momentum does not use the shared timestamp-versus-boundary freshness check that the fact resolver
uses, so the frozen-clock skew tolerance does not apply to it. Its boundary checks are: a strict
truncation to observations at or before ``as_of``, and a data-quality check on the fetched frame. What an
``--as-of`` run fetches is tested in ``test_momentum_as_of_fetch.py``.
"""

from datetime import UTC, date, datetime, timedelta
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.analysis.base_analyzer import AnalysisContext
from src.core.clock import FROZEN_CLOCK_SKEW_TOLERANCE
from src.data.market_data import HistoricalMarketData, MarketDataContext, NoEligibleObservationsError
from src.data.quality import HistoricalDataQualityError, QualityOutcome
from src.strategies.momentum.analyzer import MomentumAnalyzer, MomentumConfig, MomentumRun

FIRST_BAR = datetime(2026, 1, 1, 12, tzinfo=UTC)
EXECUTED_AT = datetime(2026, 2, 1, tzinfo=UTC)
ONE_SECOND = timedelta(seconds=1)
CONFIG = MomentumConfig(short_window=2, long_window=5, rsi_period=2)


def _run(closes: list[float], *, as_of: datetime | None) -> MomentumRun:
    index = pd.DatetimeIndex([FIRST_BAR + timedelta(days=offset) for offset in range(len(closes))])
    frame = pd.DataFrame({"Close": closes}, index=index)
    provider = MagicMock()
    provider.fetch_historical_data.return_value = HistoricalMarketData(
        frame,
        MarketDataContext(
            provider_id="fixture",
            observation_interval="1d",
            data_as_of=index[-1].date(),
            currency="USD",
            observation_count=len(closes),
        ),
    )
    analyzer = MomentumAnalyzer(market_data_provider=provider, start_date="2026-01-01")
    context = AnalysisContext(as_of=as_of, executed_at=EXECUTED_AT, use_cache=True)
    return analyzer.run_analysis("ACME", CONFIG, context)


def _bar_time(position: int) -> datetime:
    return FIRST_BAR + timedelta(days=position)


def test_as_of_keeps_the_bar_exactly_at_the_boundary() -> None:
    run = _run([float(10 + value) for value in range(10)], as_of=_bar_time(7))

    assert run.metrics.current_price == 17.0
    assert run.market_data.data_as_of == date(2026, 1, 8)


def test_as_of_drops_a_bar_one_second_after_the_boundary() -> None:
    run = _run([float(10 + value) for value in range(10)], as_of=_bar_time(7) - ONE_SECOND)

    assert run.metrics.current_price == 16.0
    assert run.market_data.data_as_of == date(2026, 1, 7)


def test_as_of_1990_never_calls_the_provider() -> None:
    provider = MagicMock()
    analyzer = MomentumAnalyzer(market_data_provider=provider, start_date="2026-01-01")
    context = AnalysisContext(as_of=datetime(1990, 1, 1, tzinfo=UTC), executed_at=EXECUTED_AT, use_cache=True)

    with pytest.raises(NoEligibleObservationsError, match="No price history is available at or before"):
        analyzer.run_analysis("ACME", CONFIG, context)

    provider.fetch_historical_data.assert_not_called()


def test_as_of_before_every_bar_has_no_eligible_observations() -> None:
    with pytest.raises(NoEligibleObservationsError, match="No price history is available at or before"):
        _run([10.0, 11.0, 12.0], as_of=FIRST_BAR - ONE_SECOND)


def _run_with_final_bar(offset: timedelta, *, as_of: datetime | None) -> MomentumRun:
    """Nine ordinary daily bars, then one dated ``offset`` after the run's execution time."""
    index = pd.DatetimeIndex([FIRST_BAR + timedelta(days=day) for day in range(9)] + [EXECUTED_AT + offset])
    frame = pd.DataFrame({"Close": [float(10 + day) for day in range(10)]}, index=index)
    provider = MagicMock()
    provider.fetch_historical_data.return_value = HistoricalMarketData(
        frame,
        MarketDataContext(
            provider_id="fixture",
            observation_interval="1d",
            data_as_of=index[-1].date(),
            currency="USD",
            observation_count=10,
        ),
    )
    analyzer = MomentumAnalyzer(market_data_provider=provider, start_date="2026-01-01")
    return analyzer.run_analysis("ACME", CONFIG, AnalysisContext(as_of=as_of, executed_at=EXECUTED_AT, use_cache=True))


@pytest.mark.parametrize("offset", [timedelta(0), timedelta(minutes=5), FROZEN_CLOCK_SKEW_TOLERANCE])
def test_live_run_accepts_a_bar_dated_within_the_skew_tolerance_after_execution(offset: timedelta) -> None:
    run = _run_with_final_bar(offset, as_of=None)

    assert run.metrics.current_price == 19.0


@pytest.mark.parametrize("offset", [FROZEN_CLOCK_SKEW_TOLERANCE + ONE_SECOND, timedelta(hours=1), timedelta(days=30)])
def test_live_run_rejects_a_bar_dated_beyond_the_skew_tolerance_with_a_specific_reason(offset: timedelta) -> None:
    """ESC-23: the bar is not dropped silently; the run fails and names the rule."""
    with pytest.raises(HistoricalDataQualityError, match="later than the execution time") as raised:
        _run_with_final_bar(offset, as_of=None)

    failed = [decision for decision in raised.value.decisions if decision.outcome is QualityOutcome.FAIL]
    assert [decision.rule_id for decision in failed] == ["historical.future_observation"]


def test_as_of_run_is_unaffected_because_truncation_already_excludes_the_future_bar() -> None:
    run = _run_with_final_bar(timedelta(days=30), as_of=_bar_time(7))

    assert run.metrics.current_price == 17.0
