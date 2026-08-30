"""Command Line Interface routing for the Financial Data Agents execution suite."""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import UTC, date, datetime, time
from enum import StrEnum
from typing import Annotated

import typer

from src.analysis.fcf_earnings_growth import (
    FCFClassificationBasis,
    FCFEarningsGrowthAnalyzer,
    FCFEarningsGrowthPolicy,
    ForwardPolicy,
    HistoricalHorizon,
    ProductionAnnualGrowthSeriesResolver,
)
from src.analysis.graham_value.calculators import compute_graham_growth_value, compute_graham_number
from src.analysis.graham_value.input_resolver import (
    GrahamInputResolver,
    GrahamNumberInputAssembly,
    GrowthValueInputAssembly,
)
from src.analysis.momentum.momentum_analyzer import MomentumAnalyzer, MomentumConfig
from src.config import settings
from src.core.analysis_status import CalculationStatus
from src.core.constants import ConfigKeys
from src.core.telemetry import RunContext
from src.core.telemetry.run_context import get_current_run_context, set_current_run_context
from src.data.base_client import DataFetchError
from src.data.financial.cache import InMemoryResolvedInputCache
from src.data.financial.facts import FinancialFactsProvider
from src.data.financial.provenance import ResolvedInput, SourceKind
from src.data.financial.providers import (
    MASSIVE_PROVIDER_ID,
    SEC_PROVIDER_ID,
    YFINANCE_PROVIDER_ID,
    MassiveFinancialFactsAdapter,
    ProductionFinancialFactsProvider,
    SecEdgarFinancialFactsAdapter,
)
from src.data.security_identity import (
    SecurityIdentityRequest,
    SecurityIdentityResolution,
    resolve_security_identity,
)
from src.data.yfinance import YFinanceClient
from src.reporting.fcf_earnings_growth import render_fcf_earnings_growth
from src.reporting.graham import (
    GrahamGrowthPresentation,
    GrahamNumberPresentation,
    render_graham_growth,
    render_graham_number,
)
from src.reporting.momentum import MomentumPresentation, render_momentum
from src.reporting.presentation import PresentationMode

app = typer.Typer(help="Financial Data Agents Command Line Interface")

_AAA_OVERRIDE_PROVIDER_ID = "user_override"
_MOMENTUM_CLI_DEFAULTS = MomentumConfig()


class GrahamCliMethod(StrEnum):
    """User-facing method choices for direct Graham analysis."""

    NUMBER = "number"
    GROWTH = "growth"


@app.callback()
def main_entry_point() -> None:
    """Initialize one RunContext for this CLI invocation if main.py did not."""
    if get_current_run_context() is None:
        set_current_run_context(RunContext.new())


def get_cli_run_context() -> RunContext:
    """Return the explicit execution identity for the current CLI invocation."""
    context = get_current_run_context()
    if context is None:
        raise RuntimeError("CLI RunContext has not been initialized.")
    return context


@app.command(name="momentum")
def momentum(  # noqa: PLR0913
    ticker: str | None = typer.Argument(None, help="Target stock/asset ticker symbol (e.g., AAPL, BTC-USD)"),
    *,
    ticker_option: str | None = typer.Option(
        None,
        "--ticker",
        "-t",
        help="Legacy ticker option; prefer the positional TICKER argument",
    ),
    short_window: int = typer.Option(
        _MOMENTUM_CLI_DEFAULTS.short_window,
        "--short-window",
        "-s",
        help="Short SMA window in daily market observations",
    ),
    long_window: int = typer.Option(
        _MOMENTUM_CLI_DEFAULTS.long_window,
        "--long-window",
        "-l",
        help="Long SMA window in daily market observations",
    ),
    rsi_period: int = typer.Option(
        _MOMENTUM_CLI_DEFAULTS.rsi_period,
        "--rsi-period",
        help="RSI lookback period in daily market observations",
    ),
    details: bool = typer.Option(False, "--details", help="Show calculation and data-context details"),
    diagnostics: bool = typer.Option(False, "--diagnostics", help="Show retained execution diagnostics"),
    json_output: bool = typer.Option(False, "--json", help="Emit stable machine-readable JSON"),
) -> None:
    """Execute SMA crossover momentum analysis over daily historical market prices."""
    target_ticker = _resolve_ticker(ticker, ticker_option, required=False)
    mode = _presentation_mode(details=details, diagnostics=diagnostics, json_output=json_output)
    _validate_momentum_windows(short_window, long_window, rsi_period)

    try:
        data_client = YFinanceClient()
        analyzer = MomentumAnalyzer(default_ticker=target_ticker, data_client=data_client)
        config = MomentumConfig(short_window=short_window, long_window=long_window, rsi_period=rsi_period)
        run = analyzer.run_with_context(config=config, ticker=target_ticker)
        identity_resolution = resolve_security_identity(
            data_client,
            SecurityIdentityRequest(ticker=run.metrics.ticker, provider_id=data_client.provider_id),
        )
        presentation = MomentumPresentation(
            metrics=run.metrics,
            config=config,
            market_data=run.market_data,
            identity_resolution=identity_resolution,
        )
        typer.echo(render_momentum(presentation, mode))
    except DataFetchError as err:
        label = target_ticker or "the configured default ticker"
        typer.echo(
            f"Unable to analyze {label}: no usable market data was returned. Verify the ticker symbol and try again.",
            err=True,
        )
        raise typer.Exit(code=1) from err
    except ValueError as err:
        label = target_ticker or "the configured default ticker"
        typer.echo(
            f"Unable to complete momentum analysis for {label}: the returned price history could not be analyzed.",
            err=True,
        )
        raise typer.Exit(code=1) from err
    except Exception as err:
        label = target_ticker or "the configured default ticker"
        typer.echo(f"Momentum analysis failed unexpectedly for {label}.", err=True)
        raise typer.Exit(code=1) from err


@app.command(name="graham")
def graham(  # noqa: PLR0913
    ticker: str | None = typer.Argument(None, help="Target stock ticker symbol (e.g., AAPL, KO)"),
    *,
    ticker_option: str | None = typer.Option(
        None,
        "--ticker",
        "-t",
        help="Legacy ticker option; prefer the positional TICKER argument",
    ),
    method: Annotated[
        GrahamCliMethod,
        typer.Option(
            "--method",
            "-m",
            help="Graham method: 'number' (default) or 'growth'",
        ),
    ] = GrahamCliMethod.NUMBER,
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
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass the in-memory resolved-input cache"),
    eps: float | None = typer.Option(None, "--eps", "-e", help="Explicit EPS override"),
    eps_basis: str | None = typer.Option(
        None,
        "--eps-basis",
        help=(
            "EPS basis; Number defaults to three_year_average; Growth defaults to "
            "three_year_average with SEC EDGAR and ttm with Massive"
        ),
    ),
    bvps: float | None = typer.Option(
        None, "--bvps", help="Explicit book value per common share override (Number only)"
    ),
    expected_growth: float | None = typer.Option(
        None,
        "--expected-growth",
        "--expected-growth-rate",
        "-g",
        help="Expected annual growth in percentage points (growth method; explicit user assumption)",
    ),
    aaa_yield: float | None = typer.Option(
        None,
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
) -> None:
    """Execute direct Benjamin Graham analysis for one ticker."""
    target_ticker = _resolve_ticker(ticker, ticker_option, required=True)
    assert target_ticker is not None
    mode = _presentation_mode(details=details, diagnostics=diagnostics, json_output=json_output)
    analysis_as_of = _parse_as_of(as_of)
    requested_provider_id = _canonical_provider_id(data_provider)
    provider_id = _effective_graham_provider_id(method, requested_provider_id)
    selected_eps_basis = _validate_graham_options(
        method=method,
        provider_id=provider_id,
        eps_basis=eps_basis,
        bvps=bvps,
        expected_growth=expected_growth,
        aaa_yield=aaa_yield,
    )

    try:
        resolver = _build_graham_resolver(method=method, data_provider=provider_id)
    except ValueError as err:
        typer.echo(f"Unable to start Graham analysis: {err}", err=True)
        raise typer.Exit(code=1) from err

    try:
        if method is GrahamCliMethod.NUMBER:
            output, exit_code = _run_graham_number(
                resolver=resolver,
                ticker=target_ticker,
                security_provider_id=provider_id,
                quote_provider_id=_quote_provider_id(GrahamCliMethod.NUMBER, provider_id),
                eps_basis=selected_eps_basis,
                eps_override=eps,
                bvps_override=bvps,
                quote_override=current_price,
                as_of=analysis_as_of,
                use_cache=not no_cache,
                mode=mode,
            )
        else:
            assert expected_growth is not None
            assert aaa_yield is not None
            output, exit_code = _run_graham_growth(
                resolver=resolver,
                ticker=target_ticker,
                security_provider_id=provider_id,
                quote_provider_id=_quote_provider_id(GrahamCliMethod.GROWTH, provider_id),
                eps_basis=selected_eps_basis,
                eps_override=eps,
                expected_growth=expected_growth,
                aaa_yield_override=aaa_yield,
                quote_override=current_price,
                as_of=analysis_as_of,
                use_cache=not no_cache,
                mode=mode,
            )
    except Exception as err:
        typer.echo(f"Graham analysis failed unexpectedly for {target_ticker}.", err=True)
        raise typer.Exit(code=1) from err

    typer.echo(output, err=exit_code != 0 and mode in (PresentationMode.CONCISE, PresentationMode.DETAILS))
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


@app.command(name="fcf-growth")
def fcf_growth(  # noqa: PLR0913
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
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass the in-memory resolved-input cache"),
    details: bool = typer.Option(False, "--details", help="Show annual facts, provenance, and derivation lineage"),
    diagnostics: bool = typer.Option(False, "--diagnostics", help="Show resolver execution trace"),
    json_output: bool = typer.Option(False, "--json", help="Emit the complete versioned typed result"),
) -> None:
    """Execute the historical free-cash-flow and diluted-EPS growth screen."""
    target_ticker = _resolve_ticker(ticker, None, required=True)
    assert target_ticker is not None
    mode = _presentation_mode(details=details, diagnostics=diagnostics, json_output=json_output)
    horizon = _historical_horizon(growth_years)
    analysis_as_of = _parse_as_of(as_of)
    provider_id = _canonical_provider_id(data_provider) or SEC_PROVIDER_ID
    normalized_currency = currency.strip().upper()
    if len(normalized_currency) != 3 or not normalized_currency.isalpha():
        raise typer.BadParameter("--currency must be a three-letter ISO 4217 code.")
    policy = FCFEarningsGrowthPolicy(
        historical_horizon=horizon,
        classification_basis=_fcf_classification_basis(classification_basis),
        forward_policy=_forward_policy(forward_policy),
    )
    boundary = analysis_as_of or datetime.now(UTC)

    try:
        provider = _build_sec_production_provider()
        resolver = ProductionAnnualGrowthSeriesResolver(
            provider,
            cache=InMemoryResolvedInputCache(),
            clock=lambda: boundary,
        )
        result = FCFEarningsGrowthAnalyzer(resolver).run_analysis(
            ticker=target_ticker,
            policy=policy,
            currency=normalized_currency,
            as_of=analysis_as_of,
            provider_id=provider_id,
            use_cache=not no_cache,
            effective_as_of=boundary,
        )
        identity_resolution = resolve_security_identity(
            provider,
            SecurityIdentityRequest(ticker=target_ticker, provider_id=provider_id),
        )
    except ValueError as err:
        typer.echo(f"Unable to start FCF & earnings-growth analysis: {err}", err=True)
        raise typer.Exit(code=1) from err
    except Exception as err:
        typer.echo(f"FCF & earnings-growth analysis failed unexpectedly for {target_ticker}.", err=True)
        raise typer.Exit(code=1) from err

    output = render_fcf_earnings_growth(result, mode, identity_resolution)
    exit_code = 0 if result.execution_status is CalculationStatus.OK else 1
    typer.echo(output, err=exit_code != 0 and mode in (PresentationMode.CONCISE, PresentationMode.DETAILS))
    if exit_code:
        raise typer.Exit(code=exit_code)


def _build_sec_production_provider() -> ProductionFinancialFactsProvider:
    """Build the SEC-backed production provider from declared application identity."""
    user_agent = settings.sec_user_agent
    if user_agent is None or not user_agent.strip():
        raise ValueError(
            "SEC EDGAR access is not configured. "
            "Set SEC_USER_AGENT to a declared identity such as "
            '"Your Name your-email@example.com" and retry.'
        )
    sec_edgar = SecEdgarFinancialFactsAdapter(user_agent=user_agent)
    return ProductionFinancialFactsProvider(sec_edgar=sec_edgar)


def _build_massive_production_provider() -> MassiveFinancialFactsAdapter:
    """Build Massive only when usable API credentials are configured."""
    massive = MassiveFinancialFactsAdapter()
    if not massive.is_configured:
        raise ValueError("Massive access is not configured. Set MASSIVE_API_KEY and retry.")
    return massive


def _build_graham_resolver(*, method: GrahamCliMethod, data_provider: str | None) -> GrahamInputResolver:
    """Build only the production provider capabilities needed by this invocation."""
    provider: FinancialFactsProvider
    if data_provider == MASSIVE_PROVIDER_ID:
        provider = _build_massive_production_provider()
    elif data_provider == SEC_PROVIDER_ID:
        provider = _build_sec_production_provider()
    elif data_provider is not None:
        raise ValueError(
            f"Unsupported valuation data provider {data_provider!r}; "
            f"supported providers are {SEC_PROVIDER_ID!r} and {MASSIVE_PROVIDER_ID!r}."
        )
    elif method in (GrahamCliMethod.NUMBER, GrahamCliMethod.GROWTH):
        provider = _build_sec_production_provider()
    else:
        raise AssertionError(f"Unhandled Graham method: {method!r}")

    return GrahamInputResolver(provider, cache=InMemoryResolvedInputCache())


def _effective_graham_provider_id(method: GrahamCliMethod, data_provider: str | None) -> str:
    """Select the investor-facing default security-fact provider."""
    if data_provider is not None:
        return data_provider
    if method in (GrahamCliMethod.NUMBER, GrahamCliMethod.GROWTH):
        return SEC_PROVIDER_ID
    raise AssertionError(f"Unhandled Graham method: {method!r}")


def _quote_provider_id(method: GrahamCliMethod, data_provider: str | None) -> str:
    """Select the approved quote source for the effective security-fact provider."""
    if data_provider is not None and data_provider not in (SEC_PROVIDER_ID, MASSIVE_PROVIDER_ID):
        return data_provider
    if data_provider == MASSIVE_PROVIDER_ID:
        return MASSIVE_PROVIDER_ID
    if method in (GrahamCliMethod.NUMBER, GrahamCliMethod.GROWTH):
        return YFINANCE_PROVIDER_ID
    raise AssertionError(f"Unhandled Graham method: {method!r}")


def _run_graham_number(  # noqa: PLR0913
    *,
    resolver: GrahamInputResolver,
    ticker: str,
    security_provider_id: str,
    quote_provider_id: str,
    eps_basis: str,
    eps_override: float | None,
    bvps_override: float | None,
    quote_override: float | None,
    as_of: datetime | None,
    use_cache: bool,
    mode: PresentationMode,
) -> tuple[str, int]:
    """Resolve, calculate, and render one Graham Number analysis."""
    assembly = resolver.assemble_graham_number(
        security_subject_id=ticker,
        security_provider_id=security_provider_id,
        eps_basis=eps_basis,
        eps_override=eps_override,
        bvps_override=bvps_override,
        quote_override=quote_override,
        quote_provider_id=quote_provider_id,
        as_of=as_of,
        use_cache=use_cache,
    )
    identity_resolution = resolve_security_identity(
        resolver.provider,
        SecurityIdentityRequest(ticker=ticker, provider_id=security_provider_id),
    )

    if assembly.status is not CalculationStatus.OK:
        return _number_failure_output(
            ticker=ticker,
            assembly=assembly,
            as_of=as_of,
            mode=mode,
            identity_resolution=identity_resolution,
        )

    if not _has_provider_backed_security_evidence(assembly.eps, assembly.bvps, assembly.current_price):
        reason = _unverified_ticker_reason(ticker)
        unverified = replace(assembly, status=CalculationStatus.INPUT_UNAVAILABLE, reason=reason)
        return _number_failure_output(
            ticker=ticker,
            assembly=unverified,
            as_of=as_of,
            mode=mode,
            identity_resolution=identity_resolution,
        )

    assert assembly.eps is not None
    assert assembly.bvps is not None
    result = compute_graham_number(assembly.eps.value, assembly.bvps.value)
    valuation_currency = _common_currency(assembly.eps, assembly.bvps)
    margin = _margin_of_safety(
        result.maximum_indicated_price,
        assembly.current_price,
        valuation_currency=valuation_currency,
    )
    presentation_assembly = _number_with_public_quote_reason(assembly)
    presentation = GrahamNumberPresentation(
        ticker=ticker,
        assembly=presentation_assembly,
        result=result,
        as_of=as_of,
        margin_of_safety_percent=margin,
        identity_resolution=identity_resolution,
    )
    exit_code = 1 if result.status is CalculationStatus.INVALID_INPUT else 0
    return render_graham_number(presentation, mode), exit_code


def _run_graham_growth(  # noqa: PLR0913
    *,
    resolver: GrahamInputResolver,
    ticker: str,
    security_provider_id: str,
    quote_provider_id: str,
    eps_basis: str,
    eps_override: float | None,
    expected_growth: float,
    aaa_yield_override: float,
    quote_override: float | None,
    as_of: datetime | None,
    use_cache: bool,
    mode: PresentationMode,
) -> tuple[str, int]:
    """Resolve, calculate, and render one Graham growth-value analysis."""
    assembly = resolver.assemble_growth_value(
        security_subject_id=ticker,
        security_provider_id=security_provider_id,
        eps_basis=eps_basis,
        eps_override=eps_override,
        expected_growth=expected_growth,
        aaa_subject_id="AAA",
        aaa_provider_id=_AAA_OVERRIDE_PROVIDER_ID,
        aaa_yield_override=aaa_yield_override,
        quote_override=quote_override,
        quote_provider_id=quote_provider_id,
        as_of=as_of,
        use_cache=use_cache,
    )
    identity_resolution = resolve_security_identity(
        resolver.provider,
        SecurityIdentityRequest(ticker=ticker, provider_id=security_provider_id),
    )

    if assembly.status is not CalculationStatus.OK:
        return _growth_failure_output(
            ticker=ticker,
            assembly=assembly,
            as_of=as_of,
            mode=mode,
            identity_resolution=identity_resolution,
        )

    if not _has_provider_backed_security_evidence(assembly.eps, assembly.current_price):
        reason = _unverified_ticker_reason(ticker)
        unverified = replace(assembly, status=CalculationStatus.INPUT_UNAVAILABLE, reason=reason)
        return _growth_failure_output(
            ticker=ticker,
            assembly=unverified,
            as_of=as_of,
            mode=mode,
            identity_resolution=identity_resolution,
        )

    assert assembly.eps is not None
    assert assembly.expected_growth is not None
    assert assembly.current_aaa_yield is not None
    base_pe, growth_multiplier, baseline_aaa_yield = _growth_assumptions()
    result = compute_graham_growth_value(
        normalized_eps=assembly.eps.value,
        expected_growth_rate=assembly.expected_growth.value,
        current_aaa_yield=assembly.current_aaa_yield.value,
        base_pe=base_pe,
        growth_multiplier=growth_multiplier,
        baseline_aaa_yield=baseline_aaa_yield,
    )
    margin = _margin_of_safety(
        result.growth_value,
        assembly.current_price,
        valuation_currency=assembly.eps.currency,
    )
    presentation_assembly = _growth_with_public_quote_reason(assembly)
    presentation = GrahamGrowthPresentation(
        ticker=ticker,
        assembly=presentation_assembly,
        result=result,
        base_pe=base_pe,
        growth_multiplier=growth_multiplier,
        baseline_aaa_yield=baseline_aaa_yield,
        as_of=as_of,
        margin_of_safety_percent=margin,
        identity_resolution=identity_resolution,
    )
    exit_code = 1 if result.status is CalculationStatus.INVALID_INPUT else 0
    return render_graham_growth(presentation, mode), exit_code


def _number_failure_output(
    *,
    ticker: str,
    assembly: GrahamNumberInputAssembly,
    as_of: datetime | None,
    mode: PresentationMode,
    identity_resolution: SecurityIdentityResolution,
) -> tuple[str, int]:
    """Render a failed Number analysis without leaking low-level details by default."""
    reason = _friendly_graham_failure(ticker, assembly.status, assembly.reason)
    safe_assembly = _number_with_public_quote_reason(replace(assembly, reason=reason))
    presentation = GrahamNumberPresentation(
        ticker=ticker,
        assembly=safe_assembly,
        result=None,
        as_of=as_of,
        identity_resolution=identity_resolution,
    )
    return render_graham_number(presentation, mode), 1


def _growth_failure_output(
    *,
    ticker: str,
    assembly: GrowthValueInputAssembly,
    as_of: datetime | None,
    mode: PresentationMode,
    identity_resolution: SecurityIdentityResolution,
) -> tuple[str, int]:
    """Render a failed growth analysis without leaking low-level details by default."""
    reason = _friendly_graham_failure(ticker, assembly.status, assembly.reason)
    safe_assembly = _growth_with_public_quote_reason(replace(assembly, reason=reason))
    base_pe, growth_multiplier, baseline_aaa_yield = _growth_assumptions()
    presentation = GrahamGrowthPresentation(
        ticker=ticker,
        assembly=safe_assembly,
        result=None,
        base_pe=base_pe,
        growth_multiplier=growth_multiplier,
        baseline_aaa_yield=baseline_aaa_yield,
        as_of=as_of,
        identity_resolution=identity_resolution,
    )
    return render_graham_growth(presentation, mode), 1


def _number_with_public_quote_reason(assembly: GrahamNumberInputAssembly) -> GrahamNumberInputAssembly:
    """Classify optional quote failures while preserving raw resolver trace events."""
    if assembly.quote_status is None:
        return assembly
    return replace(assembly, quote_reason=_public_quote_reason(assembly.quote_status))


def _growth_with_public_quote_reason(assembly: GrowthValueInputAssembly) -> GrowthValueInputAssembly:
    """Classify optional quote failures while preserving raw resolver trace events."""
    if assembly.quote_status is None:
        return assembly
    return replace(assembly, quote_reason=_public_quote_reason(assembly.quote_status))


def _public_quote_reason(status: CalculationStatus) -> str:
    """Return a stable investor-facing explanation for optional quote failure."""
    if status is CalculationStatus.PROVIDER_ERROR:
        return "The configured quote provider could not complete the request."
    if status is CalculationStatus.INPUT_UNAVAILABLE:
        return "No eligible current quote was available from the configured quote source."
    return "The current quote could not be used for price comparison."


def _friendly_graham_failure(ticker: str, status: CalculationStatus, reason: str | None) -> str:
    """Map resolver failure classes to concise investor-facing errors."""
    if reason is not None and reason.startswith("Unable to verify ticker"):
        return reason
    if status is CalculationStatus.PROVIDER_ERROR:
        return (
            f"Unable to analyze {ticker}: provider-backed security data retrieval failed. "
            "Verify the ticker and provider configuration."
        )
    if status is CalculationStatus.INPUT_UNAVAILABLE:
        return (
            f"Unable to analyze {ticker}: required financial data is unavailable. "
            "Verify the ticker, provider, and requested data basis."
        )
    return f"Unable to analyze {ticker}: the requested Graham inputs are invalid. Review the method and overrides."


def _unverified_ticker_reason(ticker: str) -> str:
    """Return the trust-boundary failure for an entirely override-driven security."""
    return (
        f"Unable to verify ticker {ticker}: no provider-backed security fact or quote was resolved. "
        "Fully override-driven security analysis is not accepted in v0.2."
    )


def _has_provider_backed_security_evidence(*inputs: ResolvedInput | None) -> bool:
    """Return whether at least one security fact carries non-override provenance."""
    return any(value is not None and value.source_kind is not SourceKind.OVERRIDE for value in inputs)


def _margin_of_safety(
    reference_value: float | None,
    current_price: ResolvedInput | None,
    *,
    valuation_currency: str | None = None,
) -> float | None:
    """Compute comparison only when value, quote, and known currencies are compatible."""
    if reference_value is None or current_price is None or reference_value <= 0:
        return None
    if (
        valuation_currency is not None
        and current_price.currency is not None
        and valuation_currency != current_price.currency
    ):
        return None
    margin = ((reference_value - current_price.value) / reference_value) * 100.0
    return margin if math.isfinite(margin) else None


def _common_currency(*inputs: ResolvedInput | None) -> str | None:
    """Return one shared known currency, or None when inputs disagree or omit it."""
    currencies = {item.currency for item in inputs if item is not None and item.currency}
    return next(iter(currencies)) if len(currencies) == 1 else None


def _growth_assumptions() -> tuple[float, float, float]:
    """Read the configured constants for the growth-value method."""
    values = settings.get_graham_value_analysis()[ConfigKeys.GRAHAM_VALUES]
    return (
        float(values[ConfigKeys.BASE_PE]),
        float(values[ConfigKeys.GROWTH_MULTIPLIER]),
        float(values[ConfigKeys.BASELINE_AAA_YIELD]),
    )


def _validate_graham_options(  # noqa: PLR0912, PLR0913
    *,
    method: GrahamCliMethod,
    provider_id: str,
    eps_basis: str | None,
    bvps: float | None,
    expected_growth: float | None,
    aaa_yield: float | None,
) -> str:
    """Validate method/provider CLI combinations and select the EPS basis."""
    normalized_basis = eps_basis.strip().lower() if eps_basis is not None else None
    if normalized_basis == "":
        raise typer.BadParameter("--eps-basis must be non-empty when supplied.")

    if method is GrahamCliMethod.NUMBER:
        if expected_growth is not None:
            raise typer.BadParameter("--expected-growth is valid only with --method growth.")
        if aaa_yield is not None:
            raise typer.BadParameter("--aaa-yield is valid only with --method growth.")
        selected = normalized_basis or "three_year_average"
        if selected not in ("three_year_average", "ttm"):
            raise typer.BadParameter("Number EPS basis must be 'three_year_average' or 'ttm'.")
        if provider_id == MASSIVE_PROVIDER_ID and (selected != "ttm" or bvps is None):
            raise typer.BadParameter("Massive Graham Number requires --eps-basis ttm and an explicit --bvps override.")
        if provider_id == SEC_PROVIDER_ID and selected != "three_year_average":
            raise typer.BadParameter(
                "SEC EDGAR Graham Number supports --eps-basis three_year_average only; "
                "use --data-provider massive with --bvps for TTM EPS."
            )
        return selected

    if bvps is not None:
        raise typer.BadParameter("--bvps is valid only with --method number.")
    if expected_growth is None:
        raise typer.BadParameter("--expected-growth is required with --method growth.")
    if aaa_yield is None:
        raise typer.BadParameter(
            "--aaa-yield is required with --method growth because no production AAA-yield series is approved yet."
        )

    if provider_id == SEC_PROVIDER_ID:
        selected = normalized_basis or "three_year_average"
        if selected != "three_year_average":
            raise typer.BadParameter(
                "SEC EDGAR Growth analysis supports --eps-basis three_year_average only; "
                "use --data-provider massive for TTM EPS."
            )
        return selected

    if provider_id == MASSIVE_PROVIDER_ID:
        selected = normalized_basis or "ttm"
        if selected != "ttm":
            raise typer.BadParameter(
                "Massive Growth analysis supports --eps-basis ttm only; "
                "use --data-provider sec_edgar for three-year-average EPS."
            )
        return selected

    selected = normalized_basis or "ttm"
    if selected not in ("ttm", "three_year_average"):
        raise typer.BadParameter("Growth EPS basis must be 'ttm' or 'three_year_average'.")
    return selected


def _validate_momentum_windows(short_window: int, long_window: int, rsi_period: int) -> None:
    """Reject invalid SMA/RSI periods with investor-readable domain language."""
    if short_window <= 0:
        typer.echo(f"Invalid momentum window: short window must be positive (received {short_window}).", err=True)
        raise typer.Exit(code=2)
    if long_window <= 0:
        typer.echo(f"Invalid momentum window: long window must be positive (received {long_window}).", err=True)
        raise typer.Exit(code=2)
    if rsi_period <= 0:
        typer.echo(f"Invalid momentum period: RSI period must be positive (received {rsi_period}).", err=True)
        raise typer.Exit(code=2)
    if short_window >= long_window:
        typer.echo(
            "Invalid momentum windows: "
            f"short window ({short_window}) must be smaller than long window ({long_window}).",
            err=True,
        )
        raise typer.Exit(code=2)


def _historical_horizon(growth_years: int | None) -> HistoricalHorizon:
    """Convert the optional CLI horizon to the typed strict/automatic policy."""
    if growth_years is None:
        return HistoricalHorizon.LONGEST_AVAILABLE
    mapping = {
        3: HistoricalHorizon.THREE_YEARS,
        4: HistoricalHorizon.FOUR_YEARS,
        5: HistoricalHorizon.FIVE_YEARS,
    }
    try:
        return mapping[growth_years]
    except KeyError as exc:
        raise typer.BadParameter("--growth-years must be 3, 4, or 5.") from exc


def _forward_policy(value: str) -> ForwardPolicy:
    """Map hyphenated investor-facing CLI values to the normative enum."""
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


def _presentation_mode(*, details: bool, diagnostics: bool, json_output: bool) -> PresentationMode:
    """Resolve the mutually exclusive progressive-disclosure flags."""
    selected_count = sum((details, diagnostics, json_output))
    if selected_count > 1:
        raise typer.BadParameter("Choose only one of --details, --diagnostics, or --json.")
    if json_output:
        return PresentationMode.JSON
    if diagnostics:
        return PresentationMode.DIAGNOSTICS
    if details:
        return PresentationMode.DETAILS
    return PresentationMode.CONCISE


def _resolve_ticker(positional: str | None, option: str | None, *, required: bool) -> str | None:
    """Resolve positional ticker with a transitional --ticker compatibility alias."""
    if positional is not None and option is not None and positional.strip().upper() != option.strip().upper():
        raise typer.BadParameter("Positional TICKER and --ticker refer to different symbols.")
    selected = positional if positional is not None else option
    if selected is None:
        if required:
            raise typer.BadParameter("TICKER is required. Use 'financial-agents graham TICKER'.")
        return None
    normalized = selected.strip().upper()
    if not normalized:
        raise typer.BadParameter("Ticker must be a non-empty symbol.")
    return normalized


def _canonical_provider_id(value: str | None) -> str | None:
    """Normalize an optional provider identifier."""
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        raise typer.BadParameter("--data-provider must be non-empty when supplied.")
    return normalized


def _parse_as_of(value: str | None) -> datetime | None:
    """Parse a CLI as-of boundary without silently assuming a timestamp timezone."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        raise typer.BadParameter("--as-of must be non-empty when supplied.")

    try:
        if len(text) == 10:
            parsed_date = date.fromisoformat(text)
            return datetime.combine(parsed_date, time.max, tzinfo=UTC)

        normalized = f"{text[:-1]}+00:00" if text.endswith(("Z", "z")) else text
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise typer.BadParameter("--as-of must be YYYY-MM-DD or a valid timezone-aware ISO-8601 timestamp.") from exc

    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        raise typer.BadParameter("Timestamp --as-of values must include an explicit timezone offset.")
    return parsed


if __name__ == "__main__":
    app()
