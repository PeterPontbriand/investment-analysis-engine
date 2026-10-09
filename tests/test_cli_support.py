"""Shared CLI parsing and exception boundaries preserve public exit semantics."""

import json
from datetime import UTC, datetime, time
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer._click.exceptions import UsageError

from src.cli_support import (
    _canonical_provider_id,
    _parse_as_of,
    _presentation_mode,
    _resolve_ticker,
    execution_errors,
    provider_failure_sentence,
)
from src.core.provider_failure_kind import ProviderFailureKind
from src.data.base_client import DataFetchError
from src.data.financial.facts import FinancialProviderError
from src.reporting.presentation import PresentationMode


@pytest.mark.parametrize("error", [typer.Exit(2), typer.BadParameter("bad option"), UsageError("bad usage")])
def test_intentional_cli_errors_propagate_without_output(error: Exception) -> None:
    callback = MagicMock()
    with (
        patch("src.cli_support.typer.echo") as echo,
        pytest.raises(type(error)) as caught,
        execution_errors(unexpected=callback),
    ):
        raise error
    assert caught.value is error
    callback.assert_not_called()
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
        (ValueError("private"), "invalid"),
        (RuntimeError("private"), "unexpected"),
    ],
)
def test_execution_errors_classify_without_exposing_exception(error: Exception, message: str) -> None:
    with (
        patch("src.cli_support.typer.echo") as echo,
        pytest.raises(typer.Exit) as caught,
        execution_errors(
            invalid=lambda _exc: "invalid",
            unexpected=lambda _exc: "unexpected",
        ),
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
def test_invalid_boundaries_are_usage_errors(value: str) -> None:
    with pytest.raises(typer.BadParameter):
        _parse_as_of(value)


def test_ticker_provider_and_presentation_normalization() -> None:
    assert _resolve_ticker(" ko ", "KO", required=True, command="graham-number") == "KO"
    assert _resolve_ticker(None, None, required=False, command="momentum") is None
    with pytest.raises(typer.BadParameter, match="graham-growth TICKER"):
        _resolve_ticker(None, None, required=True, command="graham-growth")
    assert _canonical_provider_id(" SEC_EDGAR ") == "sec_edgar"
    assert _canonical_provider_id(None) is None
    with pytest.raises(typer.BadParameter):
        _canonical_provider_id(" ")
    assert _presentation_mode(details=False, diagnostics=False, json_output=True) is PresentationMode.JSON
    with pytest.raises(typer.BadParameter):
        _presentation_mode(details=True, diagnostics=True, json_output=False)


_KIND_SENTENCES = [
    (ProviderFailureKind.UNREACHABLE, "Unable to analyze AAPL: sec_edgar did not serve the request."),
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
        patch("src.cli_support.typer.echo") as echo,
        pytest.raises(typer.Exit) as caught,
        execution_errors(mode=PresentationMode.JSON, ticker="AAPL", unexpected=lambda _exc: "unexpected"),
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


def test_a_command_with_no_callbacks_still_reports_a_raised_provider_failure_as_one() -> None:
    """Before, a command that passed no ``data_error`` reported a provider failure as invalid input."""
    error = FinancialProviderError("private", kind=ProviderFailureKind.UNREACHABLE, provider_id="sec_edgar")
    with (
        patch("src.cli_support.typer.echo") as echo,
        pytest.raises(typer.Exit),
        execution_errors(mode=PresentationMode.JSON, unexpected=lambda _exc: "unexpected"),
    ):
        raise error
    assert json.loads(echo.call_args.args[0])["reason_code"] == "provider_unreachable"
