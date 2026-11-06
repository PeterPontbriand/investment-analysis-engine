"""Graham Growth's CLI-layer functions: the direct command and the watchlist ``add-selection`` command.

The CLI tier pairs these with the Graham Growth core bundle and adds both commands to the application; nothing here
registers itself. Both commands declare the same selection options, build their selection through the same option
table, and the direct command then calls the direct-analysis operation.
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
from investment_analysis_engine.strategies.graham_growth.selection import GrahamGrowthSelection
from investment_analysis_engine.strategies.graham_growth.vocabulary import METHOD_ID
from investment_analysis_engine.workspace.strategy_types import SelectionMember

NO_CACHE_OPTION = Annotated[bool, typer.Option("--no-cache", help="Bypass resolved-input cache reads and writes")]
EPS_OPTION = Annotated[float | None, typer.Option("--eps", "-e", help="Explicit EPS override")]
EPS_BASIS_OPTION = Annotated[
    str | None,
    typer.Option(
        "--eps-basis",
        help=(
            "EPS basis; defaults to three_year_average (also accepts an explicit "
            "fiscal_year basis for reviewed workflows)"
        ),
    ),
]
EXPECTED_GROWTH_OPTION = Annotated[
    float,
    typer.Option(
        "--expected-growth",
        "--expected-growth-rate",
        "-g",
        help="Expected annual growth in percentage points (growth method; explicit user assumption)",
    ),
]
AAA_YIELD_OPTION = Annotated[
    float,
    typer.Option(
        "--aaa-yield",
        "--current-aaa-yield",
        "-y",
        help="Current AAA corporate-bond yield in percentage points (growth method override)",
    ),
]
CURRENT_PRICE_OPTION = Annotated[
    float | None, typer.Option("--current-price", "-p", help="Optional explicit current-price override")
]

SELECTION_OPTIONS = (
    SelectionOption("as_of", "as_of", "--as-of", parse_as_of_option),
    SelectionOption("no_cache", "use_cache", "--no-cache", cache_enabled),
    SelectionOption("eps", "eps_override", "--eps"),
    SelectionOption("eps_basis", "eps_basis", "--eps-basis"),
    SelectionOption("expected_growth", "expected_growth", "--expected-growth"),
    SelectionOption("aaa_yield", "aaa_yield_override", "--aaa-yield"),
    SelectionOption("current_price", "quote_override", "--current-price"),
)
"""The selection field each selection option sets: this strategy's one table of options and fields."""


def _selection(  # noqa: PLR0913
    *,
    as_of: str | None,
    no_cache: bool,
    eps: float | None,
    eps_basis: str | None,
    expected_growth: float,
    aaa_yield: float,
    current_price: float | None,
) -> SelectionMember:
    """Build the Graham Growth selection from the selection options of either command."""
    return selection_from_options(
        METHOD_ID,
        SELECTION_OPTIONS,
        {
            "as_of": as_of,
            "no_cache": no_cache,
            "eps": eps,
            "eps_basis": eps_basis,
            "expected_growth": expected_growth,
            "aaa_yield": aaa_yield,
            "current_price": current_price,
        },
    )


def command(  # noqa: PLR0913
    ticker: Annotated[str | None, typer.Argument(help="Target stock ticker symbol (e.g., AAPL, KO)")] = None,
    *,
    ticker_option: Annotated[
        str | None,
        typer.Option("--ticker", "-t", help="Legacy ticker option; prefer the positional TICKER argument"),
    ] = None,
    as_of: AS_OF_OPTION = None,
    no_cache: NO_CACHE_OPTION = False,
    eps: EPS_OPTION = None,
    eps_basis: EPS_BASIS_OPTION = None,
    expected_growth: EXPECTED_GROWTH_OPTION,
    aaa_yield: AAA_YIELD_OPTION,
    current_price: CURRENT_PRICE_OPTION = None,
    details: Annotated[bool, typer.Option("--details", help="Show resolved inputs and financial provenance")] = False,
    diagnostics: Annotated[bool, typer.Option("--diagnostics", help="Show resolver execution trace")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Emit stable machine-readable JSON")] = False,
    save_run: SAVE_RUN_OPTION = False,
    no_provider_check: NO_PROVIDER_CHECK_OPTION = False,
) -> None:
    """Execute Graham Growth Value with explicit growth and AAA-yield assumptions."""
    provider_check = not no_provider_check
    with execution_errors(
        json_output=json_output,
        selection_type=GrahamGrowthSelection,
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
        selection = _selection(
            as_of=as_of,
            no_cache=no_cache,
            eps=eps,
            eps_basis=eps_basis,
            expected_growth=expected_growth,
            aaa_yield=aaa_yield,
            current_price=current_price,
        )
        outcome = analyze_for_command(target_ticker, selection, save_run=save_run, provider_check=provider_check)
        output, exit_code = analysis_output(outcome, mode)
    emit_output(output, exit_code, mode)


def add_selection(  # noqa: PLR0913
    name: Annotated[str, typer.Argument(help="Watchlist name.")],
    tickers: Annotated[list[str], typer.Argument(help="Tickers to add this selection for.")],
    *,
    as_of: AS_OF_OPTION = None,
    no_cache: NO_CACHE_OPTION = False,
    eps: EPS_OPTION = None,
    eps_basis: EPS_BASIS_OPTION = None,
    expected_growth: EXPECTED_GROWTH_OPTION,
    aaa_yield: AAA_YIELD_OPTION,
    current_price: CURRENT_PRICE_OPTION = None,
    json_output: Annotated[bool, typer.Option("--json", help="Emit the updated watchlist document.")] = False,
) -> None:
    """Add one Graham Growth entry per ticker to an existing watchlist."""
    with parameter_failures(json_output=json_output):
        selection = _selection(
            as_of=as_of,
            no_cache=no_cache,
            eps=eps,
            eps_basis=eps_basis,
            expected_growth=expected_growth,
            aaa_yield=aaa_yield,
            current_price=current_price,
        )
    add_selection_entries(name, tickers, selection, json_output=json_output)
