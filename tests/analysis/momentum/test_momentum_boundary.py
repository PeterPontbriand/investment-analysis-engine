"""Momentum's point-in-time boundary (ESC-21, Momentum half).

Momentum does not use the shared timestamp-versus-boundary freshness check that the fact resolver
uses, so the frozen-clock skew tolerance does not apply to it. Its boundary checks are: a strict
truncation to observations at or before ``as_of``, and a data-quality check on the fetched frame.
"""

from datetime import UTC, date, datetime, timedelta
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.analysis.base_analyzer import AnalysisContext
from src.analysis.strategy.momentum.momentum_analyzer import MomentumAnalyzer, MomentumConfig, MomentumRun
from src.data.market_data import HistoricalMarketData, MarketDataContext, NoEligibleObservationsError
from src.data.quality import HistoricalDataQualityError

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


def test_as_of_before_every_bar_has_no_eligible_observations() -> None:
    with pytest.raises(NoEligibleObservationsError, match="No price history is available at or before"):
        _run([10.0, 11.0, 12.0], as_of=FIRST_BAR - ONE_SECOND)


def test_as_of_run_fails_closed_when_a_bar_after_the_boundary_is_invalid() -> None:
    """Quality is checked on the whole fetched frame before truncation (ESC-22 records this).

    The bar after the boundary never reaches the calculation, yet its invalid value still stops the run.
    This pins the current behavior so a change to it is deliberate.
    """
    closes = [float(10 + value) for value in range(10)]
    closes[-1] = float("nan")

    with pytest.raises(HistoricalDataQualityError):
        _run(closes, as_of=_bar_time(5))
