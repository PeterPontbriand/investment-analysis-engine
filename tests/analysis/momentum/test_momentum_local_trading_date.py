"""ESC-26: a zoned daily frame reports the local trading dates it supplied, exactly as a naive frame does.

A timezone-aware index whose every bar is at local midnight in its own zone is reduced to its local
calendar dates (the zone is dropped, not converted) before the ``--as-of`` truncation and before provenance
is built. Any other index keeps the converted-instant behaviour.
"""

from datetime import UTC, date, datetime, time
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.analysis.base_analyzer import AnalysisContext
from src.data.market_data import HistoricalMarketData, MarketDataContext, latest_observation_date
from src.data.quality import QualityContext, QualityOutcome, evaluate_historical_quality
from src.strategies.momentum.analyzer import MomentumAnalyzer, MomentumConfig, MomentumRun

EXECUTED_AT = datetime(2026, 9, 1, tzinfo=UTC)
DAYS = [date(2026, 8, day) for day in range(10, 15)]
CLOSES = [100.0, 101.0, 102.0, 103.0, 104.0]
CONFIG = MomentumConfig(short_window=2, long_window=3, rsi_period=3)
ZONES = ["Asia/Tokyo", "America/New_York"]
# What ``--as-of 2026-08-12`` parses to: the end of that UTC day.
AS_OF_DATE_BOUNDARY = datetime.combine(date(2026, 8, 12), time.max, tzinfo=UTC)


def _local_midnights(days: list[date], zone: str | None) -> pd.DatetimeIndex:
    return pd.DatetimeIndex([f"{day.isoformat()} 00:00" for day in days], tz=zone)


def _data(index: pd.DatetimeIndex) -> HistoricalMarketData:
    frame = pd.DataFrame({"Close": CLOSES[: len(index)]}, index=index)
    return HistoricalMarketData(
        frame,
        MarketDataContext(
            provider_id="fixture",
            observation_interval="1d",
            currency="USD",
            observation_count=len(frame),
            data_as_of=latest_observation_date(frame),
        ),
    )


def _run(index: pd.DatetimeIndex, as_of: datetime | None) -> MomentumRun:
    provider = MagicMock()
    provider.fetch_historical_data.return_value = _data(index)
    analyzer = MomentumAnalyzer(market_data_provider=provider, start_date="2026-01-01")
    return analyzer.run_analysis("ACME", CONFIG, AnalysisContext(as_of=as_of, executed_at=EXECUTED_AT, use_cache=True))


def _observed(run: MomentumRun) -> list[datetime | None]:
    return [item.observed_at for item in run.price_inputs]


@pytest.mark.parametrize("as_of", [None, datetime(2026, 9, 1, tzinfo=UTC)], ids=["live", "as_of"])
@pytest.mark.parametrize("zone", ZONES)
def test_zoned_daily_frame_reports_its_local_calendar_dates(zone: str, as_of: datetime | None) -> None:
    run = _run(_local_midnights(DAYS, zone), as_of)

    assert _observed(run) == [datetime(day.year, day.month, day.day, tzinfo=UTC) for day in DAYS]
    assert run.market_data.data_as_of == DAYS[-1]


@pytest.mark.parametrize("zone", ZONES)
def test_date_boundary_on_a_zoned_frame_matches_the_local_dates(zone: str) -> None:
    """The ledger's worked example: ``--as-of 2026-08-12`` uses the bars dated 10, 11 and 12 August."""
    run = _run(_local_midnights(DAYS, zone), AS_OF_DATE_BOUNDARY)

    assert len(run.price_inputs) == 3
    assert run.metrics.current_price == 102.0
    assert run.market_data.data_as_of == date(2026, 8, 12)


@pytest.mark.parametrize("as_of", [None, AS_OF_DATE_BOUNDARY], ids=["live", "as_of"])
@pytest.mark.parametrize("zone", ZONES)
def test_zoned_frame_and_naive_frame_with_the_same_local_dates_give_identical_results(
    zone: str, as_of: datetime | None
) -> None:
    zoned = _run(_local_midnights(DAYS, zone), as_of)
    naive = _run(_local_midnights(DAYS, None), as_of)

    assert zoned.metrics == naive.metrics
    assert zoned.market_data == naive.market_data
    assert zoned.price_inputs == naive.price_inputs
    assert zoned.resolution_trace == naive.resolution_trace


@pytest.mark.parametrize("zone", ZONES)
def test_frame_crossing_a_daylight_saving_change_is_still_all_local_midnight(zone: str) -> None:
    for start in (date(2026, 3, 6), date(2025, 10, 31), date(2025, 11, 1)):
        days = [date.fromordinal(start.toordinal() + offset) for offset in range(5)]
        index = pd.date_range(start.isoformat(), periods=5, freq="D", tz=zone)

        run = _run(index, None)

        assert _observed(run) == [datetime(day.year, day.month, day.day, tzinfo=UTC) for day in days]
        assert run.market_data.data_as_of == days[-1]


def test_zoned_frame_with_one_bar_off_local_midnight_keeps_the_converted_instants() -> None:
    index = pd.DatetimeIndex(
        [
            "2026-08-10 00:00",
            "2026-08-11 00:00",
            "2026-08-12 09:30",
            "2026-08-13 00:00",
            "2026-08-14 00:00",
        ],
        tz="Asia/Tokyo",
    )
    run = _run(index, None)

    assert _observed(run) == [item.to_pydatetime() for item in index.tz_convert("UTC")]
    assert run.market_data.data_as_of == date(2026, 8, 13)


def test_zoned_frame_with_every_bar_off_local_midnight_keeps_the_converted_instants() -> None:
    index = pd.DatetimeIndex([f"{day.isoformat()} 09:30" for day in DAYS], tz="America/New_York")
    run = _run(index, None)

    assert _observed(run) == [item.to_pydatetime() for item in index.tz_convert("UTC")]


@pytest.mark.parametrize("zone", ZONES)
def test_the_data_as_of_the_quality_check_validates_is_the_one_in_the_result(zone: str) -> None:
    """A live run's result keeps the date the context rule verified against the frame's last bar."""
    index = _local_midnights(DAYS, zone)
    data = _data(index)
    context_rule = next(
        item
        for item in evaluate_historical_quality(data, context=QualityContext("ACME:h", EXECUTED_AT, None))
        if item.rule_id == "historical.context"
    )

    run = _run(index, None)

    assert context_rule.outcome is QualityOutcome.PASS
    assert data.context.data_as_of == DAYS[-1]
    assert run.market_data.data_as_of == data.context.data_as_of
