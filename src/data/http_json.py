"""Shared HTTP/JSON transport primitives for production financial-facts adapters."""

from __future__ import annotations

import json
from collections.abc import Mapping
from http.client import HTTPException
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.core.provider_failure_kind import ProviderFailureKind
from src.data.financial.facts import FinancialProviderError
from src.data.provider_failure import DEFECT, FailureRule, call_library


class JsonFetcher(Protocol):
    """Callable transport used by production financial-facts adapters."""

    def __call__(
        self, url: str, *, headers: Mapping[str, str], not_found: ProviderFailureKind, provider_id: str
    ) -> object:
        """Return the decoded JSON payload for *url*.

        ``not_found`` is the kind of an HTTP 404 for this request: ``NO_DATA`` for a per-company document,
        ``UNEXPECTED_RESPONSE`` for a fixed endpoint. ``provider_id`` names the provider the request serves.
        """
        ...


def http_failure_rules(not_found: ProviderFailureKind) -> tuple[FailureRule, ...]:
    """Classify an HTTP failure: a 404 by the caller's kind, any other transport fault as unreachable."""
    return (
        FailureRule((HTTPError,), not_found, when=lambda error: isinstance(error, HTTPError) and error.code == 404),
        FailureRule((HTTPError, URLError, TimeoutError, OSError, HTTPException), ProviderFailureKind.UNREACHABLE),
        FailureRule((ValueError, TypeError), DEFECT),
    )


def fetch_json(url: str, *, headers: Mapping[str, str], not_found: ProviderFailureKind, provider_id: str) -> object:
    """Fetch and decode a JSON document using the standard library.

    Raises:
        FinancialProviderError: Carrying the kind of the failure and *provider_id*.
    """
    request = Request(url, headers=dict(headers))

    def read() -> bytes:
        with urlopen(request, timeout=20.0) as response:  # noqa: S310
            body: bytes = response.read()
        return body

    payload = call_library(
        read, rules=http_failure_rules(not_found), provider_id=provider_id, message=f"HTTP request failed for {url!r}"
    )
    try:
        decoded: object = json.loads(payload)
        return decoded
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        msg = f"Response from {url!r} was not valid JSON."
        raise FinancialProviderError(
            msg, kind=ProviderFailureKind.UNEXPECTED_RESPONSE, provider_id=provider_id
        ) from exc
