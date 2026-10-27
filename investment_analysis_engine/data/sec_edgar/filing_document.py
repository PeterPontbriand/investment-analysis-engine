"""Bounded, injectable SEC filing-document transport."""

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.financial.facts import FinancialProviderError
from investment_analysis_engine.data.http_json import http_failure_rules
from investment_analysis_engine.data.provider_failure import call_library


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


@dataclass(frozen=True)
class FilingHeaderPolicy:
    """Limit a filing-header read to one small text file."""

    timeout_seconds: float = 20.0
    max_header_bytes: int = 256 * 1024

    def __post_init__(self) -> None:
        """Reject unbounded or invalid transport settings."""
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("Filing header timeout must be finite and positive.")
        if self.max_header_bytes <= 0:
            raise ValueError("Filing header size limit must be positive.")


_FILING_URL_PATTERN = re.compile(r"https://www\.sec\.gov/Archives/edgar/data/[0-9]+/[0-9]{18}/[A-Za-z0-9_-]+\.html?")
_HEADER_URL_PATTERN = re.compile(
    r"https://www\.sec\.gov/Archives/edgar/data/[0-9]+/(?P<folder>[0-9]{18})/"
    r"(?P<accession>[0-9]{10}-[0-9]{2}-[0-9]{6})\.hdr\.sgml"
)


def filing_url(cik: str, accession: str, primary_document: str) -> str:
    """Construct an SEC archive URL solely from validated filing identifiers."""
    if not re.fullmatch(r"[0-9]{1,10}", cik) or int(cik) == 0:
        raise ValueError("Invalid filing CIK.")
    if not re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession):
        raise ValueError("Invalid filing accession.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*\.html?", primary_document):
        raise ValueError("Invalid primary document name.")
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{primary_document}"


def filing_header_url(cik: str, accession: str) -> str:
    """Construct an SEC filing-header URL solely from validated filing identifiers."""
    if not re.fullmatch(r"[0-9]{1,10}", cik) or int(cik) == 0:
        raise ValueError("Invalid filing CIK.")
    if not re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession):
        raise ValueError("Invalid filing accession.")
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{accession}.hdr.sgml"


class FilingFetcher(Protocol):
    """Inject a document transport without a live dependency in tests."""

    def __call__(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        policy: FilingReaderPolicy,
        not_found: ProviderFailureKind,
        provider_id: str,
    ) -> str:
        """Return bounded UTF-8 filing markup.

        ``not_found`` is the kind of an HTTP 404 and ``provider_id`` names the provider the request serves.
        """
        ...


class FilingHeaderFetcher(Protocol):
    """Inject a header transport without a live dependency in tests."""

    def __call__(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        policy: FilingHeaderPolicy,
        not_found: ProviderFailureKind,
        provider_id: str,
    ) -> str:
        """Return the bounded UTF-8 text of one filing header.

        ``not_found`` is the kind of an HTTP 404 and ``provider_id`` names the provider the request serves.
        """
        ...


class _NoRedirect(HTTPRedirectHandler):
    """Refuse redirects before any request to another origin is issued."""

    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        """Reject every redirect, including redirects to another SEC URL."""
        return None


def fetch_filing(
    url: str,
    *,
    headers: Mapping[str, str],
    policy: FilingReaderPolicy,
    not_found: ProviderFailureKind,
    provider_id: str,
) -> str:
    """Read a bounded SEC document without redirects, retries, or external parsing.

    Raises:
        ValueError: The URL or the declared identity is not acceptable; a defect of the caller.
        FinancialProviderError: A transport fault, a 404, a document over the size limit or one that is not UTF-8,
            carrying the kind of the failure and *provider_id*.
    """
    return read_bounded(
        url,
        pattern=_FILING_URL_PATTERN,
        noun="filing",
        accept="text/html,application/xhtml+xml",
        headers=headers,
        timeout_seconds=policy.timeout_seconds,
        max_bytes=policy.max_document_bytes,
        not_found=not_found,
        provider_id=provider_id,
    )


def fetch_filing_header(
    url: str,
    *,
    headers: Mapping[str, str],
    policy: FilingHeaderPolicy,
    not_found: ProviderFailureKind,
    provider_id: str,
) -> str:
    """Read one SEC filing header (``<accession>.hdr.sgml``) under the same transport rules as a filing.

    The read does not consult ``FilingReaderPolicy.max_documents``: a header is not a filing document.

    Raises:
        ValueError: The URL or the declared identity is not acceptable; a defect of the caller.
        FinancialProviderError: A transport fault, a 404, a header over the size limit or one that is not UTF-8,
            carrying the kind of the failure and *provider_id*.
    """
    match = _HEADER_URL_PATTERN.fullmatch(url)
    if match is None or match.group("folder") != match.group("accession").replace("-", ""):
        raise ValueError("Unsupported filing header URL.")
    return read_bounded(
        url,
        pattern=_HEADER_URL_PATTERN,
        noun="filing header",
        accept="text/plain",
        headers=headers,
        timeout_seconds=policy.timeout_seconds,
        max_bytes=policy.max_header_bytes,
        not_found=not_found,
        provider_id=provider_id,
    )


def read_bounded(  # noqa: PLR0913
    url: str,
    *,
    pattern: re.Pattern[str],
    noun: str,
    accept: str,
    headers: Mapping[str, str],
    timeout_seconds: float,
    max_bytes: int,
    not_found: ProviderFailureKind,
    provider_id: str,
) -> str:
    """Read one SEC document of an exact URL shape: no redirect, no retry, bounded size, UTF-8 only."""
    if pattern.fullmatch(url) is None:
        raise ValueError(f"Unsupported {noun} URL.")
    request_headers = dict(headers)
    if not request_headers.get("User-Agent", "").strip():
        raise ValueError(f"SEC {noun} requests require a declared User-Agent.")
    request_headers["Accept"] = accept
    request = Request(url, headers=request_headers)

    def read() -> bytes:
        try:
            with build_opener(_NoRedirect()).open(request, timeout=timeout_seconds) as response:
                body: bytes = response.read(max_bytes + 1)
        except HTTPError as error:
            error.close()  # an HTTPError holds the response stream; classification reads only its code
            raise
        return body

    data = call_library(
        read, rules=http_failure_rules(not_found), provider_id=provider_id, message=f"HTTP request failed for {url!r}"
    )
    if len(data) > max_bytes:
        msg = f"{noun.capitalize()} exceeds the configured size limit."
        raise FinancialProviderError(msg, kind=ProviderFailureKind.UNEXPECTED_RESPONSE, provider_id=provider_id)
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        msg = f"{noun.capitalize()} at {url!r} was not valid UTF-8."
        raise FinancialProviderError(
            msg, kind=ProviderFailureKind.UNEXPECTED_RESPONSE, provider_id=provider_id
        ) from exc
