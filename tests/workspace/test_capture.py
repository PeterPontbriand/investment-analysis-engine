"""The normalized capture derives its outcome, its failure code and the provider failure it keeps."""

import pytest

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.failure_classification import provider_failure_of
from investment_analysis_engine.core.failure_codes import PROVIDER_CODE_BY_KIND
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind, ProviderFailureRecord
from investment_analysis_engine.workspace.capture import ExecutionCapture
from tests.workspace.test_execution import _momentum_native_evidence

_FAILURE = provider_failure_of((ProviderFailureRecord(ProviderFailureKind.UNREACHABLE, "yfinance"),))


def _capture(status: CalculationStatus | None, *, recorded: bool) -> ExecutionCapture:
    return ExecutionCapture(
        native_evidence=_momentum_native_evidence(),
        profile=None,
        native_status=status,
        provider_failure=_FAILURE if recorded else None,
    )


@pytest.mark.parametrize(
    ("status", "outcome"),
    [
        (CalculationStatus.OK, RunOutcome.COMPLETED),
        (CalculationStatus.NOT_APPLICABLE, RunOutcome.NOT_APPLICABLE),
        (CalculationStatus.INPUT_UNAVAILABLE, RunOutcome.UNAVAILABLE),
        (CalculationStatus.INVALID_INPUT, RunOutcome.FAILED),
        (CalculationStatus.PROVIDER_ERROR, RunOutcome.FAILED),
        (None, RunOutcome.COMPLETED),
    ],
)
def test_execution_capture_derives_outcome_code_and_provider_failure(
    status: CalculationStatus | None, outcome: RunOutcome
) -> None:
    capture = _capture(status, recorded=True)

    assert capture.outcome is outcome
    if outcome is not RunOutcome.FAILED:
        assert capture.failure_reason_code is None
        assert capture.provider_failure is None
    elif status is CalculationStatus.INVALID_INPUT:
        assert capture.failure_reason_code == "invalid_input"
        assert capture.provider_failure is _FAILURE
    else:
        assert capture.failure_reason_code == PROVIDER_CODE_BY_KIND[ProviderFailureKind.UNREACHABLE].value
        assert capture.provider_failure is _FAILURE


def test_a_failed_capture_without_a_recorded_provider_failure_has_the_generic_provider_code() -> None:
    capture = _capture(CalculationStatus.PROVIDER_ERROR, recorded=False)

    assert capture.failure_reason_code == "provider_error"
    assert capture.provider_failure is None
