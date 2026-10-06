"""FCF Growth's CLI-layer functions: the direct command, the watchlist selection builder and the refresh executor.

The CLI tier pairs these with the FCF Growth core bundle and adds the command to the application; nothing here
registers itself.
"""

import typer

from src.cli_composition import build_sec_production_provider
from src.cli_run_support import maybe_save_run
from src.cli_support import (
    _canonical_provider_id,
    _parse_as_of,
    _presentation_mode,
    _production_financial_cache,
    _resolve_ticker,
    execution_errors,
)
from src.cli_watchlist_flags import WatchlistFlags
from src.core.analysis_status import CalculationStatus
from src.core.clock import utc_now
from src.data.financial.providers import SEC_PROVIDER_ID
from src.data.instrument_profile import profile_identity_resolution
from src.data.instrument_profile_cache import InstrumentProfileResolver
from src.reporting.presentation import PresentationMode
from src.strategies.fcf_growth.execution import execute_fcf_growth, from_fcf_growth_capture
from src.strategies.fcf_growth.input_resolver import ProductionAnnualGrowthSeriesResolver
from src.strategies.fcf_growth.models import (
    FCFClassificationBasis,
    FCFEarningsGrowthConfig,
    FCFEarningsGrowthPolicy,
    ForwardPolicy,
    HistoricalHorizon,
)
from src.strategies.fcf_growth.presenter import render_fcf_earnings_growth
from src.strategies.fcf_growth.selection import FCFGrowthSelection, FCFPolicySnapshot
from src.workspace.capture import ExecutionCapture
from src.workspace.requests import AnalysisRequest


def _fcf_historical_horizon(growth_years: int | None) -> HistoricalHorizon:
    """Convert the optional CLI horizon to the typed strict/automatic policy."""
    if growth_years is None:
        return HistoricalHorizon.LONGEST_AVAILABLE
    mapping = {3: HistoricalHorizon.THREE_YEARS, 4: HistoricalHorizon.FOUR_YEARS, 5: HistoricalHorizon.FIVE_YEARS}
    try:
        return mapping[growth_years]
    except KeyError as exc:
        raise typer.BadParameter("--growth-years must be 3, 4, or 5.") from exc


def _fcf_forward_policy(value: str) -> ForwardPolicy:
    """Map the hyphenated investor-facing CLI value to the normative enum."""
    normalized = value.strip().lower().replace("-", "_")
    try:
        return ForwardPolicy(normalized)
    except ValueError as exc:
        raise typer.BadParameter("--forward-policy must be display-only, confirmation, or hard-gate.") from exc


def _fcf_classification_basis(value: str) -> FCFClassificationBasis:
    """Map the investor-facing CLI value to the typed FCF basis policy."""
    normalized = value.strip().lower().replace("-", "_")
    try:
        return FCFClassificationBasis(normalized)
    except ValueError as exc:
        raise typer.BadParameter("--classification-basis must be total-fcf or fcf-per-share.") from exc


def build_selection(flags: WatchlistFlags) -> FCFGrowthSelection:
    """Build one validated FCF Growth selection from watchlist CLI flags.

    Mirrors the direct ``fcf-growth`` command's own flags and validation exactly. The method always executes
    against SEC EDGAR regardless of ``--data-provider``, as the direct command's own persisted selection does;
    the flag is still validated for a consistent error experience.
    """
    boundary = _parse_as_of(flags.as_of)
    _canonical_provider_id(flags.data_provider)
    normalized_currency = flags.currency.strip().upper()
    if len(normalized_currency) != 3 or not normalized_currency.isalpha():
        raise typer.BadParameter("--currency must be a three-letter ISO 4217 code.")
    policy = FCFEarningsGrowthPolicy(
        historical_horizon=_fcf_historical_horizon(flags.growth_years),
        classification_basis=_fcf_classification_basis(flags.classification_basis),
        forward_policy=_fcf_forward_policy(flags.forward_policy),
    )
    return FCFGrowthSelection(
        policy=FCFPolicySnapshot.model_validate(policy),
        currency=normalized_currency,
        provider_id="sec_edgar",
        as_of=boundary,
        use_cache=not flags.no_cache,
    )


def refresh(
    ticker: str, selection: FCFGrowthSelection, *, profile_cache: InstrumentProfileResolver | None
) -> ExecutionCapture:
    """Execute one FCF Growth refresh job with freshly composed, job-scoped dependencies."""
    config = selection.to_fcf_config()
    executed_at = utc_now()
    with _production_financial_cache(use_cache=selection.use_cache, clock=lambda: executed_at) as cache:
        provider = build_sec_production_provider()
        resolver = ProductionAnnualGrowthSeriesResolver(provider, cache=cache, clock=lambda: executed_at)
        capture = execute_fcf_growth(
            resolver,
            ticker,
            config=config,
            as_of=selection.as_of,
            executed_at=executed_at,
            use_cache=selection.use_cache,
            provider=provider,
            profile_cache=profile_cache,
        )
    return from_fcf_growth_capture(capture)


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
    as_of: str | None = typer.Option(
        None, "--as-of", help="Point-in-time boundary as YYYY-MM-DD or timezone-aware ISO-8601 timestamp"
    ),
    data_provider: str | None = typer.Option(None, "--data-provider", help="Defaults to SEC EDGAR"),
    currency: str = typer.Option("USD", "--currency", help="ISO 4217 reporting currency for compatible annual facts"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass resolved-input cache reads and writes"),
    details: bool = typer.Option(False, "--details", help="Show annual facts, provenance, and derivation lineage"),
    diagnostics: bool = typer.Option(False, "--diagnostics", help="Show resolver execution trace"),
    json_output: bool = typer.Option(False, "--json", help="Emit the complete versioned typed result"),
    save_run: bool = typer.Option(False, "--save-run", help="Persist this attempt as a durable Analysis Run"),
) -> None:
    """Execute the historical free-cash-flow and diluted-EPS growth screen."""
    target_ticker = _resolve_ticker(ticker, None, required=True, command="fcf-growth")
    assert target_ticker is not None
    mode = _presentation_mode(details=details, diagnostics=diagnostics, json_output=json_output)
    horizon = _fcf_historical_horizon(growth_years)
    analysis_as_of = _parse_as_of(as_of)
    provider_id = _canonical_provider_id(data_provider) or SEC_PROVIDER_ID
    normalized_currency = currency.strip().upper()
    if len(normalized_currency) != 3 or not normalized_currency.isalpha():
        raise typer.BadParameter("--currency must be a three-letter ISO 4217 code.")
    policy = FCFEarningsGrowthPolicy(
        historical_horizon=horizon,
        classification_basis=_fcf_classification_basis(classification_basis),
        forward_policy=_fcf_forward_policy(forward_policy),
    )
    executed_at = utc_now()
    # The command always uses the SEC production provider regardless of --data-provider
    # (see the adapter's own docstring); provider_id here only labels the requested
    # config/result, exactly as before this refactor — not the resolver actually used.
    config = FCFEarningsGrowthConfig(policy=policy, currency=normalized_currency, provider_id=provider_id)

    with (
        execution_errors(
            mode=mode,
            analysis="fcf_earnings_growth",
            method="reported_fcf_eps_cagr",
            ticker=target_ticker,
            invalid=lambda exc: f"Unable to start FCF & earnings-growth analysis: {exc}",
            unexpected=lambda _exc: f"FCF & earnings-growth analysis failed unexpectedly for {target_ticker}.",
        ),
        _production_financial_cache(use_cache=not no_cache, clock=lambda: executed_at) as cache,
    ):
        provider = build_sec_production_provider()
        resolver = ProductionAnnualGrowthSeriesResolver(
            provider,
            cache=cache,
            clock=lambda: executed_at,
        )
        capture = maybe_save_run(
            save_run=save_run,
            executed_at=executed_at,
            request_factory=lambda: AnalysisRequest(
                ticker=target_ticker,
                # The command always uses the SEC production provider regardless of
                # --data-provider (see the adapter's own docstring); the selection
                # reflects the provider actually used, not a possibly-mislabeled flag.
                selection=FCFGrowthSelection(
                    policy=FCFPolicySnapshot.model_validate(policy),
                    currency=normalized_currency,
                    provider_id="sec_edgar",
                    as_of=analysis_as_of,
                    use_cache=not no_cache,
                ),
            ),
            run_adapter=lambda profile_cache: execute_fcf_growth(
                resolver,
                target_ticker,
                config=config,
                as_of=analysis_as_of,
                executed_at=executed_at,
                use_cache=not no_cache,
                provider=provider,
                profile_cache=profile_cache,
            ),
            normalize=from_fcf_growth_capture,
        )
        result = capture.result
        profile = capture.profile
        identity_resolution = profile_identity_resolution(profile)

    output = render_fcf_earnings_growth(result, mode, identity_resolution, profile)
    exit_code = 0 if result.execution_status in (CalculationStatus.OK, CalculationStatus.NOT_APPLICABLE) else 1
    typer.echo(output, err=exit_code != 0 and mode in (PresentationMode.CONCISE, PresentationMode.DETAILS))
    if exit_code:
        raise typer.Exit(code=exit_code)
