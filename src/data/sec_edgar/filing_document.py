"""Bounded, injectable SEC filing-document transport."""

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from urllib.request import HTTPRedirectHandler, Request, build_opener


@dataclass(frozen=True)
class FilingReaderPolicy:
    """Limit optional unit verification to four moderately sized annual filings."""

    timeout_seconds: float = 20.0
    max_document_bytes: int = 8 * 1024 * 1024
    max_documents: int = 4

    def __post_init__(self) -> None:
        """Reject unbounded or invalid transport settings."""
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("Filing timeout must be finite and positive.")
        if self.max_document_bytes <= 0 or self.max_documents <= 0:
            raise ValueError("Filing size and document limits must be positive.")


def filing_url(cik: str, accession: str, primary_document: str) -> str:
    """Construct an SEC archive URL solely from validated filing identifiers."""
    if not re.fullmatch(r"[0-9]{1,10}", cik) or int(cik) == 0:
        raise ValueError("Invalid filing CIK.")
    if not re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession):
        raise ValueError("Invalid filing accession.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*\.html?", primary_document):
        raise ValueError("Invalid primary document name.")
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{primary_document}"


class FilingFetcher(Protocol):
    """Inject a document transport without a live dependency in tests."""

    def __call__(self, url: str, *, headers: Mapping[str, str], policy: FilingReaderPolicy) -> str:
        """Return bounded UTF-8 filing markup."""
        ...


class _NoRedirect(HTTPRedirectHandler):
    """Refuse redirects before any request to another origin is issued."""

    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        """Reject every redirect, including redirects to another SEC URL."""
        return None


def fetch_filing(url: str, *, headers: Mapping[str, str], policy: FilingReaderPolicy) -> str:
    """Read a bounded SEC document without redirects, retries, or external parsing."""
    if not re.fullmatch(r"https://www\.sec\.gov/Archives/edgar/data/[0-9]+/[0-9]{18}/[A-Za-z0-9_-]+\.html?", url):
        raise ValueError("Unsupported filing URL.")
    request_headers = dict(headers)
    if not request_headers.get("User-Agent", "").strip():
        raise ValueError("SEC filing requests require a declared User-Agent.")
    request_headers["Accept"] = "text/html,application/xhtml+xml"
    with build_opener(_NoRedirect()).open(
        Request(url, headers=request_headers), timeout=policy.timeout_seconds
    ) as response:
        data: bytes = response.read(policy.max_document_bytes + 1)
    if len(data) > policy.max_document_bytes:
        raise ValueError("Filing exceeds the configured size limit.")
    return data.decode("utf-8-sig")
