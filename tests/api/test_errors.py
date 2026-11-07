"""Every failure is a failure envelope with the status of its code; an unexpected exception is one fixed answer."""

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from investment_analysis_engine.api.handlers import UNEXPECTED_FAILURE_MESSAGE
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.core.failure_codes import PROVIDER_CODE_BY_KIND, FailureReasonCode
from investment_analysis_engine.core.operator_errors import InvalidParameterError
from tests.api._support import AUTH, TOKEN, client_for
from tests.application._unready_database import unready_database_url

# The status table, written out as literals so a change to the mapping fails a test.
_STATUS = {
    "invalid_parameter": 400,
    "host_not_allowed": 400,
    "origin_not_allowed": 400,
    "not_authenticated": 401,
    "analysis_run_not_found": 404,
    "watchlist_not_found": 404,
    "watchlist_entry_not_found": 404,
    "watchlist_name_conflict": 409,
    "stored_selection_unreadable": 409,
    "endpoint_not_found": 404,
    "database_busy": 503,
}
_PROVIDER_KIND = {code: kind for kind, code in PROVIDER_CODE_BY_KIND.items()}


class _CodedError(Exception):
    """An exception that declares a failure code, as the application's typed errors do."""

    def __init__(self, code: FailureReasonCode) -> None:
        super().__init__(f"message for {code.value}")
        self.reason_code = code
        kind = _PROVIDER_KIND.get(code)
        if kind is not None:
            self.kind = kind
            self.provider_id = "provider"


class _WithoutProviderFactsError(Exception):
    """Declares a provider failure code but carries no provider, so the envelope cannot be built."""

    reason_code = FailureReasonCode.PROVIDER_UNREACHABLE


def _raised(code: FailureReasonCode) -> Exception:
    return (
        InvalidParameterError("bad value", parameters=("limit",))
        if code is FailureReasonCode.INVALID_PARAMETER
        else _CodedError(code)
    )


@pytest.mark.parametrize("code", list(FailureReasonCode), ids=lambda code: code.value)
def test_each_reason_code_reaches_the_status_of_the_table_and_is_a_failure_envelope(
    code: FailureReasonCode, isolated_cli_settings: ProjectSettings
) -> None:
    with (
        client_for(isolated_cli_settings) as client,
        patch("investment_analysis_engine.api.handlers.list_watchlists", side_effect=_raised(code)),
    ):
        response = client.get("/v1/watchlists", headers=AUTH)

    assert response.status_code == _STATUS.get(code.value, 500)
    body = response.json()
    assert body["schema_version"] == 12
    assert body["reason_code"] == code.value
    assert body["result"] is None
    assert body["status"] in ("error", "input_unavailable")
    assert response.headers["content-type"] == "application/json"


def test_an_unexpected_exception_is_the_fixed_execution_error_with_its_traceback_logged_and_no_token(
    isolated_cli_settings: ProjectSettings, caplog: pytest.LogCaptureFixture
) -> None:
    error = RuntimeError("library detail that must stay out of the response")
    with (
        client_for(isolated_cli_settings) as client,
        patch("investment_analysis_engine.api.handlers.list_watchlists", side_effect=error),
        caplog.at_level(logging.DEBUG),
    ):
        response = client.get("/v1/watchlists", headers=AUTH)

    assert response.status_code == 500
    assert response.json()["reason_code"] == "execution_error"
    assert response.json()["reason"] == UNEXPECTED_FAILURE_MESSAGE
    assert "library detail" not in response.text
    assert any(record.exc_info and record.exc_info[1] is error for record in caplog.records)
    assert TOKEN not in caplog.text


def test_a_declared_code_whose_envelope_cannot_be_built_is_the_fixed_execution_error(
    isolated_cli_settings: ProjectSettings, caplog: pytest.LogCaptureFixture
) -> None:
    # A provider code with no provider facts cannot be described by the envelope.
    error = _WithoutProviderFactsError("no provider facts")
    with (
        client_for(isolated_cli_settings) as client,
        patch("investment_analysis_engine.api.handlers.list_watchlists", side_effect=error),
        caplog.at_level(logging.ERROR),
    ):
        response = client.get("/v1/watchlists", headers=AUTH)

    assert response.status_code == 500
    assert (response.json()["reason_code"], response.json()["reason"]) == (
        "execution_error",
        UNEXPECTED_FAILURE_MESSAGE,
    )
    assert any(record.exc_info is not None for record in caplog.records)


def test_a_database_that_is_not_ready_is_a_database_failure_naming_the_target(tmp_path: Path) -> None:
    settings = ProjectSettings(database_url=unready_database_url(tmp_path))
    with client_for(settings) as client:
        response = client.get("/v1/watchlists", headers=AUTH)

    assert response.status_code == 500
    assert response.json()["reason_code"].startswith("database_")
    assert response.json()["database"]["database_path"].endswith("not-a-database.sqlite3")
