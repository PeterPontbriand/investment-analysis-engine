"""The Piotroski F-Score strategy's CLI functions.

They are the direct command and the selection builder. The command parses its options, builds the selection and calls
the direct-analysis operation.
"""

import typer

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
from investment_analysis_engine.strategies.piotroski.selection import PiotroskiSelection


def build_selection(flags: WatchlistFlags) -> PiotroskiSelection:
    """Build one validated Piotroski F-Score selection.

    It is built from the watchlist flags it concerns: the boundary and the cache choice.
    """
    return PiotroskiSelection(as_of=parse_as_of(flags.as_of), use_cache=not flags.no_cache)


def command(  # noqa: PLR0913
    ticker: str = typer.Argument(..., help="Target stock ticker symbol (e.g., AAPL, KO)"),
    *,
    as_of: str | None = AS_OF_OPTION,
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass the cache"),
    details: bool = typer.Option(False, "--details", help="Show each test's operands with their year-end and value"),
    diagnostics: bool = typer.Option(
        False, "--diagnostics", help="Show where each operand came from and how the inputs were assembled"
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit the complete versioned typed result"),
    save_run: bool = SAVE_RUN_OPTION,
    no_provider_check: bool = NO_PROVIDER_CHECK_OPTION,
) -> None:
    """Run the Piotroski F-Score analysis."""
    provider_check = not no_provider_check

    with execution_errors(json_output=json_output, selection_type=PiotroskiSelection) as scope:
        target_ticker, mode = resolve_command_target(
            scope, ticker, None, command="piotroski", details=details, diagnostics=diagnostics, json_output=json_output
        )
        selection = PiotroskiSelection(as_of=parse_as_of(as_of), use_cache=not no_cache)
        outcome = analyze_for_command(target_ticker, selection, save_run=save_run, provider_check=provider_check)
        output, exit_code = analysis_output(outcome, mode)
    emit_output(output, exit_code, mode)
