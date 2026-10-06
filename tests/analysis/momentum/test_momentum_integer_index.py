"""Characterizes what the production path does with a historical frame that has no datetime index.

Nothing between the provider and the Momentum resolver rejects such a frame: the shared quality rule
reports ``INSUFFICIENT_EVIDENCE`` for it, and only ``FAIL`` stops a run. This test pins that behavior so
a later decision to reject (or to keep accepting) is made deliberately.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.analysis.base_analyzer import AnalysisContext
from src.data.market_data import HistoricalMarketData, MarketDataContext
from src.data.quality import QualityContext, QualityOutcome, evaluate_historical_quality
from src.strategies.momentum.analyzer import MomentumAnalyzer, MomentumConfig

EXECUTED_AT = datetime(2026, 9, 1, tzinfo=UTC)
CLOSES = [100.0, 101.0, 102.0, 103.0, 104.0]


def _integer_indexed() -> HistoricalMarketData:
    frame = pd.DataFrame({"Close": CLOSES})
    return HistoricalMarketData(
        frame,
        MarketDataContext(provider_id="fixture", observation_interval="1d", currency="USD", observation_count=5),
    )


def test_integer_indexed_frame_is_accepted_and_its_positions_become_epoch_nanoseconds() -> None:
    provider = MagicMock()
    provider.fetch_historical_data.return_value = _integer_indexed()
    analyzer = MomentumAnalyzer(market_data_provider=provider, start_date="2026-01-01")
    context = AnalysisContext(as_of=None, executed_at=EXECUTED_AT, use_cache=True)

    with pytest.warns(UserWarning, match="Discarding nonzero nanoseconds"):
        run = analyzer.run_analysis("ACME", MomentumConfig(short_window=2, long_window=3, rsi_period=3), context)

    assert [item.observed_at for item in run.price_inputs] == [datetime(1970, 1, 1, tzinfo=UTC)] * 5
    assert run.market_data.data_as_of == datetime(1970, 1, 1, tzinfo=UTC).date()
    assert len(run.price_inputs) == 5


def test_quality_reports_insufficient_evidence_not_failure_for_an_integer_index() -> None:
    decisions = evaluate_historical_quality(
        _integer_indexed(), context=QualityContext("ACME:historical_close", EXECUTED_AT, None)
    )
    by_rule = {decision.rule_id: decision.outcome for decision in decisions}

    assert by_rule["historical.index"] is QualityOutcome.INSUFFICIENT_EVIDENCE
    assert QualityOutcome.FAIL not in by_rule.values()
