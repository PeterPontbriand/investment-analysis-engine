"""A failed run stores a stable failure code, and a refresh job carries a code if and only if it failed.

One function turns a result's native status and stored provider failure into the code. A saved run and a refresh job
that was not saved call it through the capture, so the two never disagree.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from src.core.analysis_status import CalculationStatus
from src.core.provider_failure_kind import ProviderFailureKind, ProviderFailureRecord
from src.data.instrument_profile import InstrumentKind
from src.data.repositories.analysis_runs import AnalysisRunConflictError  # noqa: F401 - keeps the import graph warm
from src.evaluation.fixtures.instrument_profiles import fixture_instrument_profile
from src.reporting.documents.failure import FailureReasonCode
from src.reporting.failure_classification import (
    PROVIDER_CODE_BY_KIND,
    failure_reason_code,
    provider_failure_of,
)
from src.strategies.fcf_growth.execution import FCFGrowthCapture, from_fcf_growth_capture
from src.strategies.fcf_growth.models import FCFEarningsGrowthResult
from src.strategies.graham_growth.calculation import GrahamGrowthValueResult, GrowthValueInputAssembly
from src.strategies.graham_growth.execution import (
    GrahamGrowthCapture,
    classify_graham_growth_outcome,
    from_graham_growth_capture,
)
from src.strategies.graham_growth.service import GrahamGrowthAnalysis
from src.strategies.graham_number.calculation import GrahamNumberInputAssembly, GrahamNumberResult
from src.strategies.graham_number.execution import (
    GrahamNumberCapture,
    classify_graham_number_outcome,
    from_graham_number_capture,
)
from src.strategies.graham_number.service import GrahamNumberAnalysis
from src.strategies.momentum.selection import MomentumSelection
from src.strategy_wiring import RUN_SPECS_BY_KEY, run_spec_for
from src.workspace.capture import ExecutionCapture
from src.workspace.execution import execute
from src.workspace.models import RunOutcome
from src.workspace.refresh import RefreshJobResult, refresh_watchlist
from tests._wiring import failure_code
from tests.workspace.test_execution import _FakeSink as _ExecutionSink
from tests.workspace.test_execution import _momentum_native_evidence, _momentum_request
from tests.workspace.test_refresh import (
    _build_run,
    _FakeSink,
    _FakeWatchlists,
    _momentum_capture,
    _watchlist,
)

NOW = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)
_KINDS = list(ProviderFailureKind)
_PROFILE = fixture_instrument_profile("KO", kind=InstrumentKind.EQUITY, provider_value="EQUITY")


def _record(kind: ProviderFailureKind, input_name: str) -> ProviderFailureRecord:
    return ProviderFailureRecord(kind=kind, provider_id="sec_edgar", input=input_name)


def _number(
    status: CalculationStatus, failure: ProviderFailureRecord | None = None, *, result: CalculationStatus | None = None
) -> GrahamNumberAnalysis:
    assembly = GrahamNumberInputAssembly(
        status=status, reason=None if status is CalculationStatus.OK else "eps: failed", provider_failure=failure
    )
    result_status = result or status
    return GrahamNumberAnalysis(
        ticker="KO",
        as_of=None,
        effective_as_of=NOW,
        assembly=assembly,
        result=GrahamNumberResult(status=result_status, reason="failed"),
        margin_of_safety_percent=None,
    )


def _growth(status: CalculationStatus, failure: ProviderFailureRecord | None = None) -> GrahamGrowthAnalysis:
    from tests.reporting.test_analysis_run_replay import _GROWTH_POLICY  # noqa: PLC0415

    assembly = GrowthValueInputAssembly(status=status, reason="eps: failed", provider_failure=failure)
    return GrahamGrowthAnalysis(
        ticker="KO",
        as_of=None,
        effective_as_of=NOW,
        assembly=assembly,
        result=GrahamGrowthValueResult(status=status, reason="failed"),
        policy=_GROWTH_POLICY,
        margin_of_safety_percent=None,
    )


def _fcf(status: CalculationStatus, failure: ProviderFailureRecord | None = None) -> FCFEarningsGrowthResult:
    from tests._strategy_document_output import _fcf_invalid_input_result  # noqa: PLC0415
    from tests.reporting import test_analysis_run_replay as replay  # noqa: PLC0415

    return replace(_fcf_invalid_input_result(replay), execution_status=status, provider_failure=failure)


def _number_capture(analysis: GrahamNumberAnalysis) -> ExecutionCapture:
    return from_graham_number_capture(GrahamNumberCapture(analysis, _PROFILE, classify_graham_number_outcome(analysis)))


def _growth_capture(analysis: GrahamGrowthAnalysis) -> ExecutionCapture:
    return from_graham_growth_capture(GrahamGrowthCapture(analysis, _PROFILE, classify_graham_growth_outcome(analysis)))


def _fcf_capture(result: FCFEarningsGrowthResult) -> ExecutionCapture:
    from src.strategies.fcf_growth.execution import classify_fcf_growth_outcome  # noqa: PLC0415

    return from_fcf_growth_capture(FCFGrowthCapture(result, _PROFILE, classify_fcf_growth_outcome(result)))


# --- the one function from a result to its code ------------------------------------------------------------------


@pytest.mark.parametrize("kind", _KINDS)
def test_a_provider_error_is_the_mapped_provider_code(kind: ProviderFailureKind) -> None:
    element = provider_failure_of((_record(kind, "eps"),))

    assert failure_reason_code(CalculationStatus.PROVIDER_ERROR, element) is PROVIDER_CODE_BY_KIND[kind]


def test_an_unclassified_provider_error_keeps_the_generic_provider_code() -> None:
    assert failure_reason_code(CalculationStatus.PROVIDER_ERROR, None) is FailureReasonCode.PROVIDER_ERROR


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (CalculationStatus.INVALID_INPUT, FailureReasonCode.INVALID_INPUT),
        (CalculationStatus.NOT_APPLICABLE, FailureReasonCode.EXECUTION_ERROR),
        (CalculationStatus.INPUT_UNAVAILABLE, FailureReasonCode.EXECUTION_ERROR),
        (CalculationStatus.OK, FailureReasonCode.EXECUTION_ERROR),
    ],
)
def test_every_other_status_maps_to_invalid_input_or_execution_error(
    status: CalculationStatus, expected: FailureReasonCode
) -> None:
    element = provider_failure_of((_record(ProviderFailureKind.UNREACHABLE, "eps"),))

    assert failure_reason_code(status, element) is expected


_PRECEDENCE = [
    ProviderFailureKind.UNREACHABLE,
    ProviderFailureKind.UNEXPECTED_RESPONSE,
    ProviderFailureKind.NO_DATA,
]


@pytest.mark.parametrize(
    "ordering",
    [
        (first, second, third)
        for first in _PRECEDENCE
        for second in _PRECEDENCE
        for third in _PRECEDENCE
        if len({first, second, third}) == 3
    ],
)
def test_precedence_picks_the_same_code_for_every_ordering_of_the_kinds(
    ordering: tuple[ProviderFailureKind, ...],
) -> None:
    records = [_record(kind, f"input_{index}") for index, kind in enumerate(ordering)]

    element = provider_failure_of(records)

    assert element is not None
    assert element.reason_code is FailureReasonCode.PROVIDER_UNREACHABLE
    assert [item.kind for item in element.inputs] == list(ordering)
    assert failure_reason_code(CalculationStatus.PROVIDER_ERROR, element) is element.reason_code


@pytest.mark.parametrize(
    ("kinds", "expected"),
    [
        (
            (ProviderFailureKind.UNEXPECTED_RESPONSE, ProviderFailureKind.NO_DATA),
            FailureReasonCode.PROVIDER_UNEXPECTED_RESPONSE,
        ),
        (
            (ProviderFailureKind.NO_DATA, ProviderFailureKind.UNEXPECTED_RESPONSE),
            FailureReasonCode.PROVIDER_UNEXPECTED_RESPONSE,
        ),
        ((ProviderFailureKind.NO_DATA, ProviderFailureKind.NO_DATA), FailureReasonCode.PROVIDER_NO_DATA),
        ((ProviderFailureKind.NO_DATA, ProviderFailureKind.UNREACHABLE), FailureReasonCode.PROVIDER_UNREACHABLE),
    ],
)
def test_precedence_between_two_kinds(kinds: tuple[ProviderFailureKind, ...], expected: FailureReasonCode) -> None:
    element = provider_failure_of([_record(kind, f"input_{index}") for index, kind in enumerate(kinds)])

    assert element is not None
    assert element.reason_code is expected


def test_no_failed_input_is_no_element() -> None:
    assert provider_failure_of(()) is None
    assert provider_failure_of((None, None)) is None


# --- the code a failed run stores ----------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", _KINDS)
def test_a_failed_run_of_each_strategy_stores_the_mapped_provider_code(kind: ProviderFailureKind) -> None:
    captures = [
        _number_capture(_number(CalculationStatus.PROVIDER_ERROR, _record(kind, "eps"))),
        _growth_capture(_growth(CalculationStatus.PROVIDER_ERROR, _record(kind, "eps"))),
        _fcf_capture(_fcf(CalculationStatus.PROVIDER_ERROR, _record(kind, "operating_cash_flow"))),
    ]

    assert [capture.outcome for capture in captures] == [RunOutcome.FAILED] * 3
    assert {capture.failure_reason_code for capture in captures} == {PROVIDER_CODE_BY_KIND[kind].value}


def test_a_failed_run_without_a_recorded_kind_stores_the_generic_provider_code() -> None:
    captures = [
        _number_capture(_number(CalculationStatus.PROVIDER_ERROR)),
        _growth_capture(_growth(CalculationStatus.PROVIDER_ERROR)),
        _fcf_capture(_fcf(CalculationStatus.PROVIDER_ERROR)),
    ]

    assert {capture.failure_reason_code for capture in captures} == {"provider_error"}


def test_a_failed_run_with_invalid_input_stores_invalid_input() -> None:
    captures = [
        _number_capture(_number(CalculationStatus.INVALID_INPUT)),
        _growth_capture(_growth(CalculationStatus.INVALID_INPUT)),
        _fcf_capture(_fcf(CalculationStatus.INVALID_INPUT)),
    ]

    assert {capture.failure_reason_code for capture in captures} == {"invalid_input"}


def test_a_failed_run_from_a_calculation_that_does_not_apply_stores_execution_error() -> None:
    analysis = _number(CalculationStatus.OK, result=CalculationStatus.NOT_APPLICABLE)

    capture = _number_capture(analysis)

    assert capture.outcome is RunOutcome.FAILED
    assert capture.failure_reason_code == "execution_error"


def test_a_run_that_did_not_fail_stores_no_code() -> None:
    unavailable = _number_capture(_number(CalculationStatus.INPUT_UNAVAILABLE))
    not_applicable = _number_capture(_number(CalculationStatus.NOT_APPLICABLE))

    assert unavailable.outcome is RunOutcome.UNAVAILABLE
    assert not_applicable.outcome is RunOutcome.NOT_APPLICABLE
    assert unavailable.failure_reason_code is None
    assert not_applicable.failure_reason_code is None


def test_a_capture_requires_a_code_exactly_when_the_outcome_failed() -> None:
    evidence = _momentum_native_evidence()

    with pytest.raises(ValueError, match="failure_reason_code is set if and only if"):
        ExecutionCapture(native_evidence=evidence, profile=None, outcome=RunOutcome.FAILED)
    with pytest.raises(ValueError, match="failure_reason_code is set if and only if"):
        ExecutionCapture(
            native_evidence=evidence, profile=None, outcome=RunOutcome.COMPLETED, failure_reason_code="provider_error"
        )


@pytest.mark.parametrize("kind", _KINDS)
def test_execute_stores_the_code_of_the_capture_and_never_execution_failed(kind: ProviderFailureKind) -> None:
    sink = _ExecutionSink()
    code = PROVIDER_CODE_BY_KIND[kind].value

    run = execute(
        _momentum_request(),
        spec=run_spec_for(_momentum_request().selection),
        capture=lambda: ExecutionCapture(
            native_evidence=_momentum_native_evidence(),
            profile=None,
            outcome=RunOutcome.FAILED,
            failure_reason_code=code,
        ),
        repository=sink,
    )

    assert run.failure_reason_code == code
    assert run.failure_reason_code != "execution_failed"
    assert FailureReasonCode(run.failure_reason_code)


# --- the refresh invariant -----------------------------------------------------------------------------------------

_OUTCOMES = [
    (RunOutcome.COMPLETED, None),
    (RunOutcome.UNAVAILABLE, None),
    (RunOutcome.NOT_APPLICABLE, None),
    (RunOutcome.FAILED, "provider_unreachable"),
]


def _refresh(outcome: RunOutcome, code: str | None, *, save: bool, raises: bool = False) -> RefreshJobResult:
    selection = MomentumSelection(short_window=2, long_window=3)

    def executor(ticker: str, _selection: object) -> ExecutionCapture:
        if raises:
            raise RuntimeError("boom")
        capture = _momentum_capture(ticker)
        return ExecutionCapture(
            native_evidence=capture.native_evidence, profile=None, outcome=outcome, failure_reason_code=code
        )

    summary = refresh_watchlist(
        "My Watch",
        watchlists=_FakeWatchlists({"my watch": _watchlist(("KO",), (selection,))}),
        repository=_FakeSink(),
        executor=executor,
        run_specs=RUN_SPECS_BY_KEY,
        classify=failure_code,
        save=save,
    )
    return summary.results[0]


@pytest.mark.parametrize("save", [True, False])
@pytest.mark.parametrize(("outcome", "code"), _OUTCOMES)
def test_a_job_carries_a_code_if_and_only_if_it_failed(outcome: RunOutcome, code: str | None, save: bool) -> None:
    result = _refresh(outcome, code, save=save)

    assert result.reason_code == code
    assert (result.run is not None) is save
    status = result.run.status if result.run is not None else result.outcome
    assert status is outcome
    assert (result.reason_code is not None) is (outcome is RunOutcome.FAILED)


@pytest.mark.parametrize("save", [True, False])
def test_a_failed_job_copies_the_code_a_saved_run_stores(save: bool) -> None:
    result = _refresh(RunOutcome.FAILED, "provider_no_data", save=save)

    assert result.reason_code == "provider_no_data"
    if result.run is not None:
        assert result.run.failure_reason_code == result.reason_code


@pytest.mark.parametrize("save", [True, False])
def test_a_job_that_raised_carries_the_classifier_code(save: bool) -> None:
    result = _refresh(RunOutcome.COMPLETED, None, save=save, raises=True)

    assert result.error == "boom"
    assert result.reason_code == "execution_error"
    assert result.run is None
    assert result.outcome is None


@pytest.mark.parametrize("save", [True, False])
def test_the_saved_run_and_the_unsaved_job_report_the_same_code(save: bool) -> None:
    analysis = _number(CalculationStatus.PROVIDER_ERROR, _record(ProviderFailureKind.UNEXPECTED_RESPONSE, "bvps"))
    capture = _number_capture(analysis)
    selection = MomentumSelection(short_window=2, long_window=3)
    capture = replace(capture, native_evidence=_momentum_native_evidence())

    summary = refresh_watchlist(
        "My Watch",
        watchlists=_FakeWatchlists({"my watch": _watchlist(("KO",), (selection,))}),
        repository=_FakeSink(),
        executor=lambda _ticker, _selection: capture,
        run_specs=RUN_SPECS_BY_KEY,
        classify=failure_code,
        save=save,
    )

    assert summary.results[0].reason_code == "provider_unexpected_response"
    assert summary.counts == {"failed": 1}


def test_a_job_result_requires_a_code_for_a_failed_run_and_none_for_an_unavailable_one() -> None:
    failed = _build_run(status=RunOutcome.FAILED, failure_reason_code="provider_unreachable")
    unavailable = _build_run(status=RunOutcome.UNAVAILABLE)

    assert RefreshJobResult("KO", "sma_crossover", run=failed, reason_code="provider_unreachable").reason_code
    with pytest.raises(ValueError, match="reason_code is set if and only if"):
        RefreshJobResult("KO", "sma_crossover", run=failed)
    with pytest.raises(ValueError, match="reason_code is set if and only if"):
        RefreshJobResult("KO", "sma_crossover", run=unavailable, reason_code="provider_unreachable")
    with pytest.raises(ValueError, match="reason_code is set if and only if"):
        RefreshJobResult("KO", "sma_crossover", outcome=RunOutcome.FAILED)
    with pytest.raises(ValueError, match="reason_code is set if and only if"):
        RefreshJobResult("KO", "sma_crossover", outcome=RunOutcome.UNAVAILABLE, reason_code="provider_error")
    with pytest.raises(ValueError, match="reason_code is set if and only if"):
        RefreshJobResult("KO", "sma_crossover", error="boom")
