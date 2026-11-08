"""Momentum's CLI-layer functions: the direct command and the watchlist ``add-selection`` command.

The CLI tier pairs these with the Momentum core bundle and adds both commands to the application; nothing here
registers itself. Both commands declare the same selection options, build their selection through the same option
table, and the direct command then calls the direct-analysis operation.

The three window and period options default to the strategy's settings: when one is left out, the selection's builder
fills it in from the user's settings file, or from the shipped one.
"""

from typing import Annotated

import typer

from investment_analysis_engine.cli_support import (
    AS_OF_OPTION,
    NO_PROVIDER_CHECK_OPTION,
    SAVE_RUN_OPTION,
    SelectionOption,
    add_selection_entries,
    analysis_output,
    analyze_for_command,
    cache_enabled,
    emit_output,
    execution_errors,
    parameter_failures,
    parse_as_of_option,
    resolve_command_target,
    selection_from_options,
)
from investment_analysis_engine.config import settings
from investment_analysis_engine.config.component_settings import load_component_settings
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.strategies.momentum.settings import MomentumSettings
from investment_analysis_engine.strategies.momentum.vocabulary import METHOD_ID
from investment_analysis_engine.workspace.strategy_types import SelectionMember

_CONFIGURED = load_component_settings("momentum", MomentumSettings, settings.config_dir)
"""The settings in effect, which the help shows; the cached loader the startup check also uses."""


def _from_settings(value: int) -> str:
    """Return the text of the default shown in help for an option that the settings supply."""
    return f"from settings: {value}"


SHORT_WINDOW_OPTION = Annotated[
    int | None,
    typer.Option(
        "--short-window",
        "-s",
        help="Short SMA window in daily market observations",
        show_default=_from_settings(_CONFIGURED.short_window),
    ),
]
LONG_WINDOW_OPTION = Annotated[
    int | None,
    typer.Option(
        "--long-window",
        "-l",
        help="Long SMA window in daily market observations",
        show_default=_from_settings(_CONFIGURED.long_window),
    ),
]
RSI_PERIOD_OPTION = Annotated[
    int | None,
    typer.Option(
        "--rsi-period",
        help="RSI lookback period in daily market observations",
        show_default=_from_settings(_CONFIGURED.rsi_period),
    ),
]
NO_CACHE_OPTION = Annotated[bool, typer.Option("--no-cache", help="Bypass historical price cache reads and writes")]

SELECTION_OPTIONS = (
    SelectionOption("short_window", "short_window", "--short-window"),
    SelectionOption("long_window", "long_window", "--long-window"),
    SelectionOption("rsi_period", "rsi_period", "--rsi-period"),
    SelectionOption("as_of", "as_of", "--as-of", parse_as_of_option),
    SelectionOption("no_cache", "use_cache", "--no-cache", cache_enabled),
)
"""The selection field each selection option sets: this strategy's one table of options and fields."""


def _selection(
    *,
    short_window: int | None,
    long_window: int | None,
    rsi_period: int | None,
    as_of: str | None,
    no_cache: bool,
) -> SelectionMember:
    """Build the Momentum selection from the selection options of either command."""
    return selection_from_options(
        METHOD_ID,
        SELECTION_OPTIONS,
        {
            "short_window": short_window,
            "long_window": long_window,
            "rsi_period": rsi_period,
            "as_of": as_of,
            "no_cache": no_cache,
        },
    )


def command(  # noqa: PLR0913
    ticker: Annotated[str | None, typer.Argument(help="Target stock/asset ticker symbol (e.g., AAPL, BTC-USD)")] = None,
    *,
    ticker_option: Annotated[
        str | None,
        typer.Option("--ticker", "-t", help="Legacy ticker option; prefer the positional TICKER argument"),
    ] = None,
    short_window: SHORT_WINDOW_OPTION = None,
    long_window: LONG_WINDOW_OPTION = None,
    rsi_period: RSI_PERIOD_OPTION = None,
    as_of: AS_OF_OPTION = None,
    no_cache: NO_CACHE_OPTION = False,
    details: Annotated[bool, typer.Option("--details", help="Show calculation and data-context details")] = False,
    diagnostics: Annotated[bool, typer.Option("--diagnostics", help="Show retained execution diagnostics")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Emit stable machine-readable JSON")] = False,
    save_run: SAVE_RUN_OPTION = False,
    no_provider_check: NO_PROVIDER_CHECK_OPTION = False,
) -> None:
    """Execute SMA crossover momentum analysis over daily historical market prices."""
    provider_check = not no_provider_check
    with execution_errors(
        json_output=json_output,
        selection_type=MomentumSelection,
    ) as scope:
        target_ticker, mode = resolve_command_target(
            scope,
            ticker,
            ticker_option,
            command="momentum",
            details=details,
            diagnostics=diagnostics,
            json_output=json_output,
        )
        selection = _selection(
            short_window=short_window,
            long_window=long_window,
            rsi_period=rsi_period,
            as_of=as_of,
            no_cache=no_cache,
        )
        outcome = analyze_for_command(target_ticker, selection, save_run=save_run, provider_check=provider_check)
        output, exit_code = analysis_output(outcome, mode)
        emit_output(output, exit_code, mode)


def add_selection(  # noqa: PLR0913
    name: Annotated[str, typer.Argument(help="Watchlist name.")],
    tickers: Annotated[list[str], typer.Argument(help="Tickers to add this selection for.")],
    *,
    short_window: SHORT_WINDOW_OPTION = None,
    long_window: LONG_WINDOW_OPTION = None,
    rsi_period: RSI_PERIOD_OPTION = None,
    as_of: AS_OF_OPTION = None,
    no_cache: NO_CACHE_OPTION = False,
    json_output: Annotated[bool, typer.Option("--json", help="Emit the updated watchlist document.")] = False,
) -> None:
    """Add one Momentum entry per ticker to an existing watchlist."""
    with parameter_failures(json_output=json_output):
        selection = _selection(
            short_window=short_window,
            long_window=long_window,
            rsi_period=rsi_period,
            as_of=as_of,
            no_cache=no_cache,
        )
    add_selection_entries(name, tickers, selection, json_output=json_output)
