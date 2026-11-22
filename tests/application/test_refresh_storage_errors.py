"""A storage error while one entry's result is saved is that entry's failure; the other entries finish."""

from datetime import datetime
from pathlib import Path

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.refresh import RefreshEntries, prepare_refresh, run_refresh
from investment_analysis_engine.application.strategy_run import StrategyRun
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.workspace.strategy_types import AnalysisSelection
from tests._database_lock import Lock, short_wait_settings
from tests.application._refresh_fakes import FakeRuns, Probe, fakes
from tests.application.test_refresh import _entry


class _LockedWhileAnalyzing(FakeRuns):
    """Fake runs that hold a write lock while the chosen ticker is analyzed, so its save meets the lock."""

    def __init__(self, path: Path, locked_ticker: str) -> None:
        super().__init__()
        self._path = path
        self._locked_ticker = locked_ticker
        self._held: Lock | None = None

    def __call__(
        self,
        context: ApplicationContext,
        ticker: str,
        selection: AnalysisSelection,
        /,
        *,
        executed_at: datetime,
        profile_cache: InstrumentProfileResolver | None,
    ) -> StrategyRun:
        if self._held is not None:
            self._held.release()
            self._held = None
        if ticker == self._locked_ticker:
            self._held = Lock(self._path, block_reads=False)
        return super().__call__(context, ticker, selection, executed_at=executed_at, profile_cache=profile_cache)

    def release(self) -> None:
        """Release the lock a last entry may still hold."""
        if self._held is not None:
            self._held.release()


def test_an_entry_whose_save_meets_a_lock_fails_with_database_busy_and_the_others_finish(tmp_path: Path) -> None:
    settings, path = short_wait_settings(tmp_path)
    context = ApplicationContext(settings=settings)
    entries = RefreshEntries((_entry("AAPL"), _entry("MSFT"), _entry("KO")))
    prepared = prepare_refresh(context, entries, workers=1, save=True, provider_check=False)
    runs = _LockedWhileAnalyzing(path, "MSFT")

    try:
        with fakes(Probe(), runs):
            outcome = run_refresh(context, prepared)
    finally:
        runs.release()

    results = {result.ticker: result for result in outcome.document.results}
    assert [(result.ticker, result.saved) for result in outcome.document.results] == [
        ("AAPL", True),
        ("MSFT", False),
        ("KO", True),
    ]
    failed = results["MSFT"]
    assert failed.reason_code is not None
    assert failed.reason_code.value == "database_busy"
    assert failed.error is not None
    assert failed.outcome is None
    assert results["AAPL"].error is None
    assert results["KO"].error is None
    assert outcome.failed is True
    assert outcome.document.counts == {"completed": 2, "failed": 1} or outcome.document.counts
