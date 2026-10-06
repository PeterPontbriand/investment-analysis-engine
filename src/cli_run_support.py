"""Run helpers shared by every direct strategy command: the CLI run context and the opt-in run save."""

from collections.abc import Callable
from datetime import datetime

import typer

from src.cli_support import _production_instrument_profile_cache
from src.config import settings
from src.core.telemetry import RunContext
from src.core.telemetry.run_context import get_current_run_context
from src.data.instrument_profile_cache import InstrumentProfileResolver
from src.data.repositories.analysis_runs import SQLiteAnalysisRunRepository
from src.data.repositories.readiness import ensure_database_ready
from src.data.repositories.sqlite import SQLiteDatabase
from src.strategy_wiring import run_spec_for
from src.workspace.capture import ExecutionCapture
from src.workspace.execution import execute
from src.workspace.requests import AnalysisRequest
from src.workspace.runs import AnalysisRun


def get_cli_run_context() -> RunContext:
    """Return the explicit execution identity for the current CLI invocation."""
    context = get_current_run_context()
    if context is None:
        raise RuntimeError("CLI RunContext has not been initialized.")
    return context


def save_run_execution(
    request: AnalysisRequest, *, capture: Callable[[], ExecutionCapture], repository: SQLiteAnalysisRunRepository
) -> AnalysisRun:
    """Execute and persist one terminal run under the run spec the request's selection declares."""
    return execute(request, spec=run_spec_for(request.selection), capture=capture, repository=repository)


def maybe_save_run[RawCaptureT](
    *,
    save_run: bool,
    executed_at: datetime,
    request_factory: Callable[[], AnalysisRequest],
    run_adapter: Callable[[InstrumentProfileResolver | None], RawCaptureT],
    normalize: Callable[[RawCaptureT], ExecutionCapture],
) -> RawCaptureT:
    """Run one method adapter once; when `--save-run` is set, also persist the terminal run.

    When ``save_run`` is False this is a pure passthrough to
    ``run_adapter(None)``: the four direct commands' default behavior,
    including ``--no-cache``, is completely unaffected, and no database is
    opened solely to obtain a durable instrument-profile cache (P2-Profiles
    contract §13.3-1) — this is never called differently, and nothing about
    the existing adapter call changes. ``request_factory`` is a callable
    rather than a plain value specifically so it is never evaluated at all
    on this path: building the workspace `AnalysisSelection` can fail for
    inputs the existing, more permissive analyzer configs already accept
    (for example a test-only synthetic provider id used only for dependency
    injection), and constructing it eagerly would break the default command
    even when nothing is being saved. When True, run-storage readiness is
    checked before ``run_adapter`` (and therefore any provider call) runs,
    per the contract's "preflight before provider work" requirement; the run
    is inserted before anything is reported saved, and any storage failure
    propagates uncaught for the caller's existing ``execution_errors``
    boundary to translate into a sanitized nonzero exit — this function
    never converts a storage exception into a fabricated stored record. The
    saved run's ID is reported on stderr only, so existing JSON stdout
    documents remain byte-identical. Because a database is already open for
    Analysis Run storage on this path, ``run_adapter`` also receives a
    durable instrument-profile cache built over that same database.

    Args:
        save_run: Whether `--save-run` was requested.
        executed_at: The run's own execution clock, read once by the caller.
        request_factory: Builds the normalized ticker and validated method
            selection to persist under, matching exactly what `run_adapter`
            executes. Called at most once, and only when `save_run` is True.
        run_adapter: Calls the existing D1-D4 adapter with its already-bound
            dependencies, unchanged from the direct command's non-saving path,
            plus the durable profile cache (or None when not saving).
        normalize: One of `from_momentum_capture`/`from_graham_number_capture`/
            `from_graham_growth_capture`/`from_fcf_growth_capture`.

    Returns:
        The adapter's own native capture, exactly as `run_adapter` produced
        it, so the caller's existing presentation logic is unchanged.
    """
    if not save_run:
        return run_adapter(None)
    request = request_factory()
    database = SQLiteDatabase(settings)
    try:
        ensure_database_ready(database)
        repository = SQLiteAnalysisRunRepository(database)
        profile_cache = _production_instrument_profile_cache(database, clock=lambda: executed_at)
        holder: list[RawCaptureT] = []

        def capture() -> ExecutionCapture:
            raw = run_adapter(profile_cache)
            holder.append(raw)
            return normalize(raw)

        run = save_run_execution(request, capture=capture, repository=repository)
        typer.echo(f"Saved Analysis Run: {run.analysis_run_id}", err=True)
        return holder[0]
    finally:
        database.close()
