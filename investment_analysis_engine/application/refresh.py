"""Refresh: every entry of one watchlist, run now and optionally saved, with progress.

:func:`refresh_watchlist` is the one execution path of a refresh. It checks the worker count, opens and checks the
database, hands the watchlist's frozen snapshot to the workspace coordinator with a fully bound executor, runs the
provider check once after the batch and returns a :class:`RefreshOutcome`. Nothing here names a strategy: each job is
dispatched through the application tier, and the outcome carries only what every caller needs.

The caller owns cancellation (a ``threading.Event`` it sets, for example from a signal handler) and may observe
progress with a callback that receives each :class:`RefreshProgress` event on the thread that called the operation.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass

from investment_analysis_engine.application.analysis import exit_code_of
from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.database import open_database
from investment_analysis_engine.application.failures import describe_failure
from investment_analysis_engine.application.parameters import ActionParameterError
from investment_analysis_engine.application.provider_check import (
    ProviderCheckChoice,
    ProviderCheckFindings,
    provider_check_findings,
)
from investment_analysis_engine.application.providers import build_provider_probe, production_instrument_profile_cache
from investment_analysis_engine.application.tier import refresh_executor_for
from investment_analysis_engine.application.watchlists import alias_for_method_id, watchlist_repository
from investment_analysis_engine.core.clock import utc_now
from investment_analysis_engine.core.failure_codes import FailureReasonCode
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.strategy_wiring import RUN_SPECS_BY_KEY
from investment_analysis_engine.workspace.capture import ExecutionCapture
from investment_analysis_engine.workspace.refresh import (
    DEFAULT_WORKERS,
    MAX_WORKERS,
    MIN_WORKERS,
    JobFailure,
    RefreshJobResult,
    RefreshPolicy,
    RefreshProgress,
    RefreshSummary,
    coordinate_refresh,
)
from investment_analysis_engine.workspace.repositories.analysis_runs import SQLiteAnalysisRunRepository
from investment_analysis_engine.workspace.strategy_types import AnalysisSelection
from investment_analysis_engine.workspace.watchlists import WatchlistRef
from investment_analysis_engine.workspace_documents.refresh import RefreshResultDocument, RefreshSummaryDocument


@dataclass(frozen=True)
class RefreshOutcome:
    """The result of one refresh, which holds no raw execution and no strategy-specific type.

    Attributes:
        document: The refresh summary document, as ``--json`` writes it, provider-check element included.
        failed: Whether any job raised or ended in an outcome after which a direct analysis is a failure.
        text_renderer: Renders the complete text output; call it through :meth:`render_text`.
    """

    document: RefreshSummaryDocument
    failed: bool
    text_renderer: Callable[[], str]

    def render_text(self) -> str:
        """Return the complete text output: the provider-check lines first, then the summary."""
        return self.text_renderer()


def _check_workers(workers: int) -> None:
    """Reject a worker count outside the allowed range.

    Raises:
        ActionParameterError: If ``workers`` is out of range (parameter ``workers``).
    """
    if not MIN_WORKERS <= workers <= MAX_WORKERS:
        raise ActionParameterError(
            "{workers} must be between {minimum} and {maximum}.",
            parameters=("workers",),
            rule="refresh.workers_range",
            arguments={"value": workers, "minimum": MIN_WORKERS, "maximum": MAX_WORKERS},
        )


def _refresh_executor(
    context: ApplicationContext, ticker: str, selection: AnalysisSelection, *, profile_cache: InstrumentProfileResolver
) -> ExecutionCapture:
    """Dispatch one (ticker, selection) job to its strategy's refresh executor.

    Each executor composes entirely fresh provider/resolver/cache dependencies per call - job-scoped, as the
    coordinator's contract requires for safe concurrent use - mirroring how each strategy's direct command composes
    the same dependencies for one invocation. The durable instrument-profile cache is the one exception: it is built
    once per refresh over the operation's database and shared across concurrent jobs, exactly like the Analysis Run
    repository. ``CachedInstrumentProfileResolver`` serializes its own per-ticker critical section, so sharing it
    across worker threads is safe by the resolver's own contract. A selection of a strategy with no application-tier
    entry raises ``UndeclaredStrategyError``; no strategy is a default.
    """
    return refresh_executor_for(selection)(context, ticker, selection, profile_cache=profile_cache)


def _describe_job_failure(exception: BaseException, ticker: str, saving: bool) -> JobFailure:
    """Choose a failed refresh job's code and message with the rule the direct commands use."""
    description = describe_failure(exception, ticker, saving=saving)
    return JobFailure(reason_code=description.code.value, error=description.message)


def _refresh_has_failure(summary: RefreshSummary) -> bool:
    """True if any job raised, or produced an outcome for which ``exit_code_of`` is non-zero."""
    for result in summary.results:
        if result.error is not None:
            return True
        status = result.run.status if result.run is not None else result.outcome
        if status is not None and exit_code_of(status):
            return True
    return False


def _refresh_text(summary: RefreshSummary) -> str:
    lines = [f"Refresh {summary.refresh_id} for {summary.watchlist_name!r}:"]
    for result in summary.results:
        method = alias_for_method_id(result.method_id)
        if result.run is not None:
            lines.append(f"  {result.run.analysis_run_id}  {result.ticker:<10} {method:<24} {result.run.status.value}")
        elif result.outcome is not None:
            lines.append(f"  {'(not saved)':<38}{result.ticker:<10} {method:<24} {result.outcome.value}")
        else:
            lines.append(f"  {'':<38}{result.ticker:<10} {method:<24} error: {result.error}")
    counts = ", ".join(f"{key}={value}" for key, value in sorted(summary.counts.items()))
    lines.append(f"Counts: {counts}" if counts else "Counts: (none)")
    return "\n".join(lines)


def _refresh_result_document(result: RefreshJobResult) -> RefreshResultDocument:
    """Build one job's entry; its status is the saved run's, else the unsaved outcome's, else null."""
    status = result.run.status if result.run is not None else result.outcome
    return RefreshResultDocument(
        ticker=result.ticker,
        method_id=result.method_id,
        analysis_run_id=None if result.run is None else result.run.analysis_run_id,
        saved=result.run is not None,
        status=status,
        error=result.error,
        reason_code=None if result.reason_code is None else FailureReasonCode(result.reason_code),
    )


def build_refresh_document(summary: RefreshSummary, findings: ProviderCheckFindings) -> RefreshSummaryDocument:
    """Build the refresh summary document, carrying what the provider check found."""
    return RefreshSummaryDocument(
        refresh_id=summary.refresh_id,
        watchlist_id=summary.watchlist_id,
        watchlist_name=summary.watchlist_name,
        results=tuple(_refresh_result_document(result) for result in summary.results),
        counts=summary.counts,
        provider_check=findings.element(),
    )


def refresh_watchlist(  # noqa: PLR0913
    context: ApplicationContext,
    ref: WatchlistRef,
    *,
    workers: int = DEFAULT_WORKERS,
    save: bool,
    provider_check: bool,
    cancellation: threading.Event | None = None,
    on_progress: Callable[[RefreshProgress], None] | None = None,
) -> RefreshOutcome:
    """Run every entry of one watchlist, saving each result when asked, and report it.

    Args:
        context: What the operation needs from its caller; the database, the executors and the provider check are
            built from its settings.
        ref: The watchlist to refresh, by name or by ID.
        workers: How many jobs run at once, from ``MIN_WORKERS`` to ``MAX_WORKERS``.
        save: Whether to persist each finished job as an Analysis Run.
        provider_check: Whether to send one test request to a provider a failed job implicates after the batch;
            false reports that the check was turned off.
        cancellation: A stop signal the caller sets; once set, no new job is admitted and every admitted job
            finishes and is settled normally.
        on_progress: An observer called on the calling thread with each started and finished job; a callback that
            raises is logged once and then ignored, and the refresh is unaffected.

    Returns:
        The summary document, whether any job failed and the text renderer.

    Raises:
        ActionParameterError: If ``workers`` is out of range (parameter ``workers``); nothing is opened.
        WatchlistNotFoundError: If no watchlist matches ``ref``.
        EmptyRefreshTargetError: If the watchlist has no entries.
        DatabaseReadinessError: If the database is missing, busy or not at the expected revision.
    """
    _check_workers(workers)
    with open_database(context) as database:
        profile_cache = production_instrument_profile_cache(context, database, clock=utc_now)
        summary = coordinate_refresh(
            ref,
            watchlists=watchlist_repository(database),
            repository=SQLiteAnalysisRunRepository(database),
            executor=lambda ticker, selection: _refresh_executor(
                context, ticker, selection, profile_cache=profile_cache
            ),
            run_specs=RUN_SPECS_BY_KEY,
            describe=_describe_job_failure,
            policy=RefreshPolicy(workers=workers),
            save=save,
            cancellation=cancellation,
            on_progress=on_progress,
        )
    findings = provider_check_findings(
        (result.provider_failure for result in summary.results),
        ProviderCheckChoice(build_provider_probe(context), requested=provider_check),
    )

    def render_text() -> str:
        return "\n".join((*findings.lines(), _refresh_text(summary)))

    return RefreshOutcome(
        document=build_refresh_document(summary, findings),
        failed=_refresh_has_failure(summary),
        text_renderer=render_text,
    )


__all__ = ["RefreshOutcome", "build_refresh_document", "refresh_watchlist"]
