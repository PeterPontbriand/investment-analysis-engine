"""Shared CLI parsing and exception boundaries preserve public exit semantics."""

import json
from datetime import UTC, datetime, time
from unittest.mock import patch

import pytest
import typer
from pydantic import BaseModel, field_validator

from investment_analysis_engine.cli_support import (
    _canonical_provider_id,
    _parse_as_of,
    _presentation_mode,
    _resolve_ticker,
    config_usage_errors,
    execution_errors,
    parameter_failures,
    provider_failure_sentence,
)
from investment_analysis_engine.core.operator_errors import InvalidParameterError
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.data.financial.facts import FinancialProviderError
from investment_analysis_engine.reporting.presentation import PresentationMode


@pytest.mark.parametrize("error", [typer.Exit(2), typer.Exit(0)])
def test_intentional_cli_exits_propagate_without_output(error: Exception) -> None:
    with (
        patch("investment_analysis_engine.cli_support.typer.echo") as echo,
        pytest.raises(type(error)) as caught,
        execution_errors(),
    ):
        raise error
    assert caught.value is error
    echo.assert_not_called()


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (
            DataFetchError("private"),
            "Unable to analyze the requested instrument: a data provider failed; the failure was not classified.",
        ),
        (
            FinancialProviderError("private"),
            "Unable to analyze the requested instrument: a data provider failed; the failure was not classified.",
        ),
        (
            ValueError("private"),
            "Unable to analyze the requested instrument: invalid analysis inputs or provider data.",
        ),
        (RuntimeError("private"), "Unable to analyze the requested instrument: the analysis failed unexpectedly."),
    ],
)
def test_execution_errors_classify_without_exposing_exception(error: Exception, message: str) -> None:
    with (
        patch("investment_analysis_engine.cli_support.typer.echo") as echo,
        pytest.raises(typer.Exit) as caught,
        execution_errors(),
    ):
        raise error
    assert caught.value.exit_code == 1
    assert caught.value.__cause__ is error
    echo.assert_called_once_with(message, err=True)


def test_date_and_timestamp_boundaries_retain_timezone_semantics() -> None:
    assert _parse_as_of(None) is None
    assert _parse_as_of(" 2025-12-31 ") == datetime(2025, 12, 31, tzinfo=UTC).replace(
        hour=time.max.hour, minute=time.max.minute, second=time.max.second, microsecond=time.max.microsecond
    )
    assert _parse_as_of("2025-12-31T12:00:00Z") == datetime(2025, 12, 31, 12, tzinfo=UTC)
    assert _parse_as_of("2025-12-31T07:00:00-05:00") == datetime(2025, 12, 31, 12, tzinfo=UTC)


@pytest.mark.parametrize("value", ["", "bad", "2025-02-30", "2025-12-31T12:00:00"])
def test_invalid_boundaries_are_invalid_parameters(value: str) -> None:
    with pytest.raises(InvalidParameterError) as caught:
        _parse_as_of(value)
    assert caught.value.parameters == ("--as-of",)


def test_ticker_provider_and_presentation_normalization() -> None:
    assert _resolve_ticker(" ko ", "KO", required=True, command="graham-number") == "KO"
    assert _resolve_ticker(None, None, required=False, command="momentum") is None
    with pytest.raises(InvalidParameterError, match="graham-growth TICKER") as missing:
        _resolve_ticker(None, None, required=True, command="graham-growth")
    assert missing.value.parameters == ("TICKER",)
    with pytest.raises(InvalidParameterError) as blank:
        _resolve_ticker(" ", None, required=False, command="momentum")
    assert (str(blank.value), blank.value.parameters) == ("TICKER must be a non-empty symbol.", ("TICKER",))
    with pytest.raises(InvalidParameterError) as blank_option:
        _resolve_ticker(None, " ", required=False, command="momentum")
    assert blank_option.value.parameters == ("--ticker",)
    assert _canonical_provider_id(" SEC_EDGAR ") == "sec_edgar"
    assert _canonical_provider_id(None) is None
    with pytest.raises(InvalidParameterError):
        _canonical_provider_id(" ")
    assert _presentation_mode(details=False, diagnostics=False, json_output=True) is PresentationMode.JSON
    with pytest.raises(InvalidParameterError) as exclusive:
        _presentation_mode(details=True, diagnostics=True, json_output=False)
    assert exclusive.value.parameters == ("--details", "--diagnostics")


_KIND_SENTENCES = [
    (ProviderFailureKind.UNREACHABLE, "Unable to analyze AAPL: sec_edgar did not serve the request."),
    (ProviderFailureKind.RATE_LIMITED, "Unable to analyze AAPL: sec_edgar is limiting requests."),
    (
        ProviderFailureKind.UNEXPECTED_RESPONSE,
        "Unable to analyze AAPL: sec_edgar answered in a form the application does not read.",
    ),
    (ProviderFailureKind.NO_DATA, "Unable to analyze AAPL: sec_edgar returned no data for it."),
]


@pytest.mark.parametrize("exception_type", [DataFetchError, FinancialProviderError])
@pytest.mark.parametrize(("kind", "sentence"), _KIND_SENTENCES)
def test_the_sentence_table_names_the_provider_and_ticker_per_kind(
    exception_type: type[DataFetchError] | type[FinancialProviderError], kind: ProviderFailureKind, sentence: str
) -> None:
    assert provider_failure_sentence(exception_type("private", kind=kind, provider_id="sec_edgar"), "AAPL") == sentence


def test_the_sentence_table_has_one_row_per_kind_and_one_for_an_unclassified_failure() -> None:
    sentences = {
        provider_failure_sentence(DataFetchError("x", kind=kind, provider_id="p"), "T") for kind in ProviderFailureKind
    }
    assert len(sentences) == len(ProviderFailureKind)
    assert provider_failure_sentence(DataFetchError("private detail"), None) == (
        "Unable to analyze the requested instrument: a data provider failed; the failure was not classified."
    )


@pytest.mark.parametrize("exception_type", [DataFetchError, FinancialProviderError])
@pytest.mark.parametrize(("kind", "sentence"), _KIND_SENTENCES)
def test_a_raised_provider_failure_is_reported_under_its_code_with_its_element(
    exception_type: type[DataFetchError] | type[FinancialProviderError], kind: ProviderFailureKind, sentence: str
) -> None:
    error = exception_type("private detail", kind=kind, provider_id="sec_edgar")
    with (
        patch("investment_analysis_engine.cli_support.typer.echo") as echo,
        pytest.raises(typer.Exit) as caught,
        execution_errors(mode=PresentationMode.JSON, ticker="AAPL"),
    ):
        raise error
    assert caught.value.exit_code == 1
    document = json.loads(echo.call_args.args[0])
    assert document["reason_code"] == f"provider_{kind.value}"
    assert document["status"] == "input_unavailable"
    assert document["reason"] == sentence
    assert document["provider_failure"] == {
        "reason_code": document["reason_code"],
        "inputs": [{"input": None, "provider_id": "sec_edgar", "kind": kind.value}],
    }
    assert "private detail" not in echo.call_args.args[0]


def test_a_raised_provider_failure_is_reported_as_one_without_a_ticker() -> None:
    """Before, a command that passed no ``data_error`` reported a provider failure as invalid input."""
    error = FinancialProviderError("private", kind=ProviderFailureKind.UNREACHABLE, provider_id="sec_edgar")
    with (
        patch("investment_analysis_engine.cli_support.typer.echo") as echo,
        pytest.raises(typer.Exit),
        execution_errors(mode=PresentationMode.JSON),
    ):
        raise error
    assert json.loads(echo.call_args.args[0])["reason_code"] == "provider_unreachable"


def test_a_parameter_failure_before_the_mode_is_known_writes_the_envelope_when_json_was_given() -> None:
    with (
        patch("investment_analysis_engine.cli_support.typer.echo") as echo,
        pytest.raises(typer.Exit) as caught,
        execution_errors(json_output=True),
    ):
        raise InvalidParameterError("--a is wrong.", parameters=("--a",))
    assert caught.value.exit_code == 1
    document = json.loads(echo.call_args.args[0])
    assert (document["reason_code"], document["parameters"], document["ticker"]) == ("invalid_parameter", ["--a"], None)


def test_the_scope_carries_what_the_command_resolved_before_the_failure() -> None:
    def run() -> None:
        with execution_errors(json_output=True) as scope:
            scope.ticker = "KO"
            scope.mode = PresentationMode.JSON
            raise InvalidParameterError("--a is wrong.", parameters=("--a",))

    with patch("investment_analysis_engine.cli_support.typer.echo") as echo, pytest.raises(typer.Exit):
        run()
    assert json.loads(echo.call_args.args[0])["ticker"] == "KO"


def test_a_parameter_failure_in_text_goes_to_standard_error() -> None:
    with (
        patch("investment_analysis_engine.cli_support.typer.echo") as echo,
        pytest.raises(typer.Exit) as caught,
        execution_errors(),
    ):
        raise InvalidParameterError("--a is wrong.", parameters=("--a",))
    assert caught.value.exit_code == 1
    echo.assert_called_once_with("--a is wrong.", err=True)


@pytest.mark.parametrize("json_output", [False, True])
def test_parameter_failures_reports_only_an_invalid_parameter(json_output: bool) -> None:
    with (
        patch("investment_analysis_engine.cli_support.typer.echo") as echo,
        pytest.raises(typer.Exit) as caught,
        parameter_failures(json_output=json_output),
    ):
        raise InvalidParameterError("--a is wrong.", parameters=("--a",))
    assert caught.value.exit_code == 1
    written = echo.call_args.args[0]
    assert (json.loads(written)["parameters"] == ["--a"]) if json_output else (written == "--a is wrong.")
    with pytest.raises(RuntimeError), parameter_failures(json_output=json_output):
        raise RuntimeError("not a parameter")


def test_config_usage_errors_fails_loudly_for_a_field_it_does_not_map() -> None:
    class Model(BaseModel):
        mystery: int

    with pytest.raises(KeyError), config_usage_errors():
        Model.model_validate({"mystery": "x"})


def test_config_usage_errors_names_the_option_and_strips_the_library_prefix() -> None:
    class Model(BaseModel):
        eps_override: float

        @field_validator("eps_override")
        @classmethod
        def _positive(cls, value: float) -> float:
            del value
            raise ValueError("Financial override must be a finite number.")

    with pytest.raises(InvalidParameterError) as caught, config_usage_errors():
        Model.model_validate({"eps_override": 1.0})
    assert str(caught.value) == "Invalid --eps: Financial override must be a finite number."
    assert caught.value.parameters == ("--eps",)
