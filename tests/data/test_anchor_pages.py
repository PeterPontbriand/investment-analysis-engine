"""The anchor annual filing is found on the extra submissions pages when the recent block holds none."""

from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any

import pytest

from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.financial.facts import FinancialProviderError
from investment_analysis_engine.data.sec_edgar.cover_listing import CoverListingRequest, CoverUnavailableReason
from investment_analysis_engine.data.sec_edgar.financial_facts import (
    SEC_PROVIDER_ID,
    AnchorYearEndRequest,
    SecEdgarFinancialFactsAdapter,
)
from tests._sec_instants import NOW, FixtureFetcher, load

_PRIOR_10K = "0000019617-25-000270"
_BOUNDARY = datetime(2025, 6, 30, tzinfo=UTC)
_BASE_CALLS = 3
_PAGE = "CIK0000019617-submissions-{number:03d}.json"


def _pages_read(fetcher: FixtureFetcher) -> list[str]:
    """Return the extra pages the adapter requested, in order."""
    return [url.rsplit("/", 1)[1] for url in fetcher.calls[_BASE_CALLS:]]


def _block(*rows: tuple[str, str, str, str, str]) -> dict[str, list[str]]:
    """Return a submissions block of (accession, form, filing date, report date, acceptance) rows."""
    columns = list(zip(*rows, strict=True)) or [()] * 5
    accessions, forms, filed, reported, accepted = (list(column) for column in columns)
    return {
        "accessionNumber": accessions,
        "form": forms,
        "filingDate": filed,
        "reportDate": reported,
        "acceptanceDateTime": accepted,
        "primaryDocument": [f"{accession}.htm" for accession in accessions],
    }


def _synthetic(files: list[dict[str, str]], pages: Mapping[str, Any]) -> FixtureFetcher:
    """Return a fetcher for JPMorgan's facts whose recent block has no annual filing, with these pages."""
    document = load("JPM")
    submissions = {
        "tickers": ["JPM"],
        "filings": {
            "recent": _block(("0000019617-26-000001", "8-K", "2026-03-01", "", "2026-03-01T12:00:00.000Z")),
            "files": files,
        },
    }
    fetcher = FixtureFetcher("JPM", companyfacts=document["companyfacts"], submissions=submissions)
    fetcher.pages = dict(pages)
    return fetcher


def _snapshot_after(fetcher: FixtureFetcher, boundary: datetime) -> Any:
    adapter = SecEdgarFinancialFactsAdapter(json_fetcher=fetcher, clock=lambda: NOW, user_agent="Synthetic test")
    return adapter.create_analysis_snapshot(subject_id="JPM", as_of=boundary)


def test_a_boundary_before_the_newest_annual_filing_finds_the_prior_one_through_the_pages() -> None:
    fetcher = FixtureFetcher("JPM")
    adapter = SecEdgarFinancialFactsAdapter(json_fetcher=fetcher, clock=lambda: NOW, user_agent="Synthetic test")
    with adapter.analysis_scope(subject_id="JPM", provider_id=SEC_PROVIDER_ID, as_of=_BOUNDARY):
        resolution = adapter.resolve_anchor_year_end(AnchorYearEndRequest("JPM", SEC_PROVIDER_ID))
    assert resolution.anchor is not None
    anchor = resolution.anchor
    assert (anchor.accession, anchor.form, anchor.year_end) == (_PRIOR_10K, "10-K", date(2024, 12, 31))
    assert anchor.filing_date == date(2025, 2, 14)
    assert anchor.filing_dates[_PRIOR_10K] == date(2025, 2, 14)
    # Pages 004 to 008 overlap the 400 days before the boundary and start by it; the 10-K is on the last of them.
    assert _pages_read(fetcher) == [_PAGE.format(number=number) for number in (4, 5, 6, 7, 8)]
    assert len(fetcher.calls) == _BASE_CALLS + 5


def test_the_snapshot_carries_every_field_of_the_anchor_from_the_page() -> None:
    snapshot = _snapshot_after(FixtureFetcher("JPM"), _BOUNDARY)
    assert snapshot.latest_annual_accession == _PRIOR_10K
    assert snapshot.eligible_annual_accessions == (_PRIOR_10K,)
    assert snapshot.filing_forms[_PRIOR_10K] == "10-K"
    assert snapshot.report_dates[_PRIOR_10K] == date(2024, 12, 31)
    assert snapshot.filing_dates[_PRIOR_10K] == date(2025, 2, 14)
    assert snapshot.acceptance_by_accession[_PRIOR_10K] < _BOUNDARY
    assert snapshot.primary_documents[_PRIOR_10K]
    assert snapshot.taxonomy == "us-gaap"
    assert snapshot.after_boundary_message is None


def test_the_cover_listing_and_the_sic_header_are_read_for_the_anchor_found_on_the_page() -> None:
    covers: list[str] = []
    headers: list[str] = []

    def cover(url: str, **_kwargs: object) -> str:
        covers.append(url)
        raise AssertionError("stop after recording the request")

    def header(url: str, **_kwargs: object) -> str:
        headers.append(url)
        return ""

    adapter = SecEdgarFinancialFactsAdapter(
        json_fetcher=FixtureFetcher("JPM"),
        clock=lambda: NOW,
        user_agent="Synthetic test",
        cover_fetcher=cover,
        header_fetcher=header,
    )
    with adapter.analysis_scope(subject_id="JPM", provider_id=SEC_PROVIDER_ID, as_of=_BOUNDARY):
        snapshot = adapter.create_analysis_snapshot(subject_id="JPM", as_of=_BOUNDARY)
        adapter.resolve_as_filed_sic(snapshot)
        with pytest.raises(AssertionError, match="stop after recording"):
            adapter.resolve_cover_listing(CoverListingRequest("JPM", SEC_PROVIDER_ID))
    accession_path = _PRIOR_10K.replace("-", "")
    assert [accession_path in url for url in headers] == [True]
    assert [accession_path in url for url in covers] == [True]


def test_the_search_stops_at_the_first_page_that_holds_an_annual_filing() -> None:
    fetcher = FixtureFetcher("JPM")
    boundary = datetime(2025, 3, 1, tzinfo=UTC)
    snapshot = _snapshot_after(fetcher, boundary)
    assert snapshot.latest_annual_accession == _PRIOR_10K
    assert _pages_read(fetcher) == [_PAGE.format(number=number) for number in (7, 8)]


def test_no_page_is_read_when_the_recent_block_suffices() -> None:
    fetcher = FixtureFetcher("JPM")
    snapshot = _snapshot_after(fetcher, datetime(2026, 6, 30, tzinfo=UTC))
    assert snapshot.latest_annual_accession == "0001628280-26-008131"
    assert len(fetcher.calls) == _BASE_CALLS


def test_a_page_is_read_once_per_adapter() -> None:
    fetcher = FixtureFetcher("JPM")
    adapter = SecEdgarFinancialFactsAdapter(json_fetcher=fetcher, clock=lambda: NOW, user_agent="Synthetic test")
    adapter.create_analysis_snapshot(subject_id="JPM", as_of=_BOUNDARY)
    adapter.create_analysis_snapshot(subject_id="JPM", as_of=_BOUNDARY)
    pages = [url for url in fetcher.calls if "-submissions-" in url]
    assert len(pages) == len(set(pages)) == 5


def test_the_window_bounds_the_pages_read() -> None:
    files = [
        {"name": _PAGE.format(number=1), "filingFrom": "2025-09-01", "filingTo": "2025-10-01"},
        {"name": _PAGE.format(number=2), "filingFrom": "2025-04-01", "filingTo": "2025-06-01"},
        {"name": _PAGE.format(number=3), "filingFrom": "2024-06-01", "filingTo": "2025-03-31"},
        {"name": _PAGE.format(number=4), "filingFrom": "2023-01-01", "filingTo": "2024-05-01"},
    ]
    holds_annual = _block(("0000019617-24-000001", "10-K", "2024-02-16", "2023-12-31", "2024-02-16T12:00:00.000Z"))
    pages = {
        _PAGE.format(number=1): holds_annual,
        _PAGE.format(number=2): _block(),
        _PAGE.format(number=3): _block(),
        _PAGE.format(number=4): holds_annual,
    }
    fetcher = _synthetic(files, pages)
    snapshot = _snapshot_after(fetcher, _BOUNDARY)
    # Page 1 starts after the boundary and page 4 ends before the 400 days: neither is read.
    assert _pages_read(fetcher) == [_PAGE.format(number=2), _PAGE.format(number=3)]
    assert snapshot.latest_annual_accession is None
    assert snapshot.after_boundary_message is None


def test_a_page_that_is_not_the_issuers_own_is_ignored() -> None:
    other = "CIK0000000001-submissions-001.json"
    files = [
        {"name": other, "filingFrom": "2025-01-01", "filingTo": "2025-06-01"},
        {"name": "../CIK0000019617-submissions-002.json", "filingFrom": "2025-01-01", "filingTo": "2025-06-01"},
    ]
    holds_annual = _block(("0000019617-25-000001", "10-K", "2025-02-14", "2024-12-31", "2025-02-14T12:00:00.000Z"))
    fetcher = _synthetic(files, {other: holds_annual, "../CIK0000019617-submissions-002.json": holds_annual})
    snapshot = _snapshot_after(fetcher, _BOUNDARY)
    assert len(fetcher.calls) == _BASE_CALLS
    assert snapshot.latest_annual_accession is None


def test_a_page_whose_annual_filing_was_accepted_after_the_boundary_does_not_hold_the_anchor() -> None:
    files = [{"name": _PAGE.format(number=1), "filingFrom": "2025-07-01", "filingTo": "2025-09-01"}]
    late = _block(("0000019617-25-000099", "10-K", "2025-07-15", "2025-06-30", "2025-07-15T12:00:00.000Z"))
    fetcher = _synthetic(files, {_PAGE.format(number=1): late})
    snapshot = _snapshot_after(fetcher, _BOUNDARY)
    assert len(fetcher.calls) == _BASE_CALLS
    assert snapshot.latest_annual_accession is None


def test_the_existing_outcome_stands_when_no_page_in_the_window_holds_an_annual_filing() -> None:
    files = [{"name": _PAGE.format(number=1), "filingFrom": "2025-01-01", "filingTo": "2025-06-01"}]
    fetcher = _synthetic(files, {_PAGE.format(number=1): _block()})
    adapter = SecEdgarFinancialFactsAdapter(json_fetcher=fetcher, clock=lambda: NOW, user_agent="Synthetic test")
    with adapter.analysis_scope(subject_id="JPM", provider_id=SEC_PROVIDER_ID, as_of=_BOUNDARY):
        resolution = adapter.resolve_cover_listing(CoverListingRequest("JPM", SEC_PROVIDER_ID))
    assert resolution.reason is CoverUnavailableReason.NO_ANCHOR_FILING
    assert _pages_read(fetcher) == [_PAGE.format(number=1)]


def test_a_page_that_cannot_be_read_is_a_classified_provider_failure() -> None:
    fetcher = FixtureFetcher("JPM")
    fetcher.pages = {}
    original = fetcher.__call__

    def failing(url: str, **kwargs: Any) -> object:
        if "-submissions-" in url:
            raise FinancialProviderError("down", kind=ProviderFailureKind.UNREACHABLE, provider_id=SEC_PROVIDER_ID)
        return original(url, **kwargs)

    adapter = SecEdgarFinancialFactsAdapter(json_fetcher=failing, clock=lambda: NOW, user_agent="Synthetic test")
    with pytest.raises(FinancialProviderError) as raised:
        adapter.create_analysis_snapshot(subject_id="JPM", as_of=_BOUNDARY)
    assert raised.value.kind is ProviderFailureKind.UNREACHABLE
