"""Shape checks for the online providers the adapters read: Yahoo (through yfinance) and SEC EDGAR.

Each check makes a small, fixed number of requests (at most ``MAX_REQUESTS_PER_CHECK``; the Yahoo check's opening
connection counts as one) and verifies the *shape*
of what comes back, never a value: the fields and columns an adapter reads are present, not what they contain.
The live test suite and the ``ian health`` command call the same functions, so a probe is written once.

The adapter (or transport) and the monotonic clock are injected, so every body is testable against fakes. Each
provider call runs in a daemon worker thread, and the spec's timeout is a deadline for the whole check: each request
is given the time remaining and the check never waits longer than the timeout in total. The thread cannot
keep the process alive if the call never returns. A check never raises for a provider fault: it returns a failed
:class:`ProviderCheckResult` whose detail names the missing field or the transport error and whose ``kind`` says
which of the three provider failure kinds it was: a typed provider failure carries its own kind, a timeout is
``unreachable``, a wrong shape is ``unexpected_response`` and an empty history is ``no_data``. A failure with no
kind is deliberate: SEC access that is not configured, and an unexpected exception inside a check.
"""

from __future__ import annotations

import math
import socket
import ssl
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

import pandas as pd

from src.core.clock import utc_now
from src.core.provider_failure_kind import ProviderFailureKind
from src.data.base_client import DataFetchError
from src.data.financial.facts import FinancialProviderError
from src.data.http_json import JsonFetcher
from src.data.provider_failure import FailureRule, call_library
from src.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from src.data.yfinance.client import (
    YFINANCE_DATA_HOST,
    YFINANCE_HISTORY_COLUMNS,
    YFINANCE_PROVIDER_ID,
    YFinanceQuote,
)

DEFAULT_TIMEOUT_SECONDS = 20.0  # Whole-check deadline; equals the per-request transport timeout in http_json.py.
MAX_REQUESTS_PER_CHECK = 3  # SEC fair-access and guarded-egress budget; a fourth request needs project-owner review.
YAHOO_DATA_PORT = 443


@dataclass(frozen=True)
class ProviderCheckResult:
    """Outcome of one provider shape check."""

    provider_id: str
    probe: str
    passed: bool
    elapsed_seconds: float
    detail: str | None = None
    kind: ProviderFailureKind | None = None


@dataclass(frozen=True)
class YahooCheckSpec:
    """What the Yahoo check requests and the history columns the adapter reads."""

    probe_ticker: str
    history_days: int
    required_columns: tuple[str, ...]
    timeout_seconds: float


@dataclass(frozen=True)
class SecEdgarCheckSpec:
    """What the SEC EDGAR check requests and the document keys the adapter reads."""

    probe_ticker: str
    ticker_map_url: str
    company_facts_url: str
    ticker_entry_fields: tuple[str, ...]
    taxonomy: str
    timeout_seconds: float


# The URLs mirror the adapter's own constants (src/data/sec_edgar/financial_facts.py); a test pins them together.
YAHOO_SPEC = YahooCheckSpec(
    probe_ticker="AAPL",
    history_days=30,
    required_columns=YFINANCE_HISTORY_COLUMNS,
    timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
)
SEC_EDGAR_SPEC = SecEdgarCheckSpec(
    probe_ticker="AAPL",
    ticker_map_url="https://www.sec.gov/files/company_tickers.json",
    company_facts_url="https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
    ticker_entry_fields=("cik_str", "ticker", "title"),
    taxonomy="us-gaap",
    timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
)


class YahooProbeClient(Protocol):
    """The two Yahoo adapter calls the check makes; ``YFinanceClient`` satisfies it structurally."""

    def fetch_data(self, ticker: str, start_date: str, end_date: str | None = None) -> pd.DataFrame:
        """Return daily history for *ticker* from *start_date*."""
        ...

    def fetch_current_quote(self, ticker: str) -> YFinanceQuote:
        """Return the current quote for *ticker*."""
        ...


@dataclass(frozen=True)
class SecTransport:
    """The SEC request transport and declared identity the adapter would use."""

    json_fetcher: JsonFetcher
    user_agent: str


@dataclass(frozen=True)
class SecUnavailable:
    """SEC access could not be composed; the check fails with this detail rather than being skipped."""

    detail: str


Connector = Callable[[str, int, float], None]
"""Opens a connection to ``(host, port)`` within a timeout in seconds, or raises ``OSError``."""


@dataclass(frozen=True)
class ProviderClients:
    """The injected dependencies of every check; ``connect`` has no default, so no test reaches a host by accident."""

    yahoo: YahooProbeClient
    sec: SecTransport | SecUnavailable
    connect: Connector


@dataclass(frozen=True)
class ProviderCheckEntry:
    """One provider's identity, probe description and runnable check."""

    provider_id: str
    probe: str
    run: Callable[[ProviderClients], ProviderCheckResult]


class _CheckFailureError(Exception):
    """Internal: a failure the check itself found, carrying the detail and, unless deliberate, its kind."""

    def __init__(self, detail: str, kind: ProviderFailureKind | None = None) -> None:
        super().__init__(detail)
        self.kind = kind


def _wrong_shape(detail: str) -> _CheckFailureError:
    return _CheckFailureError(detail, ProviderFailureKind.UNEXPECTED_RESPONSE)


class _Deadline:
    """The whole-check time budget: every request gets what remains of it, never a fresh allowance."""

    def __init__(self, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds
        self._expires_at = time.monotonic() + timeout_seconds

    def remaining(self) -> float:
        return max(0.0, self._expires_at - time.monotonic())


def _call_with_timeout[ResultT](call: Callable[[], ResultT], deadline: _Deadline) -> ResultT:
    """Run *call* in a daemon thread and stop waiting when the check's deadline passes."""
    results: list[ResultT] = []
    errors: list[Exception] = []

    def worker() -> None:
        try:
            results.append(call())
        except Exception as exc:
            errors.append(exc)

    timed_out = f"timed out after {deadline.timeout_seconds:g} s"
    if deadline.remaining() <= 0:
        raise _CheckFailureError(timed_out, ProviderFailureKind.UNREACHABLE)
    thread = threading.Thread(target=worker, name="provider-check", daemon=True)
    thread.start()
    thread.join(deadline.remaining())
    if thread.is_alive():
        raise _CheckFailureError(timed_out, ProviderFailureKind.UNREACHABLE)
    if errors:
        raise errors[0]
    return results[0]


def _finish(
    provider_id: str,
    probe: str,
    clock: Callable[[], float],
    body: Callable[[], None],
) -> ProviderCheckResult:
    started = clock()
    detail: str | None = None
    kind: ProviderFailureKind | None = None
    try:
        body()
    except _CheckFailureError as failure:
        detail = str(failure)
        kind = failure.kind
    except (DataFetchError, FinancialProviderError) as failure:
        detail = f"{type(failure).__name__}: {failure}"
        kind = failure.kind
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc}"
    return ProviderCheckResult(provider_id, probe, detail is None, clock() - started, detail, kind)


def yahoo_probe_description(spec: YahooCheckSpec = YAHOO_SPEC) -> str:
    """Describe what the Yahoo check requests."""
    return f"connection to {YFINANCE_DATA_HOST}, {spec.probe_ticker} quote and daily history"


def sec_edgar_probe_description(spec: SecEdgarCheckSpec = SEC_EDGAR_SPEC) -> str:
    """Describe what the SEC EDGAR check requests."""
    return f"{spec.probe_ticker} ticker map and company facts"


def open_tls_connection(host: str, port: int, timeout_seconds: float) -> None:
    """Open a TCP connection to *host* and complete the TLS handshake, then close it; send no request.

    A web request is not used: Yahoo's edge answers a client that does not look like a browser with HTTP 429, so a
    status code from the standard library could not tell an unreachable service from one that rejects the client.
    """
    with (
        socket.create_connection((host, port), timeout=timeout_seconds) as raw,
        ssl.create_default_context().wrap_socket(raw, server_hostname=host),
    ):
        pass


_CONNECTION_FAILURE_RULES = (FailureRule((OSError,), ProviderFailureKind.UNREACHABLE),)


def check_yfinance(
    client: YahooProbeClient,
    *,
    spec: YahooCheckSpec = YAHOO_SPEC,
    clock: Callable[[], float] = time.monotonic,
    now: Callable[[], datetime] = utc_now,
    connect: Connector = open_tls_connection,
) -> ProviderCheckResult:
    """Check that Yahoo can be reached, then that a current quote and a short daily history come back in shape.

    The check opens with a direct TCP and TLS connection to the host yfinance requests data from, made without
    yfinance. yfinance swallows a connection fault in several places (the history download returns an empty
    frame, and the quote read can raise a ``KeyError``), so the adapter's own calls cannot reliably tell an
    unreachable service from a changed response. A failed connection is ``unreachable`` and ends the check. A
    connection that opens says nothing about throttling.
    """

    def body() -> None:
        deadline = _Deadline(spec.timeout_seconds)
        start_date = (now() - timedelta(days=spec.history_days)).date().isoformat()
        _call_with_timeout(
            lambda: call_library(
                lambda: connect(YFINANCE_DATA_HOST, YAHOO_DATA_PORT, deadline.remaining()),
                rules=_CONNECTION_FAILURE_RULES,
                provider_id=YFINANCE_PROVIDER_ID,
                message=f"Cannot open a TLS connection to {YFINANCE_DATA_HOST}:{YAHOO_DATA_PORT}",
                error_type=DataFetchError,
            ),
            deadline,
        )
        quote = _call_with_timeout(lambda: client.fetch_current_quote(spec.probe_ticker), deadline)
        price = quote.price
        if not math.isfinite(price) or price <= 0:
            msg = f"quote last price is not a positive finite number (received {price!r})"
            raise _wrong_shape(msg)
        frame = _call_with_timeout(lambda: client.fetch_data(spec.probe_ticker, start_date), deadline)
        _require_history_shape(frame, spec)

    return _finish(YFINANCE_PROVIDER_ID, yahoo_probe_description(spec), clock, body)


def _require_history_shape(frame: object, spec: YahooCheckSpec) -> None:
    if not isinstance(frame, pd.DataFrame):
        msg = f"history is not a data frame (received {type(frame).__name__})"
        raise _wrong_shape(msg)
    if frame.empty:
        msg = "history is empty"
        raise _CheckFailureError(msg, ProviderFailureKind.NO_DATA)
    missing = [column for column in spec.required_columns if column not in frame.columns]
    if missing:
        msg = f"history is missing columns: {', '.join(missing)}"
        raise _wrong_shape(msg)
    if not isinstance(frame.index, pd.DatetimeIndex) or not frame.index.is_monotonic_increasing:
        msg = "history index is not a monotonic date index"
        raise _wrong_shape(msg)


def check_sec_edgar(
    transport: SecTransport | SecUnavailable,
    *,
    spec: SecEdgarCheckSpec = SEC_EDGAR_SPEC,
    clock: Callable[[], float] = time.monotonic,
) -> ProviderCheckResult:
    """Check that the ticker map and one company-facts document carry the keys the adapter reads."""

    def body() -> None:
        if isinstance(transport, SecUnavailable):
            raise _CheckFailureError(transport.detail)
        deadline = _Deadline(spec.timeout_seconds)
        headers = {"User-Agent": transport.user_agent, "Accept": "application/json"}
        ticker_map = _call_with_timeout(
            lambda: transport.json_fetcher(
                spec.ticker_map_url,
                headers=headers,
                not_found=ProviderFailureKind.UNEXPECTED_RESPONSE,
                provider_id=SEC_PROVIDER_ID,
            ),
            deadline,
        )
        cik = _probe_cik(ticker_map, spec)
        url = spec.company_facts_url.format(cik=cik)
        company_facts = _call_with_timeout(
            lambda: transport.json_fetcher(
                url, headers=headers, not_found=ProviderFailureKind.NO_DATA, provider_id=SEC_PROVIDER_ID
            ),
            deadline,
        )
        _require_company_facts_shape(company_facts, spec)

    return _finish(SEC_PROVIDER_ID, sec_edgar_probe_description(spec), clock, body)


def _probe_cik(ticker_map: object, spec: SecEdgarCheckSpec) -> str:
    if not isinstance(ticker_map, Mapping) or not ticker_map:
        msg = "ticker map is not a non-empty object"
        raise _wrong_shape(msg)
    first_entry = next((entry for entry in ticker_map.values() if isinstance(entry, Mapping)), None)
    if first_entry is None:
        msg = "ticker map has no entries"
        raise _wrong_shape(msg)
    missing_fields = [field for field in spec.ticker_entry_fields if field not in first_entry]
    if missing_fields:
        msg = f"ticker map entries are missing fields: {', '.join(missing_fields)}"
        raise _wrong_shape(msg)
    for entry in ticker_map.values():
        if isinstance(entry, Mapping) and str(entry.get("ticker", "")).strip().upper() == spec.probe_ticker:
            missing = [field for field in spec.ticker_entry_fields if field not in entry]
            if missing:
                msg = f"ticker map entry for {spec.probe_ticker} is missing fields: {', '.join(missing)}"
                raise _wrong_shape(msg)
            cik = str(entry["cik_str"]).strip()
            if not cik.isdigit():
                msg = f"ticker map entry for {spec.probe_ticker} has a non-numeric cik_str"
                raise _wrong_shape(msg)
            return cik.zfill(10)
    msg = f"ticker map has no entry for {spec.probe_ticker}"
    raise _wrong_shape(msg)


def _require_company_facts_shape(company_facts: object, spec: SecEdgarCheckSpec) -> None:
    if not isinstance(company_facts, Mapping):
        msg = "company facts document is not an object"
        raise _wrong_shape(msg)
    facts = company_facts.get("facts")
    if not isinstance(facts, Mapping):
        msg = "company facts document has no 'facts' mapping"
        raise _wrong_shape(msg)
    if not isinstance(facts.get(spec.taxonomy), Mapping):
        msg = f"company facts document has no {spec.taxonomy!r} mapping under 'facts'"
        raise _wrong_shape(msg)


PROVIDER_CHECKS: tuple[ProviderCheckEntry, ...] = (
    ProviderCheckEntry(
        provider_id=YFINANCE_PROVIDER_ID,
        probe=yahoo_probe_description(),
        run=lambda clients: check_yfinance(clients.yahoo, connect=clients.connect),
    ),
    ProviderCheckEntry(
        provider_id=SEC_PROVIDER_ID,
        probe=sec_edgar_probe_description(),
        run=lambda clients: check_sec_edgar(clients.sec),
    ),
)
