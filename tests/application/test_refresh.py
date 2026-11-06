"""The refresh operation: worker-count check, addressing, outcome and progress, as the CLI and the API call it."""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.parameters import ActionParameterError
from investment_analysis_engine.application.refresh import refresh_watchlist
from investment_analysis_engine.application.watchlists import (
    add_watchlist_entries,
    create_watchlist,
    get_watchlist_summary,
)
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.data.provider_probe import ProbeFinding, ProbeVerdict
from investment_analysis_engine.data.repositories.readiness import DatabaseReadinessError
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.workspace.capture import ExecutionCapture
from investment_analysis_engine.workspace.refresh import (
    DEFAULT_WORKERS,
    EmptyRefreshTargetError,
    RefreshJobFinished,
    RefreshJobStarted,
    RefreshProgress,
)
from investment_analysis_engine.workspace.strategy_types import AnalysisSelection
from investment_analysis_engine.workspace.watchlists import WatchlistId, WatchlistName, WatchlistNotFoundError
from tests.application._unready_database import unready_database_url
from tests.workspace.test_refresh import _momentum_capture
from tests.workspace.test_refresh_provider_failure import _UNREACHABLE, _failed_capture

_MOMENTUM = MomentumSelection(short_window=2, long_window=3, rsi_period=14)


class _Probe:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def check(self, provider_id: str, *, requested: bool = True) -> ProbeFinding:
        self.calls.append((provider_id, requested))
        return ProbeFinding(provider_id, ProbeVerdict.UNREACHABLE)


def _executor_for(failing: frozenset[str]):  # type: ignore[no-untyped-def]
    def executor(
        _context: ApplicationContext, ticker: str, _selection: AnalysisSelection, /, *, profile_cache: object
    ) -> ExecutionCapture:
        del profile_cache
        return _failed_capture(ticker, _UNREACHABLE) if ticker in failing else _momentum_capture(ticker)

    return lambda _selection: executor


@contextmanager
def _fakes(probe: _Probe, failing: frozenset[str] = frozenset()) -> Iterator[None]:
    with (
        patch("investment_analysis_engine.application.refresh.refresh_executor_for", _executor_for(failing)),
        patch("investment_analysis_engine.application.refresh.build_provider_probe", return_value=probe),
    ):
        yield


def _seed(settings: ProjectSettings, tickers: tuple[str, ...] = ("AAPL", "MSFT")) -> ApplicationContext:
    context = ApplicationContext(settings=settings)
    create_watchlist(context, "Core")
    if tickers:
        add_watchlist_entries(context, WatchlistName("Core"), [(ticker, _MOMENTUM) for ticker in tickers])
    return context


def test_a_watchlist_is_refreshed_by_name_and_by_id(isolated_cli_settings: ProjectSettings) -> None:
    context = _seed(isolated_cli_settings)
    watchlist_id = get_watchlist_summary(context, WatchlistName("Core")).watchlist_id

    with _fakes(_Probe()):
        by_name = refresh_watchlist(context, WatchlistName("core"), workers=1, save=False, provider_check=True)
        by_id = refresh_watchlist(context, WatchlistId(watchlist_id), workers=1, save=False, provider_check=True)

    assert by_name.document.watchlist_id == by_id.document.watchlist_id == watchlist_id
    assert [result.ticker for result in by_id.document.results] == ["AAPL", "MSFT"]


def test_a_missing_watchlist_and_an_empty_one_are_reported_with_the_cli_messages(
    isolated_cli_settings: ProjectSettings,
) -> None:
    context = _seed(isolated_cli_settings, ())
    with _fakes(_Probe()):
        with pytest.raises(WatchlistNotFoundError) as missing:
            refresh_watchlist(context, WatchlistName("Nope"), save=False, provider_check=True)
        with pytest.raises(EmptyRefreshTargetError) as empty:
            refresh_watchlist(context, WatchlistName("Core"), save=False, provider_check=True)
        watchlist_id = get_watchlist_summary(context, WatchlistName("Core")).watchlist_id
        with pytest.raises(EmptyRefreshTargetError) as empty_by_id:
            refresh_watchlist(context, WatchlistId(watchlist_id), save=False, provider_check=True)

    assert str(missing.value) == "No watchlist named 'Nope' exists."
    assert str(empty.value) == "Watchlist 'Core' has no entries; there is nothing to refresh."
    assert str(empty_by_id.value) == "Watchlist 'Core' has no entries; there is nothing to refresh."


@pytest.mark.parametrize("workers", [0, 5, -1])
def test_a_worker_count_out_of_range_names_its_rule_and_values(
    isolated_cli_settings: ProjectSettings, workers: int
) -> None:
    context = _seed(isolated_cli_settings)

    with pytest.raises(ActionParameterError) as caught:
        refresh_watchlist(context, WatchlistName("Core"), workers=workers, save=False, provider_check=True)

    error = caught.value
    assert error.rule == "refresh.workers_range"
    assert error.template == "{workers} must be between {minimum} and {maximum}."
    assert error.arguments == {"value": workers, "minimum": 1, "maximum": 4}
    assert error.action_parameters == ("workers",)
    assert str(error) == "workers must be between 1 and 4."
    cli = error.named({"workers": "--workers"})
    assert str(cli) == "--workers must be between 1 and 4."
    assert cli.parameters == ("--workers",)


def test_the_worker_count_is_checked_before_the_database_opens(tmp_path: Path) -> None:
    unready = ApplicationContext(settings=ProjectSettings(database_url=unready_database_url(tmp_path)))

    with pytest.raises(ActionParameterError):
        refresh_watchlist(unready, WatchlistName("Core"), workers=9, save=False, provider_check=True)
    with pytest.raises(DatabaseReadinessError):
        refresh_watchlist(unready, WatchlistName("Core"), workers=1, save=False, provider_check=True)


def test_the_default_worker_count_is_two() -> None:
    assert DEFAULT_WORKERS == 2


def test_a_refresh_without_a_failure_has_no_provider_check_and_text_is_the_summary(
    isolated_cli_settings: ProjectSettings,
) -> None:
    context = _seed(isolated_cli_settings)
    probe = _Probe()

    with _fakes(probe):
        outcome = refresh_watchlist(context, WatchlistName("Core"), workers=1, save=True, provider_check=True)

    assert outcome.failed is False
    assert outcome.document.provider_check is None
    assert probe.calls == []
    lines = outcome.render_text().splitlines()
    assert lines[0] == f"Refresh {outcome.document.refresh_id} for 'Core':"
    assert lines[-1] == "Counts: completed=2"
    assert all(result.saved for result in outcome.document.results)


def test_a_refresh_with_a_provider_failure_fails_and_carries_the_check_first_in_text(
    isolated_cli_settings: ProjectSettings,
) -> None:
    context = _seed(isolated_cli_settings)
    probe = _Probe()

    with _fakes(probe, frozenset({"MSFT"})):
        outcome = refresh_watchlist(context, WatchlistName("Core"), workers=1, save=True, provider_check=True)

    assert outcome.failed is True
    assert probe.calls == [("yfinance", True)]
    assert outcome.document.provider_check is not None
    assert [(item.provider_id, item.verdict.value) for item in outcome.document.provider_check] == [
        ("yfinance", "unreachable")
    ]
    text = outcome.render_text().splitlines()
    assert text[0] == "Yahoo Finance is not answering: a test request also failed."
    assert text[1].startswith("Refresh ")


def test_the_provider_check_option_off_is_reported_and_sends_no_request(isolated_cli_settings: ProjectSettings) -> None:
    context = _seed(isolated_cli_settings)
    probe = _Probe()

    with _fakes(probe, frozenset({"MSFT"})):
        refresh_watchlist(context, WatchlistName("Core"), workers=1, save=False, provider_check=False)

    assert probe.calls == [("yfinance", False)]


def test_progress_reaches_the_callback_on_the_calling_thread(isolated_cli_settings: ProjectSettings) -> None:
    context = _seed(isolated_cli_settings)
    events: list[RefreshProgress] = []
    threads: set[int] = set()

    def observe(event: RefreshProgress) -> None:
        events.append(event)
        threads.add(threading.get_ident())

    with _fakes(_Probe()):
        outcome = refresh_watchlist(
            context, WatchlistName("Core"), workers=2, save=True, provider_check=True, on_progress=observe
        )

    assert threads == {threading.get_ident()}
    assert sum(isinstance(event, RefreshJobStarted) for event in events) == 2
    assert sum(isinstance(event, RefreshJobFinished) for event in events) == 2
    assert {event.refresh_id for event in events} == {outcome.document.refresh_id}
