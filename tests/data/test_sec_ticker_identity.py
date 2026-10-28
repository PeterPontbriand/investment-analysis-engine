"""Which registrant a ticker names for the SEC adapter: override, ticker file, no annual filing."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.financial.facts import (
    FactsNotAvailableAsOf,
    FinancialFactRequest,
    FinancialField,
    FinancialProviderError,
    InstantAbsenceReason,
    InstantSeriesRequest,
)
from investment_analysis_engine.data.financial.provenance import FinancialSubjectKind
from investment_analysis_engine.data.sec_edgar.cover_listing import (
    CoverListingRequest,
    CoverReaderPolicy,
    CoverUnavailableReason,
)
from investment_analysis_engine.data.sec_edgar.filing_header import SicUnavailableReason
from investment_analysis_engine.data.sec_edgar.financial_facts import (
    CIK_SOURCE_OVERRIDE,
    CIK_SOURCE_TICKER_FILE,
    SEC_PROVIDER_ID,
    SecEdgarFinancialFactsAdapter,
)

NOW = datetime(2026, 10, 27, 12, tzinfo=UTC)
_OLD_CIK, _NEW_CIK = 34088, 2115436


def _observation(year: int, value: float, cik: int, form: str = "10-K") -> dict[str, Any]:
    return {
        "val": value,
        "start": f"{year}-01-01",
        "end": f"{year}-12-31",
        "accn": f"{cik:010d}-{(year + 1) % 100:02d}-000001",
        "filed": f"{year + 1}-02-01",
        "fy": year,
        "fp": "FY",
        "form": form,
    }


def _company_facts(cik: int, form: str = "10-K") -> dict[str, Any]:
    concept = {"units": {"USD": [_observation(year, 100.0 + year, cik, form) for year in (2022, 2023, 2024)]}}
    return {"cik": cik, "entityName": f"Issuer {cik}", "facts": {"us-gaap": {_OCF: concept}}}


_OCF = "NetCashProvidedByUsedInOperatingActivities"


def _submissions(cik: int, forms: Mapping[str, str] | None = None, *, pages: str | None = None) -> dict[str, Any]:
    """Return submissions with the 10-Ks of 2023 to 2025, or the given accession -> form listing."""
    listing = forms or {f"{cik:010d}-{year % 100:02d}-000001": "10-K" for year in (2023, 2024, 2025)}
    names = list(listing)
    stamps = [f"20{name.split('-')[1]}-02-01T12:00:00.000Z" for name in names]
    files = [{"name": f"CIK{cik:010d}-submissions-001.json", "filingFrom": pages, "filingTo": "2019-12-31"}]
    return {
        "tickers": ["XOM"],
        "filings": {
            "recent": {
                "accessionNumber": names,
                "form": [listing[name] for name in names],
                "filingDate": [stamp[:10] for stamp in stamps],
                "acceptanceDateTime": stamps,
                "primaryDocument": ["a.htm"] * len(names),
            },
            "files": files if pages else [],
        },
    }


class _Sec:
    """Serve a ticker file, per-CIK documents and covers, and record every URL asked for."""

    def __init__(
        self,
        rows: list[tuple[str, int]],
        submissions: Mapping[int, dict[str, Any]],
        covers: Mapping[str, str] | None = None,
        facts_form: str = "10-K",
    ) -> None:
        self.facts_form = facts_form
        self.rows = rows
        self.submissions = dict(submissions)
        self.covers = dict(covers or {})
        self.urls: list[str] = []
        self.cover_urls: list[str] = []

    def json(self, url: str, *, headers: Mapping[str, str], not_found: ProviderFailureKind, provider_id: str) -> object:
        assert headers["User-Agent"]
        self.urls.append(url)
        if url.endswith("company_tickers.json"):
            return {
                str(index): {"cik_str": cik, "ticker": ticker, "title": f"Issuer {cik}"}
                for index, (ticker, cik) in enumerate(self.rows)
            }
        cik = int(url.rsplit("CIK", 1)[1][:10])
        if cik not in self.submissions:
            raise FinancialProviderError("not found", kind=not_found, provider_id=provider_id)
        return _company_facts(cik, self.facts_form) if "/companyfacts/" in url else self.submissions[cik]

    def cover(
        self,
        url: str,
        *,
        headers: Mapping[str, str],  # noqa: ARG002
        policy: CoverReaderPolicy,  # noqa: ARG002
        not_found: ProviderFailureKind,
        provider_id: str,
    ) -> str:
        self.cover_urls.append(url)
        if url not in self.covers:
            raise FinancialProviderError("gone", kind=not_found, provider_id=provider_id)
        return self.covers[url]

    def adapter(self, overrides: Mapping[str, str] | None = None) -> SecEdgarFinancialFactsAdapter:
        return SecEdgarFinancialFactsAdapter(
            json_fetcher=self.json,
            cover_fetcher=self.cover,
            clock=lambda: NOW,
            user_agent="Fixture Tester fixture@example.com",
            ticker_overrides=overrides,
        )


def _ocf_request(ticker: str = "XOM", as_of: datetime | None = None) -> FinancialFactRequest:
    return FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id=ticker,
        field_name=FinancialField.OPERATING_CASH_FLOW,
        provider_id=SEC_PROVIDER_ID,
        basis="fiscal_year",
        observation_count=1,
        as_of=as_of,
    )


def _scope(adapter: SecEdgarFinancialFactsAdapter, as_of: datetime | None = None, ticker: str = "XOM") -> Any:
    return adapter.analysis_scope(subject_id=ticker, provider_id=SEC_PROVIDER_ID, as_of=as_of)


# --- a ticker listed under several CIKs is refused ----------------------------------------


def test_a_ticker_listed_under_two_ciks_is_refused_naming_the_ticker_and_both_ciks() -> None:
    sec = _Sec([("XOM", _NEW_CIK), ("XOM", _OLD_CIK)], {_OLD_CIK: _submissions(_OLD_CIK)})
    for call in (
        lambda: _scope(sec.adapter()).__enter__(),
        lambda: sec.adapter().fetch_facts(_ocf_request(), effective_as_of=NOW),
        lambda: sec.adapter().fetch_instant_series(
            InstantSeriesRequest("XOM", FinancialField.TOTAL_ASSETS, SEC_PROVIDER_ID, (NOW.date(),)),
            effective_as_of=NOW,
        ),
    ):
        with pytest.raises(FinancialProviderError) as caught:
            call()
        assert caught.value.kind is ProviderFailureKind.NO_DATA
        message = str(caught.value)
        assert "XOM" in message
        assert f"{_OLD_CIK:010d}" in message
        assert f"{_NEW_CIK:010d}" in message
        assert "providers/sec_edgar.toml" in message


def test_the_order_of_the_ticker_file_never_decides_between_two_ciks() -> None:
    for rows in ([("XOM", _NEW_CIK), ("XOM", _OLD_CIK)], [("XOM", _OLD_CIK), ("XOM", _NEW_CIK)]):
        sec = _Sec(rows, {_OLD_CIK: _submissions(_OLD_CIK)})
        with pytest.raises(FinancialProviderError) as caught:
            _scope(sec.adapter()).__enter__()
        assert caught.value.kind is ProviderFailureKind.NO_DATA


def test_an_override_resolves_a_ticker_listed_under_two_ciks() -> None:
    sec = _Sec([("XOM", _NEW_CIK), ("XOM", _OLD_CIK)], {_OLD_CIK: _submissions(_OLD_CIK)})
    adapter = sec.adapter({"XOM": f"{_OLD_CIK:010d}"})
    snapshot = adapter.create_analysis_snapshot(subject_id="XOM", as_of=None)
    assert snapshot.cik == f"{_OLD_CIK:010d}"
    assert snapshot.cik_source == CIK_SOURCE_OVERRIDE


# --- an override --------------------------------------------------------------------------------


def test_an_override_wins_over_the_ticker_file_and_shows_in_the_provenance() -> None:
    sec = _Sec(
        [("XOM", _NEW_CIK)], {_OLD_CIK: _submissions(_OLD_CIK), _NEW_CIK: _submissions(_NEW_CIK, {"a-26-1": "8-K"})}
    )
    adapter = sec.adapter({"XOM": f"{_OLD_CIK:010d}"})

    with _scope(adapter):
        facts = adapter.fetch_facts(_ocf_request(), effective_as_of=NOW)

    assert facts
    assert all(fact.notes[-1] == "cik_source=override" for fact in facts)
    assert all(f"cik={_OLD_CIK:010d}" in fact.notes for fact in facts)
    assert not any(f"CIK{_NEW_CIK:010d}" in url for url in sec.urls)


def test_an_empty_override_table_changes_nothing() -> None:
    sec = _Sec([("XOM", _OLD_CIK)], {_OLD_CIK: _submissions(_OLD_CIK)})
    plain = sec.adapter()
    empty = sec.adapter({})
    with _scope(plain):
        expected = plain.fetch_facts(_ocf_request(), effective_as_of=NOW)
    with _scope(empty):
        actual = empty.fetch_facts(_ocf_request(), effective_as_of=NOW)

    assert actual == expected
    assert empty.create_analysis_snapshot(subject_id="XOM", as_of=None).cik_source == CIK_SOURCE_TICKER_FILE
    assert all(not any(note.startswith("cik_source") for note in fact.notes) for fact in actual)


def test_an_override_for_a_cik_sec_does_not_know_is_refused_naming_the_override() -> None:
    sec = _Sec([("XOM", _OLD_CIK)], {_OLD_CIK: _submissions(_OLD_CIK)})
    adapter = sec.adapter({"XOM": "0000099999"})
    for call in (
        lambda: adapter.create_analysis_snapshot(subject_id="XOM", as_of=None),
        lambda: sec.adapter({"XOM": "0000099999"}).fetch_facts(_ocf_request(), effective_as_of=NOW),
    ):
        with pytest.raises(FinancialProviderError) as caught:
            call()
        assert caught.value.kind is ProviderFailureKind.NO_DATA
        assert "XOM = 99999" in str(caught.value)
        assert "override" in str(caught.value)


def test_an_unknown_cik_without_an_override_keeps_the_plain_not_found_failure() -> None:
    sec = _Sec([("XOM", 99999)], {})
    with pytest.raises(FinancialProviderError) as caught:
        sec.adapter().create_analysis_snapshot(subject_id="XOM", as_of=None)
    assert str(caught.value) == "not found"


def test_an_override_for_a_cik_the_ticker_file_does_not_list_reads_the_tickers_from_the_submissions() -> None:
    sec = _Sec([("XOM", _NEW_CIK)], {_OLD_CIK: _submissions(_OLD_CIK)})
    adapter = sec.adapter({"XOM": f"{_OLD_CIK:010d}"})
    request = _ocf_request()
    eps = FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="XOM",
        field_name=FinancialField.EPS,
        provider_id=SEC_PROVIDER_ID,
        basis="fiscal_year",
        observation_count=1,
    )
    with _scope(adapter):
        # One ticker in the submissions data: the per-share fields are read (the fixture has no EPS concept, so none).
        assert adapter.fetch_facts(eps, effective_as_of=NOW) == ()
        assert adapter.fetch_facts(request, effective_as_of=NOW)
    sec.submissions[_OLD_CIK]["tickers"] = ["XOM", "XOMX"]
    with _scope(sec.adapter({"XOM": f"{_OLD_CIK:010d}"})) as _:
        assert sec.adapter({"XOM": f"{_OLD_CIK:010d}"}).fetch_facts(eps, effective_as_of=NOW) == ()


# --- a registrant without an annual report --------------------------------------------------

_NO_ANNUAL = {"a-26-1": "8-K", "b-26-2": "10-Q"}


def test_a_registrant_that_has_filed_no_annual_report_fails_with_no_data_on_every_request_path() -> None:
    """The shape of ExxonMobil Holdings Corp: quarterly and current reports in both sources, no annual report."""
    sec = _Sec([("XOM", _NEW_CIK)], {_NEW_CIK: _submissions(_NEW_CIK, _NO_ANNUAL)}, facts_form="10-Q")
    series = InstantSeriesRequest("XOM", FinancialField.TOTAL_ASSETS, SEC_PROVIDER_ID, (NOW.date(),))
    for call in (
        lambda: sec.adapter().create_analysis_snapshot(subject_id="XOM", as_of=None),
        lambda: sec.adapter().create_analysis_snapshot(subject_id="XOM", as_of=datetime(2020, 1, 1, tzinfo=UTC)),
        lambda: _scope(sec.adapter()).__enter__(),
        lambda: sec.adapter().fetch_facts(_ocf_request(), effective_as_of=NOW),
        lambda: sec.adapter().fetch_instant_series(series, effective_as_of=NOW),
    ):
        with pytest.raises(FinancialProviderError) as caught:
            call()
        assert caught.value.kind is ProviderFailureKind.NO_DATA
        message = str(caught.value)
        assert f"{_NEW_CIK:010d}" in message
        assert "has filed no annual report" in message
        assert "providers/sec_edgar.toml" in message
        assert "XOM = <cik>" in message


def test_an_empty_recent_block_with_no_annual_facts_is_a_registrant_with_no_annual_report() -> None:
    sec = _Sec([("XOM", _NEW_CIK)], {_NEW_CIK: {"filings": {"recent": {}}}}, facts_form="10-Q")
    with pytest.raises(FinancialProviderError) as caught:
        sec.adapter().create_analysis_snapshot(subject_id="XOM", as_of=None)
    assert caught.value.kind is ProviderFailureKind.NO_DATA


def test_an_empty_or_incomplete_recent_block_with_annual_facts_decides_nothing() -> None:
    candidates: tuple[dict[str, Any], ...] = ({"filings": {"recent": {}}}, _submissions(_NEW_CIK, _NO_ANNUAL))
    for submissions in candidates:
        sec = _Sec([("XOM", _NEW_CIK)], {_NEW_CIK: submissions}, facts_form="10-K")
        adapter = sec.adapter()
        snapshot = adapter.create_analysis_snapshot(subject_id="XOM", as_of=None)
        assert snapshot.after_boundary_message is None
        with _scope(adapter):
            # The existing behavior applies: no failure and no after-the-boundary signal.
            assert adapter.fetch_facts(_ocf_request(), effective_as_of=NOW) == ()


def test_a_registrant_with_extra_pages_is_decided_only_when_the_boundary_precedes_every_dated_filing() -> None:
    sec = _Sec([("XOM", _NEW_CIK)], {_NEW_CIK: _submissions(_NEW_CIK, pages="2000-01-01")}, facts_form="10-Q")
    # The boundary is inside the history the pages cover: older annual filings may exist, so nothing is decided.
    snapshot = sec.adapter().create_analysis_snapshot(subject_id="XOM", as_of=datetime(2010, 1, 1, tzinfo=UTC))
    assert snapshot.after_boundary_message is None
    # The boundary precedes the page range and the recent block: nothing had been filed, and no page is read.
    snapshot = sec.adapter().create_analysis_snapshot(subject_id="XOM", as_of=datetime(1999, 1, 1, tzinfo=UTC))
    assert snapshot.after_boundary_message is not None
    assert "had filed nothing by the boundary 1999-01-01" in snapshot.after_boundary_message
    assert "earliest filing is dated 2000-01-01" in snapshot.after_boundary_message
    assert not any("-submissions-001" in url for url in sec.urls)


_BEFORE_FILINGS = datetime(2022, 6, 1, tzinfo=UTC)


def test_a_registrant_whose_annual_reports_all_came_after_the_boundary_is_unavailable_not_failed() -> None:
    sec = _Sec([("XOM", _OLD_CIK)], {_OLD_CIK: _submissions(_OLD_CIK)})
    adapter = sec.adapter()
    snapshot = adapter.create_analysis_snapshot(subject_id="XOM", as_of=_BEFORE_FILINGS)
    message = snapshot.after_boundary_message
    assert message is not None
    assert "filed its first annual report on 2023-02-01" in message
    assert f"{_OLD_CIK:010d}" in message
    assert "providers/sec_edgar.toml" in message
    assert snapshot.latest_annual_accession is None

    with _scope(adapter, _BEFORE_FILINGS):
        with pytest.raises(FactsNotAvailableAsOf) as caught:
            adapter.fetch_facts(_ocf_request(as_of=_BEFORE_FILINGS), effective_as_of=_BEFORE_FILINGS)
        assert not isinstance(caught.value, FinancialProviderError)
        assert str(caught.value) == message
        listing = adapter.resolve_cover_listing(CoverListingRequest("XOM", SEC_PROVIDER_ID))
        assert listing.reason is CoverUnavailableReason.ACCEPTED_AFTER_BOUNDARY
    assert adapter.resolve_as_filed_sic(snapshot).reason is SicUnavailableReason.ACCEPTED_AFTER_BOUNDARY
    assert sec.cover_urls == []


def test_the_balance_sheet_series_of_such_a_registrant_is_after_the_boundary_with_the_same_message() -> None:
    sec = _Sec([("XOM", _OLD_CIK)], {_OLD_CIK: _submissions(_OLD_CIK)})
    adapter = sec.adapter()
    message = adapter.create_analysis_snapshot(subject_id="XOM", as_of=_BEFORE_FILINGS).after_boundary_message
    request = InstantSeriesRequest(
        "XOM", FinancialField.TOTAL_ASSETS, SEC_PROVIDER_ID, (datetime(2021, 12, 31).date(),), as_of=_BEFORE_FILINGS
    )

    result = adapter.fetch_instant_series(request, effective_as_of=NOW)

    assert [item.reason for item in result.absences] == [InstantAbsenceReason.AFTER_BOUNDARY]
    assert result.absences[0].detail == message


def test_no_anchor_filing_remains_the_reason_for_a_ticker_with_no_cik() -> None:
    sec = _Sec([("ZZZ", _OLD_CIK)], {_OLD_CIK: _submissions(_OLD_CIK)})
    adapter = sec.adapter()
    snapshot = adapter.create_analysis_snapshot(subject_id="XOM", as_of=None)
    assert snapshot.cik is None
    assert adapter.resolve_as_filed_sic(snapshot).reason is SicUnavailableReason.NO_ANCHOR_FILING
    with _scope(adapter):
        listing = adapter.resolve_cover_listing(CoverListingRequest("XOM", SEC_PROVIDER_ID))
        assert listing.reason is CoverUnavailableReason.NO_ANCHOR_FILING
    series = InstantSeriesRequest("XOM", FinancialField.TOTAL_ASSETS, SEC_PROVIDER_ID, (NOW.date(),))
    assert [i.reason for i in adapter.fetch_instant_series(series, effective_as_of=NOW).absences] == [
        InstantAbsenceReason.NO_ANCHOR_FILING
    ]
