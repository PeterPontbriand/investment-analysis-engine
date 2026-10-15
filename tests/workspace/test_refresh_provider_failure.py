"""A refresh job's in-memory result carries the ``provider_failure`` element, whichever way the job ended."""

from collections.abc import Callable

import pytest

from src.analysis.run_models import RunOutcome
from src.core.failure_classification import provider_failure_of
from src.core.provider_failure_element import ProviderFailure
from src.core.provider_failure_kind import ProviderFailureKind, ProviderFailureRecord
from src.data.base_client import DataFetchError
from src.strategies.momentum.selection import MomentumSelection
from src.strategy_wiring import RUN_SPECS_BY_KEY
from src.workspace.capture import ExecutionCapture
from src.workspace.refresh import RefreshJobResult, RefreshPolicy, RefreshSummary, refresh_watchlist
from src.workspace.strategy_types import AnalysisSelection
from tests._wiring import failure_text
from tests.workspace.test_refresh import (
    NOW,
    _FakeSink,
    _FakeWatchlists,
    _momentum_capture,
    _watchlist,
)

_SELECTION = MomentumSelection(short_window=2, long_window=3, rsi_period=14)
_UNREACHABLE = provider_failure_of((ProviderFailureRecord(ProviderFailureKind.UNREACHABLE, "yfinance"),))


def _failed_capture(ticker: str, provider_failure: ProviderFailure | None) -> ExecutionCapture:
    completed = _momentum_capture(ticker)
    return ExecutionCapture(
        native_evidence=completed.native_evidence,
        profile=None,
        outcome=RunOutcome.FAILED,
        failure_reason_code="provider_unreachable" if provider_failure is not None else "provider_error",
        provider_failure=provider_failure,
    )


def _refresh(
    executor: Callable[[str, AnalysisSelection], ExecutionCapture], *, save: bool = True, workers: int = 1
) -> RefreshSummary:
    watchlist = _watchlist(("AAPL", "BROKEN", "MSFT"), (_SELECTION,))
    return refresh_watchlist(
        "My Watch",
        watchlists=_FakeWatchlists({"my watch": watchlist}),
        repository=_FakeSink(),
        executor=executor,
        clock=lambda: NOW,
        run_specs=RUN_SPECS_BY_KEY,
        describe=failure_text,
        save=save,
        policy=RefreshPolicy(workers=workers),
    )


def _executor(ticker: str, _selection: AnalysisSelection) -> ExecutionCapture:
    if ticker == "BROKEN":
        return _failed_capture(ticker, _UNREACHABLE)
    return _momentum_capture(ticker)


@pytest.mark.parametrize("workers", [1, 2], ids=["sequential", "concurrent"])
def test_a_saved_failed_run_carries_the_element(workers: int) -> None:
    summary = _refresh(_executor, workers=workers)

    aapl, broken, msft = summary.results
    assert broken.run is not None
    assert broken.run.status is RunOutcome.FAILED
    assert broken.reason_code == "provider_unreachable"
    assert broken.provider_failure == _UNREACHABLE
    assert aapl.provider_failure is None
    assert msft.provider_failure is None


@pytest.mark.parametrize("workers", [1, 2], ids=["sequential", "concurrent"])
def test_an_unsaved_failed_outcome_carries_the_element(workers: int) -> None:
    summary = _refresh(_executor, save=False, workers=workers)

    broken = summary.results[1]
    assert broken.run is None
    assert broken.outcome is RunOutcome.FAILED
    assert broken.provider_failure == _UNREACHABLE


@pytest.mark.parametrize("save", [True, False], ids=["saved", "unsaved"])
@pytest.mark.parametrize("workers", [1, 2], ids=["sequential", "concurrent"])
def test_a_raised_provider_failure_carries_the_element(save: bool, workers: int) -> None:
    def executor(ticker: str, selection: AnalysisSelection) -> ExecutionCapture:
        if ticker == "BROKEN":
            raise DataFetchError("library detail", kind=ProviderFailureKind.RATE_LIMITED, provider_id="yfinance")
        return _executor(ticker, selection)

    summary = _refresh(executor, save=save, workers=workers)

    broken = summary.results[1]
    assert broken.error is not None
    assert broken.reason_code == "provider_rate_limited"
    assert broken.provider_failure == provider_failure_of(
        (ProviderFailureRecord(ProviderFailureKind.RATE_LIMITED, "yfinance"),)
    )


def test_a_failure_that_names_no_provider_carries_no_element() -> None:
    def executor(ticker: str, selection: AnalysisSelection) -> ExecutionCapture:
        if ticker == "BROKEN":
            raise RuntimeError("defect")
        return _executor(ticker, selection)

    broken = _refresh(executor).results[1]

    assert broken.error is not None
    assert broken.provider_failure is None


def test_an_unclassified_provider_failed_run_carries_no_element() -> None:
    def executor(ticker: str, selection: AnalysisSelection) -> ExecutionCapture:
        return _failed_capture(ticker, None) if ticker == "BROKEN" else _executor(ticker, selection)

    broken = _refresh(executor).results[1]

    assert broken.reason_code == "provider_error"
    assert broken.provider_failure is None


def test_the_element_requires_a_failed_job() -> None:
    with pytest.raises(ValueError, match="provider_failure requires a failed job"):
        RefreshJobResult(
            ticker="AAPL",
            method_id="m",
            outcome=RunOutcome.COMPLETED,
            provider_failure=_UNREACHABLE,
        )


def test_a_capture_carries_the_element_only_when_failed() -> None:
    completed = _momentum_capture("AAPL")

    with pytest.raises(ValueError, match="provider_failure requires the failed outcome"):
        ExecutionCapture(
            native_evidence=completed.native_evidence,
            profile=None,
            outcome=RunOutcome.COMPLETED,
            provider_failure=_UNREACHABLE,
        )
