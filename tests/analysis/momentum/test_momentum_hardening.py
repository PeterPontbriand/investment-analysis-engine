"""Slice F regression coverage for Momentum's shared contracts."""

from datetime import UTC, date, datetime

import pandas as pd

from src.analysis.fcf_earnings_growth.models import MetricStatus, ReasonCode
from src.analysis.momentum.momentum_analyzer import (
    MomentumAnalyzer,
    MomentumConfig,
    MomentumInputResolver,
    MomentumPolicy,
)
from src.data.market_data import HistoricalMarketData, MarketDataContext


class FixtureMarketDataProvider:
    """Deterministic provider for point-in-time Momentum tests."""

    provider_id = "fixture_market"

    def __init__(self, frame: pd.DataFrame) -> None:
        """Retain the deterministic historical frame."""
        self._frame = frame

    def fetch_historical_data(self, ticker: str, start_date: str, end_date: str | None = None) -> HistoricalMarketData:
        """Return the complete fixture series so the resolver must truncate it."""
        del ticker, start_date, end_date
        return HistoricalMarketData(
            frame=self._frame,
            context=MarketDataContext(
                provider_id=self.provider_id,
                observation_interval="1d",
                data_as_of=date(2026, 1, 6),
                currency="USD",
                observation_count=len(self._frame),
                price_adjustment="adjusted",
            ),
        )


def test_resolver_truncates_future_bars_and_retains_provenance() -> None:
    """No observation after effective as_of reaches calculation inputs."""
    frame = pd.DataFrame(
        {"Close": [10.0, 11.0, 12.0, 1000.0, 2000.0, 3000.0]},
        index=pd.date_range("2026-01-01", periods=6, tz=UTC),
    )
    resolver = MomentumInputResolver(
        FixtureMarketDataProvider(frame),
        clock=lambda: datetime(2026, 2, 1, tzinfo=UTC),
    )
    boundary = datetime(2026, 1, 3, 23, 59, tzinfo=UTC)

    resolved = resolver.resolve(ticker="TEST", start_date="2026-01-01", as_of=boundary)

    assert resolved.market_data.frame["Close"].tolist() == [10.0, 11.0, 12.0]
    assert len(resolved.price_inputs) == 3
    assert all(value.provider_id == "fixture_market" for value in resolved.price_inputs)
    assert all(value.currency == "USD" for value in resolved.price_inputs)
    assert all(value.observed_at is not None and value.observed_at <= boundary for value in resolved.price_inputs)
    assert [event.stage.value for event in resolved.resolution_trace.events] == [
        "provider",
        "provider",
        "validation",
    ]


def test_metric_results_classify_insufficient_history() -> None:
    """SMA and RSI gaps use the standard unavailable metric contract."""
    metrics = MomentumAnalyzer().run_analysis(
        ticker="SHORT",
        config=MomentumConfig(short_window=2, long_window=5, rsi_period=4),
        df=pd.DataFrame({"Close": [10.0, 11.0, 12.0]}),
    )

    assert metrics.sma_50.status is MetricStatus.OK
    assert metrics.sma_200.status is MetricStatus.UNAVAILABLE
    assert metrics.sma_200.reason_code is ReasonCode.INSUFFICIENT_HISTORY
    assert metrics.rsi_14.status is MetricStatus.UNAVAILABLE
    assert metrics.rsi_14.reason_code is ReasonCode.INSUFFICIENT_HISTORY


def test_momentum_policy_validates_all_periods() -> None:
    """The typed policy owns and validates SMA/RSI periods."""
    policy = MomentumPolicy(short_window=20, long_window=50, rsi_period=10)
    assert (policy.short_window, policy.long_window, policy.rsi_period) == (20, 50, 10)
