"""The anchor filing's fiscal year-end, the routed balance-sheet series and the dated split-history protocol."""

import inspect
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

import pytest

from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.cached_client import CachedHistoricalDataClient
from investment_analysis_engine.data.financial.facts import (
    FinancialFactRequest,
    FinancialField,
    FinancialProviderError,
    InstantAbsenceReason,
    InstantSeriesProvider,
    InstantSeriesRequest,
    ProviderFact,
)
from investment_analysis_engine.data.financial.production import ProductionFinancialFactsProvider
from investment_analysis_engine.data.market_data import DatedSplitAdjustedHistoryProvider, SplitAdjustedHistoryProvider
from investment_analysis_engine.data.sec_edgar import financial_facts
from investment_analysis_engine.data.sec_edgar.financial_facts import (
    SEC_PROVIDER_ID,
    AnchorYearEndProvider,
    AnchorYearEndRequest,
    AnchorYearEndResolution,
    AnchorYearEndUnavailableReason,
    _submission_report_dates,
)
from investment_analysis_engine.data.yfinance.client import YFinanceClient
from tests._sec_instants import ANNUAL_FIXTURES, FIXTURES, NOW, REGRESSION_SET, FixtureFetcher, adapter_for, load

_TICKERS = sorted(REGRESSION_SET)


class _NoFacts:
    """A financial-facts provider with no capability beyond ``fetch_facts``."""

    def fetch_facts(self, request: FinancialFactRequest, *, effective_as_of: datetime) -> tuple[ProviderFact, ...]:  # noqa: ARG002
        return ()


def _anchor_balance_sheet_end(document: Mapping[str, Any]) -> date:
    """Return the latest balance-sheet period end among the facts of the fixture's own anchor filing."""
    anchor = document["anchor_accession"]
    ends = {
        date.fromisoformat(observation["end"])
        for namespace in ("us-gaap", "ifrs-full")
        for concept in document["companyfacts"]["facts"].get(namespace, {}).values()
        for observations in concept["units"].values()
        for observation in observations
        if observation.get("accn") == anchor and "start" not in observation
    }
    return max(ends)


@pytest.mark.parametrize("ticker", _TICKERS)
def test_the_report_date_of_the_anchor_filing_is_the_period_end_of_its_own_facts(ticker: str) -> None:
    document = load(ticker)
    adapter = adapter_for(ticker)
    with adapter.analysis_scope(subject_id=ticker, provider_id=SEC_PROVIDER_ID, as_of=None):
        resolution = adapter.resolve_anchor_year_end(AnchorYearEndRequest(ticker, SEC_PROVIDER_ID))
    assert resolution.anchor is not None
    assert resolution.anchor.accession == document["anchor_accession"]
    assert resolution.anchor.year_end == date.fromisoformat(document["anchor_year_end"]) == REGRESSION_SET[ticker]
    assert resolution.anchor.year_end == _anchor_balance_sheet_end(document)


def test_the_year_end_follows_the_anchor_filing_of_the_boundary() -> None:
    adapter = adapter_for("WMT")
    boundary = datetime(2025, 6, 30, tzinfo=UTC)
    with adapter.analysis_scope(subject_id="WMT", provider_id=SEC_PROVIDER_ID, as_of=boundary):
        anchor = adapter.resolve_anchor_year_end(AnchorYearEndRequest("WMT", SEC_PROVIDER_ID)).anchor
    assert anchor is not None
    assert (anchor.accession, anchor.year_end, anchor.form) == ("0000104169-25-000021", date(2025, 1, 31), "10-K")
    assert anchor.filing_date == date(2025, 3, 14)
    assert anchor.filing_dates["0000104169-26-000055"] == date(2026, 3, 13)


@pytest.mark.parametrize("folder", [FIXTURES, ANNUAL_FIXTURES])
def test_every_filing_of_the_fixtures_carries_a_report_date_in_the_recent_block_and_on_the_extra_pages(
    folder: Any,
) -> None:
    for ticker in _TICKERS:
        document = load(ticker, folder)
        blocks = [document["submissions"]["filings"]["recent"], *document.get("pages", {}).values()]
        for block in blocks:
            assert len(block["reportDate"]) == len(block["accessionNumber"])
            assert set(_submission_report_dates({"filings": {"recent": block}})) == set(block["accessionNumber"])


def test_a_filing_without_a_report_date_gives_no_year_end_and_none_is_taken_from_the_facts() -> None:
    document = load("WMT")
    submissions = document["submissions"]
    del submissions["filings"]["recent"]["reportDate"]
    adapter = adapter_for("WMT", FixtureFetcher("WMT", submissions=submissions))
    with adapter.analysis_scope(subject_id="WMT", provider_id=SEC_PROVIDER_ID, as_of=None):
        resolution = adapter.resolve_anchor_year_end(AnchorYearEndRequest("WMT", SEC_PROVIDER_ID))
    assert resolution.anchor is None
    assert resolution.reason is AnchorYearEndUnavailableReason.REPORT_DATE_UNAVAILABLE
    assert resolution.message is not None


def test_a_report_date_that_is_not_a_date_is_skipped() -> None:
    block = {"accessionNumber": ["a", "b"], "reportDate": ["2025-12-31", "not-a-date"]}
    assert _submission_report_dates({"filings": {"recent": block}}) == {"a": date(2025, 12, 31)}
    assert _submission_report_dates([]) == {}


def test_a_registrant_whose_annual_filings_all_came_after_the_boundary_gives_the_adapters_message() -> None:
    adapter = adapter_for("WMT")
    with adapter.analysis_scope(subject_id="WMT", provider_id=SEC_PROVIDER_ID, as_of=datetime(2023, 1, 1, tzinfo=UTC)):
        resolution = adapter.resolve_anchor_year_end(AnchorYearEndRequest("WMT", SEC_PROVIDER_ID))
    assert resolution.reason is AnchorYearEndUnavailableReason.ACCEPTED_AFTER_BOUNDARY
    assert resolution.message is not None
    assert "filed its first annual report on 2024-03-15" in resolution.message
    assert "after the boundary 2023-01-01" in resolution.message


def test_the_year_end_needs_the_scope_of_the_same_ticker_and_the_sec_provider() -> None:
    adapter = adapter_for("WMT")
    outside = adapter.resolve_anchor_year_end(AnchorYearEndRequest("WMT", SEC_PROVIDER_ID))
    assert outside.reason is AnchorYearEndUnavailableReason.NO_ANALYSIS_SCOPE
    with adapter.analysis_scope(subject_id="WMT", provider_id=SEC_PROVIDER_ID, as_of=None):
        other = adapter.resolve_anchor_year_end(AnchorYearEndRequest("JPM", SEC_PROVIDER_ID))
        foreign = adapter.resolve_anchor_year_end(AnchorYearEndRequest("WMT", "yfinance"))
    assert other.reason is AnchorYearEndUnavailableReason.SUBJECT_MISMATCH
    assert foreign.reason is AnchorYearEndUnavailableReason.NO_ANALYSIS_SCOPE


def test_the_scope_of_a_registrant_with_no_annual_report_at_all_cannot_open() -> None:
    document = load("WMT")
    submissions = document["submissions"]
    submissions["filings"]["recent"]["form"] = ["8-K", "8-K", "8-K"]
    companyfacts = {"cik": document["cik"], "entityName": "X", "facts": {"us-gaap": {}}}
    adapter = adapter_for("WMT", FixtureFetcher("WMT", submissions=submissions, companyfacts=companyfacts))
    with (
        pytest.raises(FinancialProviderError) as raised,
        adapter.analysis_scope(subject_id="WMT", provider_id=SEC_PROVIDER_ID, as_of=None),
    ):
        pytest.fail("the scope of a registrant with no annual report cannot open")
    assert raised.value.kind is ProviderFailureKind.NO_DATA
    assert "has filed no annual report" in str(raised.value)


def test_asking_for_the_year_end_again_makes_no_request() -> None:
    fetcher = FixtureFetcher("WMT")
    adapter = adapter_for("WMT", fetcher)
    with adapter.analysis_scope(subject_id="WMT", provider_id=SEC_PROVIDER_ID, as_of=None):
        opened = len(fetcher.calls)
        first = adapter.resolve_anchor_year_end(AnchorYearEndRequest("wmt", SEC_PROVIDER_ID))
        second = adapter.resolve_anchor_year_end(AnchorYearEndRequest("WMT", SEC_PROVIDER_ID))
    assert first == second
    assert len(fetcher.calls) == opened == 3


def test_the_request_and_the_resolution_validate_themselves() -> None:
    assert AnchorYearEndRequest(" wmt ", " sec_edgar ") == AnchorYearEndRequest("WMT", "sec_edgar")
    with pytest.raises(ValueError, match="requires a ticker"):
        AnchorYearEndRequest(" ", SEC_PROVIDER_ID)
    with pytest.raises(ValueError, match="either the year-end or the reason"):
        AnchorYearEndResolution()
    with pytest.raises(ValueError, match="requires a message"):
        AnchorYearEndResolution(reason=AnchorYearEndUnavailableReason.NO_ANCHOR_FILING, message=" ")


# --- the production provider routes the balance-sheet series and the year-end ------------------------------------


def _production(ticker: str) -> ProductionFinancialFactsProvider:
    return ProductionFinancialFactsProvider(sec_edgar=adapter_for(ticker), yfinance=_NoFacts())


def test_the_production_provider_returns_an_instant_series_through_the_sec_adapter() -> None:
    provider = _production("WMT")
    assert isinstance(provider, InstantSeriesProvider)
    request = InstantSeriesRequest("WMT", FinancialField.TOTAL_ASSETS, SEC_PROVIDER_ID, (date(2026, 1, 31),))
    answer = provider.fetch_instant_series(request, effective_as_of=NOW)
    assert [fact.observation_period_end.date() for fact in answer.facts if fact.observation_period_end] == [
        date(2026, 1, 31)
    ]
    assert answer.absences == ()


@pytest.mark.parametrize("provider_id", ["yfinance", "unrouted"])
def test_the_production_provider_refuses_a_series_for_a_provider_that_does_not_serve_it(provider_id: str) -> None:
    request = InstantSeriesRequest("WMT", FinancialField.TOTAL_ASSETS, provider_id, (date(2026, 1, 31),))
    answer = _production("WMT").fetch_instant_series(request, effective_as_of=NOW)
    assert answer.facts == ()
    assert [(item.period_end, item.reason) for item in answer.absences] == [
        (date(2026, 1, 31), InstantAbsenceReason.UNSUPPORTED)
    ]
    assert provider_id in answer.absences[0].detail


def test_the_production_provider_routes_the_year_end_and_refuses_a_provider_without_it() -> None:
    provider = _production("WMT")
    assert isinstance(provider, AnchorYearEndProvider)
    with provider.analysis_scope(subject_id="WMT", provider_id=SEC_PROVIDER_ID, as_of=None):
        routed = provider.resolve_anchor_year_end(AnchorYearEndRequest("WMT", SEC_PROVIDER_ID))
        refused = provider.resolve_anchor_year_end(AnchorYearEndRequest("WMT", "yfinance"))
    assert routed.anchor is not None
    assert routed.anchor.year_end == date(2026, 1, 31)
    assert refused.anchor is None
    assert refused.message is not None
    assert "yfinance" in refused.message


# --- the dated split-history protocol ----------------------------------------------------------------------------


def test_the_cached_client_satisfies_the_dated_protocol_and_the_yahoo_client_stays_on_the_existing_one() -> None:
    cached = inspect.signature(CachedHistoricalDataClient.fetch_split_adjusted_history).parameters
    dated = inspect.signature(DatedSplitAdjustedHistoryProvider.fetch_split_adjusted_history).parameters
    raw = inspect.signature(YFinanceClient.fetch_split_adjusted_history).parameters
    assert {"adjusted_on", "as_of"} <= set(dated)
    assert {name: parameter.kind for name, parameter in dated.items()} == {
        name: parameter.kind for name, parameter in cached.items()
    }
    assert not {"adjusted_on", "as_of"} & set(raw)
    assert issubclass(CachedHistoricalDataClient, DatedSplitAdjustedHistoryProvider)
    # The existing runtime check of the cached client is on the wrapped provider, which stays the Yahoo client.
    assert issubclass(YFinanceClient, SplitAdjustedHistoryProvider)
    assert dated["adjusted_on"].default is None
    assert dated["as_of"].default is None


def test_a_ticker_with_no_cik_has_no_anchor_filing() -> None:
    adapter = adapter_for("WMT")
    with adapter.analysis_scope(subject_id="ZZZZ", provider_id=SEC_PROVIDER_ID, as_of=None):
        resolution = adapter.resolve_anchor_year_end(AnchorYearEndRequest("ZZZZ", SEC_PROVIDER_ID))
    assert resolution.reason is AnchorYearEndUnavailableReason.NO_ANCHOR_FILING
    assert resolution.message is not None
    assert "ZZZZ" in resolution.message


def test_an_anchor_filing_without_a_form_gives_no_year_end() -> None:
    adapter = adapter_for("WMT")
    with adapter.analysis_scope(subject_id="WMT", provider_id=SEC_PROVIDER_ID, as_of=None):
        snapshot = financial_facts._ACTIVE_SNAPSHOT.get()  # noqa: SLF001
        assert snapshot is not None
        token = financial_facts._ACTIVE_SNAPSHOT.set(replace(snapshot, filing_forms={}))  # noqa: SLF001
        try:
            resolution = adapter.resolve_anchor_year_end(AnchorYearEndRequest("WMT", SEC_PROVIDER_ID))
        finally:
            financial_facts._ACTIVE_SNAPSHOT.reset(token)  # noqa: SLF001
    assert resolution.reason is AnchorYearEndUnavailableReason.FORM_UNAVAILABLE
