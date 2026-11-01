"""Momentum execution adapter: borrow dependencies, call the existing analyzer.

``execute_momentum`` is the one path the direct command, ``--save-run`` and ``refresh`` share, modelled on the other
strategies' ``execute_<name>``: it composes Momentum's own profile, opens the historical client, runs the analyzer and
captures the evidence. It owns no provider, cache, or database lifecycle: the Yahoo client is borrowed, and the
historical client is opened through a scope the caller supplies, because that client wraps the durable cache and is
built in the CLI tier. The analyzer embeds the profile in the returned run; the calling context owns and closes
providers and caches.

The module reports facts only: the run's own result-level status and the provider failure it recorded. A provider
failure is a stored run with the ``provider_error`` status, not an exception, so the automatic provider check reads
it from the capture. ``RunOutcome.from_status`` produces the outcome, and ``ExecutionCapture`` derives it.

Display-derived values that the existing presenter currently computes at
render time (the SMA spread and its percentage) are captured here instead,
using the same formulas, so a future pure replay can consume them without
recomputing financial values from raw metrics. This module does not persist
anything or construct an ``AnalysisRun``; it only captures one execution's
evidence for a later execution service to assemble.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime

from investment_analysis_engine.analysis.run_models import StrictJsonMapping
from investment_analysis_engine.core.failure_classification import provider_failure_of
from investment_analysis_engine.data.instrument_profile import (
    InstrumentProfile,
    InstrumentProfileCandidate,
    compose_instrument_profile,
)
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.data.market_data import MarketDataProvider
from investment_analysis_engine.data.yfinance.client import YFINANCE_PROVIDER_ID
from investment_analysis_engine.strategies.momentum.analyzer import MomentumAnalyzer, MomentumMetrics, MomentumRun
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.workspace.capture import ExecutionCapture


@dataclass(frozen=True)
class MomentumCapture:
    """Captured evidence for one Momentum command execution.

    ``run`` is the unmodified analyzer result (status, metrics when a calculation ran, market data, price
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


def execute_momentum(  # noqa: PLR0913
    selection: MomentumSelection,
    ticker: str,
    data_client: object,
    historical_scope: Callable[[], AbstractContextManager[MarketDataProvider]],
    *,
    start_date: str,
    executed_at: datetime,
    profile_cache: InstrumentProfileResolver | None = None,
) -> MomentumCapture:
    """Compose the profile, open the historical client and run Momentum for ``selection``.

    Args:
        selection: The validated selection: the windows, the boundary and the cache choice.
        ticker: The normalized target ticker.
        data_client: The borrowed Yahoo client, which is both the identity and the kind candidate of the profile.
        historical_scope: Opens the historical client for this run and closes it on exit.
        start_date: The first date of the requested historical series.
        executed_at: The run's own execution clock, a single aware read of "now" taken once by the caller.
        profile_cache: When supplied, resolves the profile through the durable profile cache instead of composing live.

    Returns:
        The captured native run and its display values.
    """
    profile = compose_momentum_profile(ticker, data_client=data_client, profile_cache=profile_cache)
    with historical_scope() as historical_client:
        run = run_momentum(
            selection,
            ticker,
            historical_client,
            start_date=start_date,
            executed_at=executed_at,
            instrument_profile=profile,
        )
    return capture_momentum(run)


def capture_momentum(run: MomentumRun) -> MomentumCapture:
    """Bundle a run with its captured display values, which are null when no calculation ran.

    Args:
        run: The result of :func:`run_momentum`.

    Returns:
        The captured evidence, ready for a later execution service to
        assemble into a stored run.
    """
    metrics = run.metrics
    presentation_inputs: StrictJsonMapping = {
        "sma_spread": None if metrics is None else _sma_spread(metrics),
        "sma_spread_percent": None if metrics is None else _sma_spread_percent(metrics),
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
    """Normalize a Momentum capture: the run's status, its recorded provider failure and its display values."""
    return ExecutionCapture(
        native_evidence=capture.run,
        profile=capture.run.instrument_profile,
        native_status=capture.run.execution_status,
        presentation_inputs=capture.presentation_inputs,
        provider_failure=provider_failure_of((capture.run.provider_failure,)),
    )


__all__ = [
    "MomentumCapture",
    "capture_momentum",
    "compose_momentum_profile",
    "execute_momentum",
    "from_momentum_capture",
    "run_momentum",
]
