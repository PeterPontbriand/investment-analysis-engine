"""Focused tests for the refresh service: sequential (G1) and bounded concurrent (G2)."""

import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from alembic.config import Config

from alembic import command
from src.analysis.strategy.graham_number.calculation import GrahamNumberInputAssembly, GrahamNumberResult
from src.analysis.strategy.graham_number.service import GrahamNumberAnalysis
from src.analysis.strategy.momentum.momentum_analyzer import MomentumRun
from src.config import ProjectSettings
from src.core.analysis_status import CalculationStatus
from src.data.financial.provenance import ResolvedInput, SourceKind
from src.data.repositories.analysis_runs import SQLiteAnalysisRunRepository
from src.data.repositories.sqlite import SQLiteDatabase
from src.evaluation.fixtures.market_data import FixtureDataClient
from src.workspace.codecs import encode_evidence
from src.workspace.execution import ExecutionCapture
from src.workspace.models import RunOutcome
from src.workspace.momentum_execution import run_momentum
from src.workspace.refresh import (
    EmptyRefreshTargetError,
    RefreshJobResult,
    RefreshPolicy,
    RefreshSummary,
    WatchlistNotFoundError,
    refresh_watchlist,
)
from src.workspace.requests import AnalysisSelection, GrahamNumberSelection, MomentumSelection
from src.workspace.runs import AnalysisRun, Watchlist, WatchlistEntry

WATCHLIST_ID = UUID("11111111-1111-4111-8111-111111111111")
NOW = datetime(2026, 9, 19, 12, 0, 0, tzinfo=UTC)


class _FixtureClient(FixtureDataClient):
    """FixtureDataClient with a stable provider identity for the full resolver path."""

    @property
    def provider_id(self) -> str:
        return "fixture"


class _FakeWatchlists:
    """Minimal WatchlistLookup backed by an in-memory mapping."""

    def __init__(self, watchlists: dict[str, Watchlist]) -> None:
        self._watchlists = watchlists

    def get(self, name: str) -> Watchlist | None:
        return self._watchlists.get(name.strip().casefold())


class _FakeSink:
    """Minimal AnalysisRunSink; optionally fails insert for specific tickers."""

    def __init__(self, *, fail_for_tickers: frozenset[str] = frozenset()) -> None:
        self.inserted: list[AnalysisRun] = []
        self._fail_for_tickers = fail_for_tickers

    def insert(self, run: AnalysisRun) -> None:
        if run.ticker in self._fail_for_tickers:
            raise RuntimeError(f"simulated storage failure for {run.ticker}")
        self.inserted.append(run)


def _watchlist(members: tuple[str, ...], selections: tuple[AnalysisSelection, ...]) -> Watchlist:
    """Build a watchlist whose entries are the (member x selection) cross product.

    Kept as a `(members, selections)` helper rather than switching every call
    site to explicit entries: G1-G3's own tests exercise the execution
    service's admission/cancellation/persistence behavior given a job list,
    not the watchlist model itself (that is `test_runs.py`'s job), and the
    cross product is still the exact job list these tests were written
    against.
    """
    return Watchlist(
        watchlist_id=WATCHLIST_ID,
        display_name="My Watch",
        normalized_name="my watch",
        created_at=NOW,
        entries=tuple(
            WatchlistEntry(ticker=ticker, selection=selection) for ticker in members for selection in selections
        ),
    )


def _momentum_capture(ticker: str, outcome: RunOutcome = RunOutcome.COMPLETED) -> ExecutionCapture:
    selection = MomentumSelection(short_window=2, long_window=3)
    native: MomentumRun = run_momentum(selection, ticker, _FixtureClient())
    return ExecutionCapture(native_evidence=native, profile=None, outcome=outcome)


def _momentum_only_executor(ticker: str, selection: AnalysisSelection) -> ExecutionCapture:
    assert isinstance(selection, MomentumSelection)
    return _momentum_capture(ticker)


def test_refresh_watchlist_raises_for_missing_watchlist() -> None:
    with pytest.raises(WatchlistNotFoundError, match="No watchlist named"):
        refresh_watchlist(
            "Nonexistent",
            watchlists=_FakeWatchlists({}),
            repository=_FakeSink(),
            executor=_momentum_only_executor,
        )


def test_refresh_watchlist_raises_for_empty_membership() -> None:
    watchlist = _watchlist((), (MomentumSelection(short_window=2, long_window=3),))
    with pytest.raises(EmptyRefreshTargetError, match="has no entries"):
        refresh_watchlist(
            "My Watch",
            watchlists=_FakeWatchlists({"my watch": watchlist}),
            repository=_FakeSink(),
            executor=_momentum_only_executor,
        )


def test_refresh_watchlist_raises_for_zero_selections() -> None:
    watchlist = _watchlist(("AAPL",), ())
    with pytest.raises(EmptyRefreshTargetError, match="has no entries"):
        refresh_watchlist(
            "My Watch",
            watchlists=_FakeWatchlists({"my watch": watchlist}),
            repository=_FakeSink(),
            executor=_momentum_only_executor,
        )


def test_refresh_watchlist_iterates_member_then_selection_position_order() -> None:
    momentum = MomentumSelection(short_window=2, long_window=3)
    number = GrahamNumberSelection()
    watchlist = _watchlist(("AAPL", "MSFT"), (momentum, number))
    sink = _FakeSink()

    def executor(ticker: str, selection: AnalysisSelection) -> ExecutionCapture:
        if isinstance(selection, MomentumSelection):
            return _momentum_capture(ticker)
        # A minimal, deterministic Graham Number capture for ordering purposes only.
        eps = ResolvedInput("eps", 4.0, SourceKind.PROVIDER, NOW, provider_id="sec_edgar", as_of=NOW)
        bvps = ResolvedInput("book_value_per_share", 10.0, SourceKind.OVERRIDE, NOW, as_of=NOW)
        analysis = GrahamNumberAnalysis(
            ticker=ticker,
            as_of=NOW,
            assembly=GrahamNumberInputAssembly(CalculationStatus.OK, eps, bvps, None),
            result=GrahamNumberResult(status=CalculationStatus.OK, maximum_indicated_price=30.0),
            margin_of_safety_percent=None,
        )
        return ExecutionCapture(native_evidence=analysis, profile=None, outcome=RunOutcome.COMPLETED)

    summary = refresh_watchlist(
        "My Watch",
        watchlists=_FakeWatchlists({"my watch": watchlist}),
        repository=sink,
        executor=executor,
        clock=lambda: NOW,
    )

    assert [(r.ticker, r.method_id) for r in summary.results] == [
        ("AAPL", "sma_crossover"),
        ("AAPL", "graham_number"),
        ("MSFT", "sma_crossover"),
        ("MSFT", "graham_number"),
    ]
    assert [r.run.batch_position for r in summary.results if r.run is not None] == [0, 1, 2, 3]


def test_refresh_watchlist_stamps_shared_refresh_and_watchlist_identity() -> None:
    watchlist = _watchlist(("AAPL", "MSFT"), (MomentumSelection(short_window=2, long_window=3),))
    summary = refresh_watchlist(
        "My Watch",
        watchlists=_FakeWatchlists({"my watch": watchlist}),
        repository=_FakeSink(),
        executor=_momentum_only_executor,
        refresh_id_factory=lambda: UUID("22222222-2222-4222-8222-222222222222"),
        clock=lambda: NOW,
    )

    assert summary.refresh_id == UUID("22222222-2222-4222-8222-222222222222")
    assert summary.watchlist_id == WATCHLIST_ID
    assert summary.watchlist_name == "My Watch"
    for result in summary.results:
        assert result.run is not None
        assert result.run.refresh_id == summary.refresh_id
        assert result.run.watchlist_id == WATCHLIST_ID
        assert result.run.watchlist_name == "My Watch"


def test_refresh_watchlist_isolates_one_jobs_executor_exception() -> None:
    watchlist = _watchlist(("AAPL", "BROKEN", "MSFT"), (MomentumSelection(short_window=2, long_window=3),))
    sink = _FakeSink()

    def executor(ticker: str, _selection: AnalysisSelection) -> ExecutionCapture:
        if ticker == "BROKEN":
            raise RuntimeError("simulated unexpected adapter failure")
        return _momentum_capture(ticker)

    summary = refresh_watchlist(
        "My Watch",
        watchlists=_FakeWatchlists({"my watch": watchlist}),
        repository=sink,
        executor=executor,
        clock=lambda: NOW,
    )

    assert [r.ticker for r in summary.results] == ["AAPL", "BROKEN", "MSFT"]
    broken = summary.results[1]
    assert broken.run is None
    assert broken.error is not None
    assert "simulated unexpected adapter failure" in broken.error
    # The other two jobs still ran and persisted despite the middle job's failure.
    assert {item.ticker for item in sink.inserted} == {"AAPL", "MSFT"}
    assert summary.results[0].run is not None
    assert summary.results[2].run is not None


def test_refresh_watchlist_isolates_one_jobs_persistence_failure() -> None:
    watchlist = _watchlist(("AAPL", "MSFT"), (MomentumSelection(short_window=2, long_window=3),))
    sink = _FakeSink(fail_for_tickers=frozenset({"AAPL"}))

    summary = refresh_watchlist(
        "My Watch",
        watchlists=_FakeWatchlists({"my watch": watchlist}),
        repository=sink,
        executor=_momentum_only_executor,
        clock=lambda: NOW,
    )

    failed, succeeded = summary.results
    assert failed.ticker == "AAPL"
    assert failed.run is None
    assert failed.error is not None
    assert "simulated storage failure" in failed.error
    assert succeeded.ticker == "MSFT"
    assert succeeded.run is not None
    assert {item.ticker for item in sink.inserted} == {"MSFT"}


def test_refresh_watchlist_repeated_calls_produce_distinct_runs() -> None:
    watchlist = _watchlist(("AAPL",), (MomentumSelection(short_window=2, long_window=3),))
    sink = _FakeSink()

    first = refresh_watchlist(
        "My Watch",
        watchlists=_FakeWatchlists({"my watch": watchlist}),
        repository=sink,
        executor=_momentum_only_executor,
        clock=lambda: NOW,
    )
    second = refresh_watchlist(
        "My Watch",
        watchlists=_FakeWatchlists({"my watch": watchlist}),
        repository=sink,
        executor=_momentum_only_executor,
        clock=lambda: NOW,
    )

    assert first.refresh_id != second.refresh_id
    first_run = first.results[0].run
    second_run = second.results[0].run
    assert first_run is not None
    assert second_run is not None
    assert first_run.analysis_run_id != second_run.analysis_run_id
    assert len(sink.inserted) == 2


def test_refresh_watchlist_persists_each_job_before_the_next_executes() -> None:
    """Per-completion durability: job N's insert happens before job N+1's executor runs."""
    watchlist = _watchlist(("AAPL", "MSFT", "KO"), (MomentumSelection(short_window=2, long_window=3),))
    events: list[str] = []

    class _RecordingSink(_FakeSink):
        def insert(self, run: AnalysisRun) -> None:
            events.append(f"insert:{run.ticker}")
            super().insert(run)

    def executor(ticker: str, _selection: AnalysisSelection) -> ExecutionCapture:
        events.append(f"execute:{ticker}")
        return _momentum_capture(ticker)

    refresh_watchlist(
        "My Watch",
        watchlists=_FakeWatchlists({"my watch": watchlist}),
        repository=_RecordingSink(),
        executor=executor,
        clock=lambda: NOW,
    )

    assert events == [
        "execute:AAPL",
        "insert:AAPL",
        "execute:MSFT",
        "insert:MSFT",
        "execute:KO",
        "insert:KO",
    ]


def test_refresh_watchlist_with_save_false_executes_but_persists_nothing() -> None:
    """`save=False` still runs every entry; nothing reaches the repository."""
    watchlist = _watchlist(("AAPL", "MSFT"), (MomentumSelection(short_window=2, long_window=3),))
    sink = _FakeSink()

    summary = refresh_watchlist(
        "My Watch",
        watchlists=_FakeWatchlists({"my watch": watchlist}),
        repository=sink,
        executor=_momentum_only_executor,
        save=False,
        clock=lambda: NOW,
    )

    assert [r.ticker for r in summary.results] == ["AAPL", "MSFT"]
    for result in summary.results:
        assert result.run is None
        assert result.error is None
        assert result.outcome is RunOutcome.COMPLETED
    assert sink.inserted == []
    assert summary.counts == {"completed": 2}


def test_refresh_watchlist_with_save_false_still_isolates_one_jobs_executor_exception() -> None:
    watchlist = _watchlist(("AAPL", "BROKEN", "MSFT"), (MomentumSelection(short_window=2, long_window=3),))
    sink = _FakeSink()

    def executor(ticker: str, _selection: AnalysisSelection) -> ExecutionCapture:
        if ticker == "BROKEN":
            raise RuntimeError("simulated unexpected adapter failure")
        return _momentum_capture(ticker)

    summary = refresh_watchlist(
        "My Watch",
        watchlists=_FakeWatchlists({"my watch": watchlist}),
        repository=sink,
        executor=executor,
        save=False,
        clock=lambda: NOW,
    )

    assert [r.ticker for r in summary.results] == ["AAPL", "BROKEN", "MSFT"]
    broken = summary.results[1]
    assert broken.run is None
    assert broken.outcome is None
    assert broken.error is not None
    assert "simulated unexpected adapter failure" in broken.error
    assert summary.results[0].outcome is RunOutcome.COMPLETED
    assert summary.results[2].outcome is RunOutcome.COMPLETED
    assert sink.inserted == []


def test_refresh_summary_counts_by_outcome() -> None:
    completed_run = _build_run(status=RunOutcome.COMPLETED)
    failed_run = _build_run(status=RunOutcome.FAILED, failure_reason_code="execution_failed")
    summary = RefreshSummary(
        refresh_id=UUID("22222222-2222-4222-8222-222222222222"),
        watchlist_id=WATCHLIST_ID,
        watchlist_name="My Watch",
        results=(
            RefreshJobResult(ticker="AAPL", method_id="sma_crossover", run=completed_run),
            RefreshJobResult(ticker="MSFT", method_id="sma_crossover", run=failed_run),
            RefreshJobResult(ticker="KO", method_id="sma_crossover", error="boom"),
            RefreshJobResult(ticker="GE", method_id="sma_crossover", outcome=RunOutcome.UNAVAILABLE),
        ),
    )
    assert summary.counts == {"completed": 1, "failed": 1, "error": 1, "unavailable": 1}


def _build_run(*, status: RunOutcome, failure_reason_code: str | None = None) -> AnalysisRun:
    native = run_momentum(MomentumSelection(short_window=2, long_window=3), "AAPL", _FixtureClient())
    return AnalysisRun(
        analysis_run_id=UUID("33333333-3333-4333-8333-333333333333"),
        ticker="AAPL",
        analysis_id="momentum",
        method_id="sma_crossover",
        config_schema_version=1,
        requested_config=MomentumSelection(short_window=2, long_window=3),
        started_at=NOW,
        completed_at=NOW,
        method_version=1,
        result_schema_version=1,
        evidence_codec_version=1,
        status=status,
        failure_reason_code=failure_reason_code,
        result_evidence=encode_evidence(native) if status is not RunOutcome.FAILED else None,
    )


def test_refresh_policy_validates_worker_range() -> None:
    RefreshPolicy(workers=1)
    RefreshPolicy(workers=4)
    with pytest.raises(ValueError, match="between 1 and 4"):
        RefreshPolicy(workers=0)
    with pytest.raises(ValueError, match="between 1 and 4"):
        RefreshPolicy(workers=5)


def test_refresh_job_result_requires_exactly_one_of_run_outcome_or_error() -> None:
    run = _build_run(status=RunOutcome.COMPLETED)
    with pytest.raises(ValueError, match="Exactly one"):
        RefreshJobResult(ticker="AAPL", method_id="sma_crossover", run=None, error=None)
    with pytest.raises(ValueError, match="Exactly one"):
        RefreshJobResult(ticker="AAPL", method_id="sma_crossover", run=run, error="both set")
    with pytest.raises(ValueError, match="Exactly one"):
        RefreshJobResult(ticker="AAPL", method_id="sma_crossover", run=run, outcome=RunOutcome.COMPLETED)
    with pytest.raises(ValueError, match="Exactly one"):
        RefreshJobResult(ticker="AAPL", method_id="sma_crossover", outcome=RunOutcome.COMPLETED, error="both set")
    # A lone `outcome` (no run, no error) is the valid, third accepted state.
    RefreshJobResult(ticker="AAPL", method_id="sma_crossover", outcome=RunOutcome.COMPLETED)


def test_job_outcome_requires_exactly_one_of_capture_or_error() -> None:
    from src.workspace.refresh import _JobOutcome  # noqa: PLC0415 - private, test-only import

    capture = _momentum_capture("AAPL")
    with pytest.raises(ValueError, match="Exactly one"):
        _JobOutcome(started_at=NOW, completed_at=NOW, capture=None, error=None)
    with pytest.raises(ValueError, match="Exactly one"):
        _JobOutcome(started_at=NOW, completed_at=NOW, capture=capture, error=RuntimeError("both set"))


# --- G2: bounded concurrent admission -----------------------------------------------------


class _ThreadSafeLog:
    """A cross-thread-safe append-only event log for asserting causal ordering."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.entries: list[str] = []

    def append(self, entry: str) -> None:
        with self._lock:
            self.entries.append(entry)


class _GatedExecutor:
    """Fake executor that blocks each ticker until explicitly released, logging admission."""

    def __init__(self, log: _ThreadSafeLog) -> None:
        self._log = log
        self._admitted: dict[str, threading.Event] = {}
        self._release: dict[str, threading.Event] = {}

    def admitted(self, ticker: str) -> threading.Event:
        return self._admitted.setdefault(ticker, threading.Event())

    def release(self, ticker: str) -> threading.Event:
        return self._release.setdefault(ticker, threading.Event())

    def __call__(self, ticker: str, _selection: AnalysisSelection) -> ExecutionCapture:
        self._log.append(f"admit:{ticker}")
        self.admitted(ticker).set()
        assert self.release(ticker).wait(5), f"{ticker} was never released"
        return _momentum_capture(ticker)


class _LoggingSink(_FakeSink):
    """A _FakeSink that also logs each insert, for cross-thread causal-ordering assertions."""

    def __init__(self, log: _ThreadSafeLog) -> None:
        super().__init__()
        self._log = log

    def insert(self, run: AnalysisRun) -> None:
        self._log.append(f"insert:{run.ticker}")
        super().insert(run)


def test_g2_bounds_admission_and_gates_replacement_on_persisted_completion() -> None:
    """At most `workers` jobs run at once; a freed slot is only replaced after its job is persisted."""
    watchlist = _watchlist(("A", "B", "C"), (MomentumSelection(short_window=2, long_window=3),))
    log = _ThreadSafeLog()
    gated = _GatedExecutor(log)
    sink = _LoggingSink(log)
    outcome: list[RefreshSummary] = []

    thread = threading.Thread(
        target=lambda: outcome.append(
            refresh_watchlist(
                "My Watch",
                watchlists=_FakeWatchlists({"my watch": watchlist}),
                repository=sink,
                executor=gated,
                policy=RefreshPolicy(workers=2),
                clock=lambda: NOW,
            )
        )
    )
    thread.start()
    try:
        assert gated.admitted("A").wait(5)
        assert gated.admitted("B").wait(5)
        # Bounded to 2 in flight: the third job must not be admitted yet.
        assert not gated.admitted("C").is_set()

        gated.release("A").set()
        # The freed slot is only replaced after A's result is persisted.
        assert gated.admitted("C").wait(5)
        gated.release("B").set()
        gated.release("C").set()
        thread.join(5)
        assert not thread.is_alive()
    finally:
        for ticker in ("A", "B", "C"):
            gated.release(ticker).set()
        if thread.is_alive():
            thread.join(5)

    assert {log.entries[0], log.entries[1]} == {"admit:A", "admit:B"}
    assert log.entries.index("insert:A") < log.entries.index("admit:C")

    summary = outcome[0]
    assert [r.ticker for r in summary.results] == ["A", "B", "C"]
    assert all(r.run is not None for r in summary.results)


def test_g2_preserves_snapshot_order_despite_out_of_order_completion() -> None:
    """The summary is always in watchlist snapshot order, regardless of which job finishes first."""
    watchlist = _watchlist(("SLOW", "FAST"), (MomentumSelection(short_window=2, long_window=3),))
    slow_admitted = threading.Event()
    slow_may_finish = threading.Event()

    def executor(ticker: str, _selection: AnalysisSelection) -> ExecutionCapture:
        if ticker == "SLOW":
            slow_admitted.set()
            assert slow_may_finish.wait(5), "SLOW was never released"
        return _momentum_capture(ticker)

    outcome: list[RefreshSummary] = []
    thread = threading.Thread(
        target=lambda: outcome.append(
            refresh_watchlist(
                "My Watch",
                watchlists=_FakeWatchlists({"my watch": watchlist}),
                repository=_FakeSink(),
                executor=executor,
                policy=RefreshPolicy(workers=2),
                clock=lambda: NOW,
            )
        )
    )
    thread.start()
    try:
        assert slow_admitted.wait(5)
        slow_may_finish.set()
        thread.join(5)
        assert not thread.is_alive()
    finally:
        slow_may_finish.set()
        if thread.is_alive():
            thread.join(5)

    summary = outcome[0]
    assert [r.ticker for r in summary.results] == ["SLOW", "FAST"]
    assert all(r.run is not None for r in summary.results)


def test_g2_repository_insert_always_runs_on_the_calling_thread_not_a_worker() -> None:
    """The coordinator (the calling thread) is the only thread that ever writes."""
    watchlist = _watchlist(("AAPL", "MSFT", "KO"), (MomentumSelection(short_window=2, long_window=3),))
    caller_thread_id = threading.get_ident()
    executor_thread_ids: set[int] = set()
    insert_thread_ids: set[int] = set()
    lock = threading.Lock()

    def executor(ticker: str, _selection: AnalysisSelection) -> ExecutionCapture:
        with lock:
            executor_thread_ids.add(threading.get_ident())
        return _momentum_capture(ticker)

    class _ThreadTrackingSink(_FakeSink):
        def insert(self, run: AnalysisRun) -> None:
            with lock:
                insert_thread_ids.add(threading.get_ident())
            super().insert(run)

    refresh_watchlist(
        "My Watch",
        watchlists=_FakeWatchlists({"my watch": watchlist}),
        repository=_ThreadTrackingSink(),
        executor=executor,
        policy=RefreshPolicy(workers=2),
        clock=lambda: NOW,
    )

    assert insert_thread_ids == {caller_thread_id}
    assert caller_thread_id not in executor_thread_ids


def test_g2_persists_worker_measured_timing_via_replay_clock() -> None:
    """A job's started_at/completed_at reflect the worker's own measured window, not coordinator time."""
    watchlist = _watchlist(("AAPL",), (MomentumSelection(short_window=2, long_window=3),))
    ticks = iter([NOW, NOW + timedelta(seconds=5)])
    lock = threading.Lock()

    def clock() -> datetime:
        with lock:
            return next(ticks)

    summary = refresh_watchlist(
        "My Watch",
        watchlists=_FakeWatchlists({"my watch": watchlist}),
        repository=_FakeSink(),
        executor=_momentum_only_executor,
        policy=RefreshPolicy(workers=2),
        clock=clock,
    )

    run = summary.results[0].run
    assert run is not None
    assert run.started_at == NOW
    assert run.completed_at == NOW + timedelta(seconds=5)


def test_g2_isolates_one_jobs_executor_exception() -> None:
    watchlist = _watchlist(("AAPL", "BROKEN", "MSFT"), (MomentumSelection(short_window=2, long_window=3),))
    sink = _FakeSink()

    def executor(ticker: str, _selection: AnalysisSelection) -> ExecutionCapture:
        if ticker == "BROKEN":
            raise RuntimeError("simulated unexpected adapter failure")
        return _momentum_capture(ticker)

    summary = refresh_watchlist(
        "My Watch",
        watchlists=_FakeWatchlists({"my watch": watchlist}),
        repository=sink,
        executor=executor,
        policy=RefreshPolicy(workers=2),
        clock=lambda: NOW,
    )

    assert [r.ticker for r in summary.results] == ["AAPL", "BROKEN", "MSFT"]
    broken = summary.results[1]
    assert broken.run is None
    assert broken.error is not None
    assert "simulated unexpected adapter failure" in broken.error
    assert {item.ticker for item in sink.inserted} == {"AAPL", "MSFT"}
    assert summary.results[0].run is not None
    assert summary.results[2].run is not None


def test_g2_isolates_one_jobs_persistence_failure() -> None:
    watchlist = _watchlist(("AAPL", "MSFT"), (MomentumSelection(short_window=2, long_window=3),))
    sink = _FakeSink(fail_for_tickers=frozenset({"AAPL"}))

    summary = refresh_watchlist(
        "My Watch",
        watchlists=_FakeWatchlists({"my watch": watchlist}),
        repository=sink,
        executor=_momentum_only_executor,
        policy=RefreshPolicy(workers=2),
        clock=lambda: NOW,
    )

    results_by_ticker = {r.ticker: r for r in summary.results}
    assert results_by_ticker["AAPL"].run is None
    assert results_by_ticker["AAPL"].error is not None
    assert "simulated storage failure" in results_by_ticker["AAPL"].error
    assert results_by_ticker["MSFT"].run is not None
    assert {item.ticker for item in sink.inserted} == {"MSFT"}


def test_g2_workers_greater_than_job_count_runs_every_job_without_error() -> None:
    watchlist = _watchlist(("AAPL",), (MomentumSelection(short_window=2, long_window=3),))
    summary = refresh_watchlist(
        "My Watch",
        watchlists=_FakeWatchlists({"my watch": watchlist}),
        repository=_FakeSink(),
        executor=_momentum_only_executor,
        policy=RefreshPolicy(workers=4),
        clock=lambda: NOW,
    )
    assert len(summary.results) == 1
    assert summary.results[0].run is not None


def test_g2_with_save_false_executes_but_persists_nothing() -> None:
    """The concurrent path's coordinator-only settle step also honors `save=False`."""
    watchlist = _watchlist(("AAPL", "MSFT"), (MomentumSelection(short_window=2, long_window=3),))
    sink = _FakeSink()

    summary = refresh_watchlist(
        "My Watch",
        watchlists=_FakeWatchlists({"my watch": watchlist}),
        repository=sink,
        executor=_momentum_only_executor,
        save=False,
        policy=RefreshPolicy(workers=2),
        clock=lambda: NOW,
    )

    assert {r.ticker for r in summary.results} == {"AAPL", "MSFT"}
    for result in summary.results:
        assert result.run is None
        assert result.outcome is RunOutcome.COMPLETED
    assert sink.inserted == []


class _SignalingRepository:
    """Wraps a real repository, recording each inserted run's id and signaling one ticker's insert."""

    def __init__(
        self,
        inner: SQLiteAnalysisRunRepository,
        captured_ids: dict[str, UUID],
        signal_ticker: str,
        signal: threading.Event,
    ) -> None:
        self._inner = inner
        self._captured_ids = captured_ids
        self._signal_ticker = signal_ticker
        self._signal = signal

    def insert(self, run: AnalysisRun) -> None:
        self._inner.insert(run)
        self._captured_ids[run.ticker] = run.analysis_run_id
        if run.ticker == self._signal_ticker:
            self._signal.set()


def _gated_two_ticker_executor(
    admitted: dict[str, threading.Event], release: dict[str, threading.Event]
) -> Callable[[str, AnalysisSelection], ExecutionCapture]:
    def executor(ticker: str, _selection: AnalysisSelection) -> ExecutionCapture:
        admitted[ticker].set()
        assert release[ticker].wait(5), f"{ticker} was never released"
        return _momentum_capture(ticker)

    return executor


def test_g2_concurrent_refresh_saves_are_visible_to_another_connection_before_the_batch_finishes(
    tmp_path: Path,
) -> None:
    """A run persisted mid-refresh is immediately visible from a separate connection.

    Proven with real SQLite storage, not fakes: AAPL's job is released and its insert
    observed while MSFT's job is still deliberately blocked, so the batch has not
    finished when a brand-new connection looks the run up.
    """
    url = f"sqlite:///{(tmp_path / 'refresh.sqlite3').as_posix()}"
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")

    watchlist = _watchlist(("AAPL", "MSFT"), (MomentumSelection(short_window=2, long_window=3),))
    admitted = {"AAPL": threading.Event(), "MSFT": threading.Event()}
    release = {"AAPL": threading.Event(), "MSFT": threading.Event()}
    aapl_persisted = threading.Event()
    captured_ids: dict[str, UUID] = {}

    database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        repository = _SignalingRepository(SQLiteAnalysisRunRepository(database), captured_ids, "AAPL", aapl_persisted)
        outcome: list[RefreshSummary] = []
        thread = threading.Thread(
            target=lambda: outcome.append(
                refresh_watchlist(
                    "My Watch",
                    watchlists=_FakeWatchlists({"my watch": watchlist}),
                    repository=repository,
                    executor=_gated_two_ticker_executor(admitted, release),
                    policy=RefreshPolicy(workers=2),
                    clock=lambda: NOW,
                )
            )
        )
        thread.start()
        try:
            assert admitted["AAPL"].wait(5)
            assert admitted["MSFT"].wait(5)
            release["AAPL"].set()
            assert aapl_persisted.wait(5)
            assert thread.is_alive(), "MSFT is still blocked: the batch must not have finished yet"
            _assert_visible_from_a_fresh_connection(url, captured_ids["AAPL"])
        finally:
            release["MSFT"].set()
            thread.join(5)
    finally:
        database.close()

    assert not thread.is_alive()
    summary = outcome[0]
    assert {r.ticker for r in summary.results} == {"AAPL", "MSFT"}
    assert all(r.run is not None for r in summary.results)


def _assert_visible_from_a_fresh_connection(url: str, run_id: UUID) -> None:
    other_database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        visible = SQLiteAnalysisRunRepository(other_database).get(run_id)
        assert visible is not None
        assert visible.ticker == "AAPL"
    finally:
        other_database.close()


# --- G3: graceful cooperative cancellation ------------------------------------------------


def test_g3_sequential_refresh_admits_nothing_when_already_cancelled() -> None:
    watchlist = _watchlist(("AAPL", "MSFT"), (MomentumSelection(short_window=2, long_window=3),))
    already_cancelled = threading.Event()
    already_cancelled.set()

    summary = refresh_watchlist(
        "My Watch",
        watchlists=_FakeWatchlists({"my watch": watchlist}),
        repository=_FakeSink(),
        executor=_momentum_only_executor,
        clock=lambda: NOW,
        cancellation=already_cancelled,
    )

    assert summary.results == ()


def test_g3_sequential_refresh_stops_admitting_once_cancelled_mid_batch() -> None:
    watchlist = _watchlist(("AAPL", "MSFT", "KO"), (MomentumSelection(short_window=2, long_window=3),))
    cancellation = threading.Event()

    def executor(ticker: str, _selection: AnalysisSelection) -> ExecutionCapture:
        if ticker == "AAPL":
            cancellation.set()
        return _momentum_capture(ticker)

    summary = refresh_watchlist(
        "My Watch",
        watchlists=_FakeWatchlists({"my watch": watchlist}),
        repository=_FakeSink(),
        executor=executor,
        clock=lambda: NOW,
        cancellation=cancellation,
    )

    # AAPL was already admitted when cancellation fired inside its own executor
    # call; MSFT and KO were never started and never appear in the summary.
    assert [r.ticker for r in summary.results] == ["AAPL"]
    assert summary.results[0].run is not None


def test_g3_concurrent_refresh_admits_nothing_when_already_cancelled() -> None:
    watchlist = _watchlist(("AAPL", "MSFT"), (MomentumSelection(short_window=2, long_window=3),))
    already_cancelled = threading.Event()
    already_cancelled.set()

    summary = refresh_watchlist(
        "My Watch",
        watchlists=_FakeWatchlists({"my watch": watchlist}),
        repository=_FakeSink(),
        executor=_momentum_only_executor,
        policy=RefreshPolicy(workers=2),
        clock=lambda: NOW,
        cancellation=already_cancelled,
    )

    assert summary.results == ()


def test_g3_concurrent_refresh_stops_admitting_and_lets_running_jobs_settle() -> None:
    """Cancellation stops admission but never a fabricated row, and running jobs still persist."""
    watchlist = _watchlist(("A", "B", "C"), (MomentumSelection(short_window=2, long_window=3),))
    log = _ThreadSafeLog()
    gated = _GatedExecutor(log)
    sink = _LoggingSink(log)
    cancellation = threading.Event()
    outcome: list[RefreshSummary] = []

    thread = threading.Thread(
        target=lambda: outcome.append(
            refresh_watchlist(
                "My Watch",
                watchlists=_FakeWatchlists({"my watch": watchlist}),
                repository=sink,
                executor=gated,
                policy=RefreshPolicy(workers=2),
                clock=lambda: NOW,
                cancellation=cancellation,
            )
        )
    )
    thread.start()
    try:
        assert gated.admitted("A").wait(5)
        assert gated.admitted("B").wait(5)
        cancellation.set()

        gated.release("A").set()
        # A's slot freed, but cancellation is set: C must never be admitted.
        assert not gated.admitted("C").wait(1)

        gated.release("B").set()
        thread.join(5)
        assert not thread.is_alive()
    finally:
        for ticker in ("A", "B", "C"):
            gated.release(ticker).set()
        if thread.is_alive():
            thread.join(5)

    assert "admit:C" not in log.entries
    summary = outcome[0]
    assert {r.ticker for r in summary.results} == {"A", "B"}
    assert all(r.run is not None for r in summary.results)
