"""Fakes for the refresh tests: a run function that returns a canned run, and a provider probe that records calls."""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch

from pydantic import BaseModel

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.strategy_run import StrategyRun
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.data.provider_probe import ProbeFinding, ProbeVerdict
from investment_analysis_engine.workspace.strategy_types import AnalysisSelection
from tests.workspace.test_refresh import _momentum_capture
from tests.workspace.test_refresh_provider_failure import _UNREACHABLE, _failed_capture


class Probe:
    """A provider probe that records each check and reports the provider unreachable."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def check(self, provider_id: str, *, requested: bool = True) -> ProbeFinding:
        self.calls.append((provider_id, requested))
        return ProbeFinding(provider_id, ProbeVerdict.UNREACHABLE)


class FakeDocument(BaseModel):
    """The document a fake run reports: only the ticker and the provider-check element it was asked for."""

    ticker: str
    method_id: str
    provider_check: object = None


class FakeRuns:
    """A run function that returns a canned run, optionally failing for chosen tickers or waiting on a gate.

    Attributes:
        calls: The ticker and the ``executed_at`` of each call, in call order.
    """

    def __init__(
        self,
        *,
        failing: frozenset[str] = frozenset(),
        raising: frozenset[str] = frozenset(),
        gate: threading.Event | None = None,
        entered: threading.Event | None = None,
        blocked: frozenset[str] | None = None,
    ) -> None:
        """Choose which tickers fail, raise or wait; ``blocked`` limits the gate to some tickers (all if ``None``)."""
        self._failing = failing
        self._raising = raising
        self._gate = gate
        self._entered = entered
        self._blocked = blocked
        self.calls: list[tuple[str, datetime]] = []
        self._lock = threading.Lock()

    def __call__(
        self,
        _context: ApplicationContext,
        ticker: str,
        selection: AnalysisSelection,
        /,
        *,
        executed_at: datetime,
        profile_cache: InstrumentProfileResolver | None,
    ) -> StrategyRun:
        del profile_cache
        with self._lock:
            self.calls.append((ticker, executed_at))
        waits = self._blocked is None or ticker in self._blocked
        if self._entered is not None and waits:
            self._entered.set()
        if self._gate is not None and waits:
            assert self._gate.wait(30), "the test never opened the gate"
        if ticker in self._raising:
            raise RuntimeError(f"simulated failure for {ticker}")
        capture = _failed_capture(ticker, _UNREACHABLE) if ticker in self._failing else _momentum_capture(ticker)
        method_id = selection.method_id
        return StrategyRun(
            execution=capture,
            document=lambda element: FakeDocument(ticker=ticker, method_id=method_id, provider_check=element),
            render_text=lambda element, mode: (
                f"{ticker} {method_id} as {mode}" + ("" if element is None else " with a provider check")
            ),
        )


@contextmanager
def fakes(probe: Probe, runs: FakeRuns | None = None) -> Iterator[FakeRuns]:
    """Replace the strategy run functions and the provider probe for the refresh operation; yield the fake runs."""
    chosen = FakeRuns() if runs is None else runs

    def runner(_selection: AnalysisSelection) -> FakeRuns:
        return chosen

    with (
        patch("investment_analysis_engine.application.refresh.analysis_runner_for", runner),
        patch("investment_analysis_engine.application.refresh.build_provider_probe", return_value=probe),
    ):
        yield chosen
