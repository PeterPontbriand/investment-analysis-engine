"""Refresh: a watchlist's entries, or a list of entries, run now and optionally saved, with progress.

A refresh is two operations. :func:`prepare_refresh` checks the worker count, opens the database, reads the frozen
snapshot, makes every check that can be made before any job runs, creates the refresh ID and returns a
:class:`PreparedRefresh`. :func:`run_refresh` runs the prepared refresh's jobs, runs the provider check once after the
batch and returns a :class:`RefreshOutcome`. A caller that needs the refresh's ID before the jobs run, such as the
API's refresh job, prepares first and runs later. Nothing here names a strategy: each job is dispatched through the
application tier, and the outcome carries only what every caller needs.

The caller owns cancellation (a ``threading.Event`` it sets, for example from a signal handler) and may observe
progress with a callback that receives each :class:`RefreshProgress` event on the thread that called the operation; a
finished event carries the job's :class:`StrategyRun` in memory.
"""

import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from uuid import uuid4

from pydantic import JsonValue

from investment_analysis_engine.application.analysis import exit_code_of
from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.database import open_database
from investment_analysis_engine.application.failures import describe_failure, require_job_ticker
from investment_analysis_engine.application.parameters import ActionParameterError
from investment_analysis_engine.application.provider_check import (
    ProviderCheckChoice,
    ProviderCheckFindings,
    provider_check_findings,
)
from investment_analysis_engine.application.providers import build_provider_probe, production_instrument_profile_cache
from investment_analysis_engine.application.selections import build_selection
from investment_analysis_engine.application.strategy_run import StrategyRun
from investment_analysis_engine.application.tier import analysis_runner_for
from investment_analysis_engine.application.watchlists import (
    REPEATED_IN_REQUEST,
    alias_for_method_id,
    duplicate_entry_error,
    entry_key,
    watchlist_repository,
)
from investment_analysis_engine.core.clock import utc_now
from investment_analysis_engine.core.failure_codes import FailureReasonCode
from investment_analysis_engine.core.operator_errors import InvalidParameterError
from investment_analysis_engine.core.tickers import normalize_ticker
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.strategy_wiring import RUN_SPECS_BY_KEY
from investment_analysis_engine.workspace.capture import ExecutionCapture
from investment_analysis_engine.workspace.refresh import (
    MAX_WORKERS,
    MIN_WORKERS,
    EmptyRefreshTargetError,
    JobFailure,
    RefreshJobResult,
    RefreshPolicy,
    RefreshProgress,
    RefreshSnapshot,
    RefreshSummary,
    coordinate_refresh,
)
from investment_analysis_engine.workspace.repositories.analysis_runs import SQLiteAnalysisRunRepository
from investment_analysis_engine.workspace.runs import WatchlistEntry
from investment_analysis_engine.workspace.strategy_types import AnalysisSelection
from investment_analysis_engine.workspace.watchlists import (
    WatchlistId,
    WatchlistName,
    WatchlistNotFoundError,
    WatchlistRef,
    not_found_message,
)
from investment_analysis_engine.workspace_documents.refresh import RefreshResultDocument, RefreshSummaryDocument


@dataclass(frozen=True)
class RefreshEntry:
    """One entry of a list of entries to refresh, as a caller describes it.

    Attributes:
        ticker: The ticker as the caller has it; it is trimmed and upper-cased.
        method_id: The canonical method identifier of the strategy.
        selection: The selection's fields by name, as :func:`build_selection` takes them.
    """

    ticker: str
    method_id: str
    selection: Mapping[str, JsonValue]


@dataclass(frozen=True)
class RefreshEntries:
    """A list of entries to refresh that belongs to no watchlist."""

    entries: tuple[RefreshEntry, ...]


type RefreshTarget = WatchlistRef | RefreshEntries
"""What a refresh runs: a watchlist, by name or ID, or a list of entries."""


@dataclass(frozen=True)
class PreparedRefresh:
    """A refresh that passed every check and has its ID, ready to run.

    Attributes:
        snapshot: The refresh's ID and its frozen entries, with the watchlist's identity when it is a watchlist's.
        workers: How many jobs run at once.
        save: Whether each finished job is persisted as an Analysis Run.
        provider_check: Whether to send one test request to a provider a failed job implicates after the batch.
    """

    snapshot: RefreshSnapshot
    workers: int
    save: bool
    provider_check: bool


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


def _combined(errors: Sequence[InvalidParameterError]) -> InvalidParameterError:
    """Return one error for several: the first's message and parameters, and every violation listed in order."""
    first = errors[0]
    return InvalidParameterError(
        str(first),
        parameters=first.parameters,
        violations=tuple(violation for error in errors for violation in error.violations),
    )


def _entry_names(error: ActionParameterError, index: int) -> dict[str, str]:
    """Return the name of each parameter a selection error names, as the entry ``index`` of the request spells it."""
    return {
        parameter: f"entries[{index}].method_id"
        if item.rule == "selection.undeclared_method"
        else f"entries[{index}].{parameter}"
        for item in error.errors
        for parameter in item.action_parameters
    }


def _snapshot_entries(context: ApplicationContext, target: RefreshEntries) -> tuple[WatchlistEntry, ...]:
    """Build the entries of a list to refresh, reporting every rejected entry at once.

    Each entry's ticker is normalized and its selection is built by :func:`build_selection`; an error is named
    ``entries[<index>].<field>`` with the 0-based index, as the request lists them. An entry that repeats an earlier
    one, the same ticker with an equal selection, is ``entries.duplicate``.

    Raises:
        ActionParameterError: If the list is empty (parameter ``entries``, rule ``refresh.entries_empty``).
        InvalidParameterError: If any entry is rejected; the first's message and parameters, every rejection listed.
    """
    if not target.entries:
        raise ActionParameterError(
            "{entries} must hold at least one entry.", parameters=("entries",), rule="refresh.entries_empty"
        )
    errors: list[InvalidParameterError] = []
    seen: set[tuple[str, str]] = set()
    built: list[WatchlistEntry] = []
    for index, item in enumerate(target.entries):
        try:
            ticker = normalize_ticker(item.ticker)
        except ValueError:
            errors.append(
                ActionParameterError(
                    f"{{entries[{index}].ticker}} must be a non-empty symbol.",
                    parameters=(f"entries[{index}].ticker",),
                    rule="refresh.blank_ticker",
                )
            )
            continue
        try:
            selection = build_selection(context, item.method_id, item.selection)
        except ActionParameterError as error:
            errors.append(error.named(_entry_names(error, index)))
            continue
        key = entry_key(ticker, selection)
        if key in seen:
            errors.append(duplicate_entry_error(f"entries[{index}]", ticker, selection.method_id, REPEATED_IN_REQUEST))
            continue
        seen.add(key)
        built.append(WatchlistEntry(ticker=ticker, selection=selection))
    if errors:
        raise _combined(errors)
    return tuple(built)


def _watchlist_snapshot(context: ApplicationContext, ref: WatchlistRef) -> RefreshSnapshot:
    """Read the watchlist ``ref`` addresses in one lookup and freeze it as a snapshot with a new refresh ID.

    Raises:
        WatchlistNotFoundError: If no watchlist matches ``ref``.
        EmptyRefreshTargetError: If the watchlist has no entries.
        StoredSelectionError: If an entry of the watchlist cannot be read.
        DatabaseReadinessError: If the database is missing, busy or not at the expected revision.
    """
    with open_database(context) as database:
        repository = watchlist_repository(database)
        watchlist = repository.get_by_id(ref.watchlist_id) if isinstance(ref, WatchlistId) else repository.get(ref.name)
    if watchlist is None:
        raise WatchlistNotFoundError(not_found_message(ref))
    if not watchlist.entries:
        label = ref.name if isinstance(ref, WatchlistName) else watchlist.display_name
        raise EmptyRefreshTargetError(f"Watchlist {label!r} has no entries; there is nothing to refresh.")
    return RefreshSnapshot(
        refresh_id=uuid4(),
        entries=watchlist.entries,
        watchlist_id=watchlist.watchlist_id,
        watchlist_name=watchlist.display_name,
    )


def prepare_refresh(
    context: ApplicationContext,
    target: RefreshTarget,
    *,
    workers: int,
    save: bool,
    provider_check: bool,
) -> PreparedRefresh:
    """Check a refresh, freeze its entries and give it an ID, without running any job.

    The worker count and, for a list of entries, every entry are checked before the database is opened. The
    database is then opened and checked, so a missing, busy or outdated one is reported here and not after the caller
    has acknowledged the refresh; for a watchlist the entries are read in that same step.

    Args:
        context: What the operation needs from its caller.
        target: A watchlist by name or ID, or a list of entries.
        workers: How many jobs run at once, from ``MIN_WORKERS`` to ``MAX_WORKERS``.
        save: Whether :func:`run_refresh` persists each finished job as an Analysis Run.
        provider_check: Whether :func:`run_refresh` sends one test request to a provider a failed job implicates.

    Returns:
        The prepared refresh, whose snapshot holds the refresh's ID.

    Raises:
        ActionParameterError: If ``workers`` is out of range (parameter ``workers``), or a list of entries is empty
            (parameter ``entries``, rule ``refresh.entries_empty``); nothing is opened.
        InvalidParameterError: If a list of entries has a rejected entry (parameters named
            ``entries[<index>].<field>``, with ``entries.duplicate`` for a repeat); nothing is opened.
        WatchlistNotFoundError: If no watchlist matches the target.
        EmptyRefreshTargetError: If the watchlist has no entries.
        StoredSelectionError: If an entry of the watchlist cannot be read.
        DatabaseReadinessError: If the database is missing, busy or not at the expected revision.
    """
    _check_workers(workers)
    if isinstance(target, RefreshEntries):
        entries = _snapshot_entries(context, target)
        with open_database(context):
            pass
        snapshot = RefreshSnapshot(refresh_id=uuid4(), entries=entries)
    else:
        snapshot = _watchlist_snapshot(context, target)
    return PreparedRefresh(snapshot=snapshot, workers=workers, save=save, provider_check=provider_check)


def _run_job(
    context: ApplicationContext,
    ticker: str,
    selection: AnalysisSelection,
    *,
    profile_cache: InstrumentProfileResolver,
) -> StrategyRun:
    """Run one (ticker, selection) job through its strategy's run function.

    The run function composes entirely fresh provider, resolver and cache dependencies per call, job-scoped as the
    coordinator's contract requires for safe concurrent use, exactly as a direct analysis composes them. The durable
    instrument-profile cache is the one exception: it is built once per refresh over the operation's database and
    shared across concurrent jobs, like the Analysis Run repository, and ``CachedInstrumentProfileResolver``
    serializes its own per-ticker critical section. The run's own clock is read here, once per job. A selection of a
    strategy with no application-tier entry raises ``UndeclaredStrategyError``; no strategy is a default.
    """
    require_job_ticker(ticker)
    return analysis_runner_for(selection)(
        context, ticker, selection, executed_at=utc_now(), profile_cache=profile_cache
    )


def _capture_of(run: StrategyRun) -> ExecutionCapture:
    """Return the capture of a job's run."""
    return run.execution


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
    heading = (
        "Refresh " + str(summary.refresh_id)
        if summary.watchlist_name is None
        else f"Refresh {summary.refresh_id} for {summary.watchlist_name!r}"
    )
    lines = [f"{heading}:"]
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


def build_refresh_result_document(result: RefreshJobResult) -> RefreshResultDocument:
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
        results=tuple(build_refresh_result_document(result) for result in summary.results),
        counts=summary.counts,
        provider_check=findings.element(),
    )


def run_refresh(
    context: ApplicationContext,
    prepared: PreparedRefresh,
    *,
    cancellation: threading.Event | None = None,
    on_progress: Callable[[RefreshProgress[StrategyRun]], None] | None = None,
) -> RefreshOutcome:
    """Run every entry of a prepared refresh, saving each result when it asked, and report it.

    Args:
        context: What the operation needs from its caller; the database, the jobs and the provider check are built
            from its settings.
        prepared: The refresh :func:`prepare_refresh` returned.
        cancellation: A stop signal the caller sets; once set, no new job is admitted and every admitted job
            finishes and is settled normally.
        on_progress: An observer called on the calling thread with each started and finished job; a finished event
            carries the job's run in memory. A callback that raises is logged once and then ignored, and the
            refresh is unaffected.

    Returns:
        The summary document, whether any job failed and the text renderer.

    Raises:
        DatabaseReadinessError: If the database is missing, busy or not at the expected revision when the jobs
            begin.
    """
    with open_database(context) as database:
        profile_cache = production_instrument_profile_cache(context, database, clock=utc_now)

        def executor(ticker: str, selection: AnalysisSelection) -> StrategyRun:
            return _run_job(context, ticker, selection, profile_cache=profile_cache)

        summary = coordinate_refresh(
            prepared.snapshot,
            repository=SQLiteAnalysisRunRepository(database),
            executor=executor,
            capture_of=_capture_of,
            run_specs=RUN_SPECS_BY_KEY,
            describe=_describe_job_failure,
            policy=RefreshPolicy(workers=prepared.workers),
            save=prepared.save,
            cancellation=cancellation,
            on_progress=on_progress,
        )
    findings = provider_check_findings(
        (result.provider_failure for result in summary.results),
        ProviderCheckChoice(build_provider_probe(context), requested=prepared.provider_check),
    )

    def render_text() -> str:
        return "\n".join((*findings.lines(), _refresh_text(summary)))

    return RefreshOutcome(
        document=build_refresh_document(summary, findings),
        failed=_refresh_has_failure(summary),
        text_renderer=render_text,
    )


__all__ = [
    "PreparedRefresh",
    "RefreshEntries",
    "RefreshEntry",
    "RefreshOutcome",
    "RefreshTarget",
    "build_refresh_document",
    "build_refresh_result_document",
    "prepare_refresh",
    "run_refresh",
]
