"""Command Line Interface routing for the Financial Data Agents execution suite."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from src.analysis.shared.financial_resolution import PriceComparison
from src.analysis.strategy.fcf_earnings_growth import (
    FCFClassificationBasis,
    FCFEarningsGrowthAnalyzer,
    FCFEarningsGrowthPolicy,
    ForwardPolicy,
    HistoricalHorizon,
    ProductionAnnualGrowthSeriesResolver,
)
from src.analysis.strategy.graham_growth.analyzer import GrahamGrowthAnalyzer
from src.analysis.strategy.graham_growth.calculation import (
    GrahamGrowthCalculationPolicy,
    GrahamGrowthInputResolver,
    GrowthValueInputAssembly,
)
from src.analysis.strategy.graham_growth.config import GrahamGrowthConfig
from src.analysis.strategy.graham_number.analyzer import GrahamNumberAnalyzer
from src.analysis.strategy.graham_number.calculation import GrahamNumberInputAssembly, GrahamNumberInputResolver
from src.analysis.strategy.graham_number.config import GrahamNumberConfig
from src.analysis.strategy.momentum.momentum_analyzer import MomentumAnalyzer, MomentumConfig
from src.cli_support import (
    AnalysisConfigurationError,
    _canonical_provider_id,
    _parse_as_of,
    _presentation_mode,
    _production_financial_cache,
    _production_historical_client,
    _resolve_ticker,
    config_usage_errors,
    execution_errors,
)
from src.config import settings
from src.core.analysis_status import CalculationStatus
from src.core.constants import ConfigKeys
from src.core.telemetry import RunContext, TrajectoryRecorder
from src.core.telemetry.run_context import get_current_run_context, set_current_run_context
from src.data.financial.cache import (
    InMemoryResolvedInputCache,
    ResolvedInputCacheProtocol,
)
from src.data.financial.facts import FinancialFactsProvider
from src.data.financial.providers import (
    MASSIVE_PROVIDER_ID,
    SEC_PROVIDER_ID,
    YFINANCE_PROVIDER_ID,
    MassiveFinancialFactsAdapter,
    ProductionFinancialFactsProvider,
    SecEdgarFinancialFactsAdapter,
)
from src.data.financial.quote_freshness import QuoteFreshnessPolicy
from src.data.instrument_profile import (
    InstrumentProfile,
    InstrumentProfileCandidate,
    compose_instrument_profile,
    profile_identity_resolution,
)
from src.data.security_identity import SecurityIdentityResolution
from src.data.yfinance import YFinanceClient
from src.evaluation.catalog import (
    DETERMINISTIC_FIXTURE_SET_VERSION,
    DETERMINISTIC_SUITE_ID,
    DETERMINISTIC_SUITE_VERSION,
    build_deterministic_requests,
)
from src.evaluation.ollama_runner import (
    OllamaEvaluationConfig,
    OllamaEvaluationResult,
    run_real_local_ollama_suite,
)
from src.evaluation.reporting import EvaluationReport
from src.evaluation.runner import DeterministicCaseRequest, run_deterministic_suite
from src.llm.client import LLMClient
from src.reporting.fcf_earnings_growth import render_fcf_earnings_growth
from src.reporting.graham import (
    GrahamGrowthPresentation,
    GrahamNumberPresentation,
    render_graham_growth,
    render_graham_number,
)
from src.reporting.momentum import MomentumPresentation, render_momentum
from src.reporting.presentation import PresentationMode

app = typer.Typer(
    help="Analyze financial data with transparent calculations and supporting evidence.", add_completion=False
)

_MOMENTUM_CLI_DEFAULTS = MomentumConfig()


class EvaluationCliMode(StrEnum):
    """User-facing Golden-Suite execution choices."""

    DETERMINISTIC = "deterministic"
    OLLAMA = "ollama"


type EvaluationCommandResult = EvaluationReport | OllamaEvaluationResult


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
    target_ticker = _resolve_ticker(ticker, ticker_option, required=False, command="momentum")
    mode = _presentation_mode(details=details, diagnostics=diagnostics, json_output=json_output)
    _validate_momentum_windows(short_window, long_window, rsi_period)

    label = target_ticker or "the configured default ticker"
    with execution_errors(
        mode=mode,
        analysis="momentum",
        method="sma_crossover",
        ticker=target_ticker,
        data_error=lambda _exc: (
            f"Unable to analyze {label}: the configured market-data provider returned no usable price history."
        ),
        invalid=lambda _exc: (
            f"Unable to complete momentum analysis for {label}: the returned price history could not be analyzed."
        ),
        unexpected=lambda _exc: f"Momentum analysis failed unexpectedly for {label}.",
    ):
        data_client = YFinanceClient()
        with _production_historical_client(data_client) as historical_client:
            analyzer = MomentumAnalyzer(default_ticker=target_ticker, data_client=historical_client)
            config = MomentumConfig(short_window=short_window, long_window=long_window, rsi_period=rsi_period)
            run = analyzer.run_with_context(config=config, ticker=target_ticker)
        profile = compose_instrument_profile(
            run.metrics.ticker,
            identity_candidates=(InstrumentProfileCandidate(YFINANCE_PROVIDER_ID, data_client),),
            kind_candidate=InstrumentProfileCandidate(YFINANCE_PROVIDER_ID, data_client),
        )
        presentation = MomentumPresentation(
            metrics=run.metrics,
            config=config,
            market_data=run.market_data,
            resolution_trace=run.resolution_trace,
            data_resolution=run.data_resolution,
            identity_resolution=profile_identity_resolution(profile),
            instrument_profile=profile,
        )
        typer.echo(render_momentum(presentation, mode))


@app.command(name="graham-number")
def graham_number(  # noqa: PLR0913
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
            "EPS basis; Number defaults to three_year_average; Growth defaults to "
            "three_year_average with SEC EDGAR and ttm with Massive"
        ),
    ),
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
) -> None:
    """Execute the Graham Number earnings-and-book-value screen."""
    target_ticker = _resolve_ticker(ticker, ticker_option, required=True, command="graham-number")
    assert target_ticker is not None
    mode = _presentation_mode(details=details, diagnostics=diagnostics, json_output=json_output)
    boundary = _parse_as_of(as_of)
    provider_id = _canonical_provider_id(data_provider) or SEC_PROVIDER_ID
    with config_usage_errors():
        config = GrahamNumberConfig.model_validate(
            {
                "security_provider_id": provider_id,
                "eps_basis": eps_basis,
                "eps_override": eps,
                "quote_override": current_price,
                "as_of": boundary,
                "use_cache": not no_cache,
                "bvps_override": bvps,
            }
        )
    with (
        execution_errors(
            mode=mode,
            analysis="graham",
            method="graham_number",
            ticker=target_ticker,
            unexpected=lambda _exc: f"Graham analysis failed unexpectedly for {target_ticker}.",
        ),
        _production_financial_cache(enabled=config.use_cache) as cache,
    ):
        with execution_errors(
            mode=mode,
            analysis="graham",
            method="graham_number",
            ticker=target_ticker,
            invalid=lambda exc: f"Unable to start Graham analysis: {exc}",
            unexpected=lambda _exc: f"Graham analysis failed unexpectedly for {target_ticker}.",
        ):
            resolver = _build_graham_resolver(
                resolver_type=GrahamNumberInputResolver, data_provider=config.security_provider_id, cache=cache
            )
        output, exit_code = _run_graham_number(
            resolver=resolver,
            ticker=target_ticker,
            config=config,
            mode=mode,
            profile_provider=YFinanceClient(),
        )
    typer.echo(output, err=exit_code != 0 and mode in (PresentationMode.CONCISE, PresentationMode.DETAILS))
    if exit_code:
        raise typer.Exit(code=exit_code)


@app.command(name="graham-growth")
def graham_growth(  # noqa: PLR0913
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
            "EPS basis; Number defaults to three_year_average; Growth defaults to "
            "three_year_average with SEC EDGAR and ttm with Massive"
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
) -> None:
    """Execute Graham Growth Value with explicit growth and AAA-yield assumptions."""
    target_ticker = _resolve_ticker(ticker, ticker_option, required=True, command="graham-growth")
    assert target_ticker is not None
    mode = _presentation_mode(details=details, diagnostics=diagnostics, json_output=json_output)
    boundary = _parse_as_of(as_of)
    provider_id = _canonical_provider_id(data_provider) or SEC_PROVIDER_ID
    with config_usage_errors():
        config = GrahamGrowthConfig.model_validate(
            {
                "security_provider_id": provider_id,
                "eps_basis": eps_basis,
                "eps_override": eps,
                "quote_override": current_price,
                "as_of": boundary,
                "use_cache": not no_cache,
                "expected_growth": expected_growth,
                "aaa_yield_override": aaa_yield,
            }
        )
    with (
        execution_errors(
            mode=mode,
            analysis="graham",
            method="graham_growth_value",
            ticker=target_ticker,
            unexpected=lambda _exc: f"Graham analysis failed unexpectedly for {target_ticker}.",
        ),
        _production_financial_cache(enabled=config.use_cache) as cache,
    ):
        with execution_errors(
            mode=mode,
            analysis="graham",
            method="graham_growth_value",
            ticker=target_ticker,
            invalid=lambda exc: f"Unable to start Graham analysis: {exc}",
            unexpected=lambda _exc: f"Graham analysis failed unexpectedly for {target_ticker}.",
        ):
            resolver = _build_graham_resolver(
                resolver_type=GrahamGrowthInputResolver, data_provider=config.security_provider_id, cache=cache
            )
        output, exit_code = _run_graham_growth(
            resolver=resolver,
            ticker=target_ticker,
            config=config,
            mode=mode,
            profile_provider=YFinanceClient(),
        )
    typer.echo(output, err=exit_code != 0 and mode in (PresentationMode.CONCISE, PresentationMode.DETAILS))
    if exit_code:
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
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass resolved-input cache reads and writes"),
    details: bool = typer.Option(False, "--details", help="Show annual facts, provenance, and derivation lineage"),
    diagnostics: bool = typer.Option(False, "--diagnostics", help="Show resolver execution trace"),
    json_output: bool = typer.Option(False, "--json", help="Emit the complete versioned typed result"),
) -> None:
    """Execute the historical free-cash-flow and diluted-EPS growth screen."""
    target_ticker = _resolve_ticker(ticker, None, required=True, command="fcf-growth")
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

    with (
        execution_errors(
            mode=mode,
            analysis="fcf_earnings_growth",
            method="reported_fcf_eps_cagr",
            ticker=target_ticker,
            invalid=lambda exc: f"Unable to start FCF & earnings-growth analysis: {exc}",
            unexpected=lambda _exc: f"FCF & earnings-growth analysis failed unexpectedly for {target_ticker}.",
        ),
        _production_financial_cache(enabled=not no_cache) as cache,
    ):
        provider = _build_sec_production_provider()
        profile = _compose_analysis_profile(
            target_ticker,
            primary_provider=provider,
            primary_provider_id=provider_id,
            yahoo_provider=provider,
        )
        resolver = ProductionAnnualGrowthSeriesResolver(
            provider,
            cache=cache,
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
            instrument_profile=profile,
        )
        identity_resolution = profile_identity_resolution(profile)

    output = render_fcf_earnings_growth(result, mode, identity_resolution, profile)
    exit_code = 0 if result.execution_status in (CalculationStatus.OK, CalculationStatus.NOT_APPLICABLE) else 1
    typer.echo(output, err=exit_code != 0 and mode in (PresentationMode.CONCISE, PresentationMode.DETAILS))
    if exit_code:
        raise typer.Exit(code=exit_code)


@app.command(name="evaluate")
def evaluate(  # noqa: PLR0913
    *,
    mode: Annotated[
        EvaluationCliMode,
        typer.Option("--mode", help="Execution mode: deterministic (default) or ollama"),
    ] = EvaluationCliMode.DETERMINISTIC,
    case_id: str | None = typer.Option(None, "--case", help="Run one stable Golden case ID instead of the full suite"),
    report_path: Annotated[Path, typer.Option("--report", help="Explicit JSON report destination")],
    overwrite: bool = typer.Option(False, "--overwrite", help="Replace an existing report file"),
    ollama_endpoint: str | None = typer.Option(
        None,
        "--ollama-endpoint",
        help="Ollama endpoint; defaults to the configured application endpoint",
    ),
    model_id: str | None = typer.Option(
        None,
        "--model",
        help="Local model identifier; defaults to the configured application model",
    ),
    temperature: float | None = typer.Option(None, "--temperature", help="Empirical sampling temperature"),
    repetitions: int | None = typer.Option(
        None,
        "--repetitions",
        min=1,
        max=100,
        help="Independent empirical repetitions (1-100)",
    ),
    max_steps: int | None = typer.Option(
        None,
        "--max-steps",
        min=1,
        max=50,
        help="Maximum orchestration steps per case (1-50)",
    ),
) -> None:
    """Run the versioned Golden Suite and write one machine-readable report."""
    requests = _select_evaluation_requests(case_id)
    _validate_evaluation_mode_options(
        mode,
        ollama_endpoint=ollama_endpoint,
        model_id=model_id,
        temperature=temperature,
        repetitions=repetitions,
        max_steps=max_steps,
    )
    target = report_path.expanduser().resolve()
    if target.exists() and not overwrite:
        raise typer.BadParameter(
            f"Report already exists: {target}. Use --overwrite to replace it.",
            param_hint="--report",
        )

    try:
        result = asyncio.run(
            _run_evaluation_command(
                requests,
                mode=mode,
                executed_at=datetime.now(UTC),
                ollama_endpoint=ollama_endpoint,
                model_id=model_id,
                temperature=temperature,
                repetitions=repetitions,
                max_steps=max_steps,
            )
        )
        _write_evaluation_report(result, target=target, overwrite=overwrite)
    except (OSError, ValueError) as err:
        typer.echo(f"Evaluation failed: {err}", err=True)
        raise typer.Exit(code=1) from err
    except Exception as err:
        typer.echo(f"Evaluation failed unexpectedly: {err}", err=True)
        raise typer.Exit(code=1) from err

    passed, failed, skipped = _evaluation_case_counts(result)
    typer.echo(f"Evaluation report written to {target} ({passed} passed, {failed} failed, {skipped} skipped).")
    if failed or skipped:
        for diagnostic in _evaluation_failure_diagnostics(result):
            typer.echo(diagnostic, err=True)
        raise typer.Exit(code=1)


def _select_evaluation_requests(case_id: str | None) -> tuple[DeterministicCaseRequest, ...]:
    """Return the full canonical catalog or one exact stable case."""
    requests = build_deterministic_requests()
    if case_id is None:
        return requests
    normalized = case_id.strip().upper()
    selected = tuple(request for request in requests if request.case.case_id == normalized)
    if selected:
        return selected
    available = ", ".join(request.case.case_id for request in requests)
    raise typer.BadParameter(
        f"Unknown Golden case ID {case_id!r}. Available IDs: {available}.",
        param_hint="--case",
    )


def _validate_evaluation_mode_options(  # noqa: PLR0913
    mode: EvaluationCliMode,
    *,
    ollama_endpoint: str | None,
    model_id: str | None,
    temperature: float | None,
    repetitions: int | None,
    max_steps: int | None,
) -> None:
    """Reject empirical-only controls when deterministic execution is selected."""
    empirical_options = (ollama_endpoint, model_id, temperature, repetitions, max_steps)
    if mode is EvaluationCliMode.DETERMINISTIC and any(value is not None for value in empirical_options):
        raise typer.BadParameter(
            "Ollama options require --mode ollama.",
            param_hint="--mode",
        )


async def _run_evaluation_command(  # noqa: PLR0913
    requests: tuple[DeterministicCaseRequest, ...],
    *,
    mode: EvaluationCliMode,
    executed_at: datetime,
    ollama_endpoint: str | None,
    model_id: str | None,
    temperature: float | None,
    repetitions: int | None,
    max_steps: int | None,
) -> EvaluationCommandResult:
    """Route one CLI request through the reviewed deterministic or empirical runner."""
    if mode is EvaluationCliMode.DETERMINISTIC:
        recorder = TrajectoryRecorder.from_settings(get_cli_run_context())
        return await run_deterministic_suite(
            requests,
            suite_id=DETERMINISTIC_SUITE_ID,
            suite_version=DETERMINISTIC_SUITE_VERSION,
            fixture_set_version=DETERMINISTIC_FIXTURE_SET_VERSION,
            executed_at=executed_at,
            recorder=recorder,
        )

    endpoint = ollama_endpoint or settings.ollama_base_url
    selected_model = model_id or settings.model_selection
    config = OllamaEvaluationConfig(
        endpoint=endpoint,
        model_id=selected_model,
        temperature=0.0 if temperature is None else temperature,
        repetitions=1 if repetitions is None else repetitions,
        max_steps=10 if max_steps is None else max_steps,
        schema_config=settings.schema_config,
    )
    client = LLMClient(config.endpoint, default_model=config.model_id)
    try:
        return await run_real_local_ollama_suite(
            requests,
            suite_id=DETERMINISTIC_SUITE_ID,
            suite_version=DETERMINISTIC_SUITE_VERSION,
            fixture_set_version=DETERMINISTIC_FIXTURE_SET_VERSION,
            llm_client=client,
            config=config,
            executed_at=executed_at,
        )
    finally:
        await client.close()


def _write_evaluation_report(
    result: EvaluationCommandResult,
    *,
    target: Path,
    overwrite: bool,
) -> None:
    """Serialize a complete report without replacing an existing file implicitly."""
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if overwrite else "x"
    with target.open(mode, encoding="utf-8", newline="\n") as report_file:
        report_file.write(result.model_dump_json(indent=2))
        report_file.write("\n")


def _evaluation_case_counts(result: EvaluationCommandResult) -> tuple[int, int, int]:
    """Return aggregate passed, failed, and skipped case-execution counts."""
    if isinstance(result, EvaluationReport):
        return result.passed_cases, result.failed_cases, result.skipped_cases
    reports = tuple(item.report for item in result.repetition_reports)
    return (
        sum(report.passed_cases for report in reports),
        sum(report.failed_cases for report in reports),
        sum(report.skipped_cases for report in reports),
    )


def _evaluation_failure_diagnostics(result: EvaluationCommandResult) -> tuple[str, ...]:
    """Render concise case diagnostics, including typed reliability reasons and run IDs."""
    reports = (
        (result,) if isinstance(result, EvaluationReport) else tuple(item.report for item in result.repetition_reports)
    )
    diagnostics: list[str] = []
    for repetition, report in enumerate(reports, start=1):
        for case in getattr(report, "case_results", ()):
            prefix = f"{case.case_id}"
            if len(reports) > 1:
                prefix += f" repetition {repetition}"
            if case.failure_reasons:
                diagnostics.extend(f"{prefix}: {reason}" for reason in case.failure_reasons)
            elif case.skip_reason is not None:
                diagnostics.append(f"{prefix}: skipped: {case.skip_reason}")
    return tuple(diagnostics)


def _build_sec_production_provider() -> ProductionFinancialFactsProvider:
    """Build the SEC-backed production provider from declared application identity."""
    user_agent = settings.sec_user_agent
    if user_agent is None or not user_agent.strip():
        raise AnalysisConfigurationError(
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
        raise AnalysisConfigurationError("Massive access is not configured. Set MASSIVE_API_KEY and retry.")
    return massive


def _compose_analysis_profile(
    ticker: str,
    *,
    primary_provider: object,
    primary_provider_id: str,
    yahoo_provider: object,
) -> InstrumentProfile:
    """Compose current profile evidence with explicit production precedence."""
    yahoo_candidate = InstrumentProfileCandidate(YFINANCE_PROVIDER_ID, yahoo_provider)
    identity_candidates: tuple[InstrumentProfileCandidate, ...] = (
        InstrumentProfileCandidate(primary_provider_id, primary_provider),
    )
    if primary_provider_id != YFINANCE_PROVIDER_ID:
        identity_candidates = (*identity_candidates, yahoo_candidate)
    return compose_instrument_profile(
        ticker,
        identity_candidates=identity_candidates,
        kind_candidate=yahoo_candidate,
    )


def _build_graham_resolver[ResolverT: (GrahamNumberInputResolver, GrahamGrowthInputResolver)](
    *, resolver_type: type[ResolverT], data_provider: str | None, cache: ResolvedInputCacheProtocol | None = None
) -> ResolverT:
    """Build only the production provider capabilities needed by this invocation."""
    provider: FinancialFactsProvider
    if data_provider == MASSIVE_PROVIDER_ID:
        provider = _build_massive_production_provider()
    elif data_provider == SEC_PROVIDER_ID:
        provider = _build_sec_production_provider()
    elif data_provider is not None:
        raise AnalysisConfigurationError(
            f"Unsupported valuation data provider {data_provider!r}; "
            f"supported providers are {SEC_PROVIDER_ID!r} and {MASSIVE_PROVIDER_ID!r}."
        )
    else:
        provider = _build_sec_production_provider()

    return resolver_type(
        provider,
        cache=cache if cache is not None else InMemoryResolvedInputCache(),
        quote_freshness_policy=QuoteFreshnessPolicy(timedelta(seconds=settings.quote_cache_ttl_seconds)),
    )


def _run_graham_number(  # noqa: PLR0913
    *,
    resolver: GrahamNumberInputResolver,
    ticker: str,
    config: GrahamNumberConfig,
    mode: PresentationMode,
    profile_provider: object,
) -> tuple[str, int]:
    """Resolve, calculate, and render one Graham Number analysis."""
    profile = _compose_analysis_profile(
        ticker,
        primary_provider=resolver.provider,
        primary_provider_id=config.security_provider_id,
        yahoo_provider=profile_provider,
    )
    analysis = GrahamNumberAnalyzer(resolver, instrument_profile=profile).run_analysis(config, ticker=ticker)
    as_of = config.as_of
    assembly = analysis.assembly
    profile = analysis.instrument_profile or profile
    identity_resolution = profile_identity_resolution(profile)

    if assembly.status is not CalculationStatus.OK:
        if assembly.status is CalculationStatus.NOT_APPLICABLE:
            presentation = GrahamNumberPresentation(
                ticker=ticker,
                assembly=assembly,
                result=analysis.result,
                price_comparison=analysis.price_comparison,
                as_of=as_of,
                identity_resolution=identity_resolution,
                instrument_profile=profile,
            )
            return render_graham_number(presentation, mode), 0
        return _number_failure_output(
            ticker=ticker,
            assembly=assembly,
            as_of=as_of,
            mode=mode,
            identity_resolution=identity_resolution,
            instrument_profile=profile,
            price_comparison=analysis.price_comparison,
        )

    presentation_assembly = _number_with_public_quote_reason(assembly)
    presentation = GrahamNumberPresentation(
        ticker=ticker,
        assembly=presentation_assembly,
        result=analysis.result,
        as_of=as_of,
        margin_of_safety_percent=analysis.margin_of_safety_percent,
        price_comparison=analysis.price_comparison,
        identity_resolution=identity_resolution,
        instrument_profile=profile,
    )
    exit_code = 1 if analysis.result.status is CalculationStatus.INVALID_INPUT else 0
    return render_graham_number(presentation, mode), exit_code


def _run_graham_growth(  # noqa: PLR0913
    *,
    resolver: GrahamGrowthInputResolver,
    ticker: str,
    config: GrahamGrowthConfig,
    mode: PresentationMode,
    profile_provider: object,
) -> tuple[str, int]:
    """Resolve, calculate, and render one Graham growth-value analysis."""
    policy = _growth_assumptions()
    profile = _compose_analysis_profile(
        ticker,
        primary_provider=resolver.provider,
        primary_provider_id=config.security_provider_id,
        yahoo_provider=profile_provider,
    )
    analysis = GrahamGrowthAnalyzer(resolver, instrument_profile=profile, policy=policy).run_analysis(
        config, ticker=ticker
    )
    as_of = config.as_of
    assembly = analysis.assembly
    profile = analysis.instrument_profile or profile
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
                identity_resolution=identity_resolution,
                instrument_profile=profile,
            )
            return render_graham_growth(presentation, mode), 0
        return _growth_failure_output(
            ticker=ticker,
            assembly=assembly,
            as_of=as_of,
            mode=mode,
            identity_resolution=identity_resolution,
            instrument_profile=profile,
            price_comparison=analysis.price_comparison,
        )

    presentation_assembly = _growth_with_public_quote_reason(assembly)
    presentation = GrahamGrowthPresentation(
        ticker=ticker,
        assembly=presentation_assembly,
        result=analysis.result,
        base_pe=policy.base_pe,
        growth_multiplier=policy.growth_multiplier,
        baseline_aaa_yield=policy.baseline_aaa_yield,
        as_of=as_of,
        margin_of_safety_percent=analysis.margin_of_safety_percent,
        price_comparison=analysis.price_comparison,
        identity_resolution=identity_resolution,
        instrument_profile=profile,
    )
    exit_code = 1 if analysis.result.status is CalculationStatus.INVALID_INPUT else 0
    return render_graham_growth(presentation, mode), exit_code


def _number_failure_output(  # noqa: PLR0913
    *,
    ticker: str,
    assembly: GrahamNumberInputAssembly,
    as_of: datetime | None,
    mode: PresentationMode,
    identity_resolution: SecurityIdentityResolution,
    instrument_profile: InstrumentProfile,
    price_comparison: PriceComparison | None = None,
) -> tuple[str, int]:
    """Render a failed Number analysis without leaking low-level details by default."""
    reason = _friendly_graham_failure(ticker, assembly.status, assembly.reason)
    safe_assembly = _number_with_public_quote_reason(replace(assembly, reason=reason))
    presentation = GrahamNumberPresentation(
        ticker=ticker,
        assembly=safe_assembly,
        price_comparison=price_comparison,
        result=None,
        as_of=as_of,
        identity_resolution=identity_resolution,
        instrument_profile=instrument_profile,
    )
    return render_graham_number(presentation, mode), 1


def _growth_failure_output(  # noqa: PLR0913
    *,
    ticker: str,
    assembly: GrowthValueInputAssembly,
    as_of: datetime | None,
    mode: PresentationMode,
    identity_resolution: SecurityIdentityResolution,
    instrument_profile: InstrumentProfile,
    price_comparison: PriceComparison | None = None,
) -> tuple[str, int]:
    """Render a failed growth analysis without leaking low-level details by default."""
    reason = _friendly_graham_failure(ticker, assembly.status, assembly.reason)
    safe_assembly = _growth_with_public_quote_reason(replace(assembly, reason=reason))
    policy = _growth_assumptions()
    presentation = GrahamGrowthPresentation(
        ticker=ticker,
        assembly=safe_assembly,
        price_comparison=price_comparison,
        result=None,
        base_pe=policy.base_pe,
        growth_multiplier=policy.growth_multiplier,
        baseline_aaa_yield=policy.baseline_aaa_yield,
        as_of=as_of,
        identity_resolution=identity_resolution,
        instrument_profile=instrument_profile,
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
    if reason is not None and reason.startswith("Unable to analyze"):
        return reason
    if status is CalculationStatus.PROVIDER_ERROR:
        return f"Unable to analyze {ticker}: the configured provider could not retrieve required security data."
    if status is CalculationStatus.INPUT_UNAVAILABLE:
        return f"Unable to analyze {ticker}: required financial data is unavailable for the requested method."
    return f"Unable to analyze {ticker}: the requested Graham inputs are invalid. Review the method and overrides."


def _growth_assumptions() -> GrahamGrowthCalculationPolicy:
    """Read the configured constants for the growth-value method."""
    values = settings.get_graham_value_analysis()[ConfigKeys.GRAHAM_VALUES]
    return GrahamGrowthCalculationPolicy(
        base_pe=float(values[ConfigKeys.BASE_PE]),
        growth_multiplier=float(values[ConfigKeys.GROWTH_MULTIPLIER]),
        baseline_aaa_yield=float(values[ConfigKeys.BASELINE_AAA_YIELD]),
    )


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


if __name__ == "__main__":
    app()
