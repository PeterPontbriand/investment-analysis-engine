"""A request body has a size limit, and a number JSON does not define is refused wherever it stands."""

from collections.abc import Iterator

import httpx2
import pytest

from investment_analysis_engine.api.request_bodies import MAX_REQUEST_BODY_BYTES
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.strategy_wiring import MOMENTUM
from tests.api._support import AUTH, client_for

JSON_HEADERS = {**AUTH, "Content-Type": "application/json"}


def _padded(size: int) -> bytes:
    """Return a JSON object of exactly ``size`` bytes."""
    prefix, suffix = b'{"name": "', b'"}'
    return prefix + b"a" * (size - len(prefix) - len(suffix)) + suffix


def _rejected(response: httpx2.Response, expected: str | None = None) -> dict[str, object]:
    assert response.status_code == 400
    failure: dict[str, object] = response.json()
    assert failure["reason_code"] == "invalid_parameter"
    assert failure["parameters"] == ["body"]
    if expected is not None:
        assert failure["reason"] == expected
    return failure


def test_the_limit_is_one_mebibyte() -> None:
    assert MAX_REQUEST_BODY_BYTES == 1_048_576


def test_a_declared_length_over_the_limit_is_refused(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        response = client.post(
            "/v1/watchlists", content=b"{}", headers={**JSON_HEADERS, "Content-Length": str(MAX_REQUEST_BODY_BYTES + 1)}
        )

    _rejected(response, f"The request body must not be larger than {MAX_REQUEST_BODY_BYTES} bytes.")


def test_a_body_over_the_limit_is_refused_when_it_declares_no_length(isolated_cli_settings: ProjectSettings) -> None:
    def chunks() -> Iterator[bytes]:
        yield _padded(MAX_REQUEST_BODY_BYTES + 1)

    with client_for(isolated_cli_settings) as client:
        response = client.post("/v1/watchlists", content=chunks(), headers=JSON_HEADERS)

    _rejected(response, f"The request body must not be larger than {MAX_REQUEST_BODY_BYTES} bytes.")


def test_a_body_over_the_limit_is_refused_when_its_declared_length_is_false(
    isolated_cli_settings: ProjectSettings,
) -> None:
    body = _padded(MAX_REQUEST_BODY_BYTES + 1)
    with client_for(isolated_cli_settings) as client:
        small = client.post("/v1/watchlists", content=body, headers={**JSON_HEADERS, "Content-Length": "2"})
        text = client.post("/v1/watchlists", content=body, headers={**JSON_HEADERS, "Content-Length": "many"})

    _rejected(small)
    _rejected(text)


def test_a_body_at_the_limit_is_read(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        response = client.post("/v1/watchlists", content=_padded(MAX_REQUEST_BODY_BYTES), headers=JSON_HEADERS)

    assert response.status_code == 201


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity", "1e999", "-1e999"])
def test_a_non_standard_number_nested_in_the_selection_is_refused(
    token: str, isolated_cli_settings: ProjectSettings
) -> None:
    body = b'{"ticker": "KO", "method_id": "%s", "selection": {"short_window": 20, "extra": [{"deep": %s}]}}' % (
        MOMENTUM.method_id.encode(),
        token.encode(),
    )
    with client_for(isolated_cli_settings) as client:
        response = client.post("/v1/analyses", content=body, headers=JSON_HEADERS)

    _rejected(response, "The request body must not contain NaN, Infinity or a number too large to store.")


def test_an_ordinary_syntax_error_keeps_its_message(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        response = client.post("/v1/analyses", content=b"{nope", headers=JSON_HEADERS)

    _rejected(response, "The request body must be a JSON object.")
