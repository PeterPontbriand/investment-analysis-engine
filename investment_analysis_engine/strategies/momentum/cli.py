"""Momentum's CLI-layer functions: the direct command and the watchlist selection builder.

The CLI tier pairs these with the Momentum core bundle and adds the command to the application; nothing here
registers itself. The command parses its options, builds the selection and calls the direct-analysis operation.
"""

import typer

from investment_analysis_engine.analysis.base_analyzer import require_ticker
from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.cli_support import (
    AS_OF_OPTION,
    NO_PROVIDER_CHECK_OPTION,
    SAVE_RUN_OPTION,
    analysis_output,
    analyze_for_command,
    emit_output,
    execution_errors,
    parse_as_of,
    resolve_command_target,
)
from investment_analysis_engine.cli_watchlist_flags import WatchlistFlags
from investment_analysis_engine.config import settings
from investment_analysis_engine.core.operator_errors import InvalidParameterError
from investment_analysis_engine.strategies.momentum.application import momentum_settings
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection


def _validate_momentum_windows(short_window: int, long_window: int, rsi_period: int) -> None:
    """Reject invalid SMA/RSI periods with investor-readable domain language.

    The direct command and the watchlist builder share this check, so both report the same
    ``invalid_parameter`` failure with the same message, which names the offending option. The option
    names are the ones both commands declare; this function, not generic tooling, supplies them.
    """
    if short_window <= 0:
        raise InvalidParameterError(
            f"Invalid momentum window: --short-window must be positive (received {short_window}).",
            parameters=("--short-window",),
        )
    if long_window <= 0:
        raise InvalidParameterError(
            f"Invalid momentum window: --long-window must be positive (received {long_window}).",
            parameters=("--long-window",),
        )
    if rsi_period <= 0:
        raise InvalidParameterError(
            f"Invalid momentum period: --rsi-period must be positive (received {rsi_period}).",
            parameters=("--rsi-period",),
        )
    if short_window >= long_window:
        raise InvalidParameterError(
            f"Invalid momentum windows: --short-window ({short_window}) "
            f"must be smaller than --long-window ({long_window}).",
            parameters=("--short-window", "--long-window"),
        )


def build_selection(flags: WatchlistFlags) -> MomentumSelection:
    """Build one validated Momentum selection from watchlist CLI flags.

    Mirrors the direct ``momentum`` command's own flags and validation exactly, so a watchlist entry behaves
    identically to running the method directly.
    """
    _validate_momentum_windows(flags.short_window, flags.long_window, flags.rsi_period)
    return MomentumSelection(
        short_window=flags.short_window,
        long_window=flags.long_window,
        rsi_period=flags.rsi_period,
        as_of=parse_as_of(flags.as_of),
        use_cache=not flags.no_cache,
    )


_MOMENTUM_CLI_DEFAULTS = momentum_settings(ApplicationContext(settings=settings))


def command(  # noqa: PLR0913
    ticker: str | None = typer.Argument(None, help="Target stock/asset ticker symbol (e.g., AAPL, BTC-USD)"),
    *,
    ticker_option: str | None = typer.Option(
        None,
        "--ticker",
        "-t",
        help="Legacy ticker option; prefer the positional TICKER argument",
    ),
    short_window: int = typer.Option(
        _MOMENTUM_CLI_DEFAULTS.short_window,
        "--short-window",
        "-s",
        help="Short SMA window in daily market observations",
    ),
    long_window: int = typer.Option(
        _MOMENTUM_CLI_DEFAULTS.long_window,
        "--long-window",
        "-l",
        help="Long SMA window in daily market observations",
    ),
    rsi_period: int = typer.Option(
        _MOMENTUM_CLI_DEFAULTS.rsi_period,
        "--rsi-period",
        help="RSI lookback period in daily market observations",
    ),
    as_of: str | None = AS_OF_OPTION,
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass historical price cache reads and writes"),
    details: bool = typer.Option(False, "--details", help="Show calculation and data-context details"),
    diagnostics: bool = typer.Option(False, "--diagnostics", help="Show retained execution diagnostics"),
    json_output: bool = typer.Option(False, "--json", help="Emit stable machine-readable JSON"),
    save_run: bool = SAVE_RUN_OPTION,
    no_provider_check: bool = NO_PROVIDER_CHECK_OPTION,
) -> None:
    """Execute SMA crossover momentum analysis over daily historical market prices."""
    provider_check = not no_provider_check
    with execution_errors(
        json_output=json_output,
        selection_type=MomentumSelection,
    ) as scope:
        requested_ticker, mode = resolve_command_target(
            scope,
            ticker,
            ticker_option,
            command="momentum",
            details=details,
            diagnostics=diagnostics,
            json_output=json_output,
        )
        _validate_momentum_windows(short_window, long_window, rsi_period)
        boundary = parse_as_of(as_of)
        target_ticker = require_ticker(requested_ticker)
        selection = MomentumSelection(
            short_window=short_window,
            long_window=long_window,
            rsi_period=rsi_period,
            as_of=boundary,
            use_cache=not no_cache,
        )
        outcome = analyze_for_command(target_ticker, selection, save_run=save_run, provider_check=provider_check)
        output, exit_code = analysis_output(outcome, mode)
        emit_output(output, exit_code, mode)
