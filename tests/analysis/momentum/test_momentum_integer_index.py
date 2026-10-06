"""ESC-25: Momentum never reports dates the provider's frame did not supply.

A historical frame whose index is not date-like fails the shared quality check, so Momentum rejects it
instead of reading the index as epoch nanoseconds (which produced observation dates of 1970-01-01).
Frames with an allowlisted date index keep their own dates in the result's provenance.
"""

from datetime import UTC, date, datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.analysis.base_analyzer import AnalysisContext
from src.data.market_data import HistoricalMarketData, MarketDataContext
from src.data.quality import HistoricalDataQualityError, QualityContext, QualityOutcome, evaluate_historical_quality
from src.strategies.momentum.analyzer import MomentumAnalyzer, MomentumConfig, MomentumRun

EXECUTED_AT = datetime(2026, 9, 1, tzinfo=UTC)
CLOSES = [100.0, 101.0, 102.0, 103.0, 104.0]
CONFIG = MomentumConfig(short_window=2, long_window=3, rsi_period=3)
DAYS = [date(2026, 8, day) for day in range(10, 15)]


def _data(index: pd.Index | None) -> HistoricalMarketData:
    frame = pd.DataFrame({"Close": CLOSES}) if index is None else pd.DataFrame({"Close": CLOSES}, index=index)
    return HistoricalMarketData(
        frame,
        MarketDataContext(
            provider_id="fixture",
            observation_interval="1d",
            currency="USD",
            observation_count=5,
            data_as_of=None if index is None else DAYS[-1],
        ),
    )


def _run(data: HistoricalMarketData) -> MomentumRun:
    provider = MagicMock()
    provider.fetch_historical_data.return_value = data
    analyzer = MomentumAnalyzer(market_data_provider=provider, start_date="2026-01-01")
    context = AnalysisContext(as_of=None, executed_at=EXECUTED_AT, use_cache=True)
    return analyzer.run_analysis("ACME", CONFIG, context)


def test_integer_indexed_frame_is_rejected_with_the_index_rule() -> None:
    with pytest.raises(HistoricalDataQualityError) as raised:
        _run(_data(None))

    failures = [item for item in raised.value.decisions if item.outcome is QualityOutcome.FAIL]
    assert [item.rule_id for item in failures] == ["historical.index"]
    assert "date-like index" in str(raised.value)


@pytest.mark.parametrize(
    "index",
    [
        pd.Index([0.5, 1.5, 2.5, 3.5, 4.5]),
        pd.Index(["a", "b", "c", "d", "e"]),
    ],
    ids=["float", "string"],
)
def test_other_non_date_indexes_are_rejected(index: pd.Index) -> None:
    with pytest.raises(HistoricalDataQualityError):
        _run(_data(index))


def test_quality_fails_an_integer_index() -> None:
    decisions = evaluate_historical_quality(_data(None), context=QualityContext("ACME:h", EXECUTED_AT, None))

    assert {item.rule_id: item.outcome for item in decisions}["historical.index"] is QualityOutcome.FAIL


@pytest.mark.parametrize(
    "index",
    [
        pd.DatetimeIndex(DAYS),
        pd.DatetimeIndex(DAYS, tz="UTC"),
        pd.Index(DAYS),
    ],
    ids=["naive", "utc", "python_dates"],
)
def test_provenance_carries_exactly_the_dates_the_frame_supplied(index: pd.Index) -> None:
    run = _run(_data(index))

    assert [item.observed_at.date() for item in run.price_inputs if item.observed_at is not None] == DAYS
    assert all(item.observed_at is not None and item.observed_at.year == 2026 for item in run.price_inputs)
    assert run.market_data.data_as_of == DAYS[-1]
