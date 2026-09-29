"""Momentum execution adapter: borrow dependencies, call the existing analyzer.

This adapter extracts the analyzer invocation and captured-evidence assembly
currently inlined in ``src.cli``'s ``momentum`` command so both the direct
command and a future save/refresh service call identical code. It owns no
provider, cache, or database lifecycle: the historical client is borrowed,
never constructed or closed here, and instrument-profile composition stays
the caller's responsibility (matching the contract: retain the profile
composed by the CLI after calculation, without claiming it was used by the
calculator, and let the calling context own/close providers and caches in
their existing order).

Display-derived values that the existing presenter currently computes at
render time (the SMA spread and its percentage) are captured here instead,
using the same formulas, so a future pure replay can consume them without
recomputing financial values from raw metrics. This module does not persist
anything or construct an ``AnalysisRun``; it only captures one execution's
evidence for a later execution service to assemble.
"""

from dataclasses import dataclass
from datetime import datetime

from src.analysis.strategy.momentum.momentum_analyzer import MomentumAnalyzer, MomentumMetrics, MomentumRun
from src.data.instrument_profile import InstrumentProfile
from src.data.market_data import MarketDataProvider
from src.workspace.models import StrictJsonMapping
from src.workspace.requests import MomentumSelection


@dataclass(frozen=True)
class MomentumCapture:
    """Captured evidence for one Momentum command execution.

    ``run`` is the unmodified analyzer result (metrics, market data, price
    inputs, resolution trace, and any data resolution it retained).
    ``profile`` is the instrument profile composed after calculation, exactly
    as the CLI currently does, without claiming it was used by the
    calculator. ``presentation_inputs`` holds display-derived values
    (currently only the SMA spread and its percentage) computed once here
    rather than left to be recomputed by every future consumer.
    """

    run: MomentumRun
    profile: InstrumentProfile | None
    presentation_inputs: StrictJsonMapping


def _sma_spread(metrics: MomentumMetrics) -> float | None:
    """Return short-minus-long SMA, or None when either SMA is unavailable."""
    if metrics.short_sma_val is None or metrics.long_sma_val is None:
        return None
    return metrics.short_sma_val - metrics.long_sma_val


def _sma_spread_percent(metrics: MomentumMetrics) -> float | None:
    """Return the spread as a percentage of the long SMA, guarding a zero base."""
    spread = _sma_spread(metrics)
    long_sma = metrics.long_sma_val
    if spread is None or long_sma is None or long_sma == 0.0:
        return None
    return (spread / long_sma) * 100.0


def run_momentum(
    selection: MomentumSelection,
    ticker: str,
    market_data_provider: MarketDataProvider,
    *,
    start_date: str,
    executed_at: datetime,
) -> MomentumRun:
    """Run Momentum through the existing analyzer with a borrowed market-data provider.

    Args:
        selection: A validated, immutable Momentum configuration snapshot.
        ticker: The ticker to analyze; the analyzer normalizes it.
        market_data_provider: A borrowed provider; not constructed or closed here.
        start_date: The first date of the requested historical series.
        executed_at: The run's own execution clock, a single aware read of
            "now" taken once by the caller.

    Returns:
        The unmodified native analyzer result.
    """
    analyzer = MomentumAnalyzer(market_data_provider=market_data_provider, start_date=start_date)
    context = selection.to_analysis_context(executed_at=executed_at)
    return analyzer.run_analysis(ticker=ticker, config=selection.to_momentum_config(), context=context)


def capture_momentum(run: MomentumRun, profile: InstrumentProfile | None) -> MomentumCapture:
    """Bundle a completed run with its composed profile and captured display values.

    Args:
        run: The result of :func:`run_momentum`.
        profile: The instrument profile composed by the caller after
            calculation (or None when profile composition is unavailable).

    Returns:
        The captured evidence, ready for a later execution service to
        assemble into a stored run.
    """
    presentation_inputs: StrictJsonMapping = {
        "sma_spread": _sma_spread(run.metrics),
        "sma_spread_percent": _sma_spread_percent(run.metrics),
    }
    return MomentumCapture(run=run, profile=profile, presentation_inputs=presentation_inputs)


__all__ = [
    "MomentumCapture",
    "capture_momentum",
    "run_momentum",
]
