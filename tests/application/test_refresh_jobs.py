"""The refresh job: states, polling and the one-at-a-time rule, driving the real refresh with fake strategies."""

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

import pytest

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.refresh import PreparedRefresh, prepare_refresh
from investment_analysis_engine.application.refresh_jobs import (
    RefreshJob,
    RefreshJobNotFoundError,
    RefreshJobRunningError,
    RefreshJobs,
    RefreshJobState,
)
from investment_analysis_engine.application.strategy_run import StrategyRun
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.core.failure_codes import FailureReasonCode
from investment_analysis_engine.workspace.refresh import RefreshJobStarted, RefreshProgress, RefreshTotals
from investment_analysis_engine.workspace.watchlists import WatchlistName
from tests.application._refresh_fakes import FakeRuns, Probe, fakes
from tests.application._unready_database import unready_database_url
from tests.application.test_refresh import _seed

type Recorded = tuple[int, str, int]
"""What the test recorder builds: the sequence, the progress kind and the position."""


class _Recorder:
    """An event recorder that counts its calls, gives each event a chosen size and can fail on one."""

    def __init__(self, sizes: Callable[[int], int] = lambda _sequence: 10, *, fail_on: int | None = None) -> None:
        self.calls = 0
        self._sizes = sizes
        self._fail_on = fail_on

    def __call__(self, sequence: int, progress: RefreshProgress[StrategyRun]) -> tuple[Recorded, int]:
        self.calls += 1
        if sequence == self._fail_on:
            raise RuntimeError(f"cannot build event {sequence}")
        kind = "started" if isinstance(progress, RefreshJobStarted) else "finished"
        return (sequence, kind, progress.position), self._sizes(sequence)


def _wait(job_ended: Callable[[], bool]) -> None:
    for _ in range(3000):
        if job_ended():
            return
        threading.Event().wait(0.01)
    raise AssertionError("the job did not end")


def _ended(job: RefreshJob[Recorded]) -> None:
    _wait(lambda: not job.is_running())


def _prepared(context: ApplicationContext, *, workers: int = 1) -> PreparedRefresh:
    return prepare_refresh(context, WatchlistName("Core"), workers=workers, save=False, provider_check=False)


def _context(settings: ProjectSettings, *tickers: str) -> ApplicationContext:
    return _seed(settings, tickers)


def test_sequences_start_at_one_and_after_selects_the_events_that_follow(
    isolated_cli_settings: ProjectSettings,
) -> None:
    context = _context(isolated_cli_settings, "AAPL", "MSFT")
    recorder = _Recorder()
    with fakes(Probe()):
        jobs: RefreshJobs[Recorded] = RefreshJobs(recorder)
        job = jobs.start(context, _prepared(context))
        _ended(job)

    everything = job.view(0, 1_000)
    assert [item.sequence for item in everything.events] == [1, 2, 3, 4]
    assert (everything.next_after, everything.has_more) == (4, False)
    after_two = job.view(2, 1_000)
    assert [item.event for item in after_two.events] == [(3, "started", 1), (4, "finished", 1)]
    assert after_two.next_after == 4
    beyond = job.view(99, 1_000)
    assert beyond.events == ()
    assert (beyond.next_after, beyond.has_more) == (99, False)
    assert recorder.calls == 4  # built once per event; a view builds nothing


def test_a_view_holds_events_to_the_budget_and_always_at_least_one(isolated_cli_settings: ProjectSettings) -> None:
    context = _context(isolated_cli_settings, "AAPL", "MSFT", "KO")
    sizes = {1: 400, 2: 400, 3: 400, 4: 5_000}
    with fakes(Probe()):
        jobs: RefreshJobs[Recorded] = RefreshJobs(_Recorder(lambda sequence: sizes.get(sequence, 10)))
        job = jobs.start(context, _prepared(context))
        _ended(job)

    first = job.view(0, 1_000)
    assert [item.sequence for item in first.events] == [1, 2]  # a third would take the events to 1,200 bytes
    assert (first.next_after, first.has_more) == (2, True)
    second = job.view(first.next_after, 1_000)
    assert [item.sequence for item in second.events] == [3]  # the next is larger than the budget
    third = job.view(second.next_after, 1_000)
    assert [item.sequence for item in third.events] == [4]  # an event larger than the budget is returned alone
    assert (third.next_after, third.has_more) == (4, True)
    last = job.view(third.next_after, 1_000)
    assert [item.sequence for item in last.events] == [5, 6]
    assert last.has_more is False


def test_an_event_that_cannot_be_built_fails_the_job_and_admits_nothing_more(
    isolated_cli_settings: ProjectSettings, caplog: pytest.LogCaptureFixture
) -> None:
    context = _context(isolated_cli_settings, "AAPL", "MSFT", "KO")
    runs = FakeRuns()
    with fakes(Probe(), runs), caplog.at_level("ERROR"):
        jobs: RefreshJobs[Recorded] = RefreshJobs(_Recorder(fail_on=2))
        job = jobs.start(context, _prepared(context))
        _ended(job)

    view = job.view(0, 1_000)
    assert view.state is RefreshJobState.FAILED
    assert isinstance(view.failure, RuntimeError)
    assert str(view.failure) == "cannot build event 2"
    assert view.outcome is None
    assert [item.sequence for item in view.events] == [1]  # kept; nothing after the failure is recorded
    assert [ticker for ticker, _ in runs.calls] == ["AAPL"]  # the admitted job finished; no more were admitted
    assert view.totals == RefreshTotals(admitted=1, finished=1, remaining=2)
    logged = [record for record in caplog.records if "could not be recorded" in record.getMessage()]
    assert len(logged) == 1


def test_a_job_that_raises_has_failed_with_its_events_kept(
    isolated_cli_settings: ProjectSettings, tmp_path: Path
) -> None:
    context = _context(isolated_cli_settings, "AAPL")
    with fakes(Probe()):
        prepared = _prepared(context)
        broken = ApplicationContext(settings=ProjectSettings(database_url=unready_database_url(tmp_path)))
        jobs: RefreshJobs[Recorded] = RefreshJobs(_Recorder())
        job = jobs.start(broken, prepared)
        _ended(job)

    view = job.view(0, 1_000)
    assert view.state is RefreshJobState.FAILED
    assert view.failure is not None
    assert view.outcome is None
    assert view.events == ()


def test_only_one_job_runs_at_a_time_and_a_new_one_replaces_an_ended_one(
    isolated_cli_settings: ProjectSettings,
) -> None:
    context = _context(isolated_cli_settings, "AAPL")
    gate, entered = threading.Event(), threading.Event()
    with fakes(Probe(), FakeRuns(gate=gate, entered=entered)):
        jobs: RefreshJobs[Recorded] = RefreshJobs(_Recorder())
        with pytest.raises(RefreshJobNotFoundError):
            jobs.latest()
        first_prepared = _prepared(context)
        first = jobs.start(context, first_prepared)
        assert entered.wait(30)
        with pytest.raises(RefreshJobRunningError) as running:
            jobs.start(context, _prepared(context))
        assert running.value.reason_code is FailureReasonCode.REFRESH_JOB_RUNNING
        assert str(first.refresh_id) in str(running.value)
        state_before_stop = first.view(0, 10).state
        first.stop()
        with pytest.raises(RefreshJobRunningError):  # stopping is still running
            jobs.start(context, _prepared(context))
        gate.set()
        _ended(first)
        second_prepared = _prepared(context)
        second = jobs.start(context, second_prepared)
        _ended(second)

    assert state_before_stop is RefreshJobState.RUNNING
    assert jobs.latest() is second
    assert jobs.get(second_prepared.snapshot.refresh_id) is second
    with pytest.raises(RefreshJobNotFoundError) as old:
        jobs.get(first_prepared.snapshot.refresh_id)
    assert old.value.reason_code is FailureReasonCode.REFRESH_JOB_NOT_FOUND
    with pytest.raises(RefreshJobNotFoundError):
        jobs.get(UUID(int=0))


@contextmanager
def _thread_held_after_the_state_is_final(monkeypatch: pytest.MonkeyPatch) -> Iterator[threading.Event]:
    """Hold each job's thread alive after its run has returned and its final state is set."""
    release = threading.Event()
    original = RefreshJob._run  # noqa: SLF001 - the one place a job's end is set

    def held(self: RefreshJob[Recorded]) -> None:
        original(self)
        release.wait(30)

    monkeypatch.setattr(RefreshJob, "_run", held)
    try:
        yield release
    finally:
        release.set()


def test_a_new_job_starts_once_the_state_has_ended_though_the_thread_is_still_held(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _context(isolated_cli_settings, "AAPL")
    with fakes(Probe()), _thread_held_after_the_state_is_final(monkeypatch) as release:
        jobs: RefreshJobs[Recorded] = RefreshJobs(_Recorder())
        first = jobs.start(context, _prepared(context))
        _wait(lambda: first.view(0, 10).state is RefreshJobState.COMPLETED)

        assert first.is_running()  # the thread is held, as the shutdown wait sees it
        assert jobs.wait_for_job(0.05) is False
        second = jobs.start(context, _prepared(context))  # but the job has ended, so a new one starts

        assert jobs.latest() is second
        release.set()
        _ended(first)
        _ended(second)


def test_a_stop_before_every_entry_was_admitted_ends_stopped_and_stop_is_idempotent(
    isolated_cli_settings: ProjectSettings,
) -> None:
    context = _context(isolated_cli_settings, "AAPL", "MSFT", "KO")
    gate, entered = threading.Event(), threading.Event()
    with fakes(Probe(), FakeRuns(gate=gate, entered=entered)):
        jobs: RefreshJobs[Recorded] = RefreshJobs(_Recorder())
        job = jobs.start(context, _prepared(context))
        assert entered.wait(30)
        assert job.view(0, 1_000).state is RefreshJobState.RUNNING
        job.stop()
        job.stop()
        assert job.view(0, 1_000).state is RefreshJobState.STOPPING
        gate.set()
        _ended(job)

    view = job.view(0, 10_000)
    assert view.state is RefreshJobState.STOPPED
    assert view.outcome is not None
    assert [result.ticker for result in view.outcome.document.results] == ["AAPL"]
    assert view.totals == RefreshTotals(admitted=1, finished=1, remaining=2)
    job.stop()  # a stop after the end changes nothing
    assert job.view(0, 10_000).state is RefreshJobState.STOPPED


def test_a_stop_after_the_last_admission_ends_completed(isolated_cli_settings: ProjectSettings) -> None:
    context = _context(isolated_cli_settings, "AAPL", "MSFT")
    gate, entered = threading.Event(), threading.Event()
    with fakes(Probe(), FakeRuns(gate=gate, entered=entered)):
        jobs: RefreshJobs[Recorded] = RefreshJobs(_Recorder())
        job = jobs.start(context, _prepared(context, workers=2))
        assert entered.wait(30)
        _wait(lambda: job.view(0, 1_000).totals.admitted == 2)
        job.stop()
        assert job.view(0, 1_000).state is RefreshJobState.STOPPING
        gate.set()
        _ended(job)

    view = job.view(0, 10_000)
    assert view.state is RefreshJobState.COMPLETED
    assert view.outcome is not None
    assert len(view.outcome.document.results) == 2
    assert [kind for _sequence, kind, _position in (item.event for item in view.events)].count("finished") == 2


def test_the_shutdown_hooks_cancel_a_running_job_and_wait_for_it(isolated_cli_settings: ProjectSettings) -> None:
    context = _context(isolated_cli_settings, "AAPL", "MSFT")
    gate, entered = threading.Event(), threading.Event()
    with fakes(Probe(), FakeRuns(gate=gate, entered=entered)):
        jobs: RefreshJobs[Recorded] = RefreshJobs(_Recorder())
        assert jobs.wait_for_job(0) is True  # no job
        jobs.begin_shutdown()  # and nothing to cancel
        job = jobs.start(context, _prepared(context))
        assert entered.wait(30)

        jobs.begin_shutdown()

        assert jobs.wait_for_job(0.05) is False  # the job is still blocked
        gate.set()
        assert jobs.wait_for_job(30) is True

    view = job.view(0, 10_000)
    assert view.state is RefreshJobState.STOPPED  # the second entry was never admitted
    assert view.totals == RefreshTotals(admitted=1, finished=1, remaining=1)
