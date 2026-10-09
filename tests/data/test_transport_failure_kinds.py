"""Transport classification: ``fetch_json`` and ``fetch_filing`` raise typed provider failures, offline."""

import inspect
import json
from collections.abc import Callable
from http.client import IncompleteRead
from io import BytesIO
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from src.core.provider_failure_kind import ProviderFailureKind
from src.data.financial.facts import FinancialProviderError
from src.data.http_json import JsonFetcher, fetch_json
from src.data.sec_edgar.filing_document import FilingFetcher, FilingReaderPolicy, fetch_filing
from src.evaluation.fixtures.sec_edgar_fpi import _FrozenSecFetcher

_FILING_URL = "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm"
_HEADERS = {"User-Agent": "Synthetic test"}
_NO_DATA = ProviderFailureKind.NO_DATA
_UNEXPECTED = ProviderFailureKind.UNEXPECTED_RESPONSE
_UNREACHABLE = ProviderFailureKind.UNREACHABLE


def _http_error(code: int) -> HTTPError:
    return HTTPError("https://example.test/x", code, "status", {}, BytesIO(b""))  # type: ignore[arg-type]


def _response(body: bytes) -> MagicMock:
    response = MagicMock()
    response.read.return_value = body
    response.__enter__.return_value = response
    return response


def _json(**overrides: Any) -> object:
    arguments: dict[str, Any] = {"not_found": _NO_DATA, "provider_id": "sec_edgar"} | overrides
    return fetch_json("https://example.test/x", headers=_HEADERS, **arguments)


def _filing(**overrides: Any) -> str:
    arguments: dict[str, Any] = {"not_found": _NO_DATA, "provider_id": "sec_edgar"} | overrides
    return fetch_filing(_FILING_URL, headers=_HEADERS, policy=FilingReaderPolicy(), **arguments)


def _patched_json(side_effect: object) -> Any:
    return patch("src.data.http_json.urlopen", side_effect=side_effect)


def _patched_filing(side_effect: object) -> Any:
    opener = MagicMock()
    opener.open.side_effect = side_effect
    return patch("src.data.sec_edgar.filing_document.build_opener", return_value=opener)


def test_a_successful_json_fetch_decodes_the_document() -> None:
    with _patched_json([_response(json.dumps({"a": 1}).encode())]):
        assert _json() == {"a": 1}


@pytest.mark.parametrize("caller_kind", [_NO_DATA, _UNEXPECTED])
def test_a_json_404_takes_the_kind_the_caller_passes(caller_kind: ProviderFailureKind) -> None:
    with _patched_json(_http_error(404)), pytest.raises(FinancialProviderError) as caught:
        _json(not_found=caller_kind, provider_id="massive")
    assert (caught.value.kind, caught.value.provider_id) == (caller_kind, "massive")
    assert "HTTP request failed for 'https://example.test/x'" in str(caught.value)


@pytest.mark.parametrize(
    "fault",
    [
        _http_error(403),
        _http_error(429),
        _http_error(400),
        _http_error(401),
        _http_error(410),
        _http_error(500),
        _http_error(503),
        URLError("name resolution failed"),
        TimeoutError("timed out"),
        ConnectionResetError("reset"),
        IncompleteRead(b"partial"),
    ],
)
def test_other_transport_faults_are_unreachable_whatever_the_404_kind(fault: BaseException) -> None:
    with _patched_json(fault), pytest.raises(FinancialProviderError) as caught:
        _json(not_found=_NO_DATA)
    assert caught.value.kind is _UNREACHABLE
    assert caught.value.provider_id == "sec_edgar"
    assert caught.value.__cause__ is fault


@pytest.mark.parametrize("body", [b"<html>not json</html>", b"\xff\xfe\x00bad"])
def test_a_body_that_is_not_json_is_an_unexpected_response(body: bytes) -> None:
    with _patched_json([_response(body)]), pytest.raises(FinancialProviderError) as caught:
        _json()
    assert caught.value.kind is _UNEXPECTED


def test_a_programming_error_inside_the_request_is_not_reported_as_a_provider_failure() -> None:
    with _patched_json(ValueError("unknown url type")), pytest.raises(ValueError, match="unknown url type"):
        _json()


@pytest.mark.parametrize("caller_kind", [_NO_DATA, _UNEXPECTED])
def test_a_filing_404_takes_the_kind_the_caller_passes(caller_kind: ProviderFailureKind) -> None:
    with _patched_filing(_http_error(404)), pytest.raises(FinancialProviderError) as caught:
        _filing(not_found=caller_kind)
    assert caught.value.kind is caller_kind


@pytest.mark.parametrize(
    "fault",
    [
        _http_error(403),
        _http_error(400),
        _http_error(401),
        _http_error(410),
        _http_error(502),
        URLError("refused"),
        TimeoutError(),
        IncompleteRead(b"partial"),
    ],
)
def test_a_filing_transport_fault_is_unreachable(fault: BaseException) -> None:
    with _patched_filing(fault), pytest.raises(FinancialProviderError) as caught:
        _filing()
    assert caught.value.kind is _UNREACHABLE


def test_an_oversized_or_undecodable_filing_is_an_unexpected_response() -> None:
    policy = FilingReaderPolicy(max_document_bytes=4)
    for body in (b"too long for the limit", b"\xff\xfe\xfa"):
        opener_response = _response(body)
        with _patched_filing([opener_response]), pytest.raises(FinancialProviderError) as caught:
            fetch_filing(_FILING_URL, headers=_HEADERS, policy=policy, not_found=_NO_DATA, provider_id="sec_edgar")
        assert caught.value.kind is _UNEXPECTED


def test_a_readable_filing_is_returned() -> None:
    with _patched_filing([_response(b"<html>ok</html>")]):
        assert _filing() == "<html>ok</html>"


@pytest.mark.parametrize(
    ("url", "headers"),
    [("https://example.test/not-a-filing", _HEADERS), (_FILING_URL, {})],
)
def test_a_bad_filing_request_is_a_value_error_not_a_provider_failure(url: str, headers: dict[str, str]) -> None:
    with pytest.raises(ValueError, match="filing|User-Agent"):
        fetch_filing(url, headers=headers, policy=FilingReaderPolicy(), not_found=_NO_DATA, provider_id="sec_edgar")


@pytest.mark.parametrize(
    "fetcher",
    [
        fetch_json,
        fetch_filing,
        JsonFetcher.__call__,
        FilingFetcher.__call__,
        _FrozenSecFetcher.__call__,
    ],
    ids=["fetch_json", "fetch_filing", "JsonFetcher", "FilingFetcher", "evaluation fixture fetcher"],
)
def test_both_keywords_are_required_and_keyword_only_on_every_fetcher(fetcher: Callable[..., object]) -> None:
    parameters = inspect.signature(fetcher).parameters
    for name in ("not_found", "provider_id"):
        assert parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
        assert parameters[name].default is inspect.Parameter.empty
    assert parameters["not_found"].annotation in (ProviderFailureKind, "ProviderFailureKind")
    assert parameters["provider_id"].annotation in (str, "str")


def test_omitting_a_keyword_is_a_type_error() -> None:
    with pytest.raises(TypeError):
        fetch_json("https://example.test/x", headers=_HEADERS, provider_id="sec_edgar")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        fetch_json("https://example.test/x", headers=_HEADERS, not_found=_NO_DATA)  # type: ignore[call-arg]
