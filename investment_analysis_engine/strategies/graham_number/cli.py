"""Graham Number's CLI-layer functions: the direct command and the watchlist selection builder.

The CLI tier pairs these with the Graham Number core bundle and adds the command to the application; nothing here
registers itself. The command parses its options, builds the selection and calls the direct-analysis operation.
"""

import typer

from investment_analysis_engine.cli_provider_check import provider_check_choice
from investment_analysis_engine.cli_support import (
    AS_OF_OPTION,
    NO_PROVIDER_CHECK_OPTION,
    SAVE_RUN_OPTION,
    analysis_output,
    analyze_for_command,
    config_usage_errors,
    emit_output,
    execution_errors,
    parse_as_of,
    resolve_command_target,
)
from investment_analysis_engine.cli_watchlist_flags import WatchlistFlags
from investment_analysis_engine.strategies.graham_number.selection import GrahamNumberSelection


def build_selection(flags: WatchlistFlags) -> GrahamNumberSelection:
    """Build one validated Graham Number selection from watchlist CLI flags.

    Mirrors the direct ``graham-number`` command's own flags and validation exactly, so a watchlist entry
    behaves identically to running the method directly.
    """
    boundary = parse_as_of(flags.as_of)
    with config_usage_errors():
        return GrahamNumberSelection.model_validate(
            {
                "eps_override": flags.eps,
                "quote_override": flags.current_price,
                "as_of": boundary,
                "use_cache": not flags.no_cache,
                "bvps_override": flags.bvps,
            }
        )


def command(  # noqa: PLR0913
    context: typer.Context,
    ticker: str | None = typer.Argument(None, help="Target stock ticker symbol (e.g., AAPL, KO)"),
    *,
    ticker_option: str | None = typer.Option(
        None,
        "--ticker",
        "-t",
        help="Legacy ticker option; prefer the positional TICKER argument",
    ),
    as_of: str | None = AS_OF_OPTION,
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass resolved-input cache reads and writes"),
    eps: float | None = typer.Option(None, "--eps", "-e", help="Explicit EPS override"),
    bvps: float | None = typer.Option(
        None, "--bvps", help="Explicit book value per common share override (Number only)"
    ),
    current_price: float | None = typer.Option(
        None,
        "--current-price",
        "-p",
        help="Optional explicit current-price override",
    ),
    details: bool = typer.Option(False, "--details", help="Show resolved inputs and financial provenance"),
    diagnostics: bool = typer.Option(False, "--diagnostics", help="Show resolver execution trace"),
    json_output: bool = typer.Option(False, "--json", help="Emit stable machine-readable JSON"),
    save_run: bool = SAVE_RUN_OPTION,
    no_provider_check: bool = NO_PROVIDER_CHECK_OPTION,
) -> None:
    """Execute the Graham Number earnings-and-book-value screen."""
    use_cache = not no_cache
    provider_check = provider_check_choice(context, no_provider_check=no_provider_check)
    with execution_errors(
        json_output=json_output,
        selection_type=GrahamNumberSelection,
        provider_check=provider_check,
    ) as scope:
        target_ticker, mode = resolve_command_target(
            scope,
            ticker,
            ticker_option,
            command="graham-number",
            details=details,
            diagnostics=diagnostics,
            json_output=json_output,
        )
        boundary = parse_as_of(as_of)
        with config_usage_errors():
            selection = GrahamNumberSelection.model_validate(
                {
                    "eps_override": eps,
                    "quote_override": current_price,
                    "bvps_override": bvps,
                    "as_of": boundary,
                    "use_cache": use_cache,
                }
            )
        outcome = analyze_for_command(target_ticker, selection, save_run=save_run, provider_check=provider_check)
        output, exit_code = analysis_output(outcome, mode)
    emit_output(output, exit_code, mode)
