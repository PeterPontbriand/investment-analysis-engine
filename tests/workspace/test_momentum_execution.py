"""Focused tests for the Momentum execution adapter, using fake dependencies only."""

import socket
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from src.analysis.strategy.momentum.momentum_analyzer import (
    MomentumAnalyzer,
    MomentumConfig,
    MomentumMetrics,
    MomentumRun,
)
from src.core.constants import TrendStatus
from src.data.instrument_profile import InstrumentKind, InstrumentProfile
from src.data.market_data import MarketDataContext
from src.evaluation.fixtures.instrument_profiles import fixture_instrument_profile
from src.evaluation.fixtures.market_data import FixtureDataClient
from src.reporting.momentum import _sma_spread, _sma_spread_percent
from src.workspace.momentum_execution import capture_momentum, run_momentum
from src.workspace.requests import MomentumSelection

STAMP = datetime(2026, 9, 18, 12, tzinfo=UTC)


class _FixtureClient(FixtureDataClient):
    """FixtureDataClient with a stable provider identity for the full resolver path."""

    @property
    def provider_id(self) -> str:
        return "fixture"


@pytest.fixture(autouse=True)
def mock_settings_config() -> Generator[None, None, None]:
    """Stub out configured analysis defaults; the adapter's tests supply their own."""
    mock_analysis = {"default": {"default_ticker": "BTC-USD", "data_start_date": "2026-01-01"}}
    with patch("src.config.ProjectSettings.get_analysis_settings", return_value=mock_analysis):
        yield


def _selection() -> MomentumSelection:
    return MomentumSelection(short_window=2, long_window=3, rsi_period=2)


def _profile(ticker: str) -> InstrumentProfile:
    return fixture_instrument_profile(ticker, kind=InstrumentKind.EQUITY, provider_value="EQUITY")


def test_run_momentum_delegates_to_the_existing_analyzer_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prove the extraction is a faithful delegation, not a reimplementation."""
    client = _FixtureClient()
    selection = _selection()
    canned = MomentumRun(metrics=_metrics(short=1.0, long=2.0), market_data=MarketDataContext())
    captured: dict[str, object] = {}

    def fake_run_with_context(
        self: MomentumAnalyzer, *, config: MomentumConfig, ticker: str | None = None, as_of: datetime | None = None
    ) -> MomentumRun:
        del as_of
        captured["data_client_is_ours"] = self.data_client is client
        captured["config"] = config
        captured["ticker"] = ticker
        return canned

    monkeypatch.setattr(MomentumAnalyzer, "run_with_context", fake_run_with_context)

    result = run_momentum(selection, "AAPL", client)

    assert result is canned
    assert captured == {
        "data_client_is_ours": True,
        "config": selection.to_momentum_config(),
        "ticker": "AAPL",
    }


def test_run_momentum_computes_real_sma_values_from_the_fixture_series() -> None:
    """Exercise the real analyzer math against a known deterministic series."""
    client = _FixtureClient()
    run = run_momentum(_selection(), "AAPL", client)

    closes = [100.0 * (1.01**i) for i in range(5)]
    expected_short = sum(closes[-2:]) / 2
    expected_long = sum(closes[-3:]) / 3

    assert run.metrics.ticker == "AAPL"
    assert run.metrics.short_sma_val == pytest.approx(expected_short)
    assert run.metrics.long_sma_val == pytest.approx(expected_long)


def test_run_momentum_falls_back_to_configured_default_ticker_when_none() -> None:
    client = _FixtureClient()
    run = run_momentum(_selection(), None, client)
    assert run.metrics.ticker == "BTC-USD"


def test_capture_momentum_computes_spread_and_percent_matching_reporting() -> None:
    client = _FixtureClient()
    run = run_momentum(_selection(), "AAPL", client)
    profile = _profile("AAPL")

    capture = capture_momentum(run, profile)

    assert capture.run is run
    assert capture.profile is profile
    assert capture.presentation_inputs["sma_spread"] == _sma_spread(run.metrics)
    assert capture.presentation_inputs["sma_spread_percent"] == _sma_spread_percent(run.metrics)
    assert run.metrics.short_sma_val is not None
    assert run.metrics.long_sma_val is not None
    assert capture.presentation_inputs["sma_spread"] == run.metrics.short_sma_val - run.metrics.long_sma_val


def _metrics(*, short: float | None, long: float | None) -> MomentumMetrics:
    return MomentumMetrics(
        ticker="AAPL",
        status=TrendStatus.UNKNOWN,
        current_price=100.0,
        short_sma_val=short,
        long_sma_val=long,
        crossover_signal=None,
        timestamp=STAMP,
    )


def test_capture_momentum_leaves_presentation_inputs_null_when_smas_unavailable() -> None:
    run = MomentumRun(metrics=_metrics(short=None, long=None), market_data=MarketDataContext())
    capture = capture_momentum(run, None)
    assert capture.presentation_inputs == {"sma_spread": None, "sma_spread_percent": None}
    assert capture.profile is None


def test_capture_momentum_guards_a_zero_long_sma() -> None:
    run = MomentumRun(metrics=_metrics(short=1.0, long=0.0), market_data=MarketDataContext())
    capture = capture_momentum(run, None)
    assert capture.presentation_inputs["sma_spread"] == 1.0
    assert capture.presentation_inputs["sma_spread_percent"] is None


def test_no_network_access(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Momentum execution adapter must not access the network.")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket.socket, "connect", reject_network)

    client = _FixtureClient()
    run = run_momentum(_selection(), "AAPL", client)
    capture = capture_momentum(run, _profile("AAPL"))
    assert capture.run.metrics.ticker == "AAPL"
