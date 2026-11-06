"""Shared CLI parsing and exception boundaries preserve public exit semantics."""

import json
from datetime import UTC, date, datetime
from unittest.mock import patch

import pytest
import typer

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.application.analysis import exit_code_of
from investment_analysis_engine.application.failures import provider_failure_message
from investment_analysis_engine.cli_support import (
    execution_errors,
    parameter_failures,
    parse_as_of_option,
    presentation_mode,
    resolve_ticker,
    selection_from_options,
)
from investment_analysis_engine.core.operator_errors import InvalidParameterError
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.data.financial.facts import FinancialProviderError
from investment_analysis_engine.reporting.presentation import PresentationMode
from investment_analysis_engine.strategies.graham_number import cli as graham_number_cli
from investment_analysis_engine.strategies.graham_number.selection import GrahamNumberSelection
from investment_analysis_engine.strategy_wiring import GRAHAM_NUMBER


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


def test_the_as_of_option_parses_by_syntax_only() -> None:
    """The option returns a date or a timestamp as written; the end-of-day and offset rules are the builder's."""
    assert parse_as_of_option(None) is None
    assert parse_as_of_option(" 2025-12-31 ") == date(2025, 12, 31)
    assert parse_as_of_option("2025-12-31T12:00:00Z") == datetime(2025, 12, 31, 12, tzinfo=UTC)
    assert parse_as_of_option("2025-12-31T12:00:00") == datetime(2025, 12, 31, 12)  # noqa: DTZ001 - a naive value parses


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("", "--as-of must be non-empty when supplied."),
        ("  ", "--as-of must be non-empty when supplied."),
        ("bad", "--as-of must be YYYY-MM-DD or a valid timezone-aware ISO-8601 timestamp."),
        ("2025-02-30", "--as-of must be YYYY-MM-DD or a valid timezone-aware ISO-8601 timestamp."),
    ],
)
def test_invalid_boundaries_are_invalid_parameters_named_by_the_option(value: str, message: str) -> None:
    with pytest.raises(InvalidParameterError) as caught:
        parse_as_of_option(value)
    assert (str(caught.value), caught.value.parameters) == (message, ("--as-of",))


def test_ticker_provider_and_presentation_normalization() -> None:
    assert resolve_ticker(" ko ", "KO", command="graham-number") == "KO"
    with pytest.raises(InvalidParameterError, match="graham-growth TICKER") as missing:
        resolve_ticker(None, None, command="graham-growth")
    assert missing.value.parameters == ("TICKER",)
    with pytest.raises(InvalidParameterError, match="momentum TICKER") as missing_momentum:
        resolve_ticker(None, None, command="momentum")
    assert missing_momentum.value.parameters == ("TICKER",)
    with pytest.raises(InvalidParameterError) as blank:
        resolve_ticker(" ", None, command="momentum")
    assert (str(blank.value), blank.value.parameters) == ("TICKER must be a non-empty symbol.", ("TICKER",))
    with pytest.raises(InvalidParameterError) as blank_option:
        resolve_ticker(None, " ", command="momentum")
    assert blank_option.value.parameters == ("--ticker",)
    assert presentation_mode(details=False, diagnostics=False, json_output=True) is PresentationMode.JSON
    with pytest.raises(InvalidParameterError) as exclusive:
        presentation_mode(details=True, diagnostics=True, json_output=False)
    assert exclusive.value.parameters == ("--details", "--diagnostics")


_KIND_MESSAGES = [
    (ProviderFailureKind.UNREACHABLE, "Unable to analyze AAPL: sec_edgar did not serve the request."),
    (ProviderFailureKind.RATE_LIMITED, "Unable to analyze AAPL: sec_edgar is limiting requests."),
    (
        ProviderFailureKind.UNEXPECTED_RESPONSE,
        "Unable to analyze AAPL: sec_edgar answered in a form the application does not read.",
    ),
    (ProviderFailureKind.NO_DATA, "Unable to analyze AAPL: sec_edgar returned no data for it."),
]


@pytest.mark.parametrize("exception_type", [DataFetchError, FinancialProviderError])
@pytest.mark.parametrize(("kind", "message"), _KIND_MESSAGES)
def test_the_message_table_names_the_provider_and_ticker_per_kind(
    exception_type: type[DataFetchError] | type[FinancialProviderError], kind: ProviderFailureKind, message: str
) -> None:
    assert provider_failure_message(exception_type("private", kind=kind, provider_id="sec_edgar"), "AAPL") == message


def test_the_message_table_has_one_row_per_kind_and_one_for_an_unclassified_failure() -> None:
    messages = {
        provider_failure_message(DataFetchError("x", kind=kind, provider_id="p"), "T") for kind in ProviderFailureKind
    }
    assert len(messages) == len(ProviderFailureKind)
    assert provider_failure_message(DataFetchError("private detail"), None) == (
        "Unable to analyze the requested instrument: a data provider failed; the failure was not classified."
    )


@pytest.mark.parametrize("exception_type", [DataFetchError, FinancialProviderError])
@pytest.mark.parametrize(("kind", "message"), _KIND_MESSAGES)
def test_a_raised_provider_failure_is_reported_under_its_code_with_its_element(
    exception_type: type[DataFetchError] | type[FinancialProviderError], kind: ProviderFailureKind, message: str
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
    assert document["reason"] == message
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


def test_a_selection_error_is_spelled_with_the_options_of_the_command() -> None:
    values = {"as_of": None, "no_cache": False, "eps": float("inf"), "bvps": None, "current_price": None}
    with pytest.raises(InvalidParameterError) as caught:
        selection_from_options(GRAHAM_NUMBER.method_id, graham_number_cli.SELECTION_OPTIONS, values)
    assert str(caught.value) == "Invalid --eps: Financial override must be a finite number."
    assert caught.value.parameters == ("--eps",)


def test_an_option_left_out_leaves_its_field_to_the_default() -> None:
    values = {"as_of": None, "no_cache": True, "eps": None, "bvps": None, "current_price": None}
    built = selection_from_options(GRAHAM_NUMBER.method_id, graham_number_cli.SELECTION_OPTIONS, values)
    assert isinstance(built, GrahamNumberSelection)
    assert (built.eps_override, built.use_cache) == (None, False)


@pytest.mark.parametrize(
    ("outcome", "code"),
    [
        (RunOutcome.COMPLETED, 0),
        (RunOutcome.NOT_APPLICABLE, 0),
        (RunOutcome.UNAVAILABLE, 1),
        (RunOutcome.FAILED, 1),
    ],
)
def test_exit_code_of_is_one_exactly_for_unavailable_and_failed(outcome: RunOutcome, code: int) -> None:
    assert exit_code_of(outcome) == code


def test_every_run_outcome_has_an_exit_code_row() -> None:
    assert len(RunOutcome) == 4, "A new outcome needs a row in the table above."
