"""Semantic tests for investor-facing Momentum presentation."""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime

from src.analysis.momentum.momentum_analyzer import MomentumConfig, MomentumMetrics
from src.core.constants import TrendStatus
from src.data.market_data import MarketDataContext
from src.reporting.momentum import MomentumPresentation, render_momentum
from src.reporting.presentation import PresentationMode

NOW = datetime(2026, 8, 22, 4, 0, tzinfo=UTC)
DATA_AS_OF = date(2026, 8, 21)


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
    context = MarketDataContext(
        provider_id="fixture_market_data",
        observation_interval="1d",
        data_as_of=DATA_AS_OF,
        currency="USD",
        observation_count=500,
        price_adjustment="adjusted",
    )
    return MomentumPresentation(
        metrics=metrics,
        config=MomentumConfig(short_window=20, long_window=50),
        market_data=context,
    )


def test_momentum_concise_surfaces_investor_useful_values_and_context() -> None:
    rendered = render_momentum(_presentation())

    assert "Bullish Trend" in rendered
    assert "Price used (adjusted Close): 225.00 USD" in rendered
    assert "20-day SMA: 220.00 USD" in rendered
    assert "50-day SMA: 210.00 USD" in rendered
    assert "SMA spread: 10.00 USD (4.76%)" in rendered
    assert "20-day SMA is above the 50-day SMA" in rendered
    assert "bullish crossover" in rendered
    assert "Data: fixture_market_data · daily · through 2026-08-21" in rendered
    assert "Raw crossover signal" not in rendered
    assert "not a valuation" in rendered


def test_momentum_details_add_context_without_repeating_raw_signal() -> None:
    rendered = render_momentum(_presentation(), PresentationMode.DETAILS)

    assert "Method: simple moving-average crossover" in rendered
    assert "Configured windows: 20 / 50 daily observations" in rendered
    assert "Price basis: latest adjusted historical Close value" in rendered
    assert "Data provider: fixture_market_data" in rendered
    assert "Data interval: 1d (daily)" in rendered
    assert "Latest data observation: 2026-08-21" in rendered
    assert "Observations returned: 500" in rendered
    assert "Raw crossover signal" not in rendered


def test_momentum_diagnostics_expose_retained_raw_and_market_context() -> None:
    rendered = render_momentum(_presentation(), PresentationMode.DIAGNOSTICS)

    assert "Raw crossover signal: 1" in rendered
    assert "Trend relationship: short_above_long" in rendered
    assert "provider=fixture_market_data" in rendered
    assert "interval=1d" in rendered
    assert "observations=500" in rendered
    assert "adjustment=adjusted" in rendered


def test_momentum_json_adds_semantic_fields_without_removing_schema_one_fields() -> None:
    payload = json.loads(render_momentum(_presentation(), PresentationMode.JSON))

    assert payload["schema_version"] == 1
    assert payload["analysis"] == "momentum"
    assert payload["method"] == "sma_crossover"
    assert payload["as_of"] == DATA_AS_OF.isoformat()
    assert payload["analysis_timestamp"] == NOW.isoformat()
    assert payload["status"] == "BULLISH"
    assert payload["result"]["current_price"] == 225.0
    assert payload["result"]["price_basis"] == "latest_adjusted_historical_close"
    assert payload["result"]["crossover_signal"] == 1.0
    assert payload["result"]["crossover_state"] == "bullish_crossover"
    assert payload["result"]["trend_relationship"] == "short_above_long"
    assert payload["result"]["sma_spread"] == 10.0
    assert payload["source"]["provider"] == "fixture_market_data"
    assert payload["source"]["interval"] == "1d"
    assert payload["source"]["observation_count"] == 500
    assert payload["source"]["currency"] == "USD"
    assert payload["source"]["price_adjustment"] == "adjusted"


def test_momentum_missing_source_metadata_is_compact_not_repeated_as_warnings() -> None:
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

    assert "Price used (Close): 200.00 (currency unspecified)" in rendered
    assert "20-observation SMA is below the 50-observation SMA" in rendered
    assert "Data: provider unavailable · interval unavailable · observation date unavailable" in rendered
    assert "metadata is incomplete" not in rendered
    assert "currency is not retained" not in rendered
    assert NOW.isoformat() not in rendered


def test_momentum_json_keeps_unknown_data_date_separate_from_analysis_timestamp() -> None:
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
    assert payload["result"]["crossover_state"] == "no_new_crossover"
    assert payload["result"]["trend_relationship"] == "short_below_long"


def test_momentum_equal_smas_are_reported_as_equal_not_below() -> None:
    metrics = MomentumMetrics(
        ticker="FLAT",
        status=TrendStatus.BEARISH,
        current_price=100.0,
        short_sma_val=100.0,
        long_sma_val=100.0,
        crossover_signal=0.0,
        timestamp=NOW,
    )
    presentation = MomentumPresentation(
        metrics=metrics,
        config=MomentumConfig(short_window=20, long_window=50),
    )

    concise = render_momentum(presentation)
    payload = json.loads(render_momentum(presentation, PresentationMode.JSON))

    assert "20-observation SMA is equal to the 50-observation SMA" in concise
    assert "classified as bearish" in concise
    assert payload["result"]["trend_relationship"] == "short_equal_long"


def test_momentum_insufficient_history_names_both_unmet_sma_requirements() -> None:
    metrics = MomentumMetrics(
        ticker="NEW",
        status=TrendStatus.UNKNOWN,
        current_price=15.0,
        short_sma_val=None,
        long_sma_val=None,
        crossover_signal=None,
        timestamp=NOW,
    )
    context = MarketDataContext(
        provider_id="fixture_market_data",
        observation_interval="1d",
        data_as_of=DATA_AS_OF,
        currency="USD",
        observation_count=3,
    )
    presentation = MomentumPresentation(
        metrics=metrics,
        config=MomentumConfig(short_window=50, long_window=200),
        market_data=context,
    )

    concise = render_momentum(presentation)

    assert "3 observations available; 50 required for the short SMA and 200 required for the long SMA." in concise


def test_momentum_unavailable_sma_explains_insufficient_history_without_nan() -> None:
    metrics = MomentumMetrics(
        ticker="SHORT",
        status=TrendStatus.UNKNOWN,
        current_price=12.0,
        short_sma_val=11.5,
        long_sma_val=None,
        crossover_signal=None,
        timestamp=NOW,
    )
    context = MarketDataContext(
        provider_id="fixture_market_data",
        observation_interval="1d",
        data_as_of=DATA_AS_OF,
        currency="USD",
        observation_count=3,
    )
    presentation = MomentumPresentation(
        metrics=metrics,
        config=MomentumConfig(short_window=2, long_window=5),
        market_data=context,
    )

    concise = render_momentum(presentation)
    details = render_momentum(presentation, PresentationMode.DETAILS)
    payload = json.loads(render_momentum(presentation, PresentationMode.JSON))

    assert re.search(r"\bnan\b", concise, flags=re.IGNORECASE) is None
    assert re.search(r"\bnan\b", details, flags=re.IGNORECASE) is None
    assert "2-day SMA: 11.50 USD" in concise
    assert "5-day SMA: unavailable" in concise
    assert "insufficient history" in concise.lower()
    assert "3 observations available; 5 required" in concise
    assert payload["result"]["long_sma"] is None
    assert payload["result"]["crossover_signal"] is None
    assert payload["result"]["crossover_state"] is None
    assert payload["result"]["trend_relationship"] is None
