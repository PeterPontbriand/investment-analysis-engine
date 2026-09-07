"""Shared CLI parsing and exception boundaries preserve public exit semantics."""

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
)
from src.data.base_client import DataFetchError
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
    [(DataFetchError("private"), "data"), (ValueError("private"), "invalid"), (RuntimeError("private"), "unexpected")],
)
def test_execution_errors_classify_without_exposing_exception(error: Exception, message: str) -> None:
    with (
        patch("src.cli_support.typer.echo") as echo,
        pytest.raises(typer.Exit) as caught,
        execution_errors(
            data_error=lambda _exc: "data",
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
