"""Semantic tests for investor-facing Momentum presentation."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.constants import TrendStatus
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind, ProviderFailureRecord
from investment_analysis_engine.data.financial.resolution_trace import (
    ResolutionEvent,
    ResolutionOutcome,
    ResolutionStage,
    ResolutionTrace,
)
from investment_analysis_engine.data.market_data import MarketDataContext
from investment_analysis_engine.reporting.presentation import PresentationMode, ResolutionDiagnostic
from investment_analysis_engine.strategies.momentum.analyzer import MomentumConfig, MomentumMetrics
from investment_analysis_engine.strategies.momentum.envelope import MomentumDocument
from investment_analysis_engine.strategies.momentum.presenter import MomentumPresentation, render_momentum

NOW = datetime(2026, 8, 22, 4, 0, tzinfo=UTC)
DATA_AS_OF = date(2026, 8, 21)


def test_legacy_and_typed_resolution_diagnostics_are_not_duplicated() -> None:
    event = ResolutionEvent("close", ResolutionStage.CACHE, ResolutionOutcome.HIT, "Retained cached history.")
    presentation = replace(
        _presentation(),
        resolution_trace=ResolutionTrace((event,)),
        diagnostics=(ResolutionDiagnostic("close", "cache", "hit", event.message),),
    )
    assert render_momentum(presentation, PresentationMode.DIAGNOSTICS).count(event.message) == 1
    payload = json.loads(render_momentum(presentation, PresentationMode.JSON))
    assert len(payload["diagnostics"]) == 1


def _status_of(metrics: MomentumMetrics) -> CalculationStatus:
    """Return the run status that goes with a trend: ok when known, input_unavailable when unknown."""
    return CalculationStatus.INPUT_UNAVAILABLE if metrics.status is TrendStatus.UNKNOWN else CalculationStatus.OK


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
        ticker=metrics.ticker,
        effective_as_of=metrics.timestamp,
        execution_status=_status_of(metrics),
        metrics=metrics,
        config=MomentumConfig(short_window=20, long_window=50, rsi_period=14),
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


def test_default_call_sites_still_compute_spread_from_metrics() -> None:
    """use_captured_spread defaults to False: every existing caller is unaffected."""
    presentation = _presentation()
    assert presentation.use_captured_spread is False
    assert "SMA spread: 10.00 USD (4.76%)" in render_momentum(presentation)


def test_use_captured_spread_overrides_the_computed_value() -> None:
    """Replay consumes the stored spread instead of recomputing it from metrics.

    The metrics here still imply a spread of 10.00 (220 - 210), but a
    deliberately different captured value is supplied and must win — proving
    this is a substitution, not a coincidental match.
    """
    presentation = replace(
        _presentation(),
        use_captured_spread=True,
        captured_sma_spread=999.0,
        captured_sma_spread_percent=111.0,
    )
    rendered = render_momentum(presentation)
    assert "SMA spread: 999.00 USD (111.00%)" in rendered
    assert "SMA spread: 10.00 USD" not in rendered

    payload = json.loads(render_momentum(presentation, PresentationMode.JSON))
    assert payload["result"]["sma_spread"] == 999.0
    assert payload["result"]["sma_spread_percent"] == 111.0


def test_use_captured_spread_preserves_a_captured_null() -> None:
    """A captured 'unavailable' spread must not fall back to a live computation."""
    presentation = replace(
        _presentation(),
        use_captured_spread=True,
        captured_sma_spread=None,
        captured_sma_spread_percent=None,
    )
    rendered = render_momentum(presentation)
    assert "SMA spread:" not in rendered


def test_momentum_diagnostics_expose_retained_raw_and_market_context() -> None:
    rendered = render_momentum(_presentation(), PresentationMode.DIAGNOSTICS)

    assert "Raw crossover signal: 1" in rendered
    assert "Trend relationship: short_above_long" in rendered
    assert "provider=fixture_market_data" in rendered
    assert "interval=1d" in rendered
    assert "observations=500" in rendered
    assert "adjustment=adjusted" in rendered


def test_momentum_json_adds_semantic_fields_with_identity_schema_version() -> None:
    payload = json.loads(render_momentum(_presentation(), PresentationMode.JSON))

    assert payload["schema_version"] == 10
    assert payload["security_identity"]["instrument_name"] is None
    assert payload["analysis"] == "momentum"
    assert payload["method"] == "sma_crossover"
    assert "as_of" not in payload
    assert payload["source"]["data_as_of"] == DATA_AS_OF.isoformat()
    assert payload["effective_as_of"] == NOW.isoformat()
    assert payload["status"] == "ok"
    assert payload["result"]["trend"] == "BULLISH"
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
        ticker=metrics.ticker,
        effective_as_of=metrics.timestamp,
        execution_status=_status_of(metrics),
        metrics=metrics,
        config=MomentumConfig(short_window=20, long_window=50, rsi_period=14),
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
    presentation = MomentumPresentation(
        ticker=metrics.ticker,
        effective_as_of=metrics.timestamp,
        execution_status=_status_of(metrics),
        metrics=metrics,
        config=MomentumConfig(short_window=20, long_window=50, rsi_period=14),
    )

    payload = json.loads(render_momentum(presentation, PresentationMode.JSON))

    assert "as_of" not in payload
    assert payload["requested_as_of"] is None
    assert payload["effective_as_of"] == NOW.isoformat()
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
        ticker=metrics.ticker,
        effective_as_of=metrics.timestamp,
        execution_status=_status_of(metrics),
        metrics=metrics,
        config=MomentumConfig(short_window=20, long_window=50, rsi_period=14),
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
        ticker=metrics.ticker,
        effective_as_of=metrics.timestamp,
        execution_status=_status_of(metrics),
        metrics=metrics,
        config=MomentumConfig(short_window=50, long_window=200, rsi_period=14),
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
        ticker=metrics.ticker,
        effective_as_of=metrics.timestamp,
        execution_status=_status_of(metrics),
        metrics=metrics,
        config=MomentumConfig(short_window=2, long_window=5, rsi_period=14),
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


def test_momentum_json_carries_the_requested_boundary_apart_from_the_evaluated_instant() -> None:
    """``requested_as_of`` is what the user asked for; ``effective_as_of`` stays the instant the analysis ran at."""
    boundary = NOW - timedelta(days=30)
    metrics = MomentumMetrics(
        ticker="AAPL",
        status=TrendStatus.BEARISH,
        current_price=200.0,
        short_sma_val=190.0,
        long_sma_val=210.0,
        crossover_signal=0.0,
        timestamp=boundary,
    )
    presentation = MomentumPresentation(
        ticker=metrics.ticker,
        effective_as_of=metrics.timestamp,
        execution_status=_status_of(metrics),
        metrics=metrics,
        config=MomentumConfig(short_window=20, long_window=50, rsi_period=14),
        requested_as_of=boundary,
    )

    payload = json.loads(render_momentum(presentation, PresentationMode.JSON))

    assert payload["requested_as_of"] == boundary.isoformat()
    assert payload["effective_as_of"] == boundary.isoformat()
    assert payload["status"] == "ok"
    assert payload["result"]["trend"] == "BEARISH"


# A run in which no calculation ran -----------------------------------------------------------------------------

_NO_CALCULATION_CASES = [
    pytest.param(
        CalculationStatus.INPUT_UNAVAILABLE,
        ReasonCode.NOT_AVAILABLE_AS_OF,
        "No price history is available at or before the requested --as-of boundary.",
        None,
        id="no-observation",
    ),
    pytest.param(
        CalculationStatus.INPUT_UNAVAILABLE,
        None,
        "Close contains non-finite values. Affected observations: Close at 2026-08-03.",
        None,
        id="quality",
    ),
    pytest.param(
        CalculationStatus.PROVIDER_ERROR,
        ReasonCode.PROVIDER_ERROR,
        "Historical prices could not be retrieved from the market-data provider.",
        ProviderFailureRecord(ProviderFailureKind.UNREACHABLE, "yfinance", "historical_close"),
        id="provider-classified",
    ),
    pytest.param(
        CalculationStatus.PROVIDER_ERROR,
        ReasonCode.PROVIDER_ERROR,
        "Historical prices could not be retrieved from the market-data provider.",
        None,
        id="provider-unclassified",
    ),
]


def _no_calculation(
    status: CalculationStatus, code: ReasonCode | None, reason: str, failure: ProviderFailureRecord | None
) -> MomentumPresentation:
    return MomentumPresentation(
        ticker="AAPL",
        effective_as_of=NOW,
        execution_status=status,
        metrics=None,
        config=MomentumConfig(short_window=20, long_window=50, rsi_period=14),
        reason_code=code,
        reason=reason,
        provider_failure=failure,
        resolution_trace=ResolutionTrace(
            (ResolutionEvent("historical_close", ResolutionStage.PROVIDER, ResolutionOutcome.ERROR, "It failed."),)
        ),
    )


@pytest.mark.parametrize(("status", "code", "reason", "failure"), _NO_CALCULATION_CASES)
@pytest.mark.parametrize("mode", list(PresentationMode))
def test_every_mode_renders_a_run_without_metrics(
    status: CalculationStatus,
    code: ReasonCode | None,
    reason: str,
    failure: ProviderFailureRecord | None,
    mode: PresentationMode,
) -> None:
    rendered = render_momentum(_no_calculation(status, code, reason, failure), mode)

    if mode is PresentationMode.JSON:
        document = MomentumDocument.model_validate_json(rendered)
        assert document.status is status
        assert document.result is None
        assert (document.reason_code, document.reason) == (code, reason)
        assert (document.provider_failure is None) is (failure is None)
        assert document.effective_as_of == NOW
        return
    assert "AAPL — Momentum" in rendered
    assert "Momentum could not be calculated." in rendered
    assert f"Reason: {reason}" in rendered
    assert "Price used" not in rendered
    assert "nan" not in rendered.lower()
    if mode is PresentationMode.DIAGNOSTICS:
        assert "historical_close: provider -> error — It failed." in rendered
        assert "Raw crossover signal" not in rendered


def test_a_run_without_metrics_warns_of_nothing_it_did_not_try() -> None:
    presentation = _no_calculation(CalculationStatus.PROVIDER_ERROR, ReasonCode.PROVIDER_ERROR, "Why.", None)

    assert "Warning:" not in render_momentum(presentation)
    assert json.loads(render_momentum(presentation, PresentationMode.JSON))["warnings"] == []


def test_a_known_trend_document_reports_ok_with_no_reason() -> None:
    document = MomentumDocument.model_validate_json(render_momentum(_presentation(), PresentationMode.JSON))

    assert document.status is CalculationStatus.OK
    assert (document.reason, document.reason_code, document.provider_failure) == (None, None, None)
    assert document.result is not None


def test_an_unknown_trend_document_carries_its_result_and_its_status_and_reason() -> None:
    base = _presentation()
    assert base.metrics is not None
    presentation = replace(
        base,
        metrics=replace(base.metrics, status=TrendStatus.UNKNOWN, long_sma_val=None, crossover_signal=None),
        execution_status=CalculationStatus.INPUT_UNAVAILABLE,
        reason_code=ReasonCode.INSUFFICIENT_HISTORY,
        reason="The long moving average requires 50 observations; 40 were available.",
    )

    document = MomentumDocument.model_validate_json(render_momentum(presentation, PresentationMode.JSON))

    assert document.status is CalculationStatus.INPUT_UNAVAILABLE
    assert document.result is not None
    assert document.result.trend is TrendStatus.UNKNOWN
    assert document.reason_code is ReasonCode.INSUFFICIENT_HISTORY
