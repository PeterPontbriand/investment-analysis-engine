"""Graham Number's CLI-layer functions: the direct command, the watchlist selection builder and the refresh executor.

The CLI tier pairs these with the Graham Number core bundle and adds the command to the application; nothing here
registers itself.
"""

from dataclasses import replace
from datetime import datetime

import typer

from investment_analysis_engine.analysis.shared.financial_resolution import PriceComparison
from investment_analysis_engine.cli_composition import build_graham_resolver
from investment_analysis_engine.cli_provider_check import (
    ProviderCheckChoice,
    provider_check_choice,
)
from investment_analysis_engine.cli_run_support import analyze_and_maybe_save
from investment_analysis_engine.cli_support import (
    AS_OF_OPTION,
    NO_PROVIDER_CHECK_OPTION,
    SAVE_RUN_OPTION,
    config_usage_errors,
    emit_output,
    execution_errors,
    parse_as_of,
    production_financial_cache,
    render_execution,
    require_job_ticker,
    resolve_command_target,
    stored_configuration,
)
from investment_analysis_engine.cli_watchlist_flags import WatchlistFlags
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.clock import utc_now
from investment_analysis_engine.core.provider_check_element import ProviderCheckItem
from investment_analysis_engine.data.instrument_profile import InstrumentProfile, profile_identity_resolution
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.data.security_identity import SecurityIdentityResolution
from investment_analysis_engine.data.yfinance.client import YFinanceClient
from investment_analysis_engine.reporting.evidence_presentation import friendly_valuation_failure
from investment_analysis_engine.reporting.presentation import PresentationMode
from investment_analysis_engine.strategies.graham_number.calculation import (
    GrahamNumberInputAssembly,
    GrahamNumberInputResolver,
)
from investment_analysis_engine.strategies.graham_number.execution import (
    execute_graham_number,
    from_graham_number_capture,
)
from investment_analysis_engine.strategies.graham_number.presenter import (
    GrahamNumberPresentation,
    number_with_public_quote_reason,
    render_graham_number,
)
from investment_analysis_engine.strategies.graham_number.selection import GrahamNumberSelection
from investment_analysis_engine.workspace.capture import ExecutionCapture
from investment_analysis_engine.workspace.requests import AnalysisRequest


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


def refresh(
    ticker: str, selection: GrahamNumberSelection, *, profile_cache: InstrumentProfileResolver | None
) -> ExecutionCapture:
    """Execute one Graham Number refresh job with freshly composed, job-scoped dependencies."""
    require_job_ticker(ticker)
    config = stored_configuration(selection.to_graham_number_config)
    executed_at = utc_now()
    with production_financial_cache(use_cache=selection.use_cache, clock=lambda: executed_at) as cache:
        resolver = build_graham_resolver(
            resolver_type=GrahamNumberInputResolver,
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
    executed_at = utc_now()
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
        with production_financial_cache(use_cache=use_cache, clock=lambda: executed_at) as cache:
            with execution_errors(
                mode=mode,
                selection_type=GrahamNumberSelection,
                ticker=target_ticker,
            ):
                resolver = build_graham_resolver(
                    resolver_type=GrahamNumberInputResolver,
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
    emit_output(output, exit_code, mode)


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
    capture = analyze_and_maybe_save(
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
        normalize=from_graham_number_capture,
    )
    execution = from_graham_number_capture(capture)
    analysis = capture.analysis
    profile = capture.profile
    identity_resolution = profile_identity_resolution(profile)

    def render(provider_check_element: tuple[ProviderCheckItem, ...] | None) -> str:
        """Render the failure, not-applicable or success output of this analysis."""
        assembly = analysis.assembly
        if assembly.status is CalculationStatus.OK:
            presentation = GrahamNumberPresentation(
                ticker=ticker,
                assembly=number_with_public_quote_reason(assembly),
                result=analysis.result,
                as_of=as_of,
                effective_as_of=analysis.effective_as_of,
                margin_of_safety_percent=analysis.margin_of_safety_percent,
                price_comparison=analysis.price_comparison,
                identity_resolution=identity_resolution,
                instrument_profile=profile,
                provider_check=provider_check_element,
            )
            return render_graham_number(presentation, mode)
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
                provider_check=provider_check_element,
            )
            return render_graham_number(presentation, mode)
        return _number_failure_output(
            ticker=ticker,
            assembly=assembly,
            as_of=as_of,
            effective_as_of=analysis.effective_as_of,
            mode=mode,
            identity_resolution=identity_resolution,
            instrument_profile=profile,
            price_comparison=analysis.price_comparison,
            provider_check=provider_check_element,
        )

    return render_execution(execution, provider_check, mode, render)


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
) -> str:
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
    return render_graham_number(presentation, mode)
