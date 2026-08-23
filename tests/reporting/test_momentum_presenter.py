"""Semantic tests for investor-facing Momentum presentation."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from src.analysis.momentum.momentum_analyzer import MomentumConfig, MomentumMetrics
from src.core.constants import TrendStatus
from src.reporting.momentum import MomentumPresentation, render_momentum
from src.reporting.presentation import PresentationMode

NOW = datetime(2026, 8, 22, 4, 0, tzinfo=UTC)
DATA_AS_OF = datetime(2026, 8, 21, 20, 0, tzinfo=UTC)


def _presentation() -> MomentumPresentation:
    metrics = MomentumMetrics(
        ticker="AAPL",
        status=TrendStatus.BULLISH,
        current_price=225.0,
        short_sma_val=220.0,
        long_sma_val=210.0,
        crossover_signal=1.0,
        timestamp=NOW,
    )
    return MomentumPresentation(
        metrics=metrics,
        config=MomentumConfig(short_window=20, long_window=50),
        source_label="fixture_market_data",
        data_as_of=DATA_AS_OF,
        currency="USD",
    )


def test_momentum_concise_uses_investor_language_not_raw_signal_flag() -> None:
    rendered = render_momentum(_presentation())

    assert "Bullish Trend" in rendered
    assert "20-period average is above the 50-period average" in rendered
    assert "new bullish crossover" in rendered
    assert "Raw crossover signal" not in rendered
    assert "1.0" not in rendered
    assert "not a valuation" in rendered


def test_momentum_details_retain_raw_implementation_metric() -> None:
    rendered = render_momentum(_presentation(), PresentationMode.DETAILS)

    assert "Raw crossover signal: 1" in rendered
    assert "Short SMA value: 220.000000" in rendered
    assert "Data source: fixture_market_data" in rendered


def test_momentum_json_has_stable_strategy_specific_shape() -> None:
    payload = json.loads(render_momentum(_presentation(), PresentationMode.JSON))

    assert payload["schema_version"] == 1
    assert payload["analysis"] == "momentum"
    assert payload["method"] == "sma_crossover"
    assert payload["as_of"] == DATA_AS_OF.isoformat()
    assert payload["analysis_timestamp"] == NOW.isoformat()
    assert payload["status"] == "BULLISH"
    assert payload["result"]["crossover_signal"] == 1.0
    assert payload["source"]["provider"] == "fixture_market_data"


def test_momentum_missing_source_metadata_is_reported_not_invented() -> None:
    metrics = MomentumMetrics(
        ticker="AAPL",
        status=TrendStatus.BEARISH,
        current_price=200.0,
        short_sma_val=190.0,
        long_sma_val=210.0,
        crossover_signal=0.0,
        timestamp=NOW,
    )
    presentation = MomentumPresentation(
        metrics=metrics,
        config=MomentumConfig(short_window=20, long_window=50),
    )

    rendered = render_momentum(presentation)

    assert "As of: unavailable" in rendered
    assert NOW.isoformat() not in rendered
    assert "not retained by current Momentum result" in rendered
    assert "metadata is incomplete" in rendered
    assert "currency is not retained" in rendered


def test_momentum_json_keeps_unknown_data_as_of_separate_from_analysis_timestamp() -> None:
    metrics = MomentumMetrics(
        ticker="AAPL",
        status=TrendStatus.BEARISH,
        current_price=200.0,
        short_sma_val=190.0,
        long_sma_val=210.0,
        crossover_signal=0.0,
        timestamp=NOW,
    )
    presentation = MomentumPresentation(metrics=metrics, config=MomentumConfig(short_window=20, long_window=50))

    payload = json.loads(render_momentum(presentation, PresentationMode.JSON))

    assert payload["as_of"] is None
    assert payload["analysis_timestamp"] == NOW.isoformat()
    assert payload["source"]["data_as_of"] is None


def test_momentum_presentation_rejects_naive_data_as_of() -> None:
    metrics = MomentumMetrics(
        ticker="AAPL",
        status=TrendStatus.BULLISH,
        current_price=225.0,
        short_sma_val=220.0,
        long_sma_val=210.0,
        crossover_signal=0.0,
        timestamp=NOW,
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        MomentumPresentation(
            metrics=metrics,
            config=MomentumConfig(short_window=20, long_window=50),
            data_as_of=datetime(2026, 8, 21, 20, 0),
        )


def test_momentum_unavailable_sma_renders_without_nan() -> None:
    metrics = MomentumMetrics(
        ticker="SHORT",
        status=TrendStatus.UNKNOWN,
        current_price=12.0,
        short_sma_val=11.5,
        long_sma_val=None,
        crossover_signal=None,
        timestamp=NOW,
    )
    presentation = MomentumPresentation(
        metrics=metrics,
        config=MomentumConfig(short_window=2, long_window=5),
        source_label="fixture_market_data",
        data_as_of=DATA_AS_OF,
        currency="USD",
    )

    concise = render_momentum(presentation)
    details = render_momentum(presentation, PresentationMode.DETAILS)
    payload = json.loads(render_momentum(presentation, PresentationMode.JSON))

    assert "nan" not in concise.lower()
    assert "nan" not in details.lower()
    assert "Long SMA value: unavailable" in details
    assert "Raw crossover signal: unavailable" in details
    assert payload["result"]["long_sma"] is None
    assert payload["result"]["crossover_signal"] is None
