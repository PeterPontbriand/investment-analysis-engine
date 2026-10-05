"""Shape checks for the online providers the adapters read: Yahoo (through yfinance) and SEC EDGAR.

Each check makes a small, fixed number of requests (at most ``MAX_REQUESTS_PER_CHECK``) and verifies the *shape*
of what comes back, never a value: the fields and columns an adapter reads are present, not what they contain.
The live test suite and the ``ian health`` command call the same functions, so a probe is written once.

The adapter (or transport) and the monotonic clock are injected, so every body is testable against fakes. Each
provider call runs in a daemon worker thread and the check stops waiting at the spec's timeout; the thread cannot
keep the process alive if the call never returns. A check never raises for a provider fault: it returns a failed
:class:`ProviderCheckResult` whose detail names the missing field or the transport error.
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

import pandas as pd

from src.core.clock import utc_now
from src.data.http_json import JsonFetcher
from src.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from src.data.yfinance.client import YFINANCE_PROVIDER_ID, YFinanceQuote

DEFAULT_TIMEOUT_SECONDS = 20.0  # Matches the transport timeout in src/data/http_json.py.
MAX_REQUESTS_PER_CHECK = 3  # SEC fair-access and guarded-egress budget; a fourth request needs project-owner review.


@dataclass(frozen=True)
class ProviderCheckResult:
    """Outcome of one provider shape check."""

    provider_id: str
    probe: str
    passed: bool
    elapsed_seconds: float
    detail: str | None = None


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
    required_columns=("Open", "High", "Low", "Close", "Volume"),
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


@dataclass(frozen=True)
class ProviderClients:
    """The injected dependencies of every check."""

    yahoo: YahooProbeClient
    sec: SecTransport | SecUnavailable


@dataclass(frozen=True)
class ProviderCheckEntry:
    """One provider's identity, probe description and runnable check."""

    provider_id: str
    probe: str
    run: Callable[[ProviderClients], ProviderCheckResult]


class _CheckFailureError(Exception):
    """Internal: a shape mismatch or timeout, carrying the failure detail."""


def _call_with_timeout[ResultT](call: Callable[[], ResultT], timeout_seconds: float) -> ResultT:
    """Run *call* in a daemon thread and stop waiting at the timeout."""
    results: list[ResultT] = []
    errors: list[Exception] = []

    def worker() -> None:
        try:
            results.append(call())
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=worker, name="provider-check", daemon=True)
    thread.start()
    thread.join(timeout_seconds)
    if thread.is_alive():
        msg = f"timed out after {timeout_seconds:g} s"
        raise _CheckFailureError(msg)
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
    try:
        body()
    except _CheckFailureError as failure:
        detail = str(failure)
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc}"
    return ProviderCheckResult(provider_id, probe, detail is None, clock() - started, detail)


def yahoo_probe_description(spec: YahooCheckSpec = YAHOO_SPEC) -> str:
    """Describe what the Yahoo check requests."""
    return f"{spec.probe_ticker} daily history and quote"


def sec_edgar_probe_description(spec: SecEdgarCheckSpec = SEC_EDGAR_SPEC) -> str:
    """Describe what the SEC EDGAR check requests."""
    return f"{spec.probe_ticker} ticker map and company facts"


def check_yfinance(
    client: YahooProbeClient,
    *,
    spec: YahooCheckSpec = YAHOO_SPEC,
    clock: Callable[[], float] = time.monotonic,
    now: Callable[[], datetime] = utc_now,
) -> ProviderCheckResult:
    """Check that a short daily history and a current quote come back in the shape the adapter reads."""

    def body() -> None:
        start_date = (now() - timedelta(days=spec.history_days)).date().isoformat()
        frame = _call_with_timeout(lambda: client.fetch_data(spec.probe_ticker, start_date), spec.timeout_seconds)
        _require_history_shape(frame, spec)
        quote = _call_with_timeout(lambda: client.fetch_current_quote(spec.probe_ticker), spec.timeout_seconds)
        price = quote.price
        if not math.isfinite(price) or price <= 0:
            msg = f"quote last price is not a positive finite number (received {price!r})"
            raise _CheckFailureError(msg)

    return _finish(YFINANCE_PROVIDER_ID, yahoo_probe_description(spec), clock, body)


def _require_history_shape(frame: object, spec: YahooCheckSpec) -> None:
    if not isinstance(frame, pd.DataFrame):
        msg = f"history is not a data frame (received {type(frame).__name__})"
        raise _CheckFailureError(msg)
    if frame.empty:
        msg = "history is empty"
        raise _CheckFailureError(msg)
    missing = [column for column in spec.required_columns if column not in frame.columns]
    if missing:
        msg = f"history is missing columns: {', '.join(missing)}"
        raise _CheckFailureError(msg)
    if not isinstance(frame.index, pd.DatetimeIndex) or not frame.index.is_monotonic_increasing:
        msg = "history index is not a monotonic date index"
        raise _CheckFailureError(msg)


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
        headers = {"User-Agent": transport.user_agent, "Accept": "application/json"}
        ticker_map = _call_with_timeout(
            lambda: transport.json_fetcher(spec.ticker_map_url, headers=headers), spec.timeout_seconds
        )
        cik = _probe_cik(ticker_map, spec)
        url = spec.company_facts_url.format(cik=cik)
        company_facts = _call_with_timeout(lambda: transport.json_fetcher(url, headers=headers), spec.timeout_seconds)
        _require_company_facts_shape(company_facts, spec)

    return _finish(SEC_PROVIDER_ID, sec_edgar_probe_description(spec), clock, body)


def _probe_cik(ticker_map: object, spec: SecEdgarCheckSpec) -> str:
    if not isinstance(ticker_map, Mapping) or not ticker_map:
        msg = "ticker map is not a non-empty object"
        raise _CheckFailureError(msg)
    first_entry = next((entry for entry in ticker_map.values() if isinstance(entry, Mapping)), None)
    if first_entry is None:
        msg = "ticker map has no entries"
        raise _CheckFailureError(msg)
    missing_fields = [field for field in spec.ticker_entry_fields if field not in first_entry]
    if missing_fields:
        msg = f"ticker map entries are missing fields: {', '.join(missing_fields)}"
        raise _CheckFailureError(msg)
    for entry in ticker_map.values():
        if isinstance(entry, Mapping) and str(entry.get("ticker", "")).strip().upper() == spec.probe_ticker:
            missing = [field for field in spec.ticker_entry_fields if field not in entry]
            if missing:
                msg = f"ticker map entry for {spec.probe_ticker} is missing fields: {', '.join(missing)}"
                raise _CheckFailureError(msg)
            cik = str(entry["cik_str"]).strip()
            if not cik.isdigit():
                msg = f"ticker map entry for {spec.probe_ticker} has a non-numeric cik_str"
                raise _CheckFailureError(msg)
            return cik.zfill(10)
    msg = f"ticker map has no entry for {spec.probe_ticker}"
    raise _CheckFailureError(msg)


def _require_company_facts_shape(company_facts: object, spec: SecEdgarCheckSpec) -> None:
    if not isinstance(company_facts, Mapping):
        msg = "company facts document is not an object"
        raise _CheckFailureError(msg)
    facts = company_facts.get("facts")
    if not isinstance(facts, Mapping):
        msg = "company facts document has no 'facts' mapping"
        raise _CheckFailureError(msg)
    if not isinstance(facts.get(spec.taxonomy), Mapping):
        msg = f"company facts document has no {spec.taxonomy!r} mapping under 'facts'"
        raise _CheckFailureError(msg)


PROVIDER_CHECKS: tuple[ProviderCheckEntry, ...] = (
    ProviderCheckEntry(
        provider_id=YFINANCE_PROVIDER_ID,
        probe=yahoo_probe_description(),
        run=lambda clients: check_yfinance(clients.yahoo),
    ),
    ProviderCheckEntry(
        provider_id=SEC_PROVIDER_ID,
        probe=sec_edgar_probe_description(),
        run=lambda clients: check_sec_edgar(clients.sec),
    ),
)
