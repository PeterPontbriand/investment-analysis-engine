"""The steps every direct command repeats: target resolution, writing the outcome and exiting."""

import json

import pytest
import typer
from pydantic import BaseModel

from investment_analysis_engine.application.analysis import AnalysisOutcome
from investment_analysis_engine.cli_support import FailureScope, analysis_output, emit_output, resolve_command_target
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.failure_classification import provider_failure_of
from investment_analysis_engine.core.operator_errors import InvalidParameterError
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind, ProviderFailureRecord
from investment_analysis_engine.reporting.presentation import PresentationMode
from investment_analysis_engine.workspace.capture import ExecutionCapture
from tests.workspace.test_execution import _momentum_native_evidence

_FAILURE = provider_failure_of((ProviderFailureRecord(ProviderFailureKind.UNREACHABLE, "yfinance"),))


def _execution(status: CalculationStatus) -> ExecutionCapture:
    return ExecutionCapture(
        native_evidence=_momentum_native_evidence(), profile=None, native_status=status, provider_failure=_FAILURE
    )


def _scope() -> FailureScope:
    return FailureScope(ticker=None, mode=None)


def test_the_target_is_the_normalized_ticker_and_the_resolved_mode_recorded_on_the_scope() -> None:
    scope = _scope()

    ticker, mode = resolve_command_target(
        scope, " ko ", None, command="demo", details=True, diagnostics=False, json_output=False
    )

    assert (ticker, mode) == ("KO", PresentationMode.DETAILS)
    assert (scope.ticker, scope.mode) == ("KO", PresentationMode.DETAILS)


def test_the_legacy_ticker_option_is_read_when_there_is_no_positional_ticker() -> None:
    ticker, _mode = resolve_command_target(
        _scope(), None, "ko", command="demo", details=False, diagnostics=False, json_output=True
    )

    assert ticker == "KO"


def test_a_rejected_output_flag_is_reported_with_the_ticker_already_recorded() -> None:
    scope = _scope()

    with pytest.raises(InvalidParameterError, match="Choose only one"):
        resolve_command_target(scope, "KO", None, command="demo", details=True, diagnostics=True, json_output=False)

    assert (scope.ticker, scope.mode) == ("KO", None)


def test_a_missing_ticker_names_the_command_and_records_nothing() -> None:
    scope = _scope()

    with pytest.raises(InvalidParameterError, match="Use 'ian demo TICKER'"):
        resolve_command_target(scope, None, None, command="demo", details=False, diagnostics=False, json_output=False)

    assert (scope.ticker, scope.mode) == (None, None)


def _outcome(status: CalculationStatus, *, mode_text: str = "result") -> AnalysisOutcome:
    """Return an outcome whose document is a stand-in model and whose text is ``mode_text`` in every text mode."""
    execution = _execution(status)
    return AnalysisOutcome(
        document=_Document(),
        analysis_run_id=None,
        outcome=execution.outcome,
        text_renderer=lambda _mode: mode_text,
    )


class _Document(BaseModel):
    """A stand-in for a strategy document."""

    value: int = 1


def test_a_completed_outcome_is_written_as_its_text_with_exit_code_zero() -> None:
    output, exit_code = analysis_output(_outcome(CalculationStatus.OK), PresentationMode.CONCISE)

    assert (output, exit_code) == ("result", 0)


def test_a_failed_outcome_has_exit_code_one_and_its_own_text() -> None:
    output, exit_code = analysis_output(_outcome(CalculationStatus.PROVIDER_ERROR), PresentationMode.DETAILS)

    assert (output, exit_code) == ("result", 1)


def test_the_json_mode_writes_the_serialized_document_not_the_text() -> None:
    output, exit_code = analysis_output(_outcome(CalculationStatus.PROVIDER_ERROR), PresentationMode.JSON)

    assert json.loads(output) == {"value": 1}
    assert exit_code == 1


@pytest.mark.parametrize(
    ("mode", "stream"),
    [
        (PresentationMode.CONCISE, "err"),
        (PresentationMode.DETAILS, "err"),
        (PresentationMode.DIAGNOSTICS, "out"),
        (PresentationMode.JSON, "out"),
    ],
)
def test_a_failure_is_written_to_standard_error_in_the_concise_and_details_modes_only(
    mode: PresentationMode, stream: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(typer.Exit) as raised:
        emit_output("text", 1, mode)

    captured = capsys.readouterr()
    assert raised.value.exit_code == 1
    assert (captured.err if stream == "err" else captured.out) == "text\n"
    assert (captured.out if stream == "err" else captured.err) == ""


def test_a_success_is_written_to_standard_output_in_every_mode_and_does_not_exit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    emit_output("text", 0, PresentationMode.CONCISE)

    captured = capsys.readouterr()
    assert (captured.out, captured.err) == ("text\n", "")
