"""Momentum's application functions: its settings and its run function.

The application tier pairs these with the Momentum core bundle; nothing here registers itself. The run function
composes the dependencies of one run, runs it through :func:`execute_momentum`, and returns it with the means to present
it as a document and as text, so a caller never needs Momentum's presentation.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime

from investment_analysis_engine.analysis.base_analyzer import require_ticker
from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.providers import production_historical_client
from investment_analysis_engine.application.strategy_run import StrategyRun
from investment_analysis_engine.config.component_settings import load_component_settings
from investment_analysis_engine.core.provider_check_element import ProviderCheckItem
from investment_analysis_engine.data.instrument_profile import profile_identity_resolution
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.data.market_data import MarketDataProvider
from investment_analysis_engine.data.yfinance.client import YFinanceClient
from investment_analysis_engine.reporting.replay_inputs import TextPresentationMode
from investment_analysis_engine.strategies.momentum.analyzer import MomentumConfig
from investment_analysis_engine.strategies.momentum.presenter import (
    MomentumPresentation,
    build_momentum_document,
    render_momentum,
)
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.strategies.momentum.settings import MomentumSettings
from investment_analysis_engine.strategies.momentum.workspace import execute_momentum, from_momentum_capture
from investment_analysis_engine.strategy_wiring import MOMENTUM


def momentum_settings(context: ApplicationContext) -> MomentumSettings:
    """Return Momentum's validated settings from the context's settings folder, loaded once per folder."""
    return load_component_settings(MOMENTUM.alias, MomentumSettings, context.settings.config_dir)


def _historical_scope(
    context: ApplicationContext, data_client: YFinanceClient, selection: MomentumSelection, executed_at: datetime
) -> Callable[[], AbstractContextManager[MarketDataProvider]]:
    """Return the scope that opens Momentum's historical client over the borrowed Yahoo client for one run."""
    return lambda: production_historical_client(
        context, data_client, use_cache=selection.use_cache, clock=lambda: executed_at
    )


def run(
    context: ApplicationContext,
    ticker: str,
    selection: MomentumSelection,
    /,
    *,
    executed_at: datetime,
    profile_cache: InstrumentProfileResolver | None,
) -> StrategyRun:
    """Run Momentum once with freshly composed, run-scoped dependencies and return it with its presentation.

    Args:
        context: The application context, whose settings give the history start and the cache.
        ticker: The target ticker.
        selection: The validated selection: the windows, the boundary and the cache choice.
        executed_at: The run's own execution clock, distinct from the requested boundary.
        profile_cache: The durable profile cache, or ``None`` to compose the profile live.

    Returns:
        The normalized capture with the document and the text of the run.
    """
    target_ticker = require_ticker(ticker)
    data_client = YFinanceClient()
    capture = execute_momentum(
        selection,
        target_ticker,
        data_client,
        _historical_scope(context, data_client, selection, executed_at),
        start_date=momentum_settings(context).history_start_date.isoformat(),
        executed_at=executed_at,
        profile_cache=profile_cache,
    )
    analysis = capture.run

    def presentation(element: tuple[ProviderCheckItem, ...] | None) -> MomentumPresentation:
        embedded_profile = analysis.instrument_profile
        if embedded_profile is None:
            raise ValueError("Momentum result did not retain the instrument profile it ran with.")
        return MomentumPresentation(
            ticker=analysis.ticker,
            effective_as_of=analysis.effective_as_of,
            execution_status=analysis.execution_status,
            metrics=analysis.metrics,
            config=MomentumConfig(
                short_window=selection.short_window, long_window=selection.long_window, rsi_period=selection.rsi_period
            ),
            reason_code=analysis.reason_code,
            reason=analysis.reason,
            provider_failure=analysis.provider_failure,
            provider_check=element,
            requested_as_of=selection.as_of,
            market_data=analysis.market_data,
            resolution_trace=analysis.resolution_trace,
            data_resolution=analysis.data_resolution,
            identity_resolution=profile_identity_resolution(embedded_profile),
            instrument_profile=embedded_profile,
        )

    def render_text(element: tuple[ProviderCheckItem, ...] | None, mode: TextPresentationMode) -> str:
        return render_momentum(presentation(element), mode)

    return StrategyRun(
        execution=from_momentum_capture(capture),
        document=lambda element: build_momentum_document(presentation(element)),
        render_text=render_text,
    )


__all__ = ["momentum_settings", "run"]
