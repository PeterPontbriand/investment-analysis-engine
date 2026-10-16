"""Graham Number's CLI-layer functions: the direct command, the watchlist selection builder and the refresh executor.

The CLI tier pairs these with the Graham Number core bundle and adds the command to the application; nothing here
registers itself.
"""

from dataclasses import replace
from datetime import datetime

import typer

from src.analysis.shared.financial_resolution import PriceComparison
from src.cli_composition import build_graham_resolver
from src.cli_provider_check import (
    ProviderCheckChoice,
    provider_check_choice,
    provider_check_findings,
    with_provider_check,
)
from src.cli_run_support import maybe_save_run
from src.cli_support import (
    SaveStage,
    _canonical_provider_id,
    _parse_as_of,
    _presentation_mode,
    _production_financial_cache,
    _resolve_ticker,
    config_usage_errors,
    execution_errors,
    require_job_ticker,
    saving_failures,
    stored_configuration,
)
from src.cli_watchlist_flags import WatchlistFlags
from src.core.analysis_status import CalculationStatus
from src.core.clock import utc_now
from src.core.provider_check_element import ProviderCheckItem
from src.data.instrument_profile import InstrumentProfile, profile_identity_resolution
from src.data.instrument_profile_cache import InstrumentProfileResolver
from src.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from src.data.security_identity import SecurityIdentityResolution
from src.data.yfinance.client import YFinanceClient
from src.reporting.evidence_presentation import friendly_valuation_failure
from src.reporting.presentation import PresentationMode
from src.strategies.graham_number.calculation import GrahamNumberInputAssembly, GrahamNumberInputResolver
from src.strategies.graham_number.execution import (
    capture_provider_failure,
    execute_graham_number,
    from_graham_number_capture,
)
from src.strategies.graham_number.presenter import (
    GrahamNumberPresentation,
    number_with_public_quote_reason,
    render_graham_number,
)
from src.strategies.graham_number.selection import GrahamNumberSelection
from src.workspace.capture import ExecutionCapture
from src.workspace.requests import AnalysisRequest


def build_selection(flags: WatchlistFlags) -> GrahamNumberSelection:
    """Build one validated Graham Number selection from watchlist CLI flags.

    Mirrors the direct ``graham-number`` command's own flags and validation exactly, so a watchlist entry
    behaves identically to running the method directly.
    """
    boundary = _parse_as_of(flags.as_of)
    provider_id = _canonical_provider_id(flags.data_provider) or SEC_PROVIDER_ID
    with config_usage_errors():
        return GrahamNumberSelection.model_validate(
            {
                "security_provider_id": provider_id,
                "eps_override": flags.eps,
                "quote_override": flags.current_price,
                "as_of": boundary,
                "use_cache": not flags.no_cache,
                "bvps_override": flags.bvps,
            }
        )


def refresh(
    ticker: str, selection: GrahamNumberSelection, *, profile_cache: InstrumentProfileResolver | None
) -> ExecutionCapture:
    """Execute one Graham Number refresh job with freshly composed, job-scoped dependencies."""
    require_job_ticker(ticker)
    config = stored_configuration(selection.to_graham_number_config)
    executed_at = utc_now()
    with _production_financial_cache(use_cache=selection.use_cache, clock=lambda: executed_at) as cache:
        resolver = build_graham_resolver(
            resolver_type=GrahamNumberInputResolver,
            data_provider=config.security_provider_id,
            cache=cache,
            clock=lambda: executed_at,
        )
        capture = execute_graham_number(
            resolver,
            ticker,
            config,
            YFinanceClient(),
            as_of=selection.as_of,
            executed_at=executed_at,
            use_cache=selection.use_cache,
            profile_cache=profile_cache,
        )
    return from_graham_number_capture(capture)


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
    as_of: str | None = typer.Option(
        None,
        "--as-of",
        help="Point-in-time boundary as YYYY-MM-DD or timezone-aware ISO-8601 timestamp",
    ),
    data_provider: str | None = typer.Option(
        None,
        "--data-provider",
        help="Security-fact provider override; defaults to SEC EDGAR",
    ),
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
    save_run: bool = typer.Option(False, "--save-run", help="Persist this attempt as a durable Analysis Run"),
    no_provider_check: bool = typer.Option(
        False, "--no-provider-check", help="Do not send a test request to a provider after it fails"
    ),
) -> None:
    """Execute the Graham Number earnings-and-book-value screen."""
    use_cache = not no_cache
    executed_at = utc_now()
    provider_check = provider_check_choice(context, no_provider_check=no_provider_check)
    with execution_errors(
        json_output=json_output,
        selection_type=GrahamNumberSelection,
        provider_check=provider_check,
    ) as scope:
        target_ticker = _resolve_ticker(ticker, ticker_option, required=True, command="graham-number")
        assert target_ticker is not None
        scope.ticker = target_ticker
        mode = _presentation_mode(details=details, diagnostics=diagnostics, json_output=json_output)
        scope.mode = mode
        boundary = _parse_as_of(as_of)
        provider_id = _canonical_provider_id(data_provider) or SEC_PROVIDER_ID
        with config_usage_errors():
            selection = GrahamNumberSelection.model_validate(
                {
                    "security_provider_id": provider_id,
                    "eps_override": eps,
                    "quote_override": current_price,
                    "bvps_override": bvps,
                    "as_of": boundary,
                    "use_cache": use_cache,
                }
            )
        with _production_financial_cache(use_cache=use_cache, clock=lambda: executed_at) as cache:
            with execution_errors(
                mode=mode,
                selection_type=GrahamNumberSelection,
                ticker=target_ticker,
            ):
                resolver = build_graham_resolver(
                    resolver_type=GrahamNumberInputResolver,
                    data_provider=selection.security_provider_id,
                    cache=cache,
                    clock=lambda: executed_at,
                )
            output, exit_code = _run_graham_number(
                resolver=resolver,
                ticker=target_ticker,
                selection=selection,
                mode=mode,
                profile_provider=YFinanceClient(),
                executed_at=executed_at,
                save_run=save_run,
                provider_check=provider_check,
            )
    typer.echo(output, err=exit_code != 0 and mode in (PresentationMode.CONCISE, PresentationMode.DETAILS))
    if exit_code:
        raise typer.Exit(code=exit_code)


def _run_graham_number(  # noqa: PLR0913
    *,
    resolver: GrahamNumberInputResolver,
    ticker: str,
    selection: GrahamNumberSelection,
    mode: PresentationMode,
    profile_provider: object,
    executed_at: datetime,
    save_run: bool = False,
    provider_check: ProviderCheckChoice | None = None,
) -> tuple[str, int]:
    """Resolve, calculate, and render one Graham Number analysis."""
    config = selection.to_graham_number_config()
    as_of = selection.as_of
    use_cache = selection.use_cache
    stage = SaveStage()
    with saving_failures(stage):
        capture = maybe_save_run(
            save_run=save_run,
            executed_at=executed_at,
            request_factory=lambda: AnalysisRequest(ticker=ticker, selection=selection),
            run_adapter=lambda profile_cache: execute_graham_number(
                resolver,
                ticker,
                config,
                profile_provider,
                as_of=as_of,
                executed_at=executed_at,
                use_cache=use_cache,
                profile_cache=profile_cache,
            ),
            normalize=stage.after_analysis(from_graham_number_capture),
        )
    analysis = capture.analysis
    profile = capture.profile
    assembly = analysis.assembly
    identity_resolution = profile_identity_resolution(profile)

    if assembly.status is not CalculationStatus.OK:
        if assembly.status is CalculationStatus.NOT_APPLICABLE:
            presentation = GrahamNumberPresentation(
                ticker=ticker,
                assembly=assembly,
                result=analysis.result,
                price_comparison=analysis.price_comparison,
                as_of=as_of,
                effective_as_of=analysis.effective_as_of,
                identity_resolution=identity_resolution,
                instrument_profile=profile,
            )
            return render_graham_number(presentation, mode), 0
        findings = provider_check_findings((capture_provider_failure(capture),), provider_check)
        failure_output, failure_exit_code = _number_failure_output(
            ticker=ticker,
            assembly=assembly,
            as_of=as_of,
            effective_as_of=analysis.effective_as_of,
            mode=mode,
            identity_resolution=identity_resolution,
            instrument_profile=profile,
            price_comparison=analysis.price_comparison,
            provider_check=findings.element(),
        )
        return with_provider_check(failure_output, findings, mode), failure_exit_code

    presentation_assembly = number_with_public_quote_reason(assembly)
    presentation = GrahamNumberPresentation(
        ticker=ticker,
        assembly=presentation_assembly,
        result=analysis.result,
        as_of=as_of,
        effective_as_of=analysis.effective_as_of,
        margin_of_safety_percent=analysis.margin_of_safety_percent,
        price_comparison=analysis.price_comparison,
        identity_resolution=identity_resolution,
        instrument_profile=profile,
    )
    exit_code = 1 if analysis.result.status is CalculationStatus.INVALID_INPUT else 0
    return render_graham_number(presentation, mode), exit_code


def _number_failure_output(  # noqa: PLR0913
    *,
    ticker: str,
    assembly: GrahamNumberInputAssembly,
    as_of: datetime | None,
    effective_as_of: datetime,
    mode: PresentationMode,
    identity_resolution: SecurityIdentityResolution,
    instrument_profile: InstrumentProfile,
    price_comparison: PriceComparison | None = None,
    provider_check: tuple[ProviderCheckItem, ...] | None = None,
) -> tuple[str, int]:
    """Render a failed Number analysis without leaking low-level details by default."""
    reason = friendly_valuation_failure(ticker, assembly.status, assembly.reason)
    safe_assembly = number_with_public_quote_reason(replace(assembly, reason=reason))
    presentation = GrahamNumberPresentation(
        ticker=ticker,
        assembly=safe_assembly,
        price_comparison=price_comparison,
        result=None,
        as_of=as_of,
        effective_as_of=effective_as_of,
        identity_resolution=identity_resolution,
        instrument_profile=instrument_profile,
        provider_check=provider_check,
    )
    return render_graham_number(presentation, mode), 1
