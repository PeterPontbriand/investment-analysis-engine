"""Slice F regression coverage for Momentum's shared contracts."""

from datetime import UTC, datetime
from unittest.mock import patch

import pandas as pd
import pytest

from src.analysis.base_analyzer import AnalysisContext
from src.analysis.strategy.fcf_earnings_growth.models import MetricStatus, ReasonCode
from src.analysis.strategy.momentum.momentum_analyzer import (
    MomentumAnalyzer,
    MomentumConfig,
    MomentumInputResolver,
    MomentumPolicy,
    compute_momentum_metrics,
)
from src.data.quality import HistoricalDataQualityError
from src.evaluation.fixtures.market_data import FixtureMarketDataProvider


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

    resolved = resolver.resolve(ticker="TEST", start_date="2026-01-01", as_of=boundary, effective_as_of=boundary)

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
    metrics = compute_momentum_metrics(
        df=pd.DataFrame({"Close": [10.0, 11.0, 12.0]}),
        config=MomentumConfig(short_window=2, long_window=5, rsi_period=4),
        ticker="SHORT",
        timestamp=datetime(2026, 1, 20, tzinfo=UTC),
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


def test_first_valid_long_window_does_not_invent_a_crossover() -> None:
    """An event needs a prior valid pair even when today's trend is known."""
    metrics = compute_momentum_metrics(
        df=pd.DataFrame({"Close": [1.0, 2.0, 3.0]}),
        config=MomentumConfig(short_window=2, long_window=3, rsi_period=2),
        ticker="ACME",
        timestamp=datetime(2026, 1, 20, tzinfo=UTC),
    )
    assert metrics.short_sma_val == 2.5
    assert metrics.long_sma_val == 2.0
    assert metrics.crossover_signal is None


@pytest.mark.parametrize("invalid", [float("nan"), float("inf")])
def test_run_analysis_rejects_invalid_values_outside_latest_windows(invalid: float) -> None:
    """run_analysis's re-check must still catch a concealed invalid observation.

    compute_momentum_metrics is now pure and trusts its input; only run_analysis's
    re-check protects against an invalid observation that rolling-window
    arithmetic would otherwise conceal outside the latest windows.
    """
    frame = pd.DataFrame(
        {"Close": [invalid, 2.0, 3.0, 4.0]},
        index=pd.date_range("2026-01-01", periods=4, tz=UTC),
    )
    analysis_settings = {"default": {"default_ticker": "ACME", "data_start_date": "2026-01-01"}}
    momentum_settings = {"window_sizes": {"short_window": 2, "long_window": 3}}
    context = AnalysisContext(as_of=None, executed_at=datetime(2026, 1, 5, tzinfo=UTC), use_cache=True)
    with (
        patch("src.config.ProjectSettings.get_analysis_settings", return_value=analysis_settings),
        patch("src.config.ProjectSettings.get_momentum_analysis", return_value=momentum_settings),
    ):
        analyzer = MomentumAnalyzer(market_data_provider=FixtureMarketDataProvider(frame))
        with pytest.raises(HistoricalDataQualityError, match="finite"):
            analyzer.run_analysis(
                ticker="ACME",
                config=MomentumConfig(short_window=2, long_window=3, rsi_period=2),
                context=context,
            )
