"""Stopping ``ian serve`` with a refresh job running: cancel at once, share the grace, end a job that outlives it."""

import io
import logging
import signal
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import uvicorn

from investment_analysis_engine.api.app import create_app, refresh_jobs_of
from investment_analysis_engine.api.handlers import RefreshJobsOfServer
from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.refresh import prepare_refresh
from investment_analysis_engine.application.refresh_jobs import RefreshJobs, RefreshJobState
from investment_analysis_engine.application.strategy_run import StrategyRun
from investment_analysis_engine.cli_serve import (
    GRACEFUL_SHUTDOWN_SECONDS,
    _AnnouncingServer,
    _ShutdownClock,
    _stop_when_stdin_closes,
    finish_refresh_job,
)
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.workspace.refresh import RefreshProgress
from investment_analysis_engine.workspace.watchlists import WatchlistName
from tests.application._refresh_fakes import FakeRuns, Probe, fakes
from tests.application.test_refresh import _seed

_CONTEXT = ApplicationContext(settings=ProjectSettings())


class _Clock:
    """A clock the test moves."""

    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def _no_event(_sequence: int, _progress: RefreshProgress[StrategyRun]) -> tuple[None, int]:
    return None, 0


@contextmanager
def _running(settings: ProjectSettings) -> Iterator[tuple[RefreshJobs[None], threading.Event]]:
    """Yield jobs with a real refresh of two entries started and blocked on its first, and the gate that frees it."""
    context = _seed(settings, ("AAPL", "MSFT"))
    gate, entered = threading.Event(), threading.Event()
    with fakes(Probe(), FakeRuns(gate=gate, entered=entered)):
        jobs: RefreshJobs[None] = RefreshJobs(_no_event)
        try:
            prepared = prepare_refresh(context, WatchlistName("Core"), workers=1, save=False, provider_check=False)
            jobs.start(context, prepared)
            assert entered.wait(30)
            yield jobs, gate
        finally:
            gate.set()
            jobs.wait_for_job(30)


def test_create_app_makes_one_set_of_jobs_per_server() -> None:
    first = refresh_jobs_of(create_app(context=_CONTEXT, token="t", port=1))
    second = refresh_jobs_of(create_app(context=_CONTEXT, token="t", port=1))

    assert first is not second


def test_the_job_is_cancelled_the_moment_the_stop_begins(isolated_cli_settings: ProjectSettings) -> None:
    with _running(isolated_cli_settings) as (jobs, gate):
        shutdown = _ShutdownClock(jobs)
        assert jobs.latest().view(0, 10).state is RefreshJobState.RUNNING

        shutdown.begin()

        assert jobs.latest().view(0, 10).state is RefreshJobState.STOPPING  # at once, with the job still blocked
        assert jobs.wait_for_job(0) is False
        shutdown.begin()  # a second call changes nothing
        gate.set()
        assert jobs.wait_for_job(30) is True
        assert jobs.latest().view(0, 10).state is RefreshJobState.STOPPED  # the second entry was never admitted


def test_the_job_gets_the_whole_grace_from_the_start_of_the_stop_and_not_after_uvicorn(
    isolated_cli_settings: ProjectSettings,
) -> None:
    clock = _Clock()
    with _running(isolated_cli_settings) as (jobs, _gate):
        shutdown = _ShutdownClock(jobs, clock=clock)
        assert shutdown.remaining() == GRACEFUL_SHUTDOWN_SECONDS  # no stop yet
        shutdown.begin()
        clock.now += 3.0
        assert shutdown.remaining() == pytest.approx(GRACEFUL_SHUTDOWN_SECONDS - 3.0)  # the time uvicorn took counts
        clock.now += 10.0
        assert shutdown.remaining() == 0.0


def test_a_job_that_outlives_the_grace_is_abandoned_by_ending_the_process(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    clock = _Clock()
    exits: list[int] = []
    flushed = MagicMock()
    monkeypatch.setattr(logging, "shutdown", flushed)
    with _running(isolated_cli_settings) as (jobs, _gate):
        shutdown = _ShutdownClock(jobs, clock=clock)
        shutdown.begin()
        clock.now += GRACEFUL_SHUTDOWN_SECONDS  # the grace is spent; the job thread is still blocked

        with caplog.at_level(logging.WARNING, logger="investment_analysis_engine.cli_serve"):
            finish_refresh_job(jobs, shutdown, exit_process=exits.append)

    assert exits == [0]
    flushed.assert_called_once_with()
    lines = [record.getMessage() for record in caplog.records if record.name.endswith("cli_serve")]
    assert lines == ["The refresh did not finish before the server stopped; its unfinished jobs were not saved."]


def test_a_job_that_ends_within_the_grace_is_waited_for_and_the_process_is_not_ended(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    exits: list[int] = []
    flushed = MagicMock()
    monkeypatch.setattr(logging, "shutdown", flushed)
    with _running(isolated_cli_settings) as (jobs, gate):
        shutdown = _ShutdownClock(jobs)
        shutdown.begin()
        gate.set()

        finish_refresh_job(jobs, shutdown, exit_process=exits.append)

        assert jobs.latest().view(0, 10).state is RefreshJobState.STOPPED
    assert exits == []
    flushed.assert_not_called()


def test_with_no_job_the_process_is_not_ended() -> None:
    jobs: RefreshJobsOfServer = refresh_jobs_of(create_app(context=_CONTEXT, token="t", port=1))
    exits: list[int] = []

    finish_refresh_job(jobs, _ShutdownClock(jobs), exit_process=exits.append)

    assert exits == []


def test_closing_standard_input_announces_the_stop_before_asking_uvicorn_to_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order: list[str] = []

    class _Server:
        def __setattr__(self, name: str, value: object) -> None:
            order.append(f"{name}={value}")

    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(b"")))

    _stop_when_stdin_closes(_Server(), lambda: order.append("stopping"))  # type: ignore[arg-type]

    assert order == ["stopping", "should_exit=True"]


def test_a_signal_announces_the_stop_before_uvicorn_handles_it() -> None:
    order: list[str] = []
    config = uvicorn.Config(lambda *_: None, log_config=None)
    server = _AnnouncingServer(config, on_started=lambda: None, on_stopping=lambda: order.append("stopping"))

    server.handle_exit(signal.SIGINT, None)

    assert order == ["stopping"]
    assert server.should_exit is True
