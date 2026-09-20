"""Multi-ticker refresh service for one watchlist snapshot (G1 sequential, G2 concurrent).

``refresh_watchlist`` freezes one watchlist's ordered entries in a single
read (the contract's "one read snapshot" requirement: edits made to the
watchlist afterward apply only to the *next* refresh, never to this one),
then executes every (ticker, selection) entry against an injected
``executor`` callable, persisting each finished result through
:func:`src.workspace.execution.execute` unless the caller passes
``save=False``, in which case every entry still executes but nothing is
written to storage — a preview of current numbers across a watchlist
without adding to its saved history.

This module owns no provider, resolver, cache, or CLI composition at all:
``executor`` is supplied fully bound by the caller (mirroring the D1-D4
adapters' own "borrow dependencies, don't construct them" convention), and
this service never invokes a Typer command or parses rendered/terminal
output back into a canonical result.

``policy.workers`` selects between two admission strategies over the exact
same per-job contract:

- ``workers == 1`` (the default): strictly sequential, one job at a time -
  byte-identical to G1's original behavior, so every existing caller that
  never passes ``policy`` is unaffected by G2's addition.
- ``workers > 1``: bounded concurrent admission (G2). At most ``workers``
  jobs run at once; a worker only calls the injected ``executor`` (job-scoped
  dependencies are the caller's responsibility, exactly as documented on
  ``executor`` below); the coordinator - this function's own calling thread,
  never a worker thread - is the only thread that ever calls :func:`execute`
  (and therefore the only thread that ever calls ``repository.insert``), and
  it persists one finished job before admitting its replacement, never
  eagerly submitting the whole remaining queue.

A job's failure - whether the adapter itself raises, or the terminal insert
fails - is isolated to that one job and recorded as an explicit result; it
never aborts the remaining (ticker, selection) pairs, under either admission
strategy. Deciding whether a *storage* failure specifically should stop
admitting further work is explicitly a G3 concern (interruption/stop
semantics), not this slice's; both strategies provide the uniform per-job
isolation that behavior is built on.

``cancellation`` (G3) is an optional cooperative stop signal: a caller (the
refresh CLI, on Ctrl+C) sets it from another thread. Once set, no *new* job
is admitted - remaining, never-started (ticker, selection) pairs simply do
not appear in the returned summary, never as a fabricated "cancelled" row -
while any job already admitted is left to run to completion and its outcome
is still persisted normally. Nothing here ever raises `KeyboardInterrupt` or
attempts to kill a running thread; "graceful" means cooperative admission
control only.
"""

import threading
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from src.workspace.execution import AnalysisRunSink, BatchContext, ExecutionCapture, execute
from src.workspace.models import RunOutcome
from src.workspace.requests import AnalysisRequest, AnalysisSelection
from src.workspace.runs import AnalysisRun, Watchlist


class WatchlistNotFoundError(ValueError):
    """No watchlist exists with the requested name."""


class EmptyRefreshTargetError(ValueError):
    """The watchlist has no members or no selections; refresh has nothing to do.

    Raised before any job runs, matching the contract's "usage error before
    work begins" requirement — never a zero-job refresh silently succeeding.
    """


class WatchlistLookup(Protocol):
    """The one read capability refresh needs: a frozen-snapshot lookup by name."""

    def get(self, name: str) -> Watchlist | None:
        """Return the watchlist matching ``name``, or None if it does not exist."""
        ...


@dataclass(frozen=True)
class RefreshPolicy:
    """Bounded worker count for a refresh.

    ``workers`` is a small local-workspace concurrency knob (default 2,
    range 1-4), not a financial assumption. This is the class's own default
    for a caller that wants concurrency without picking a specific count;
    :func:`refresh_watchlist` itself defaults to a *different*,
    strictly-sequential policy (``workers=1``) so that no existing caller's
    behavior changes merely because this parameter was added - a caller
    must explicitly opt into concurrent admission by passing
    ``RefreshPolicy()`` or an explicit worker count.
    """

    workers: int = 2

    def __post_init__(self) -> None:
        """Reject an out-of-range worker count."""
        if not 1 <= self.workers <= 4:
            raise ValueError("workers must be between 1 and 4.")


_SEQUENTIAL_POLICY = RefreshPolicy(workers=1)


@dataclass(frozen=True)
class RefreshJobResult:
    """One (ticker, selection) attempt's outcome within a refresh.

    Exactly one of ``run``/``outcome``/``error`` is set: ``run`` for any
    attempt that produced and persisted a terminal :class:`AnalysisRun`
    (regardless of its own financial outcome — completed, unavailable,
    not_applicable and failed are all still a *produced* run); ``outcome``
    for an attempt that executed successfully but was not persisted
    (``refresh_watchlist(..., save=False)``) — the attempt has a real
    financial outcome but no addressable run, so it is never given a
    fabricated ``analysis_run_id``; ``error`` for an attempt whose adapter
    or persistence step raised before a result could be assembled. ``error``
    carries the exception's own message for caller-side diagnosis — it is
    not persisted anywhere, and any user-facing sanitization is the
    caller's (eventual CLI) responsibility, mirroring how ``execution_errors``
    sanitizes at the presentation boundary rather than deep in a service.
    """

    ticker: str
    method_id: str
    run: AnalysisRun | None = None
    outcome: RunOutcome | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        """Enforce the run-xor-outcome-xor-error invariant."""
        set_count = sum(value is not None for value in (self.run, self.outcome, self.error))
        if set_count != 1:
            raise ValueError("Exactly one of run, outcome, or error must be set.")


@dataclass(frozen=True)
class RefreshSummary:
    """The complete, ordered outcome of one refresh attempt."""

    refresh_id: UUID
    watchlist_id: UUID
    watchlist_name: str
    results: tuple[RefreshJobResult, ...]

    @property
    def counts(self) -> dict[str, int]:
        """Count results by outcome; a job that never produced a run or outcome counts as ``error``."""
        counts: dict[str, int] = {}
        for item in self.results:
            if item.run is not None:
                key = item.run.status.value
            elif item.outcome is not None:
                key = item.outcome.value
            else:
                key = "error"
            counts[key] = counts.get(key, 0) + 1
        return counts


def refresh_watchlist(  # noqa: PLR0913
    name: str,
    *,
    watchlists: WatchlistLookup,
    repository: AnalysisRunSink,
    executor: Callable[[str, AnalysisSelection], ExecutionCapture],
    save: bool = True,
    policy: RefreshPolicy = _SEQUENTIAL_POLICY,
    refresh_id_factory: Callable[[], UUID] = uuid4,
    id_factory: Callable[[], UUID] = uuid4,
    clock: Callable[[], datetime] | None = None,
    cancellation: threading.Event | None = None,
) -> RefreshSummary:
    """Execute every (member, selection) pair in one watchlist's frozen snapshot.

    Args:
        name: The watchlist to refresh, matched case-insensitively by ``watchlists``.
        watchlists: A read-only lookup for the frozen snapshot; only ``get`` is used.
        repository: An already-composed, ready sink for each terminal run.
            Under ``policy.workers > 1`` it is still only ever called from
            this function's own calling thread, never from a worker thread.
        executor: Runs one method adapter for one (ticker, selection) pair and
            returns its normalized capture — fully bound with whatever
            provider/resolver/cache dependencies it needs, exactly as a
            direct command's own adapter call is bound. Job-scoped: called
            once per (ticker, selection) pair, never shared/reused state
            across calls unless the caller has proven that is safe. Under
            ``policy.workers > 1`` it may be called concurrently from
            multiple worker threads, so this job-scoping requirement is load
            -bearing, not merely a style preference.
        save: When ``True`` (the default), every finished job is persisted
            exactly as before. When ``False``, every entry still executes
            but no job is persisted and no :class:`AnalysisRun` is ever
            constructed — a preview refresh; each result's outcome is
            available on :attr:`RefreshJobResult.outcome` instead of
            :attr:`RefreshJobResult.run`.
        policy: Selects sequential (``workers=1``, the default) or bounded
            concurrent (``workers>1``) admission; see the module docstring.
        refresh_id_factory: Produces the one refresh identity shared by
            every job in this call; defaults to `uuid4`.
        id_factory: Produces each individual run's identity; defaults to `uuid4`.
        clock: Produces aware UTC instants for each job's timing; defaults
            to the wall clock. Under concurrent admission this is called
            from worker threads and must itself be safe to call that way;
            the default wall clock is.
        cancellation: An optional cooperative stop signal a caller sets from
            another thread (typically a Ctrl+C handler); see the module
            docstring. ``None`` (the default) means refresh always runs
            every job to completion.

    Returns:
        The ordered outcome of every job that was admitted, in the
        watchlist's own entry order, whether it succeeded, produced a
        non-completed financial outcome, or failed to produce a run at all.
        Order is the watchlist's own snapshot order regardless of actual
        completion order under concurrent admission. A job never admitted
        because ``cancellation`` was already set does not appear at all.

    Raises:
        WatchlistNotFoundError: If no watchlist matches ``name``.
        EmptyRefreshTargetError: If the watchlist has no entries. Not raised
            mid-refresh; checked before any job runs.
    """
    watchlist = watchlists.get(name)
    if watchlist is None:
        raise WatchlistNotFoundError(f"No watchlist named {name!r} exists.")
    if not watchlist.entries:
        raise EmptyRefreshTargetError(f"Watchlist {name!r} has no entries; there is nothing to refresh.")

    refresh_id = refresh_id_factory()
    resolved_clock = clock if clock is not None else lambda: datetime.now(UTC)
    jobs = [(entry.ticker, entry.selection) for entry in watchlist.entries]

    if policy.workers == 1:
        results: list[RefreshJobResult] = []
        for position, (ticker, selection) in enumerate(jobs):
            if cancellation is not None and cancellation.is_set():
                break

            def capture(
                captured_ticker: str = ticker, captured_selection: AnalysisSelection = selection
            ) -> ExecutionCapture:
                return executor(captured_ticker, captured_selection)

            if not save:
                try:
                    result = capture()
                    results.append(
                        RefreshJobResult(ticker=ticker, method_id=selection.method_id, outcome=result.outcome)
                    )
                except Exception as exc:  # noqa: BLE001 - one job's failure must never abort the batch
                    results.append(RefreshJobResult(ticker=ticker, method_id=selection.method_id, error=str(exc)))
                continue

            batch = BatchContext(
                refresh_id=refresh_id,
                batch_position=position,
                watchlist_id=watchlist.watchlist_id,
                watchlist_name=watchlist.display_name,
            )
            try:
                run = execute(
                    AnalysisRequest(ticker=ticker, selection=selection),
                    capture=capture,
                    repository=repository,
                    id_factory=id_factory,
                    clock=resolved_clock,
                    batch=batch,
                )
                results.append(RefreshJobResult(ticker=ticker, method_id=selection.method_id, run=run))
            except Exception as exc:  # noqa: BLE001 - one job's failure must never abort the batch
                results.append(RefreshJobResult(ticker=ticker, method_id=selection.method_id, error=str(exc)))

        return RefreshSummary(
            refresh_id=refresh_id,
            watchlist_id=watchlist.watchlist_id,
            watchlist_name=watchlist.display_name,
            results=tuple(results),
        )

    return _refresh_concurrently(
        jobs,
        watchlist=watchlist,
        refresh_id=refresh_id,
        workers=policy.workers,
        repository=repository,
        executor=executor,
        save=save,
        id_factory=id_factory,
        clock=resolved_clock,
        cancellation=cancellation,
    )


@dataclass(frozen=True)
class _JobOutcome:
    """One worker's raw result, before the coordinator persists or records it.

    Exactly one of ``capture``/``error`` is set, mirroring
    :class:`RefreshJobResult`'s own invariant one layer earlier.
    """

    started_at: datetime
    completed_at: datetime
    capture: ExecutionCapture | None
    error: BaseException | None

    def __post_init__(self) -> None:
        """Enforce the capture-xor-error invariant."""
        if (self.capture is None) == (self.error is None):
            raise ValueError("Exactly one of capture or error must be set.")


def _replay_clock(started_at: datetime, completed_at: datetime) -> Callable[[], datetime]:
    """Replay two already-measured instants through ``execute``'s own two ``clock()`` calls.

    A worker measures ``started_at``/``completed_at`` around its own call to
    ``executor`` (the real work), in its own thread. The coordinator then
    calls :func:`execute` with an already-computed capture — a call whose
    own two ``clock()`` calls would otherwise record a near-zero window
    around nothing but handing that capture off, not the real work time.
    Passing this replay clock instead makes the persisted run's
    ``started_at``/``completed_at`` reflect when the work actually happened.
    """
    values = iter((started_at, completed_at))
    return lambda: next(values)


def _refresh_concurrently(  # noqa: PLR0913
    jobs: list[tuple[str, AnalysisSelection]],
    *,
    watchlist: Watchlist,
    refresh_id: UUID,
    workers: int,
    repository: AnalysisRunSink,
    executor: Callable[[str, AnalysisSelection], ExecutionCapture],
    save: bool,
    id_factory: Callable[[], UUID],
    clock: Callable[[], datetime],
    cancellation: threading.Event | None,
) -> RefreshSummary:
    """Bounded concurrent admission (G2/G3) over the same per-job contract as the sequential path.

    At most ``workers`` jobs are ever in flight. A worker's only
    responsibility is calling ``executor`` and reporting back what happened;
    this function's own calling thread — the coordinator — is the only
    thread that ever calls :func:`execute` (and therefore the only thread
    that ever calls ``repository.insert``) when ``save`` is true, and it
    admits one replacement job only after settling (persisting, or recording
    the outcome/failure of) the job whose completion freed that slot.

    Once ``cancellation`` is set, no further job is admitted; any future
    still pending but not yet started is cancelled (a narrow window that can
    occur even under bounded admission), while an already-running job is
    left to finish naturally and its outcome is still persisted.
    """

    def run_one(ticker: str, selection: AnalysisSelection) -> _JobOutcome:
        started_at = clock()
        try:
            capture = executor(ticker, selection)
        except Exception as exc:  # noqa: BLE001 - reported to the coordinator, never crashes the worker
            return _JobOutcome(started_at=started_at, completed_at=clock(), capture=None, error=exc)
        return _JobOutcome(started_at=started_at, completed_at=clock(), capture=capture, error=None)

    remaining = iter(enumerate(jobs))
    pending: dict[Future[_JobOutcome], tuple[int, str, AnalysisSelection]] = {}
    results: dict[int, RefreshJobResult] = {}

    with ThreadPoolExecutor(max_workers=workers) as pool:

        def admit_next() -> None:
            if cancellation is not None and cancellation.is_set():
                return
            item = next(remaining, None)
            if item is None:
                return
            position, (ticker, selection) = item
            pending[pool.submit(run_one, ticker, selection)] = (position, ticker, selection)

        for _ in range(min(workers, len(jobs))):
            admit_next()

        while pending:
            done, _still_pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                position, ticker, selection = pending.pop(future)
                outcome = future.result()
                batch = BatchContext(
                    refresh_id=refresh_id,
                    batch_position=position,
                    watchlist_id=watchlist.watchlist_id,
                    watchlist_name=watchlist.display_name,
                )
                results[position] = _settle(
                    outcome,
                    ticker=ticker,
                    selection=selection,
                    batch=batch,
                    repository=repository,
                    save=save,
                    id_factory=id_factory,
                )
                admit_next()
            if cancellation is not None and cancellation.is_set():
                for leftover in list(pending):
                    if leftover.cancel():
                        pending.pop(leftover)

    return RefreshSummary(
        refresh_id=refresh_id,
        watchlist_id=watchlist.watchlist_id,
        watchlist_name=watchlist.display_name,
        results=tuple(results[position] for position in sorted(results)),
    )


def _settle(  # noqa: PLR0913
    outcome: _JobOutcome,
    *,
    ticker: str,
    selection: AnalysisSelection,
    batch: BatchContext,
    repository: AnalysisRunSink,
    save: bool,
    id_factory: Callable[[], UUID],
) -> RefreshJobResult:
    """Persist a worker's evidence on the coordinator thread, or record its outcome/failure.

    Always runs on the coordinator thread — never inside a worker. When
    ``save`` is false, a successful worker outcome is recorded without ever
    calling :func:`execute`/``repository.insert``.
    """
    if outcome.error is not None:
        return RefreshJobResult(ticker=ticker, method_id=selection.method_id, error=str(outcome.error))
    captured = outcome.capture
    assert captured is not None  # enforced by _JobOutcome's own capture-xor-error invariant
    if not save:
        return RefreshJobResult(ticker=ticker, method_id=selection.method_id, outcome=captured.outcome)
    try:
        run = execute(
            AnalysisRequest(ticker=ticker, selection=selection),
            capture=lambda: captured,
            repository=repository,
            id_factory=id_factory,
            clock=_replay_clock(outcome.started_at, outcome.completed_at),
            batch=batch,
        )
        return RefreshJobResult(ticker=ticker, method_id=selection.method_id, run=run)
    except Exception as exc:  # noqa: BLE001 - one job's failure must never abort the batch
        return RefreshJobResult(ticker=ticker, method_id=selection.method_id, error=str(exc))


__all__ = [
    "EmptyRefreshTargetError",
    "RefreshJobResult",
    "RefreshPolicy",
    "RefreshSummary",
    "WatchlistLookup",
    "WatchlistNotFoundError",
    "refresh_watchlist",
]
