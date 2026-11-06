"""FCF Growth's CLI-layer functions: the direct command and the watchlist ``add-selection`` command.

The CLI tier pairs these with the FCF Growth core bundle and adds both commands to the application; nothing here
registers itself. Both commands declare the same selection options, build their selection through the same option
table, and the direct command then calls the direct-analysis operation.

A converter in the option table translates the command-line spelling of a value (a hyphenated policy name, a
horizon in years) into the field's value; every rule about the value itself is the selection model's.
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
from investment_analysis_engine.core.operator_errors import InvalidParameterError
from investment_analysis_engine.strategies.fcf_growth.selection import FCFGrowthSelection
from investment_analysis_engine.strategies.fcf_growth.vocabulary import (
    METHOD_ID,
    FCFClassificationBasis,
    ForwardPolicy,
    HistoricalHorizon,
)
from investment_analysis_engine.workspace.strategy_types import SelectionMember


def _fcf_historical_horizon(growth_years: int) -> HistoricalHorizon:
    """Convert the CLI horizon in years to the typed strict policy."""
    mapping = {3: HistoricalHorizon.THREE_YEARS, 4: HistoricalHorizon.FOUR_YEARS, 5: HistoricalHorizon.FIVE_YEARS}
    try:
        return mapping[growth_years]
    except KeyError as exc:
        raise InvalidParameterError("--growth-years must be 3, 4, or 5.", parameters=("--growth-years",)) from exc


def _fcf_forward_policy(value: str) -> ForwardPolicy:
    """Map the hyphenated investor-facing CLI value to the normative enum."""
    normalized = value.strip().lower().replace("-", "_")
    try:
        return ForwardPolicy(normalized)
    except ValueError as exc:
        raise InvalidParameterError(
            "--forward-policy must be display-only, confirmation, or hard-gate.", parameters=("--forward-policy",)
        ) from exc


def _fcf_classification_basis(value: str) -> FCFClassificationBasis:
    """Map the investor-facing CLI value to the typed FCF basis policy."""
    normalized = value.strip().lower().replace("-", "_")
    try:
        return FCFClassificationBasis(normalized)
    except ValueError as exc:
        raise InvalidParameterError(
            "--classification-basis must be total-fcf or fcf-per-share.", parameters=("--classification-basis",)
        ) from exc


GROWTH_YEARS_OPTION = Annotated[
    int | None,
    typer.Option(
        "--growth-years",
        help="Strict elapsed-year horizon (3, 4, or 5); omit for automatic 5 → 4 → 3 selection",
    ),
]
FORWARD_POLICY_OPTION = Annotated[
    str,
    typer.Option(
        "--forward-policy",
        help="Forward evidence policy: display-only, confirmation, or hard-gate",
    ),
]
CLASSIFICATION_BASIS_OPTION = Annotated[
    str,
    typer.Option(
        "--classification-basis",
        help="Classification basis: total-fcf or fcf-per-share",
    ),
]
CURRENCY_OPTION = Annotated[
    str, typer.Option("--currency", help="ISO 4217 reporting currency for compatible annual facts")
]
NO_CACHE_OPTION = Annotated[bool, typer.Option("--no-cache", help="Bypass resolved-input cache reads and writes")]

DEFAULT_FORWARD_POLICY = "display-only"
DEFAULT_CLASSIFICATION_BASIS = "total-fcf"
DEFAULT_CURRENCY = "USD"

SELECTION_OPTIONS = (
    SelectionOption("growth_years", "policy.historical_horizon", "--growth-years", _fcf_historical_horizon),
    SelectionOption("forward_policy", "policy.forward_policy", "--forward-policy", _fcf_forward_policy),
    SelectionOption(
        "classification_basis", "policy.classification_basis", "--classification-basis", _fcf_classification_basis
    ),
    SelectionOption("as_of", "as_of", "--as-of", parse_as_of),
    SelectionOption("currency", "currency", "--currency"),
    SelectionOption("no_cache", "use_cache", "--no-cache", cache_enabled),
)
"""The selection field each selection option sets: this strategy's one table of options and fields."""


def _selection(  # noqa: PLR0913
    *,
    growth_years: int | None,
    forward_policy: str,
    classification_basis: str,
    as_of: str | None,
    currency: str,
    no_cache: bool,
) -> SelectionMember:
    """Build the FCF Growth selection from the selection options of either command."""
    return selection_from_options(
        METHOD_ID,
        SELECTION_OPTIONS,
        {
            "growth_years": growth_years,
            "forward_policy": forward_policy,
            "classification_basis": classification_basis,
            "as_of": as_of,
            "currency": currency,
            "no_cache": no_cache,
        },
    )


def command(  # noqa: PLR0913
    ticker: Annotated[str, typer.Argument(help="Target stock ticker symbol (e.g., AAPL, KO)")],
    *,
    growth_years: GROWTH_YEARS_OPTION = None,
    forward_policy: FORWARD_POLICY_OPTION = DEFAULT_FORWARD_POLICY,
    classification_basis: CLASSIFICATION_BASIS_OPTION = DEFAULT_CLASSIFICATION_BASIS,
    as_of: AS_OF_OPTION = None,
    currency: CURRENCY_OPTION = DEFAULT_CURRENCY,
    no_cache: NO_CACHE_OPTION = False,
    details: Annotated[
        bool, typer.Option("--details", help="Show annual facts, provenance, and derivation lineage")
    ] = False,
    diagnostics: Annotated[bool, typer.Option("--diagnostics", help="Show resolver execution trace")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Emit the complete versioned typed result")] = False,
    save_run: SAVE_RUN_OPTION = False,
    no_provider_check: NO_PROVIDER_CHECK_OPTION = False,
) -> None:
    """Execute the historical free-cash-flow and diluted-EPS growth screen."""
    provider_check = not no_provider_check

    with execution_errors(
        json_output=json_output,
        selection_type=FCFGrowthSelection,
    ) as scope:
        target_ticker, mode = resolve_command_target(
            scope, ticker, None, command="fcf-growth", details=details, diagnostics=diagnostics, json_output=json_output
        )
        selection = _selection(
            growth_years=growth_years,
            forward_policy=forward_policy,
            classification_basis=classification_basis,
            as_of=as_of,
            currency=currency,
            no_cache=no_cache,
        )
        outcome = analyze_for_command(target_ticker, selection, save_run=save_run, provider_check=provider_check)
        output, exit_code = analysis_output(outcome, mode)
    emit_output(output, exit_code, mode)


def add_selection(  # noqa: PLR0913
    name: Annotated[str, typer.Argument(help="Watchlist name.")],
    tickers: Annotated[list[str], typer.Argument(help="Tickers to add this selection for.")],
    *,
    growth_years: GROWTH_YEARS_OPTION = None,
    forward_policy: FORWARD_POLICY_OPTION = DEFAULT_FORWARD_POLICY,
    classification_basis: CLASSIFICATION_BASIS_OPTION = DEFAULT_CLASSIFICATION_BASIS,
    as_of: AS_OF_OPTION = None,
    currency: CURRENCY_OPTION = DEFAULT_CURRENCY,
    no_cache: NO_CACHE_OPTION = False,
    json_output: Annotated[bool, typer.Option("--json", help="Emit the updated watchlist document.")] = False,
) -> None:
    """Add one FCF Growth entry per ticker to an existing watchlist."""
    with parameter_failures(json_output=json_output):
        selection = _selection(
            growth_years=growth_years,
            forward_policy=forward_policy,
            classification_basis=classification_basis,
            as_of=as_of,
            currency=currency,
            no_cache=no_cache,
        )
    add_selection_entries(name, tickers, selection, json_output=json_output)
