"""The refresh job: one refresh running on its own thread, which a caller starts, follows and stops.

:class:`RefreshJobs` holds the latest job of one server. Starting a job runs a prepared refresh on a daemon thread and
records the refresh's progress; a job that has ended stays until a new one replaces it. A caller follows a job by
asking for a :meth:`RefreshJob.view` of it, which reads the recorded events after a sequence number, and stops it with
:meth:`RefreshJob.stop`, which sets the refresh's cancellation.

The jobs are generic over the event the caller keeps. A caller supplies the function that builds an event, and measures
its serialized size, from a progress event; it is called once per event, when the event is recorded, never on a view,
so a poll builds nothing and copies the recorded events; the caller's response encodes the events a poll returns. The
application never learns what an event is. An event that cannot be built fails the job: no more entries are admitted,
and when the refresh returns the job is ``failed`` with that exception, keeping the events recorded before it.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar
from uuid import UUID

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.refresh import PreparedRefresh, RefreshOutcome, run_refresh
from investment_analysis_engine.application.strategy_run import StrategyRun
from investment_analysis_engine.core.failure_codes import FailureReasonCode
from investment_analysis_engine.workspace.refresh import RefreshProgress, RefreshTotals

logger = logging.getLogger(__name__)


class RefreshJobNotFoundError(ValueError):
    """No refresh job with the given ID is kept: it never existed, or a newer job replaced it."""

    reason_code: ClassVar[FailureReasonCode] = FailureReasonCode.REFRESH_JOB_NOT_FOUND


class RefreshJobRunningError(ValueError):
    """A refresh job is already running; the server runs one at a time."""

    reason_code: ClassVar[FailureReasonCode] = FailureReasonCode.REFRESH_JOB_RUNNING


class RefreshJobState(StrEnum):
    """Where a refresh job is: the vocabulary is open, so a client treats a value it does not know as unfinished."""

    RUNNING = "running"
    STOPPING = "stopping"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"


type EventRecorder[EventT] = Callable[[int, RefreshProgress[StrategyRun]], tuple[EventT, int]]
"""Builds the event of a progress event, given its sequence number, and returns it with its serialized size in bytes."""


@dataclass(frozen=True)
class RecordedEvent[EventT]:
    """One recorded event: the caller's event, built once, and the size in bytes of its serialization."""

    sequence: int
    event: EventT
    size: int


@dataclass(frozen=True)
class RefreshJobView[EventT]:
    """A consistent reading of a job at one moment.

    Attributes:
        refresh_id: The refresh's ID, which is the job's.
        watchlist_id: The watchlist refreshed, or ``None`` for a refresh of a list of entries.
        state: Where the job is.
        totals: How many jobs of the refresh were admitted, finished and are still to be admitted.
        events: The recorded events after the requested sequence, up to the size budget.
        next_after: The last sequence in ``events``, or the requested one when there are none.
        has_more: Whether recorded events remain after ``events``.
        outcome: The refresh's outcome, for a job that completed or stopped; ``None`` otherwise.
        failure: The exception that ended a failed job; ``None`` otherwise.
    """

    refresh_id: UUID
    watchlist_id: UUID | None
    state: RefreshJobState
    totals: RefreshTotals
    events: tuple[RecordedEvent[EventT], ...]
    next_after: int
    has_more: bool
    outcome: RefreshOutcome | None
    failure: BaseException | None


class RefreshJob[EventT]:
    """One refresh job: its state, its recorded events and the thread it runs on.

    Every read and write of the job's state holds one lock; the refresh itself runs outside it.
    """

    def __init__(
        self,
        context: ApplicationContext,
        prepared: PreparedRefresh,
        record: EventRecorder[EventT],
    ) -> None:
        """Keep what the job needs; nothing runs until :meth:`start`."""
        self._context = context
        self._prepared = prepared
        self._record = record
        self._lock = threading.Lock()
        self._cancellation = threading.Event()
        self._state = RefreshJobState.RUNNING
        self._totals = RefreshTotals(admitted=0, finished=0, remaining=len(prepared.snapshot.entries))
        self._events: list[RecordedEvent[EventT]] = []
        self._outcome: RefreshOutcome | None = None
        self._failure: BaseException | None = None
        self._recording_error: Exception | None = None
        self._thread = threading.Thread(target=self._run, name="refresh-job", daemon=True)

    @property
    def refresh_id(self) -> UUID:
        """The refresh's ID, which is the job's."""
        return self._prepared.snapshot.refresh_id

    def start(self) -> None:
        """Start the job's thread."""
        self._thread.start()

    def is_running(self) -> bool:
        """Whether the job's thread is alive; the shutdown wait and cancellation use this."""
        return self._thread.is_alive()

    def has_not_ended(self) -> bool:
        """Whether the job's state is ``running`` or ``stopping``: the job a start must not replace.

        The state becomes final only after the refresh has returned, so the coordinator of an ended job is done even
        while its thread is still winding down.
        """
        with self._lock:
            return self._state in (RefreshJobState.RUNNING, RefreshJobState.STOPPING)

    def wait(self, timeout: float) -> bool:
        """Wait up to ``timeout`` seconds for the job's thread to end; return whether it has."""
        self._thread.join(timeout)
        return not self._thread.is_alive()

    def stop(self) -> None:
        """Ask the refresh to stop admitting jobs; idempotent, and without effect on a job that has ended."""
        with self._lock:
            self._cancellation.set()
            if self._state is RefreshJobState.RUNNING:
                self._state = RefreshJobState.STOPPING

    def view(self, after: int, budget: int) -> RefreshJobView[EventT]:
        """Return the job as it is now, with the events after the sequence ``after``.

        Args:
            after: The last sequence the caller has seen; 0 for none. A value past the last event returns none.
            budget: The most bytes of events to return: events are taken in order until the next would take the total
                past it, and at least one is returned when one is waiting.
        """
        with self._lock:
            waiting = self._events[after:]
            taken: list[RecordedEvent[EventT]] = []
            total = 0
            for item in waiting:
                if taken and total + item.size > budget:
                    break
                taken.append(item)
                total += item.size
            return RefreshJobView(
                refresh_id=self.refresh_id,
                watchlist_id=self._prepared.snapshot.watchlist_id,
                state=self._state,
                totals=self._totals,
                events=tuple(taken),
                next_after=taken[-1].sequence if taken else after,
                has_more=len(taken) < len(waiting),
                outcome=self._outcome,
                failure=self._failure,
            )

    def _on_progress(self, progress: RefreshProgress[StrategyRun]) -> None:
        """Record one progress event: build and size it once, and count it. It never raises.

        Only the refresh's coordinating thread calls this, so the next sequence is known without the lock, and the
        event is built before the lock is taken: a view never waits for a document to be built.
        """
        recorded: RecordedEvent[EventT] | None = None
        if self._recording_error is None:
            sequence = len(self._events) + 1
            try:
                event, size = self._record(sequence, progress)
                recorded = RecordedEvent(sequence=sequence, event=event, size=size)
            except Exception as exc:
                self._recording_error = exc
                self._cancellation.set()
                logger.exception(
                    "A refresh event could not be recorded; the job stops admitting entries and will fail."
                )
        with self._lock:
            self._totals = progress.totals
            if recorded is not None:
                self._events.append(recorded)

    def _run(self) -> None:
        """Run the refresh and settle the job's state; the one place the job ends."""
        try:
            outcome = run_refresh(
                self._context,
                self._prepared,
                cancellation=self._cancellation,
                on_progress=self._on_progress,
            )
        except Exception as exc:
            logger.exception("The refresh job failed.")
            with self._lock:
                self._failure = exc
                self._state = RefreshJobState.FAILED
            return
        with self._lock:
            if self._recording_error is not None:
                self._failure = self._recording_error
                self._state = RefreshJobState.FAILED
                return
            self._outcome = outcome
            never_admitted = len(outcome.document.results) < len(self._prepared.snapshot.entries)
            self._state = RefreshJobState.STOPPED if never_admitted else RefreshJobState.COMPLETED


class RefreshJobs[EventT]:
    """The latest refresh job of one server, and the one operation that replaces it."""

    def __init__(
        self,
        record: EventRecorder[EventT],
    ) -> None:
        """Keep the event recorder.

        Args:
            record: Builds each event and its size; see :data:`EventRecorder`.
        """
        self._record = record
        self._lock = threading.Lock()
        self._latest: RefreshJob[EventT] | None = None

    def start(self, context: ApplicationContext, prepared: PreparedRefresh) -> RefreshJob[EventT]:
        """Start a job for a prepared refresh, replacing the latest job if it has ended.

        Raises:
            RefreshJobRunningError: If the latest job is still running.
        """
        with self._lock:
            if self._latest is not None and self._latest.has_not_ended():
                raise RefreshJobRunningError(
                    f"Refresh {self._latest.refresh_id} is still running; wait for it to end or stop it."
                )
            job = RefreshJob(context, prepared, self._record)
            self._latest = job
            job.start()
            return job

    def get(self, refresh_id: UUID) -> RefreshJob[EventT]:
        """Return the latest job if its refresh ID is ``refresh_id``.

        Raises:
            RefreshJobNotFoundError: If no job is kept, or the latest job has another ID.
        """
        with self._lock:
            latest = self._latest
        if latest is None or latest.refresh_id != refresh_id:
            raise RefreshJobNotFoundError(f"No refresh job with refresh ID {refresh_id} is kept.")
        return latest

    def latest(self) -> RefreshJob[EventT]:
        """Return the latest job.

        Raises:
            RefreshJobNotFoundError: If the server has not started a job.
        """
        with self._lock:
            latest = self._latest
        if latest is None:
            raise RefreshJobNotFoundError("This server has not started a refresh job.")
        return latest

    def begin_shutdown(self) -> None:
        """Stop the latest job from admitting more jobs, if it is running; the server is stopping."""
        with self._lock:
            latest = self._latest
        if latest is not None and latest.is_running():
            latest.stop()

    def wait_for_job(self, timeout: float) -> bool:
        """Wait up to ``timeout`` seconds for the latest job's thread to end; return whether it has (true with none)."""
        with self._lock:
            latest = self._latest
        return True if latest is None else latest.wait(timeout)


__all__ = [
    "EventRecorder",
    "RecordedEvent",
    "RefreshJob",
    "RefreshJobNotFoundError",
    "RefreshJobRunningError",
    "RefreshJobState",
    "RefreshJobView",
    "RefreshJobs",
]
