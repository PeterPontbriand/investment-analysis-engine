"""Momentum execution adapter: borrow dependencies, call the existing analyzer.

This adapter extracts the analyzer invocation and captured-evidence assembly
formerly inlined in the ``momentum`` command so both the direct
command and a future save/refresh service call identical code. It owns no
provider, cache, or database lifecycle: the historical provider is borrowed,
never constructed or closed here, and instrument-profile composition stays
the caller's responsibility. The caller composes the profile before
calculation and passes it in, and the analyzer embeds it in the returned run;
the calling context owns and closes providers and caches.

Display-derived values that the existing presenter currently computes at
render time (the SMA spread and its percentage) are captured here instead,
using the same formulas, so a future pure replay can consume them without
recomputing financial values from raw metrics. This module does not persist
anything or construct an ``AnalysisRun``; it only captures one execution's
evidence for a later execution service to assemble.
"""

from dataclasses import dataclass
from datetime import datetime

from src.data.financial.providers import YFINANCE_PROVIDER_ID
from src.data.instrument_profile import InstrumentProfile, InstrumentProfileCandidate, compose_instrument_profile
from src.data.instrument_profile_cache import InstrumentProfileResolver
from src.data.market_data import MarketDataProvider
from src.strategies.momentum.analyzer import MomentumAnalyzer, MomentumMetrics, MomentumRun
from src.strategies.momentum.selection import MomentumSelection
from src.workspace.capture import ExecutionCapture
from src.workspace.models import RunOutcome, StrictJsonMapping


@dataclass(frozen=True)
class MomentumCapture:
    """Captured evidence for one Momentum command execution.

    ``run`` is the unmodified analyzer result (metrics, market data, price
    inputs, resolution trace, the instrument profile it was run with, and any
    data resolution it retained). ``presentation_inputs`` holds display-derived values
    (currently only the SMA spread and its percentage) computed once here
    rather than left to be recomputed by every future consumer.
    """

    run: MomentumRun
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


def run_momentum(  # noqa: PLR0913
    selection: MomentumSelection,
    ticker: str,
    market_data_provider: MarketDataProvider,
    *,
    start_date: str,
    executed_at: datetime,
    instrument_profile: InstrumentProfile | None,
) -> MomentumRun:
    """Run Momentum through the existing analyzer with a borrowed market-data provider.

    Args:
        selection: A validated, immutable Momentum configuration snapshot.
        ticker: The ticker to analyze; the analyzer normalizes it.
        market_data_provider: A borrowed provider; not constructed or closed here.
        start_date: The first date of the requested historical series.
        instrument_profile: The instrument profile the caller composed before calculation,
            embedded in the returned run (None when unavailable).
        executed_at: The run's own execution clock, a single aware read of
            "now" taken once by the caller.

    Returns:
        The unmodified native analyzer result.
    """
    analyzer = MomentumAnalyzer(market_data_provider=market_data_provider, start_date=start_date)
    context = selection.to_analysis_context(executed_at=executed_at, instrument_profile=instrument_profile)
    return analyzer.run_analysis(ticker=ticker, config=selection.to_momentum_config(), context=context)


def capture_momentum(run: MomentumRun) -> MomentumCapture:
    """Bundle a completed run with its captured display values.

    Args:
        run: The result of :func:`run_momentum`.

    Returns:
        The captured evidence, ready for a later execution service to
        assemble into a stored run.
    """
    presentation_inputs: StrictJsonMapping = {
        "sma_spread": _sma_spread(run.metrics),
        "sma_spread_percent": _sma_spread_percent(run.metrics),
    }
    return MomentumCapture(run=run, presentation_inputs=presentation_inputs)


def compose_momentum_profile(
    ticker: str,
    *,
    data_client: object,
    profile_cache: InstrumentProfileResolver | None = None,
) -> InstrumentProfile:
    """Compose Momentum's current instrument profile from its one market-data client.

    The client is both the identity candidate and the kind candidate. ``profile_cache``, when supplied,
    resolves through the durable cache instead of composing live; candidate construction is identical
    either way.
    """
    identity_candidate = InstrumentProfileCandidate(YFINANCE_PROVIDER_ID, data_client)
    kind_candidate = InstrumentProfileCandidate(YFINANCE_PROVIDER_ID, data_client)
    if profile_cache is not None:
        return profile_cache.resolve(ticker, identity_candidates=(identity_candidate,), kind_candidate=kind_candidate)
    return compose_instrument_profile(ticker, identity_candidates=(identity_candidate,), kind_candidate=kind_candidate)


def from_momentum_capture(capture: MomentumCapture) -> ExecutionCapture:
    """Normalize a Momentum capture; Momentum has no native failure status."""
    return ExecutionCapture(
        native_evidence=capture.run,
        profile=capture.run.instrument_profile,
        outcome=RunOutcome.COMPLETED,
        presentation_inputs=capture.presentation_inputs,
    )


__all__ = [
    "MomentumCapture",
    "capture_momentum",
    "compose_momentum_profile",
    "from_momentum_capture",
    "run_momentum",
]
