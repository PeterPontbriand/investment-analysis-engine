"""Momentum's CLI-layer functions: the watchlist selection builder and the refresh executor.

The CLI tier pairs these with the Momentum core bundle; nothing here registers itself.
"""

import typer

from src.analysis.base_analyzer import require_ticker
from src.cli_support import _default_history_start_date, _parse_as_of, _production_historical_client
from src.cli_watchlist_flags import WatchlistFlags
from src.core.clock import utc_now
from src.data.instrument_profile_cache import InstrumentProfileResolver
from src.data.yfinance import YFinanceClient
from src.strategies.momentum.execution import (
    capture_momentum,
    compose_momentum_profile,
    from_momentum_capture,
    run_momentum,
)
from src.strategies.momentum.selection import MomentumSelection
from src.workspace.capture import ExecutionCapture


def _check_momentum_windows(short_window: int, long_window: int, rsi_period: int) -> None:
    """Reject invalid SMA/RSI periods exactly as the direct ``momentum`` command does."""
    if short_window <= 0:
        raise typer.BadParameter(
            f"short window must be positive (received {short_window}).", param_hint="--short-window"
        )
    if long_window <= 0:
        raise typer.BadParameter(f"long window must be positive (received {long_window}).", param_hint="--long-window")
    if rsi_period <= 0:
        raise typer.BadParameter(f"RSI period must be positive (received {rsi_period}).", param_hint="--rsi-period")
    if short_window >= long_window:
        raise typer.BadParameter(f"short window ({short_window}) must be smaller than long window ({long_window}).")


def build_selection(flags: WatchlistFlags) -> MomentumSelection:
    """Build one validated Momentum selection from watchlist CLI flags.

    Mirrors the direct ``momentum`` command's own flags and validation exactly, so a watchlist entry behaves
    identically to running the method directly.
    """
    _check_momentum_windows(flags.short_window, flags.long_window, flags.rsi_period)
    return MomentumSelection(
        short_window=flags.short_window,
        long_window=flags.long_window,
        rsi_period=flags.rsi_period,
        as_of=_parse_as_of(flags.as_of),
        use_cache=not flags.no_cache,
    )


def refresh(
    ticker: str, selection: MomentumSelection, *, profile_cache: InstrumentProfileResolver | None
) -> ExecutionCapture:
    """Execute one Momentum refresh job with freshly composed, job-scoped dependencies."""
    data_client = YFinanceClient()
    executed_at = utc_now()
    normalized_ticker = require_ticker(ticker)
    profile = compose_momentum_profile(normalized_ticker, data_client=data_client, profile_cache=profile_cache)
    with _production_historical_client(
        data_client, use_cache=selection.use_cache, clock=lambda: executed_at
    ) as historical_client:
        run = run_momentum(
            selection,
            normalized_ticker,
            historical_client,
            start_date=_default_history_start_date(),
            executed_at=executed_at,
            instrument_profile=profile,
        )
    return from_momentum_capture(capture_momentum(run))
