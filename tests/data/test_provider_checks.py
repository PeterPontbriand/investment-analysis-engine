"""Offline tests of the provider shape checks against fake adapters; no test reaches a real service."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator, Mapping
from datetime import UTC, datetime

import pandas as pd
import pytest

from src.data.provider_checks import (
    MAX_REQUESTS_PER_CHECK,
    PROVIDER_CHECKS,
    SEC_EDGAR_SPEC,
    YAHOO_SPEC,
    ProviderCheckResult,
    ProviderClients,
    SecEdgarCheckSpec,
    SecTransport,
    SecUnavailable,
    YahooCheckSpec,
    check_sec_edgar,
    check_yfinance,
)
from src.data.sec_edgar import financial_facts
from src.data.yfinance.client import YFinanceQuote

_NOW = datetime(2026, 10, 5, tzinfo=UTC)
_COLUMNS = ("Open", "High", "Low", "Close", "Volume")
_SHORT_TIMEOUT = 0.2


def _frame(columns: tuple[str, ...] = _COLUMNS, index: pd.Index | None = None) -> pd.DataFrame:
    dates = index if index is not None else pd.date_range("2026-09-01", periods=3)
    return pd.DataFrame({column: [1.0, 2.0, 3.0] for column in columns}, index=dates)


def _ticks() -> Callable[[], float]:
    values: Iterator[float] = iter([10.0, 12.5, 99.0, 99.0])
    return lambda: next(values)


class _FakeYahoo:
    """Fake adapter whose history may be any object, so non-frame responses can be exercised."""

    def __init__(
        self,
        history: object | None = None,
        quote: float | Exception = 190.0,
        block: threading.Event | None = None,
    ) -> None:
        self.history = _frame() if history is None else history
        self.quote = quote
        self.block = block
        self.history_calls: list[tuple[str, str]] = []
        self.quote_calls: list[str] = []

    def fetch_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str | None = None,  # noqa: ARG002
    ) -> pd.DataFrame:
        self.history_calls.append((ticker, start_date))
        if self.block is not None:
            self.block.wait()
        if isinstance(self.history, Exception):
            raise self.history
        return self.history  # type: ignore[return-value]

    def fetch_current_quote(self, ticker: str) -> YFinanceQuote:
        self.quote_calls.append(ticker)
        if isinstance(self.quote, Exception):
            raise self.quote
        return YFinanceQuote(price=self.quote, currency="USD")


def _yahoo(client: _FakeYahoo, spec: YahooCheckSpec = YAHOO_SPEC) -> ProviderCheckResult:
    return check_yfinance(client, spec=spec, clock=_ticks(), now=lambda: _NOW)


def test_yahoo_well_formed_response_passes_with_elapsed_from_the_injected_clock() -> None:
    client = _FakeYahoo()

    result = _yahoo(client)

    assert result.passed
    assert result.detail is None
    assert result.provider_id == "yfinance"
    assert result.elapsed_seconds == 2.5
    assert client.history_calls == [("AAPL", "2026-09-05")]
    assert client.quote_calls == ["AAPL"]


@pytest.mark.parametrize("missing", _COLUMNS)
def test_yahoo_missing_column_fails_and_names_it(missing: str) -> None:
    columns = tuple(column for column in _COLUMNS if column != missing)

    result = _yahoo(_FakeYahoo(history=_frame(columns)))

    assert not result.passed
    assert result.detail == f"history is missing columns: {missing}"


def test_yahoo_empty_history_fails() -> None:
    result = _yahoo(_FakeYahoo(history=_frame().iloc[0:0]))

    assert result.detail == "history is empty"


def test_yahoo_non_frame_history_fails() -> None:
    result = _yahoo(_FakeYahoo(history={"Close": [1.0]}))

    assert result.detail == "history is not a data frame (received dict)"


@pytest.mark.parametrize(
    "index",
    [
        pd.DatetimeIndex(["2026-09-03", "2026-09-02", "2026-09-04"]),
        pd.Index([0, 1, 2]),
    ],
)
def test_yahoo_non_monotonic_or_non_date_index_fails(index: pd.Index) -> None:
    result = _yahoo(_FakeYahoo(history=_frame(index=index)))

    assert result.detail == "history index is not a monotonic date index"


@pytest.mark.parametrize("price", [float("nan"), float("inf"), 0.0, -1.0])
def test_yahoo_quote_must_be_positive_and_finite(price: float) -> None:
    result = _yahoo(_FakeYahoo(quote=price))

    assert not result.passed
    assert result.detail is not None
    assert result.detail.startswith("quote last price is not a positive finite number")


def test_yahoo_history_exception_fails_the_check_and_skips_the_quote_request() -> None:
    client = _FakeYahoo(history=ConnectionError("boom"))

    result = _yahoo(client)

    assert result.detail == "ConnectionError: boom"
    assert client.quote_calls == []


def test_yahoo_quote_exception_fails_the_check() -> None:
    result = _yahoo(_FakeYahoo(quote=ValueError("no quote")))

    assert result.detail == "ValueError: no quote"


def test_yahoo_hung_adapter_times_out_on_a_daemon_worker_thread() -> None:
    release = threading.Event()
    spec = YahooCheckSpec("AAPL", 30, _COLUMNS, _SHORT_TIMEOUT)
    try:
        result = _yahoo(_FakeYahoo(block=release), spec)

        workers = [thread for thread in threading.enumerate() if thread.name == "provider-check"]
        assert result.detail == "timed out after 0.2 s"
        assert not result.passed
        assert workers
        assert all(thread.daemon for thread in workers)
    finally:
        release.set()


class _FakeSec:
    def __init__(self, documents: Mapping[str, object], block: threading.Event | None = None) -> None:
        self.documents = documents
        self.block = block
        self.requests: list[tuple[str, Mapping[str, str]]] = []

    def __call__(self, url: str, *, headers: Mapping[str, str]) -> object:
        self.requests.append((url, headers))
        if self.block is not None:
            self.block.wait()
        document = self.documents[url]
        if isinstance(document, Exception):
            raise document
        return document


_TICKER_ENTRY: dict[str, object] = {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}
_OTHER_ENTRY: dict[str, object] = {"cik_str": 1, "ticker": "OTHR", "title": "Other Inc."}
_FACTS_URL = SEC_EDGAR_SPEC.company_facts_url.format(cik="0000320193")


def _documents(ticker_map: object | None = None, facts: object | None = None) -> dict[str, object]:
    return {
        SEC_EDGAR_SPEC.ticker_map_url: {"0": _TICKER_ENTRY, "1": _OTHER_ENTRY} if ticker_map is None else ticker_map,
        _FACTS_URL: {"facts": {"us-gaap": {"Assets": {}}}} if facts is None else facts,
    }


def _sec(fetcher: _FakeSec, spec: SecEdgarCheckSpec = SEC_EDGAR_SPEC) -> ProviderCheckResult:
    return check_sec_edgar(SecTransport(fetcher, "Test Agent test@example.com"), spec=spec, clock=_ticks())


def test_sec_well_formed_documents_pass_within_the_request_budget() -> None:
    fetcher = _FakeSec(_documents())

    result = _sec(fetcher)

    assert result.passed
    assert result.provider_id == "sec_edgar"
    assert result.elapsed_seconds == 2.5
    assert [url for url, _ in fetcher.requests] == [SEC_EDGAR_SPEC.ticker_map_url, _FACTS_URL]
    assert len(fetcher.requests) <= MAX_REQUESTS_PER_CHECK
    assert fetcher.requests[0][1] == {"User-Agent": "Test Agent test@example.com", "Accept": "application/json"}


@pytest.mark.parametrize("field", SEC_EDGAR_SPEC.ticker_entry_fields)
def test_sec_missing_ticker_entry_field_fails_and_names_it(field: str) -> None:
    entry = {key: value for key, value in _TICKER_ENTRY.items() if key != field}

    result = _sec(_FakeSec(_documents(ticker_map={"0": entry})))

    assert result.detail == f"ticker map entries are missing fields: {field}"


@pytest.mark.parametrize("field", ["cik_str", "title"])
def test_sec_probe_entry_missing_a_field_fails_and_names_it(field: str) -> None:
    entry = {key: value for key, value in _TICKER_ENTRY.items() if key != field}

    result = _sec(_FakeSec(_documents(ticker_map={"0": _OTHER_ENTRY, "1": entry})))

    assert result.detail == f"ticker map entry for AAPL is missing fields: {field}"


@pytest.mark.parametrize(
    ("ticker_map", "detail"),
    [
        ([], "ticker map is not a non-empty object"),
        ({"0": "not an entry"}, "ticker map has no entries"),
        ({}, "ticker map is not a non-empty object"),
        ({"0": _OTHER_ENTRY}, "ticker map has no entry for AAPL"),
        ({"0": {**_TICKER_ENTRY, "cik_str": "abc"}}, "ticker map entry for AAPL has a non-numeric cik_str"),
    ],
)
def test_sec_ticker_map_shape_failures(ticker_map: object, detail: str) -> None:
    fetcher = _FakeSec(_documents(ticker_map=ticker_map))

    result = _sec(fetcher)

    assert result.detail == detail
    assert len(fetcher.requests) == 1


@pytest.mark.parametrize(
    ("facts", "detail"),
    [
        ([], "company facts document is not an object"),
        ({"cik": 1}, "company facts document has no 'facts' mapping"),
        ({"facts": {"dei": {}}}, "company facts document has no 'us-gaap' mapping under 'facts'"),
    ],
)
def test_sec_company_facts_shape_failures(facts: object, detail: str) -> None:
    result = _sec(_FakeSec(_documents(facts=facts)))

    assert result.detail == detail


def test_sec_transport_exception_fails_the_check() -> None:
    result = _sec(_FakeSec(_documents(facts=OSError("HTTP request failed"))))

    assert result.detail == "OSError: HTTP request failed"


def test_sec_unavailable_identity_fails_with_its_detail() -> None:
    result = check_sec_edgar(SecUnavailable("SEC EDGAR access is not configured."), clock=_ticks())

    assert not result.passed
    assert result.detail == "SEC EDGAR access is not configured."


def test_sec_hung_adapter_times_out_on_a_daemon_worker_thread() -> None:
    release = threading.Event()
    spec = SecEdgarCheckSpec(
        probe_ticker="AAPL",
        ticker_map_url=SEC_EDGAR_SPEC.ticker_map_url,
        company_facts_url=SEC_EDGAR_SPEC.company_facts_url,
        ticker_entry_fields=SEC_EDGAR_SPEC.ticker_entry_fields,
        taxonomy=SEC_EDGAR_SPEC.taxonomy,
        timeout_seconds=_SHORT_TIMEOUT,
    )
    try:
        result = _sec(_FakeSec(_documents(), block=release), spec)

        assert result.detail == "timed out after 0.2 s"
        workers = [thread for thread in threading.enumerate() if thread.name == "provider-check"]
        assert workers
        assert all(thread.daemon for thread in workers)
    finally:
        release.set()


def test_sec_urls_match_the_adapter_constants() -> None:
    assert SEC_EDGAR_SPEC.ticker_map_url == financial_facts._COMPANY_TICKERS_URL
    assert SEC_EDGAR_SPEC.company_facts_url == financial_facts._COMPANY_FACTS_URL


def test_the_check_tuple_lists_yfinance_then_sec_edgar_and_each_entry_runs_its_own_body() -> None:
    clients = ProviderClients(yahoo=_FakeYahoo(), sec=SecTransport(_FakeSec(_documents()), "Agent a@example.com"))

    results = [entry.run(clients) for entry in PROVIDER_CHECKS]

    assert [entry.provider_id for entry in PROVIDER_CHECKS] == ["yfinance", "sec_edgar"]
    assert [result.provider_id for result in results] == ["yfinance", "sec_edgar"]
    assert [result.probe for result in results] == [entry.probe for entry in PROVIDER_CHECKS]
    assert all(result.passed for result in results)
