"""Momentum's CLI-layer functions: the direct command, the watchlist selection builder and the refresh executor.

The CLI tier pairs these with the Momentum core bundle and adds the command to the application; nothing here
registers itself.
"""

import typer

from investment_analysis_engine.analysis.base_analyzer import require_ticker
from investment_analysis_engine.cli_composition import momentum_settings
from investment_analysis_engine.cli_provider_check import provider_check_choice
from investment_analysis_engine.cli_run_support import save_run_execution
from investment_analysis_engine.cli_support import (
    SaveStage,
    _parse_as_of,
    _presentation_mode,
    _production_database,
    _production_historical_client,
    _production_instrument_profile_cache,
    _resolve_ticker,
    execution_errors,
    require_job_ticker,
    saving_failures,
)
from investment_analysis_engine.cli_watchlist_flags import WatchlistFlags
from investment_analysis_engine.core.clock import utc_now
from investment_analysis_engine.core.operator_errors import InvalidParameterError
from investment_analysis_engine.data.instrument_profile import profile_identity_resolution
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.data.repositories.readiness import ensure_database_ready
from investment_analysis_engine.data.yfinance.client import YFinanceClient
from investment_analysis_engine.strategies.momentum.analyzer import MomentumConfig
from investment_analysis_engine.strategies.momentum.execution import (
    capture_momentum,
    compose_momentum_profile,
    from_momentum_capture,
    run_momentum,
)
from investment_analysis_engine.strategies.momentum.presenter import MomentumPresentation, render_momentum
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.workspace.capture import ExecutionCapture
from investment_analysis_engine.workspace.repositories.analysis_runs import SQLiteAnalysisRunRepository
from investment_analysis_engine.workspace.requests import AnalysisRequest


def _validate_momentum_windows(short_window: int, long_window: int, rsi_period: int) -> None:
    """Reject invalid SMA/RSI periods with investor-readable domain language.

    The direct command and the watchlist builder share this check, so both report the same
    ``invalid_parameter`` failure with the same sentence, which names the offending option. The option
    names are the ones both commands declare; this function, not generic tooling, supplies them.
    """
    if short_window <= 0:
        raise InvalidParameterError(
            f"Invalid momentum window: --short-window must be positive (received {short_window}).",
            parameters=("--short-window",),
        )
    if long_window <= 0:
        raise InvalidParameterError(
            f"Invalid momentum window: --long-window must be positive (received {long_window}).",
            parameters=("--long-window",),
        )
    if rsi_period <= 0:
        raise InvalidParameterError(
            f"Invalid momentum period: --rsi-period must be positive (received {rsi_period}).",
            parameters=("--rsi-period",),
        )
    if short_window >= long_window:
        raise InvalidParameterError(
            f"Invalid momentum windows: --short-window ({short_window}) "
            f"must be smaller than --long-window ({long_window}).",
            parameters=("--short-window", "--long-window"),
        )


def build_selection(flags: WatchlistFlags) -> MomentumSelection:
    """Build one validated Momentum selection from watchlist CLI flags.

    Mirrors the direct ``momentum`` command's own flags and validation exactly, so a watchlist entry behaves
    identically to running the method directly.
    """
    _validate_momentum_windows(flags.short_window, flags.long_window, flags.rsi_period)
    return MomentumSelection(
        short_window=flags.short_window,
        long_window=flags.long_window,
        rsi_period=flags.rsi_period,
        as_of=_parse_as_of(flags.as_of),
        use_cache=not flags.no_cache,
    )


def refresh(
    ticker: str, selection: MomentumSelection, *, profile_cache: InstrumentProfileResolver | None
) -> ExecutionCapture:
    """Execute one Momentum refresh job with freshly composed, job-scoped dependencies."""
    data_client = YFinanceClient()
    executed_at = utc_now()
    normalized_ticker = require_ticker(require_job_ticker(ticker))
    profile = compose_momentum_profile(normalized_ticker, data_client=data_client, profile_cache=profile_cache)
    with _production_historical_client(
        data_client, use_cache=selection.use_cache, clock=lambda: executed_at
    ) as historical_client:
        run = run_momentum(
            selection,
            normalized_ticker,
            historical_client,
            start_date=momentum_settings().history_start_date.isoformat(),
            executed_at=executed_at,
            instrument_profile=profile,
        )
    return from_momentum_capture(capture_momentum(run))


_MOMENTUM_CLI_DEFAULTS = momentum_settings()


def command(  # noqa: PLR0913
    context: typer.Context,
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
    as_of: str | None = typer.Option(
        None,
        "--as-of",
        help="Point-in-time boundary as YYYY-MM-DD or timezone-aware ISO-8601 timestamp",
    ),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass historical price cache reads and writes"),
    details: bool = typer.Option(False, "--details", help="Show calculation and data-context details"),
    diagnostics: bool = typer.Option(False, "--diagnostics", help="Show retained execution diagnostics"),
    json_output: bool = typer.Option(False, "--json", help="Emit stable machine-readable JSON"),
    save_run: bool = typer.Option(False, "--save-run", help="Persist this attempt as a durable Analysis Run"),
    no_provider_check: bool = typer.Option(
        False, "--no-provider-check", help="Do not send a test request to a provider after it fails"
    ),
) -> None:
    """Execute SMA crossover momentum analysis over daily historical market prices."""
    with execution_errors(
        json_output=json_output,
        selection_type=MomentumSelection,
        provider_check=provider_check_choice(context, no_provider_check=no_provider_check),
    ) as scope:
        requested_ticker = _resolve_ticker(ticker, ticker_option, command="momentum")
        scope.ticker = requested_ticker
        mode = _presentation_mode(details=details, diagnostics=diagnostics, json_output=json_output)
        scope.mode = mode
        _validate_momentum_windows(short_window, long_window, rsi_period)
        boundary = _parse_as_of(as_of)
        target_ticker = require_ticker(requested_ticker)
        start_date = momentum_settings().history_start_date.isoformat()
        data_client = YFinanceClient()
        config = MomentumConfig(short_window=short_window, long_window=long_window, rsi_period=rsi_period)
        selection = MomentumSelection(
            short_window=short_window,
            long_window=long_window,
            rsi_period=rsi_period,
            as_of=boundary,
            use_cache=not no_cache,
        )
        # executed_at is the run's own execution clock, distinct from the requested as_of boundary.
        executed_at = utc_now()

        if save_run:
            # Momentum's profile is composed CLI-side (outside the D1 adapter). Readiness is
            # checked before the historical-data provider call, matching every other
            # command's "preflight before provider work" ordering.
            database = _production_database()
            try:
                ensure_database_ready(database)
                profile_cache = _production_instrument_profile_cache(database, clock=lambda: executed_at)
                profile = compose_momentum_profile(target_ticker, data_client=data_client, profile_cache=profile_cache)
                with _production_historical_client(
                    data_client, use_cache=selection.use_cache, clock=lambda: executed_at
                ) as historical_client:
                    run = run_momentum(
                        selection,
                        target_ticker,
                        historical_client,
                        start_date=start_date,
                        executed_at=executed_at,
                        instrument_profile=profile,
                    )
                momentum_capture = capture_momentum(run)
                with saving_failures(SaveStage(analyzed=True)):
                    saved = save_run_execution(
                        AnalysisRequest(ticker=target_ticker, selection=selection),
                        capture=lambda: from_momentum_capture(momentum_capture),
                        repository=SQLiteAnalysisRunRepository(database),
                    )
                typer.echo(f"Saved Analysis Run: {saved.analysis_run_id}", err=True)
            finally:
                database.close()
        else:
            profile = compose_momentum_profile(target_ticker, data_client=data_client)
            with _production_historical_client(
                data_client, use_cache=selection.use_cache, clock=lambda: executed_at
            ) as historical_client:
                run = run_momentum(
                    selection,
                    target_ticker,
                    historical_client,
                    start_date=start_date,
                    executed_at=executed_at,
                    instrument_profile=profile,
                )
        embedded_profile = run.instrument_profile
        if embedded_profile is None:
            raise ValueError("Momentum result did not retain the instrument profile it ran with.")
        presentation = MomentumPresentation(
            metrics=run.metrics,
            config=config,
            requested_as_of=boundary,
            market_data=run.market_data,
            resolution_trace=run.resolution_trace,
            data_resolution=run.data_resolution,
            identity_resolution=profile_identity_resolution(embedded_profile),
            instrument_profile=embedded_profile,
        )
        typer.echo(render_momentum(presentation, mode))
