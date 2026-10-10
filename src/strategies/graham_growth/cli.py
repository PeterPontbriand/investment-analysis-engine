"""Graham Growth's CLI-layer functions: the direct command, the watchlist selection builder and the refresh executor.

The CLI tier pairs these with the Graham Growth core bundle and adds the command to the application; nothing here
registers itself.
"""

from dataclasses import replace
from datetime import datetime

import typer

from src.analysis.shared.financial_resolution import PriceComparison
from src.cli_composition import build_graham_resolver, growth_assumptions
from src.cli_run_support import maybe_save_run
from src.cli_support import (
    _canonical_provider_id,
    _parse_as_of,
    _presentation_mode,
    _production_financial_cache,
    _resolve_ticker,
    config_usage_errors,
    execution_errors,
)
from src.cli_watchlist_flags import WatchlistFlags
from src.core.analysis_status import CalculationStatus
from src.core.clock import utc_now
from src.data.financial.providers import SEC_PROVIDER_ID
from src.data.instrument_profile import InstrumentProfile, profile_identity_resolution
from src.data.instrument_profile_cache import InstrumentProfileResolver
from src.data.security_identity import SecurityIdentityResolution
from src.data.yfinance import YFinanceClient
from src.reporting.evidence_presentation import friendly_valuation_failure
from src.reporting.presentation import PresentationMode
from src.strategies.graham_growth.calculation import GrahamGrowthInputResolver, GrowthValueInputAssembly
from src.strategies.graham_growth.config import GrahamGrowthConfig
from src.strategies.graham_growth.execution import execute_graham_growth, from_graham_growth_capture
from src.strategies.graham_growth.presenter import (
    GrahamGrowthPresentation,
    growth_with_public_quote_reason,
    render_graham_growth,
)
from src.strategies.graham_growth.selection import GrahamGrowthSelection
from src.workspace.capture import ExecutionCapture
from src.workspace.requests import AnalysisRequest


def build_selection(flags: WatchlistFlags) -> GrahamGrowthSelection:
    """Build one validated Graham Growth selection from watchlist CLI flags.

    Mirrors the direct ``graham-growth`` command's own flags and validation exactly, so a watchlist entry
    behaves identically to running the method directly.
    """
    boundary = _parse_as_of(flags.as_of)
    provider_id = _canonical_provider_id(flags.data_provider) or SEC_PROVIDER_ID
    with config_usage_errors():
        if flags.expected_growth is None:
            raise typer.BadParameter("Required when --analysis is graham-growth.", param_hint="--expected-growth")
        if flags.aaa_yield is None:
            raise typer.BadParameter("Required when --analysis is graham-growth.", param_hint="--aaa-yield")
        return GrahamGrowthSelection.model_validate(
            {
                "security_provider_id": provider_id,
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
    config = selection.to_graham_growth_config()
    policy = growth_assumptions()
    executed_at = utc_now()
    with _production_financial_cache(use_cache=selection.use_cache, clock=lambda: executed_at) as cache:
        resolver = build_graham_resolver(
            resolver_type=GrahamGrowthInputResolver,
            data_provider=config.security_provider_id,
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
    eps_basis: str | None = typer.Option(
        None,
        "--eps-basis",
        help=(
            "EPS basis; Number defaults to three_year_average and accepts ttm with Massive; "
            "Growth defaults to three_year_average with SEC EDGAR (also accepts an explicit "
            "fiscal_year basis for reviewed workflows) and ttm with Massive"
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
) -> None:
    """Execute Graham Growth Value with explicit growth and AAA-yield assumptions."""
    target_ticker = _resolve_ticker(ticker, ticker_option, required=True, command="graham-growth")
    assert target_ticker is not None
    mode = _presentation_mode(details=details, diagnostics=diagnostics, json_output=json_output)
    boundary = _parse_as_of(as_of)
    provider_id = _canonical_provider_id(data_provider) or SEC_PROVIDER_ID
    use_cache = not no_cache
    executed_at = utc_now()
    # Permissive by design: see graham_number's identical comment above.
    with config_usage_errors():
        config = GrahamGrowthConfig.model_validate(
            {
                "security_provider_id": provider_id,
                "eps_basis": eps_basis,
                "eps_override": eps,
                "quote_override": current_price,
                "expected_growth": expected_growth,
                "aaa_yield_override": aaa_yield,
            }
        )
    with (
        execution_errors(
            mode=mode,
            selection_type=GrahamGrowthSelection,
            ticker=target_ticker,
            unexpected=lambda _exc: f"Graham analysis failed unexpectedly for {target_ticker}.",
        ),
        _production_financial_cache(use_cache=use_cache, clock=lambda: executed_at) as cache,
    ):
        with execution_errors(
            mode=mode,
            selection_type=GrahamGrowthSelection,
            ticker=target_ticker,
            invalid=lambda exc: f"Unable to start Graham analysis: {exc}",
            unexpected=lambda _exc: f"Graham analysis failed unexpectedly for {target_ticker}.",
        ):
            resolver = build_graham_resolver(
                resolver_type=GrahamGrowthInputResolver,
                data_provider=config.security_provider_id,
                cache=cache,
                clock=lambda: executed_at,
            )
        output, exit_code = _run_graham_growth(
            resolver=resolver,
            ticker=target_ticker,
            config=config,
            mode=mode,
            profile_provider=YFinanceClient(),
            as_of=boundary,
            executed_at=executed_at,
            use_cache=use_cache,
            save_run=save_run,
        )
    typer.echo(output, err=exit_code != 0 and mode in (PresentationMode.CONCISE, PresentationMode.DETAILS))
    if exit_code:
        raise typer.Exit(code=exit_code)


def _run_graham_growth(  # noqa: PLR0913
    *,
    resolver: GrahamGrowthInputResolver,
    ticker: str,
    config: GrahamGrowthConfig,
    mode: PresentationMode,
    profile_provider: object,
    as_of: datetime | None,
    executed_at: datetime,
    use_cache: bool,
    save_run: bool = False,
) -> tuple[str, int]:
    """Resolve, calculate, and render one Graham growth-value analysis."""
    policy = growth_assumptions()
    capture = maybe_save_run(
        save_run=save_run,
        executed_at=executed_at,
        request_factory=lambda: AnalysisRequest(
            ticker=ticker,
            selection=GrahamGrowthSelection(
                security_provider_id=config.security_provider_id,
                quote_provider_id=config.quote_provider_id,
                eps_basis=config.eps_basis,
                eps_override=config.eps_override,
                quote_override=config.quote_override,
                expected_growth=config.expected_growth,
                aaa_yield_override=config.aaa_yield_override,
                as_of=as_of,
                use_cache=use_cache,
            ),
        ),
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
        normalize=from_graham_growth_capture,
    )
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
            return render_graham_growth(presentation, mode), 0
        return _growth_failure_output(
            ticker=ticker,
            assembly=assembly,
            as_of=as_of,
            effective_as_of=analysis.effective_as_of,
            mode=mode,
            identity_resolution=identity_resolution,
            instrument_profile=profile,
            price_comparison=analysis.price_comparison,
        )

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
    exit_code = 1 if analysis.result.status is CalculationStatus.INVALID_INPUT else 0
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
) -> tuple[str, int]:
    """Render a failed growth analysis without leaking low-level details by default."""
    reason = friendly_valuation_failure(ticker, assembly.status, assembly.reason)
    safe_assembly = growth_with_public_quote_reason(replace(assembly, reason=reason))
    policy = growth_assumptions()
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
    )
    return render_graham_growth(presentation, mode), 1
