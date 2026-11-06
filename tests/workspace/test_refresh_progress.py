"""Progress events of a refresh: who sends them, what they count, and what a failing observer changes."""

import logging
import threading
from datetime import UTC, datetime
from uuid import UUID

import pytest

from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.strategy_wiring import RUN_SPECS_BY_KEY
from investment_analysis_engine.workspace.capture import ExecutionCapture
from investment_analysis_engine.workspace.refresh import (
    RefreshJobFinished,
    RefreshJobStarted,
    RefreshPolicy,
    RefreshProgress,
    RefreshSummary,
    coordinate_refresh,
)
from investment_analysis_engine.workspace.strategy_types import AnalysisSelection
from investment_analysis_engine.workspace.watchlists import WatchlistId, WatchlistName, WatchlistNotFoundError
from tests._wiring import failure_text
from tests.workspace.test_refresh import (
    WATCHLIST_ID,
    _FakeSink,
    _FakeWatchlists,
    _momentum_capture,
    _watchlist,
)

_MOMENTUM = MomentumSelection(short_window=2, long_window=3, rsi_period=14)
_OTHER = MomentumSelection(short_window=2, long_window=4, rsi_period=14)
_NOW = datetime(2026, 9, 19, 12, 0, 0, tzinfo=UTC)


def _executor(ticker: str, _selection: AnalysisSelection) -> ExecutionCapture:
    return _momentum_capture(ticker)


def _run(  # noqa: PLR0913
    tickers: tuple[str, ...],
    *,
    workers: int,
    selections: tuple[AnalysisSelection, ...] = (_MOMENTUM,),
    on_progress: object = None,
    cancellation: threading.Event | None = None,
    executor: object = _executor,
    save: bool = True,
) -> RefreshSummary:
    watchlist = _watchlist(tickers, selections)
    return coordinate_refresh(
        WatchlistName("My Watch"),
        watchlists=_FakeWatchlists({"my watch": watchlist}),
        repository=_FakeSink(),
        executor=executor,  # type: ignore[arg-type]
        run_specs=RUN_SPECS_BY_KEY,
        describe=failure_text,
        policy=RefreshPolicy(workers=workers),
        clock=lambda: _NOW,
        save=save,
        cancellation=cancellation,
        on_progress=on_progress,  # type: ignore[arg-type]
    )


@pytest.mark.parametrize("workers", [1, 4])
def test_events_arrive_only_on_the_calling_thread(workers: int) -> None:
    caller = threading.get_ident()
    threads: list[int] = []

    def observe(_event: RefreshProgress) -> None:
        threads.append(threading.get_ident())

    _run(("AAPL", "MSFT", "KO", "IBM", "T"), workers=workers, on_progress=observe)

    assert len(threads) == 10
    assert set(threads) == {caller}


@pytest.mark.parametrize("workers", [1, 2, 4])
def test_each_job_has_one_started_then_one_finished_event_with_counting_totals(workers: int) -> None:
    events: list[RefreshProgress] = []
    summary = _run(("AAPL", "MSFT", "KO", "IBM", "T"), workers=workers, on_progress=events.append)

    assert {event.refresh_id for event in events} == {summary.refresh_id}
    for position in range(5):
        pair = [event for event in events if event.position == position]
        assert [type(event) for event in pair] == [RefreshJobStarted, RefreshJobFinished]
        assert events.index(pair[0]) < events.index(pair[1])
    admitted = [event.totals.admitted for event in events]
    finished = [event.totals.finished for event in events]
    assert admitted == sorted(admitted)
    assert finished == sorted(finished)
    assert all(event.totals.admitted + event.totals.remaining == 5 for event in events)
    assert events[-1].totals.finished == events[-1].totals.admitted == 5
    assert events[-1].totals.remaining == 0


def test_started_counts_the_job_as_admitted_and_finished_counts_it_as_finished() -> None:
    events: list[RefreshProgress] = []
    _run(("AAPL", "MSFT"), workers=1, on_progress=events.append)

    assert [(type(event).__name__, event.totals.admitted, event.totals.finished) for event in events] == [
        ("RefreshJobStarted", 1, 0),
        ("RefreshJobFinished", 1, 1),
        ("RefreshJobStarted", 2, 1),
        ("RefreshJobFinished", 2, 2),
    ]


def test_a_finished_event_carries_the_settled_result_and_a_saved_run_is_already_persisted() -> None:
    sink = _FakeSink()
    seen: list[tuple[int, bool]] = []

    def observe(event: RefreshProgress) -> None:
        if isinstance(event, RefreshJobFinished):
            seen.append((len(sink.inserted), event.result.run is not None))

    coordinate_refresh(
        WatchlistName("My Watch"),
        watchlists=_FakeWatchlists({"my watch": _watchlist(("AAPL", "MSFT"), (_MOMENTUM,))}),
        repository=sink,
        executor=_executor,
        run_specs=RUN_SPECS_BY_KEY,
        describe=failure_text,
        policy=RefreshPolicy(workers=1),
        on_progress=observe,
    )

    assert seen == [(1, True), (2, True)]


def test_a_ticker_under_two_methods_yields_two_distinguishable_pairs() -> None:
    events: list[RefreshProgress] = []
    _run(("AAPL",), workers=2, selections=(_MOMENTUM, _OTHER), on_progress=events.append)

    started = [event for event in events if isinstance(event, RefreshJobStarted)]
    assert [event.ticker for event in started] == ["AAPL", "AAPL"]
    assert sorted(event.position for event in started) == [0, 1]
    assert {event.selection for event in started} == {_MOMENTUM, _OTHER}
    finished = {event.position for event in events if isinstance(event, RefreshJobFinished)}
    assert finished == {0, 1}


@pytest.mark.parametrize("workers", [1, 2])
def test_after_cancellation_every_admitted_job_is_finished_and_remaining_counts_the_rest(workers: int) -> None:
    cancellation = threading.Event()
    events: list[RefreshProgress] = []

    def observe(event: RefreshProgress) -> None:
        events.append(event)
        if isinstance(event, RefreshJobFinished):
            cancellation.set()

    inserted = _FakeSink()
    summary = coordinate_refresh(
        WatchlistName("My Watch"),
        watchlists=_FakeWatchlists({"my watch": _watchlist(("AAPL", "MSFT", "KO", "IBM", "T"), (_MOMENTUM,))}),
        repository=inserted,
        executor=_executor,
        run_specs=RUN_SPECS_BY_KEY,
        describe=failure_text,
        policy=RefreshPolicy(workers=workers),
        cancellation=cancellation,
        on_progress=observe,
    )

    started = [event.position for event in events if isinstance(event, RefreshJobStarted)]
    finished = [event.position for event in events if isinstance(event, RefreshJobFinished)]
    assert len(started) == workers
    assert sorted(finished) == sorted(started)
    assert events[-1].totals.finished == events[-1].totals.admitted == workers
    assert events[-1].totals.remaining == 5 - workers
    assert len(summary.results) == workers
    assert all(result.run is not None for result in summary.results)
    assert len(inserted.inserted) == workers


def test_a_callback_that_raises_on_its_first_event_is_logged_once_and_the_refresh_is_unchanged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls: list[RefreshProgress] = []

    def failing(event: RefreshProgress) -> None:
        calls.append(event)
        raise RuntimeError("observer failure")

    baseline = _run(("AAPL", "MSFT"), workers=1)
    with caplog.at_level(logging.WARNING):
        summary = _run(("AAPL", "MSFT"), workers=1, on_progress=failing)

    assert len(calls) == 1
    records = [record for record in caplog.records if record.name == "investment_analysis_engine.workspace.refresh"]
    assert len(records) == 1
    assert records[0].exc_info is not None
    assert str(records[0].exc_info[1]) == "observer failure"
    assert _comparable(summary) == _comparable(baseline)


def test_a_callback_that_raises_on_a_later_event_stops_receiving_events(caplog: pytest.LogCaptureFixture) -> None:
    calls: list[RefreshProgress] = []

    def failing_on_third(event: RefreshProgress) -> None:
        calls.append(event)
        if len(calls) == 3:
            raise ValueError("third event")

    baseline = _run(("AAPL", "MSFT", "KO"), workers=2)
    with caplog.at_level(logging.WARNING):
        summary = _run(("AAPL", "MSFT", "KO"), workers=2, on_progress=failing_on_third)

    assert len(calls) == 3
    records = [record for record in caplog.records if record.name == "investment_analysis_engine.workspace.refresh"]
    assert len(records) == 1
    assert records[0].exc_info is not None
    assert _comparable(summary) == _comparable(baseline)


def _comparable(summary: RefreshSummary) -> list[tuple[str, str, str]]:
    return [
        (result.ticker, result.method_id, "run" if result.run is not None else "other") for result in summary.results
    ]


def test_a_watchlist_addressed_by_id_is_refreshed_and_a_missing_id_is_not_found() -> None:
    watchlists = _FakeWatchlists({"my watch": _watchlist(("AAPL",), (_MOMENTUM,))})
    summary = coordinate_refresh(
        WatchlistId(WATCHLIST_ID),
        watchlists=watchlists,
        repository=_FakeSink(),
        executor=_executor,
        run_specs=RUN_SPECS_BY_KEY,
        describe=failure_text,
        policy=RefreshPolicy(workers=1),
    )
    assert [result.ticker for result in summary.results] == ["AAPL"]

    missing = UUID("22222222-2222-4222-8222-222222222222")
    with pytest.raises(WatchlistNotFoundError, match=f"No watchlist with ID {missing} exists"):
        coordinate_refresh(
            WatchlistId(missing),
            watchlists=watchlists,
            repository=_FakeSink(),
            executor=_executor,
            run_specs=RUN_SPECS_BY_KEY,
            describe=failure_text,
            policy=RefreshPolicy(workers=1),
        )
