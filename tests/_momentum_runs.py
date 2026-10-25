"""Assertions shared by the Momentum tests about a run in which no calculation ran."""

from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.data.market_data import MarketDataContext
from investment_analysis_engine.strategies.momentum.analyzer import MomentumRun


def assert_not_calculated(
    run: MomentumRun,
    status: CalculationStatus,
    *,
    code: ReasonCode | None,
    reason_contains: str | None = None,
) -> None:
    """Require a run with the given status and code, no metrics and a non-empty reason that keeps its trace."""
    assert run.execution_status is status
    assert run.reason_code is code
    assert run.metrics is None
    assert run.reason
    if reason_contains is not None:
        assert reason_contains in run.reason
    assert run.resolution_trace.events, "A run without metrics keeps the trace that led to it."


def assert_no_series_resolved(run: MomentumRun) -> None:
    """Require the empty context and no price inputs, as for a run whose series never resolved."""
    assert run.market_data == MarketDataContext()
    assert run.price_inputs == ()
    assert run.data_resolution is None
