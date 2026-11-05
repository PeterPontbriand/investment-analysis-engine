"""FCF Growth's CLI-layer functions: the direct command and the watchlist selection builder.

The CLI tier pairs these with the FCF Growth core bundle and adds the command to the application; nothing here
registers itself. The command parses its options, builds the selection and calls the direct-analysis operation.
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
from investment_analysis_engine.core.operator_errors import InvalidParameterError
from investment_analysis_engine.strategies.fcf_growth.models import FCFEarningsGrowthPolicy
from investment_analysis_engine.strategies.fcf_growth.selection import FCFGrowthSelection, FCFPolicySnapshot
from investment_analysis_engine.strategies.fcf_growth.vocabulary import (
    FCFClassificationBasis,
    ForwardPolicy,
    HistoricalHorizon,
)


def _fcf_historical_horizon(growth_years: int | None) -> HistoricalHorizon:
    """Convert the optional CLI horizon to the typed strict/automatic policy."""
    if growth_years is None:
        return HistoricalHorizon.LONGEST_AVAILABLE
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


def _fcf_currency(value: str) -> str:
    """Normalize the reporting currency, which must be a three-letter ISO 4217 code."""
    normalized = value.strip().upper()
    if len(normalized) != 3 or not normalized.isalpha():
        raise InvalidParameterError("--currency must be a three-letter ISO 4217 code.", parameters=("--currency",))
    return normalized


def build_selection(flags: WatchlistFlags) -> FCFGrowthSelection:
    """Build one validated FCF Growth selection from watchlist CLI flags.

    Mirrors the direct ``fcf-growth`` command's own flags and validation exactly.
    """
    boundary = parse_as_of(flags.as_of)
    normalized_currency = _fcf_currency(flags.currency)
    policy = FCFEarningsGrowthPolicy(
        historical_horizon=_fcf_historical_horizon(flags.growth_years),
        classification_basis=_fcf_classification_basis(flags.classification_basis),
        forward_policy=_fcf_forward_policy(flags.forward_policy),
    )
    return FCFGrowthSelection(
        policy=FCFPolicySnapshot.model_validate(policy),
        currency=normalized_currency,
        as_of=boundary,
        use_cache=not flags.no_cache,
    )


def command(  # noqa: PLR0913
    ticker: str = typer.Argument(..., help="Target stock ticker symbol (e.g., AAPL, KO)"),
    *,
    growth_years: int | None = typer.Option(
        None,
        "--growth-years",
        help="Strict elapsed-year horizon (3, 4, or 5); omit for automatic 5 → 4 → 3 selection",
    ),
    forward_policy: str = typer.Option(
        "display-only",
        "--forward-policy",
        help="Forward evidence policy: display-only, confirmation, or hard-gate",
    ),
    classification_basis: str = typer.Option(
        "total-fcf",
        "--classification-basis",
        help="Classification basis: total-fcf or fcf-per-share",
    ),
    as_of: str | None = AS_OF_OPTION,
    currency: str = typer.Option("USD", "--currency", help="ISO 4217 reporting currency for compatible annual facts"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass resolved-input cache reads and writes"),
    details: bool = typer.Option(False, "--details", help="Show annual facts, provenance, and derivation lineage"),
    diagnostics: bool = typer.Option(False, "--diagnostics", help="Show resolver execution trace"),
    json_output: bool = typer.Option(False, "--json", help="Emit the complete versioned typed result"),
    save_run: bool = SAVE_RUN_OPTION,
    no_provider_check: bool = NO_PROVIDER_CHECK_OPTION,
) -> None:
    """Execute the historical free-cash-flow and diluted-EPS growth screen."""
    provider_check = not no_provider_check

    with execution_errors(
        json_output=json_output,
        selection_type=FCFGrowthSelection,
        provider_check=provider_check,
    ) as scope:
        target_ticker, mode = resolve_command_target(
            scope, ticker, None, command="fcf-growth", details=details, diagnostics=diagnostics, json_output=json_output
        )
        horizon = _fcf_historical_horizon(growth_years)
        analysis_as_of = parse_as_of(as_of)
        normalized_currency = _fcf_currency(currency)
        policy = FCFEarningsGrowthPolicy(
            historical_horizon=horizon,
            classification_basis=_fcf_classification_basis(classification_basis),
            forward_policy=_fcf_forward_policy(forward_policy),
        )
        selection = FCFGrowthSelection(
            policy=FCFPolicySnapshot.model_validate(policy),
            currency=normalized_currency,
            as_of=analysis_as_of,
            use_cache=not no_cache,
        )
        outcome = analyze_for_command(target_ticker, selection, save_run=save_run, provider_check=provider_check)
        output, exit_code = analysis_output(outcome, mode)
    emit_output(output, exit_code, mode)
