"""The refresh job: its states, its polling, its one-at-a-time rule and its shutdown hooks, with fake runners."""

import threading
from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.refresh import PreparedRefresh, RefreshOutcome, run_refresh
from investment_analysis_engine.application.refresh_jobs import (
    RefreshJobNotFoundError,
    RefreshJobRunningError,
    RefreshJobs,
    RefreshJobState,
)
from investment_analysis_engine.application.strategy_run import StrategyRun
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.core.failure_codes import FailureReasonCode
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.workspace.refresh import (
    RefreshJobStarted,
    RefreshProgress,
    RefreshSnapshot,
    RefreshTotals,
)
from investment_analysis_engine.workspace.runs import WatchlistEntry
from investment_analysis_engine.workspace.watchlists import WatchlistName
from tests.application._refresh_fakes import FakeRuns, Probe, fakes
from tests.application._unready_database import unready_database_url
from tests.application.test_refresh import _seed

_SELECTION = MomentumSelection(short_window=2, long_window=3, rsi_period=14)

type Recorded = tuple[int, str, int]
"""What the test recorder builds: the sequence, the progress kind and the position."""


class _Recorder:
    """An event recorder that counts its calls and gives each event a chosen size."""

    def __init__(self, sizes: Callable[[int], int] = lambda _sequence: 10) -> None:
        self.calls = 0
        self._sizes = sizes

    def __call__(self, sequence: int, progress: RefreshProgress[StrategyRun]) -> tuple[Recorded, int]:
        self.calls += 1
        kind = "started" if isinstance(progress, RefreshJobStarted) else "finished"
        return (sequence, kind, progress.position), self._sizes(sequence)


def _prepared(count: int, *, workers: int = 1) -> PreparedRefresh:
    entries = tuple(WatchlistEntry(ticker=f"T{index}", selection=_SELECTION) for index in range(count))
    return PreparedRefresh(
        snapshot=RefreshSnapshot(refresh_id=uuid4(), entries=entries), workers=workers, save=False, provider_check=False
    )


def _started(prepared: PreparedRefresh, position: int, admitted: int) -> RefreshJobStarted:
    return RefreshJobStarted(
        refresh_id=prepared.snapshot.refresh_id,
        position=position,
        ticker=f"T{position}",
        selection=_SELECTION,
        totals=RefreshTotals(admitted=admitted, finished=0, remaining=len(prepared.snapshot.entries) - admitted),
    )


def _wait(job_ended: Callable[[], bool]) -> None:
    for _ in range(3000):
        if job_ended():
            return
        threading.Event().wait(0.01)
    raise AssertionError("the job did not end")


def _scripted(
    events: int, *, size_of: Callable[[int], int] = lambda _sequence: 10
) -> tuple[RefreshJobs[Recorded], _Recorder, PreparedRefresh]:
    """Return jobs whose runner emits ``events`` started events and ends, and a prepared refresh for them."""
    prepared = _prepared(events)
    recorder = _Recorder(size_of)

    def runner(
        _context: ApplicationContext,
        given: PreparedRefresh,
        *,
        cancellation: threading.Event,
        on_progress: Callable[[RefreshProgress[StrategyRun]], None],
    ) -> RefreshOutcome:
        del cancellation
        for position in range(events):
            on_progress(_started(given, position, position + 1))
        return _outcome(given)

    return RefreshJobs(recorder, runner), recorder, prepared


def _outcome(prepared: PreparedRefresh) -> RefreshOutcome:
    from investment_analysis_engine.workspace_documents.refresh import RefreshSummaryDocument  # noqa: PLC0415

    return RefreshOutcome(
        document=RefreshSummaryDocument(
            refresh_id=prepared.snapshot.refresh_id,
            watchlist_id=None,
            watchlist_name=None,
            results=(),
            counts={},
            provider_check=None,
        ),
        failed=False,
        text_renderer=lambda: "",
    )


_CONTEXT = ApplicationContext(settings=ProjectSettings())


def test_sequences_start_at_one_and_after_selects_the_events_that_follow() -> None:
    jobs, recorder, prepared = _scripted(4)
    job = jobs.start(_CONTEXT, prepared)
    _wait(lambda: not job.is_running())

    everything = job.view(0, 1_000)
    assert [item.sequence for item in everything.events] == [1, 2, 3, 4]
    assert everything.next_after == 4
    assert everything.has_more is False
    after_two = job.view(2, 1_000)
    assert [item.event for item in after_two.events] == [(3, "started", 2), (4, "started", 3)]
    assert after_two.next_after == 4
    beyond = job.view(99, 1_000)
    assert beyond.events == ()
    assert (beyond.next_after, beyond.has_more) == (99, False)
    assert recorder.calls == 4  # built once per event; a view builds nothing


def test_a_view_holds_events_to_the_budget_and_always_at_least_one() -> None:
    jobs, _recorder, prepared = _scripted(
        5, size_of=lambda sequence: {1: 400, 2: 400, 3: 400, 4: 5_000, 5: 10}[sequence]
    )
    job = jobs.start(_CONTEXT, prepared)
    _wait(lambda: not job.is_running())

    first = job.view(0, 1_000)
    assert [item.sequence for item in first.events] == [1, 2]  # a third would take the events to 1,200 bytes
    assert (first.next_after, first.has_more) == (2, True)
    second = job.view(first.next_after, 1_000)
    assert [item.sequence for item in second.events] == [3]  # the next is larger than the budget
    third = job.view(second.next_after, 1_000)
    assert [item.sequence for item in third.events] == [4]  # an event larger than the budget is returned alone
    assert (third.next_after, third.has_more) == (4, True)
    last = job.view(third.next_after, 1_000)
    assert [item.sequence for item in last.events] == [5]
    assert last.has_more is False


def test_an_event_that_cannot_be_recorded_is_dropped_and_the_job_still_ends() -> None:
    prepared = _prepared(3)

    def record(sequence: int, progress: RefreshProgress[StrategyRun]) -> tuple[int, int]:
        if sequence == 2:
            raise RuntimeError("cannot build")
        return progress.position, 1

    def runner(
        _context: ApplicationContext,
        given: PreparedRefresh,
        *,
        cancellation: threading.Event,
        on_progress: Callable[[RefreshProgress[StrategyRun]], None],
    ) -> RefreshOutcome:
        del cancellation
        for position in range(3):
            on_progress(_started(given, position, position + 1))
        return _outcome(given)

    jobs: RefreshJobs[int] = RefreshJobs(record, runner)
    job = jobs.start(_CONTEXT, prepared)
    _wait(lambda: not job.is_running())

    view = job.view(0, 100)
    assert [item.sequence for item in view.events] == [1]
    assert view.totals.admitted == 3  # counting never stops


def test_a_job_that_raises_has_failed_with_its_events_kept() -> None:
    prepared = _prepared(2)
    failure = RuntimeError("the database went away")

    def runner(
        _context: ApplicationContext,
        given: PreparedRefresh,
        *,
        cancellation: threading.Event,
        on_progress: Callable[[RefreshProgress[StrategyRun]], None],
    ) -> RefreshOutcome:
        del cancellation
        on_progress(_started(given, 0, 1))
        raise failure

    jobs: RefreshJobs[Recorded] = RefreshJobs(_Recorder(), runner)
    job = jobs.start(_CONTEXT, prepared)
    _wait(lambda: not job.is_running())

    view = job.view(0, 1_000)
    assert view.state is RefreshJobState.FAILED
    assert view.failure is failure
    assert view.outcome is None
    assert [item.sequence for item in view.events] == [1]


def test_only_one_job_runs_at_a_time_and_a_new_one_replaces_an_ended_one() -> None:
    release = threading.Event()
    prepared = _prepared(1)

    def runner(
        _context: ApplicationContext,
        given: PreparedRefresh,
        *,
        cancellation: threading.Event,
        on_progress: Callable[[RefreshProgress[StrategyRun]], None],
    ) -> RefreshOutcome:
        del cancellation, on_progress
        assert release.wait(30)
        return _outcome(given)

    jobs: RefreshJobs[Recorded] = RefreshJobs(_Recorder(), runner)
    with pytest.raises(RefreshJobNotFoundError):
        jobs.latest()
    first = jobs.start(_CONTEXT, prepared)
    with pytest.raises(RefreshJobRunningError) as running:
        jobs.start(_CONTEXT, _prepared(1))
    assert running.value.reason_code is FailureReasonCode.REFRESH_JOB_RUNNING
    assert str(first.refresh_id) in str(running.value)
    release.set()
    _wait(lambda: not first.is_running())

    second_prepared = _prepared(1)
    second = jobs.start(_CONTEXT, second_prepared)
    _wait(lambda: not second.is_running())
    assert jobs.latest() is second
    assert jobs.get(second_prepared.snapshot.refresh_id) is second
    with pytest.raises(RefreshJobNotFoundError) as old:
        jobs.get(prepared.snapshot.refresh_id)
    assert old.value.reason_code is FailureReasonCode.REFRESH_JOB_NOT_FOUND
    with pytest.raises(RefreshJobNotFoundError):
        jobs.get(UUID(int=0))


def test_a_stop_before_every_entry_was_admitted_ends_stopped_and_stop_is_idempotent(
    isolated_cli_settings: ProjectSettings,
) -> None:
    context = _seed(isolated_cli_settings, ("AAPL", "MSFT", "KO"))
    gate, entered = threading.Event(), threading.Event()
    runs = FakeRuns(gate=gate, entered=entered)
    with fakes(Probe(), runs):
        prepared = PreparedRefresh(snapshot=_snapshot_of(context), workers=1, save=False, provider_check=False)
        jobs: RefreshJobs[Recorded] = RefreshJobs(_Recorder())
        job = jobs.start(context, prepared)
        assert entered.wait(30)
        assert job.view(0, 1_000).state is RefreshJobState.RUNNING
        job.stop()
        job.stop()
        assert job.view(0, 1_000).state is RefreshJobState.STOPPING
        gate.set()
        _wait(lambda: not job.is_running())

    view = job.view(0, 10_000)
    assert view.state is RefreshJobState.STOPPED
    assert view.outcome is not None
    assert [result.ticker for result in view.outcome.document.results] == ["AAPL"]
    assert view.totals == RefreshTotals(admitted=1, finished=1, remaining=2)
    job.stop()  # a stop after the end changes nothing
    assert job.view(0, 10_000).state is RefreshJobState.STOPPED


def test_a_stop_after_the_last_admission_ends_completed(isolated_cli_settings: ProjectSettings) -> None:
    context = _seed(isolated_cli_settings, ("AAPL", "MSFT"))
    gate, entered = threading.Event(), threading.Event()
    with fakes(Probe(), FakeRuns(gate=gate, entered=entered)):
        prepared = PreparedRefresh(snapshot=_snapshot_of(context), workers=2, save=False, provider_check=False)
        jobs: RefreshJobs[Recorded] = RefreshJobs(_Recorder())
        job = jobs.start(context, prepared)
        assert entered.wait(30)
        _wait(lambda: job.view(0, 1_000).totals.admitted == 2)
        job.stop()
        assert job.view(0, 1_000).state is RefreshJobState.STOPPING
        gate.set()
        _wait(lambda: not job.is_running())

    view = job.view(0, 10_000)
    assert view.state is RefreshJobState.COMPLETED
    assert view.outcome is not None
    assert len(view.outcome.document.results) == 2
    assert [kind for _sequence, kind, _position in (item.event for item in view.events)].count("finished") == 2


def _snapshot_of(context: ApplicationContext) -> RefreshSnapshot:
    from investment_analysis_engine.application.refresh import prepare_refresh  # noqa: PLC0415

    return prepare_refresh(context, WatchlistName("Core"), workers=1, save=False, provider_check=False).snapshot


def test_a_database_that_fails_when_the_job_opens_it_fails_the_job(
    isolated_cli_settings: ProjectSettings, tmp_path: Path
) -> None:
    context = _seed(isolated_cli_settings)
    with fakes(Probe()):
        prepared = PreparedRefresh(snapshot=_snapshot_of(context), workers=1, save=True, provider_check=False)
        broken = ApplicationContext(settings=ProjectSettings(database_url=unready_database_url(tmp_path)))
        jobs: RefreshJobs[Recorded] = RefreshJobs(_Recorder(), run_refresh)
        job = jobs.start(broken, prepared)
        _wait(lambda: not job.is_running())

    view = job.view(0, 1_000)
    assert view.state is RefreshJobState.FAILED
    assert view.failure is not None
    assert view.events == ()


def test_the_shutdown_hooks_cancel_a_running_job_and_wait_for_it() -> None:
    release = threading.Event()
    seen: list[bool] = []

    def runner(
        _context: ApplicationContext,
        given: PreparedRefresh,
        *,
        cancellation: threading.Event,
        on_progress: Callable[[RefreshProgress[StrategyRun]], None],
    ) -> RefreshOutcome:
        del on_progress
        seen.append(cancellation.wait(30))
        assert release.wait(30)
        return _outcome(given)

    jobs: RefreshJobs[Recorded] = RefreshJobs(_Recorder(), runner)
    assert jobs.wait_for_job(0) is True  # no job
    jobs.begin_shutdown()  # and nothing to cancel
    job = jobs.start(_CONTEXT, _prepared(1))

    jobs.begin_shutdown()

    assert jobs.wait_for_job(0.05) is False  # the job is still blocked
    release.set()
    assert jobs.wait_for_job(30) is True
    assert seen == [True]
    assert job.view(0, 10).state in {RefreshJobState.COMPLETED, RefreshJobState.STOPPED}
