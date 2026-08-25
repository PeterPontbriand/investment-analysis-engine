"""Shared HTTP/JSON transport primitives for production valuation adapters."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class JsonFetcher(Protocol):
    """Callable transport used by production valuation adapters."""

    def __call__(self, url: str, *, headers: Mapping[str, str]) -> object:
        """Return the decoded JSON payload for *url*."""
        ...


def fetch_json(url: str, *, headers: Mapping[str, str]) -> object:
    """Fetch and decode a JSON document using the standard library."""
    request = Request(url, headers=dict(headers))
    try:
        with urlopen(request, timeout=20.0) as response:  # noqa: S310
            payload = response.read()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        msg = f"HTTP request failed for {url!r}: {exc}"
        raise OSError(msg) from exc

    try:
        decoded: object = json.loads(payload)
        return decoded
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        msg = f"Response from {url!r} was not valid JSON."
        raise ValueError(msg) from exc
