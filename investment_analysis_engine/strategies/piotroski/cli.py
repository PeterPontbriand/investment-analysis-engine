"""The Piotroski F-Score strategy's CLI functions.

They are the direct command and the watchlist ``add-selection`` command. Both declare the same selection options and
build their selection through the same option table; the direct command then calls the direct-analysis operation.
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
    parse_as_of,
    resolve_command_target,
    selection_from_options,
)
from investment_analysis_engine.strategies.piotroski.selection import PiotroskiSelection
from investment_analysis_engine.strategies.piotroski.vocabulary import METHOD_ID
from investment_analysis_engine.workspace.strategy_types import SelectionMember

NO_CACHE_OPTION = Annotated[bool, typer.Option("--no-cache", help="Bypass the cache")]

SELECTION_OPTIONS = (
    SelectionOption("as_of", "as_of", "--as-of", parse_as_of),
    SelectionOption("no_cache", "use_cache", "--no-cache", cache_enabled),
)
"""The selection field each selection option sets: this strategy's one table of options and fields."""


def _selection(*, as_of: str | None, no_cache: bool) -> SelectionMember:
    """Build the Piotroski F-Score selection from the selection options of either command."""
    return selection_from_options(METHOD_ID, SELECTION_OPTIONS, {"as_of": as_of, "no_cache": no_cache})


def command(  # noqa: PLR0913
    ticker: Annotated[str, typer.Argument(help="Target stock ticker symbol (e.g., AAPL, KO)")],
    *,
    as_of: AS_OF_OPTION = None,
    no_cache: NO_CACHE_OPTION = False,
    details: Annotated[
        bool, typer.Option("--details", help="Show each test's operands with their year-end and value")
    ] = False,
    diagnostics: Annotated[
        bool,
        typer.Option("--diagnostics", help="Show where each operand came from and how the inputs were assembled"),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Emit the complete versioned typed result")] = False,
    save_run: SAVE_RUN_OPTION = False,
    no_provider_check: NO_PROVIDER_CHECK_OPTION = False,
) -> None:
    """Run the Piotroski F-Score analysis."""
    provider_check = not no_provider_check

    with execution_errors(json_output=json_output, selection_type=PiotroskiSelection) as scope:
        target_ticker, mode = resolve_command_target(
            scope, ticker, None, command="piotroski", details=details, diagnostics=diagnostics, json_output=json_output
        )
        selection = _selection(as_of=as_of, no_cache=no_cache)
        outcome = analyze_for_command(target_ticker, selection, save_run=save_run, provider_check=provider_check)
        output, exit_code = analysis_output(outcome, mode)
    emit_output(output, exit_code, mode)


def add_selection(
    name: Annotated[str, typer.Argument(help="Watchlist name.")],
    tickers: Annotated[list[str], typer.Argument(help="Tickers to add this selection for.")],
    *,
    as_of: AS_OF_OPTION = None,
    no_cache: NO_CACHE_OPTION = False,
    json_output: Annotated[bool, typer.Option("--json", help="Emit the updated watchlist document.")] = False,
) -> None:
    """Add one Piotroski F-Score entry per ticker to an existing watchlist."""
    with parameter_failures(json_output=json_output):
        selection = _selection(as_of=as_of, no_cache=no_cache)
    add_selection_entries(name, tickers, selection, json_output=json_output)
