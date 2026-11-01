"""The steps every direct command repeats: target resolution, rendering with the provider check, exit and save."""

from datetime import UTC, datetime

import pytest
import typer

from investment_analysis_engine.cli_provider_check import ProviderCheckChoice
from investment_analysis_engine.cli_run_support import analyze_and_maybe_save
from investment_analysis_engine.cli_support import (
    FailureScope,
    emit_output,
    render_execution,
    resolve_command_target,
)
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.failure_classification import provider_failure_of
from investment_analysis_engine.core.operator_errors import InvalidParameterError
from investment_analysis_engine.core.provider_check_element import ProviderCheckItem
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind, ProviderFailureRecord
from investment_analysis_engine.data.provider_probe import ProbeFinding, ProbeVerdict
from investment_analysis_engine.reporting.presentation import PresentationMode
from investment_analysis_engine.workspace.capture import ExecutionCapture
from investment_analysis_engine.workspace.requests import AnalysisRequest
from tests.workspace.test_execution import _momentum_native_evidence

_FAILURE = provider_failure_of((ProviderFailureRecord(ProviderFailureKind.UNREACHABLE, "yfinance"),))


class _Probe:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def check(self, provider_id: str, *, requested: bool = True) -> ProbeFinding:
        self.calls.append((provider_id, requested))
        return ProbeFinding(provider_id, ProbeVerdict.UNREACHABLE)


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


def test_a_completed_run_is_rendered_without_a_provider_check() -> None:
    probe = _Probe()
    seen: list[tuple[ProviderCheckItem, ...] | None] = []

    def render(element: tuple[ProviderCheckItem, ...] | None) -> str:
        seen.append(element)
        return "result"

    output, exit_code = render_execution(
        _execution(CalculationStatus.OK),
        ProviderCheckChoice(probe=probe, requested=True),
        PresentationMode.CONCISE,
        render,
    )

    assert (output, exit_code) == ("result", 0)
    assert seen == [None]
    assert probe.calls == []


def test_a_failed_run_runs_the_provider_check_once_and_precedes_the_text_with_its_lines() -> None:
    probe = _Probe()
    seen: list[tuple[ProviderCheckItem, ...] | None] = []

    def render(element: tuple[ProviderCheckItem, ...] | None) -> str:
        seen.append(element)
        return "result"

    output, exit_code = render_execution(
        _execution(CalculationStatus.PROVIDER_ERROR),
        ProviderCheckChoice(probe=probe, requested=False),
        PresentationMode.CONCISE,
        render,
    )

    assert exit_code == 1
    assert probe.calls == [("yfinance", False)]
    assert output.splitlines()[-1] == "result"
    assert len(output.splitlines()) == 2
    assert seen[0] is not None
    assert seen[0][0].provider_id == "yfinance"


def test_a_failed_run_in_json_mode_carries_the_findings_in_the_document_only() -> None:
    output, exit_code = render_execution(
        _execution(CalculationStatus.PROVIDER_ERROR),
        ProviderCheckChoice(probe=_Probe(), requested=True),
        PresentationMode.JSON,
        lambda element: "{}" if element is None else "{provider_check}",
    )

    assert (output, exit_code) == ("{provider_check}", 1)


def test_a_run_without_a_probe_renders_with_no_element_and_no_extra_lines() -> None:
    output, exit_code = render_execution(
        _execution(CalculationStatus.PROVIDER_ERROR), None, PresentationMode.CONCISE, str
    )

    assert (output, exit_code) == ("None", 1)


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


def test_without_save_run_the_adapter_runs_once_without_a_profile_cache_and_no_request_is_built() -> None:
    adapter_arguments: list[object] = []

    def build_request() -> AnalysisRequest:
        raise AssertionError("the request is built only when the run is saved")

    def adapter(profile_cache: object) -> str:
        adapter_arguments.append(profile_cache)
        return "raw"

    result = analyze_and_maybe_save(
        save_run=False,
        executed_at=datetime(2026, 11, 1, tzinfo=UTC),
        request_factory=build_request,
        run_adapter=adapter,
        normalize=lambda _raw: _execution(CalculationStatus.OK),
    )

    assert result == "raw"
    assert adapter_arguments == [None]


def _no_request() -> AnalysisRequest:
    raise AssertionError("no request is built when nothing is saved")


def test_an_analysis_failure_propagates_unchanged_when_nothing_is_saved() -> None:
    error = ValueError("analysis failed")

    def adapter(_profile_cache: object) -> str:
        raise error

    with pytest.raises(ValueError, match="analysis failed") as raised:
        analyze_and_maybe_save(
            save_run=False,
            executed_at=datetime(2026, 11, 1, tzinfo=UTC),
            request_factory=_no_request,
            run_adapter=adapter,
            normalize=lambda _raw: _execution(CalculationStatus.OK),
        )

    assert raised.value is error
