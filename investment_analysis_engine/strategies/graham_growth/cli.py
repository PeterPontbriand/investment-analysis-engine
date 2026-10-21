"""Graham Growth's CLI-layer functions: the direct command, the watchlist selection builder and the refresh executor.

The CLI tier pairs these with the Graham Growth core bundle and adds the command to the application; nothing here
registers itself.
"""

from dataclasses import replace
from datetime import datetime

import typer

from investment_analysis_engine.analysis.shared.financial_resolution import PriceComparison
from investment_analysis_engine.cli_composition import build_graham_resolver, graham_growth_settings
from investment_analysis_engine.cli_provider_check import (
    ProviderCheckChoice,
    provider_check_choice,
    provider_check_findings,
    with_provider_check,
)
from investment_analysis_engine.cli_run_support import maybe_save_run
from investment_analysis_engine.cli_support import (
    SaveStage,
    _parse_as_of,
    _presentation_mode,
    _production_financial_cache,
    _resolve_ticker,
    config_usage_errors,
    execution_errors,
    exit_code_of,
    require_job_ticker,
    saving_failures,
    stored_configuration,
)
from investment_analysis_engine.cli_watchlist_flags import WatchlistFlags
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.clock import utc_now
from investment_analysis_engine.core.operator_errors import InvalidParameterError
from investment_analysis_engine.core.provider_check_element import ProviderCheckItem
from investment_analysis_engine.data.instrument_profile import InstrumentProfile, profile_identity_resolution
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.data.security_identity import SecurityIdentityResolution
from investment_analysis_engine.data.yfinance.client import YFinanceClient
from investment_analysis_engine.reporting.evidence_presentation import friendly_valuation_failure
from investment_analysis_engine.reporting.presentation import PresentationMode
from investment_analysis_engine.strategies.graham_growth.calculation import (
    GrahamGrowthInputResolver,
    GrowthValueInputAssembly,
)
from investment_analysis_engine.strategies.graham_growth.execution import (
    execute_graham_growth,
    from_graham_growth_capture,
)
from investment_analysis_engine.strategies.graham_growth.presenter import (
    GrahamGrowthPresentation,
    growth_with_public_quote_reason,
    render_graham_growth,
)
from investment_analysis_engine.strategies.graham_growth.selection import GrahamGrowthSelection
from investment_analysis_engine.workspace.capture import ExecutionCapture
from investment_analysis_engine.workspace.requests import AnalysisRequest


def build_selection(flags: WatchlistFlags) -> GrahamGrowthSelection:
    """Build one validated Graham Growth selection from watchlist CLI flags.

    Mirrors the direct ``graham-growth`` command's own flags and validation exactly, so a watchlist entry
    behaves identically to running the method directly.
    """
    boundary = _parse_as_of(flags.as_of)
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


def refresh(
    ticker: str, selection: GrahamGrowthSelection, *, profile_cache: InstrumentProfileResolver | None
) -> ExecutionCapture:
    """Execute one Graham Growth refresh job with freshly composed, job-scoped dependencies."""
    require_job_ticker(ticker)
    config = stored_configuration(selection.to_graham_growth_config)
    policy = graham_growth_settings().to_policy()
    executed_at = utc_now()
    with _production_financial_cache(use_cache=selection.use_cache, clock=lambda: executed_at) as cache:
        resolver = build_graham_resolver(
            resolver_type=GrahamGrowthInputResolver,
            cache=cache,
            clock=lambda: executed_at,
        )
        capture = execute_graham_growth(
            resolver,
            ticker,
            config,
            policy,
            YFinanceClient(),
            as_of=selection.as_of,
            executed_at=executed_at,
            use_cache=selection.use_cache,
            profile_cache=profile_cache,
        )
    return from_graham_growth_capture(capture)


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
    save_run: bool = typer.Option(False, "--save-run", help="Persist this attempt as a durable Analysis Run"),
    no_provider_check: bool = typer.Option(
        False, "--no-provider-check", help="Do not send a test request to a provider after it fails"
    ),
) -> None:
    """Execute Graham Growth Value with explicit growth and AAA-yield assumptions."""
    use_cache = not no_cache
    executed_at = utc_now()
    provider_check = provider_check_choice(context, no_provider_check=no_provider_check)
    with execution_errors(
        json_output=json_output,
        selection_type=GrahamGrowthSelection,
        provider_check=provider_check,
    ) as scope:
        target_ticker = _resolve_ticker(ticker, ticker_option, command="graham-growth")
        assert target_ticker is not None
        scope.ticker = target_ticker
        mode = _presentation_mode(details=details, diagnostics=diagnostics, json_output=json_output)
        scope.mode = mode
        boundary = _parse_as_of(as_of)
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
        with _production_financial_cache(use_cache=use_cache, clock=lambda: executed_at) as cache:
            with execution_errors(
                mode=mode,
                selection_type=GrahamGrowthSelection,
                ticker=target_ticker,
            ):
                resolver = build_graham_resolver(
                    resolver_type=GrahamGrowthInputResolver,
                    cache=cache,
                    clock=lambda: executed_at,
                )
            output, exit_code = _run_graham_growth(
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


def _run_graham_growth(  # noqa: PLR0913
    *,
    resolver: GrahamGrowthInputResolver,
    ticker: str,
    selection: GrahamGrowthSelection,
    mode: PresentationMode,
    profile_provider: object,
    executed_at: datetime,
    save_run: bool = False,
    provider_check: ProviderCheckChoice | None = None,
) -> tuple[str, int]:
    """Resolve, calculate, and render one Graham growth-value analysis."""
    policy = graham_growth_settings().to_policy()
    config = selection.to_graham_growth_config()
    as_of = selection.as_of
    use_cache = selection.use_cache
    stage = SaveStage()
    with saving_failures(stage):
        capture = maybe_save_run(
            save_run=save_run,
            executed_at=executed_at,
            request_factory=lambda: AnalysisRequest(ticker=ticker, selection=selection),
            run_adapter=lambda profile_cache: execute_graham_growth(
                resolver,
                ticker,
                config,
                policy,
                profile_provider,
                as_of=as_of,
                executed_at=executed_at,
                use_cache=use_cache,
                profile_cache=profile_cache,
            ),
            normalize=stage.after_analysis(from_graham_growth_capture),
        )
    execution = from_graham_growth_capture(capture)
    exit_code = exit_code_of(execution.outcome)
    analysis = capture.analysis
    profile = capture.profile
    assembly = analysis.assembly
    identity_resolution = profile_identity_resolution(profile)

    if assembly.status is not CalculationStatus.OK:
        if assembly.status is CalculationStatus.NOT_APPLICABLE:
            presentation = GrahamGrowthPresentation(
                ticker=ticker,
                assembly=assembly,
                result=analysis.result,
                price_comparison=analysis.price_comparison,
                base_pe=policy.base_pe,
                growth_multiplier=policy.growth_multiplier,
                baseline_aaa_yield=policy.baseline_aaa_yield,
                as_of=as_of,
                effective_as_of=analysis.effective_as_of,
                identity_resolution=identity_resolution,
                instrument_profile=profile,
            )
            return render_graham_growth(presentation, mode), exit_code
        findings = provider_check_findings((execution.provider_failure,), provider_check)
        failure_output = _growth_failure_output(
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
        return with_provider_check(failure_output, findings, mode), exit_code

    presentation_assembly = growth_with_public_quote_reason(assembly)
    presentation = GrahamGrowthPresentation(
        ticker=ticker,
        assembly=presentation_assembly,
        result=analysis.result,
        base_pe=policy.base_pe,
        growth_multiplier=policy.growth_multiplier,
        baseline_aaa_yield=policy.baseline_aaa_yield,
        as_of=as_of,
        effective_as_of=analysis.effective_as_of,
        margin_of_safety_percent=analysis.margin_of_safety_percent,
        price_comparison=analysis.price_comparison,
        identity_resolution=identity_resolution,
        instrument_profile=profile,
    )
    return render_graham_growth(presentation, mode), exit_code


def _growth_failure_output(  # noqa: PLR0913
    *,
    ticker: str,
    assembly: GrowthValueInputAssembly,
    as_of: datetime | None,
    effective_as_of: datetime,
    mode: PresentationMode,
    identity_resolution: SecurityIdentityResolution,
    instrument_profile: InstrumentProfile,
    price_comparison: PriceComparison | None = None,
    provider_check: tuple[ProviderCheckItem, ...] | None = None,
) -> str:
    """Render a failed growth analysis without leaking low-level details by default."""
    reason = friendly_valuation_failure(ticker, assembly.status, assembly.reason)
    safe_assembly = growth_with_public_quote_reason(replace(assembly, reason=reason))
    policy = graham_growth_settings().to_policy()
    presentation = GrahamGrowthPresentation(
        ticker=ticker,
        assembly=safe_assembly,
        price_comparison=price_comparison,
        result=None,
        base_pe=policy.base_pe,
        growth_multiplier=policy.growth_multiplier,
        baseline_aaa_yield=policy.baseline_aaa_yield,
        as_of=as_of,
        effective_as_of=effective_as_of,
        identity_resolution=identity_resolution,
        instrument_profile=instrument_profile,
        provider_check=provider_check,
    )
    return render_graham_growth(presentation, mode)
