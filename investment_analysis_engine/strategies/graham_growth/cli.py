"""Graham Growth's CLI-layer functions: the direct command and the watchlist selection builder.

The CLI tier pairs these with the Graham Growth core bundle and adds the command to the application; nothing here
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
from investment_analysis_engine.core.operator_errors import InvalidParameterError
from investment_analysis_engine.strategies.graham_growth.selection import GrahamGrowthSelection


def build_selection(flags: WatchlistFlags) -> GrahamGrowthSelection:
    """Build one validated Graham Growth selection from watchlist CLI flags.

    Mirrors the direct ``graham-growth`` command's own flags and validation exactly, so a watchlist entry
    behaves identically to running the method directly.
    """
    boundary = parse_as_of(flags.as_of)
    with config_usage_errors():
        if flags.expected_growth is None:
            raise InvalidParameterError(
                "--expected-growth is required when --analysis is graham-growth.", parameters=("--expected-growth",)
            )
        if flags.aaa_yield is None:
            raise InvalidParameterError(
                "--aaa-yield is required when --analysis is graham-growth.", parameters=("--aaa-yield",)
            )
        return GrahamGrowthSelection.model_validate(
            {
                "eps_basis": flags.eps_basis,
                "eps_override": flags.eps,
                "quote_override": flags.current_price,
                "as_of": boundary,
                "use_cache": not flags.no_cache,
                "expected_growth": flags.expected_growth,
                "aaa_yield_override": flags.aaa_yield,
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
    eps_basis: str | None = typer.Option(
        None,
        "--eps-basis",
        help=(
            "EPS basis; defaults to three_year_average (also accepts an explicit "
            "fiscal_year basis for reviewed workflows)"
        ),
    ),
    expected_growth: float = typer.Option(
        ...,
        "--expected-growth",
        "--expected-growth-rate",
        "-g",
        help="Expected annual growth in percentage points (growth method; explicit user assumption)",
    ),
    aaa_yield: float = typer.Option(
        ...,
        "--aaa-yield",
        "--current-aaa-yield",
        "-y",
        help="Current AAA corporate-bond yield in percentage points (growth method override)",
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
    """Execute Graham Growth Value with explicit growth and AAA-yield assumptions."""
    use_cache = not no_cache
    provider_check = provider_check_choice(context, no_provider_check=no_provider_check)
    with execution_errors(
        json_output=json_output,
        selection_type=GrahamGrowthSelection,
        provider_check=provider_check,
    ) as scope:
        target_ticker, mode = resolve_command_target(
            scope,
            ticker,
            ticker_option,
            command="graham-growth",
            details=details,
            diagnostics=diagnostics,
            json_output=json_output,
        )
        boundary = parse_as_of(as_of)
        with config_usage_errors():
            selection = GrahamGrowthSelection.model_validate(
                {
                    "eps_basis": eps_basis,
                    "eps_override": eps,
                    "quote_override": current_price,
                    "expected_growth": expected_growth,
                    "aaa_yield_override": aaa_yield,
                    "as_of": boundary,
                    "use_cache": use_cache,
                }
            )
        outcome = analyze_for_command(target_ticker, selection, save_run=save_run, provider_check=provider_check)
        output, exit_code = analysis_output(outcome, mode)
    emit_output(output, exit_code, mode)
