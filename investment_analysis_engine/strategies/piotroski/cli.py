"""The Piotroski F-Score strategy's CLI functions.

They are the direct command, the selection builder and the refresh executor.

The strategy reads no market data and no cache: the balance-sheet series, the annual series and the share counts are not
cached, so a run composes the SEC adapter once and builds the analyzer on it. The adapter is also the as-filed SIC
source of the industry class, so it is built here and the production provider is composed from it.
"""

from datetime import datetime

import typer

from investment_analysis_engine.cli_composition import build_sec_edgar_adapter
from investment_analysis_engine.cli_provider_check import (
    provider_check_choice,
)
from investment_analysis_engine.cli_run_support import analyze_and_maybe_save
from investment_analysis_engine.cli_support import (
    AS_OF_OPTION,
    NO_PROVIDER_CHECK_OPTION,
    SAVE_RUN_OPTION,
    emit_output,
    execution_errors,
    parse_as_of,
    render_execution,
    require_job_ticker,
    resolve_command_target,
)
from investment_analysis_engine.cli_watchlist_flags import WatchlistFlags
from investment_analysis_engine.core.clock import utc_now
from investment_analysis_engine.data.financial.production import ProductionFinancialFactsProvider
from investment_analysis_engine.data.financial.resolver import InputResolver
from investment_analysis_engine.data.instrument_profile import profile_identity_resolution
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.strategies.piotroski.analyzer import PiotroskiAnalyzer
from investment_analysis_engine.strategies.piotroski.execution import execute_piotroski, from_piotroski_capture
from investment_analysis_engine.strategies.piotroski.presenter import render_piotroski
from investment_analysis_engine.strategies.piotroski.selection import PiotroskiSelection
from investment_analysis_engine.workspace.capture import ExecutionCapture
from investment_analysis_engine.workspace.requests import AnalysisRequest


def compose_piotroski(executed_at: datetime) -> tuple[PiotroskiAnalyzer, ProductionFinancialFactsProvider]:
    """Compose the production analyzer and the provider its profile is composed from.

    The SEC adapter is built once. It serves the analyzer's resolver through the production provider and is the
    analyzer's as-filed SIC source, so the industry class is read from the same analysis scope as the inputs.

    Args:
        executed_at: The run's single reading of the current time, never the ``--as-of`` boundary.

    Returns:
        The analyzer and the production provider.
    """
    adapter = build_sec_edgar_adapter()
    provider = ProductionFinancialFactsProvider(sec_edgar=adapter)
    return PiotroskiAnalyzer(InputResolver(provider, clock=lambda: executed_at), adapter), provider


def build_selection(flags: WatchlistFlags) -> PiotroskiSelection:
    """Build one validated Piotroski F-Score selection.

    It is built from the watchlist flags it concerns: the boundary and the cache choice.
    """
    return PiotroskiSelection(as_of=parse_as_of(flags.as_of), use_cache=not flags.no_cache)


def refresh(
    ticker: str, selection: PiotroskiSelection, *, profile_cache: InstrumentProfileResolver | None
) -> ExecutionCapture:
    """Execute one Piotroski F-Score refresh job with a freshly composed, job-scoped analyzer."""
    require_job_ticker(ticker)
    executed_at = utc_now()
    analyzer, provider = compose_piotroski(executed_at)
    capture = execute_piotroski(
        analyzer, ticker, selection, executed_at=executed_at, provider=provider, profile_cache=profile_cache
    )
    return from_piotroski_capture(capture)


def command(  # noqa: PLR0913
    context: typer.Context,
    ticker: str = typer.Argument(..., help="Target stock ticker symbol (e.g., AAPL, KO)"),
    *,
    as_of: str | None = AS_OF_OPTION,
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass the cache"),
    details: bool = typer.Option(False, "--details", help="Show each test's operands with their year-end and value"),
    diagnostics: bool = typer.Option(
        False, "--diagnostics", help="Show where each operand came from and how the inputs were assembled"
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit the complete versioned typed result"),
    save_run: bool = SAVE_RUN_OPTION,
    no_provider_check: bool = NO_PROVIDER_CHECK_OPTION,
) -> None:
    """Run the Piotroski F-Score analysis."""
    executed_at = utc_now()
    provider_check = provider_check_choice(context, no_provider_check=no_provider_check)

    with execution_errors(
        json_output=json_output, selection_type=PiotroskiSelection, provider_check=provider_check
    ) as scope:
        target_ticker, mode = resolve_command_target(
            scope, ticker, None, command="piotroski", details=details, diagnostics=diagnostics, json_output=json_output
        )
        selection = PiotroskiSelection(as_of=parse_as_of(as_of), use_cache=not no_cache)
        analyzer, provider = compose_piotroski(executed_at)
        capture = analyze_and_maybe_save(
            save_run=save_run,
            executed_at=executed_at,
            request_factory=lambda: AnalysisRequest(ticker=target_ticker, selection=selection),
            run_adapter=lambda profile_cache: execute_piotroski(
                analyzer,
                target_ticker,
                selection,
                executed_at=executed_at,
                provider=provider,
                profile_cache=profile_cache,
            ),
            normalize=from_piotroski_capture,
        )
        result = capture.result
        profile = capture.profile
        identity_resolution = profile_identity_resolution(profile)

    output, exit_code = render_execution(
        from_piotroski_capture(capture),
        provider_check,
        mode,
        lambda element: render_piotroski(result, mode, identity_resolution, profile, element),
    )
    emit_output(output, exit_code, mode)
