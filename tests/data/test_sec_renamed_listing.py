"""A ticker renamed since the anchor filing: affirmed only when the one share line of the anchor cover is renamed."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from investment_analysis_engine.analysis.shared.market_cap import ListingCheck, listing_check_from_resolution
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.core.package_root import PACKAGE_ROOT
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.financial.facts import FinancialProviderError
from investment_analysis_engine.data.sec_edgar.cover_listing import (
    CoverListingRequest,
    CoverReaderPolicy,
    CoverUnavailableReason,
    ListingEvidence,
    ListingRename,
    ListingResolution,
    SecurityKind,
    read_renamed_listing,
)
from investment_analysis_engine.data.sec_edgar.financial_facts import (
    SEC_PROVIDER_ID,
    SecEdgarAnalysisSnapshot,
    SecEdgarFinancialFactsAdapter,
)

FIXTURES = PACKAGE_ROOT / "evaluation" / "fixtures" / "sec_edgar" / "cover_pages"
NOW = datetime(2026, 10, 27, 12, tzinfo=UTC)
_FY2020, _FY2025 = "0001326801-21-000014", "0001628280-26-003942"
_ACCEPTED_2020, _ACCEPTED_2025 = "2021-01-28T02:13:48.000Z", "2026-01-29T00:13:46.000Z"
_URL = "https://www.sec.gov/Archives/edgar/data/1326801/{folder}/R1.htm"
_BOUNDARY_2021 = datetime(2021, 6, 1, tzinfo=UTC)


def _read(name: str) -> str:
    return (FIXTURES / f"{name}.r1.htm").read_text(encoding="utf-8")


def _row(concept: str, label: str, value: str) -> str:
    link = f'<a class="a" href="javascript:void(0);" onclick="Show.showAR( this, \'defref_dei_{concept}\', window );">'
    return f'<tr class="re"><td class="pl">{link}{label}</a></td><td class="text">{value}</td></tr>'


def _cover(cik: str, *shares: tuple[str, str | None], form: str = "10-K") -> str:
    """Return a synthetic cover that registers each (title, symbol) under the CIK on NYSE."""
    rows = [_row("DocumentType", "Document Type", form), _row("EntityCentralIndexKey", "Key", cik)]
    for title, symbol in shares:
        rows.append(_row("Security12bTitle", "Title", title))
        if symbol is not None:
            rows.append(_row("TradingSymbol", "Trading Symbol", symbol))
        rows.append(_row("SecurityExchangeName", "Exchange", "NYSE"))
    return '<table class="report">' + "".join(rows) + "</table>"


def _renamed(anchor: str, latest: str, *, ticker: str, cik: str) -> ListingEvidence | None:
    return read_renamed_listing(
        anchor,
        latest,
        ticker=ticker,
        cik=cik,
        anchor_accession="0000000001-21-000001",
        anchor_form="10-K",
        latest_accession="0000000001-26-000001",
        latest_form="10-K",
        latest_accepted_at=NOW,
        latest_source_url="https://www.sec.gov/Archives/edgar/data/1/000000000126000001/R1.htm",
        retrieved_at=NOW,
    )


# --- the reader ---------------------------------------------------------------------------------------------------


def test_meta_platforms_fb_on_the_fiscal_2020_cover_is_the_meta_on_the_latest_cover() -> None:
    evidence = _renamed(_read("meta_fy2020"), _read("meta_fy2025"), ticker="META", cik="1326801")

    assert evidence is not None
    assert evidence.kind is SecurityKind.SHARE
    assert evidence.ticker == "META"
    assert evidence.title == "Class A Common Stock, $0.000006 par value"
    assert evidence.rename == ListingRename(
        anchor_accession="0000000001-21-000001",
        anchor_form="10-K",
        anchor_symbol="FB",
        latest_accession="0000000001-26-000001",
        latest_form="10-K",
        latest_symbol="META",
    )


def test_the_old_symbol_is_not_listed_on_the_latest_cover_so_it_is_not_a_rename() -> None:
    assert _renamed(_read("meta_fy2020"), _read("meta_fy2025"), ticker="FB", cik="1326801") is None


def test_an_anchor_cover_with_two_share_lines_is_not_renamed() -> None:
    alphabet = _read("googl_fy2025")
    latest = _cover("0001652044", ("Class A Common Stock, $0.001 par value", "NEWA"))

    assert _renamed(alphabet, latest, ticker="NEWA", cik="1652044") is None


def test_an_anchor_cover_with_a_depositary_share_is_not_renamed() -> None:
    latest = _cover("0000019617", ("Common stock", "JPMX"))

    assert _renamed(_read("jpm_fy2025"), latest, ticker="JPMX", cik="19617") is None


@pytest.mark.parametrize(
    "shares",
    [
        (("Common stock", "NEW"), ("Class B Common Stock", "NEW.B")),
        (("Common stock", "OTHER"),),
        (("Warrants", "NEW"),),
    ],
)
def test_the_latest_cover_must_list_the_ticker_as_its_only_share_line(shares: tuple[tuple[str, str], ...]) -> None:
    anchor = _cover("0000000001", ("Common stock", "OLD"))

    assert _renamed(anchor, _cover("0000000001", *shares), ticker="NEW", cik="1") is None


def test_a_synthetic_one_line_anchor_and_latest_cover_is_a_rename() -> None:
    anchor = _cover("0000000001", ("Common stock", "OLD"), ("Notes due 2030", "OLD30"))
    latest = _cover("0000000001", ("Common stock", "NEW"), ("Notes due 2030", "NEW30"))

    evidence = _renamed(anchor, latest, ticker="new", cik="1")

    assert evidence is not None
    assert evidence.rename is not None
    assert (evidence.rename.anchor_symbol, evidence.rename.latest_symbol) == ("OLD", "NEW")


@pytest.mark.parametrize(
    ("anchor", "latest"),
    [
        (_cover("0000000001", ("Common stock", None)), _cover("0000000001", ("Common stock", "NEW"))),
        (_cover("0000000001", ("Common stock", "OLD")), _cover("0000000002", ("Common stock", "NEW"))),
        (_cover("0000000001", ("Common stock", "OLD")), _cover("0000000001", ("Common stock", "NEW"), form="10-Q")),
        (_cover("0000000001", ("Common stock", "OLD")), "<html>not a cover</html>"),
        (_cover("0000000001", ("Common stock", "OLD")), _cover("0000000001")),
    ],
)
def test_a_cover_that_cannot_be_used_leaves_the_ticker_unrenamed(anchor: str, latest: str) -> None:
    assert _renamed(anchor, latest, ticker="NEW", cik="1") is None


def test_an_evidence_with_a_rename_is_a_share_and_a_rename_needs_its_parts() -> None:
    rename = ListingRename("0000000001-21-000001", "10-K", "FB", "0000000001-26-000001", "10-K", "META")
    with pytest.raises(ValueError, match="renamed listing is a share"):
        ListingEvidence(
            ticker="META",
            kind=SecurityKind.OTHER,
            title="x",
            cik="0000000001",
            accession="0000000001-26-000001",
            form="10-K",
            accepted_at=NOW,
            source_url="u",
            retrieved_at=NOW,
            rename=rename,
        )
    with pytest.raises(ValueError, match="dashed accession"):
        ListingRename("bad", "10-K", "FB", "0000000001-26-000001", "10-K", "META")
    with pytest.raises(ValueError, match="forms and symbols"):
        ListingRename("0000000001-21-000001", "10-K", " ", "0000000001-26-000001", "10-K", "META")


# --- the listing check ----------------------------------------------------------------------------------------------


def test_a_renamed_listing_is_affirmed_and_records_both_accessions_and_symbols() -> None:
    evidence = _renamed(_read("meta_fy2020"), _read("meta_fy2025"), ticker="META", cik="1326801")
    assert evidence is not None

    check = listing_check_from_resolution(ListingResolution(evidence=evidence))

    assert check.affirmed
    assert check.accession == "0000000001-21-000001"
    assert check.rename == evidence.rename


def test_a_refused_listing_check_records_no_rename() -> None:
    rename = ListingRename("0000000001-21-000001", "10-K", "FB", "0000000001-26-000001", "10-K", "META")
    with pytest.raises(ValueError, match="Only an affirmed"):
        ListingCheck(affirmed=False, reason_code=ReasonCode.MISSING_FACT, reason="no", rename=rename)


# --- the adapter ----------------------------------------------------------------------------------------------------


class _Sec:
    """Meta Platforms filings and two covers, counting the cover requests."""

    def __init__(
        self,
        *,
        covers: Mapping[str, str] | None = None,
        filings: tuple[tuple[str, str, str], ...] | None = None,
    ) -> None:
        self.filings = filings or ((_FY2025, "10-K", _ACCEPTED_2025), (_FY2020, "10-K", _ACCEPTED_2020))
        self.cover_urls: list[str] = []
        self.covers = dict(
            covers
            or {
                _URL.format(folder=_FY2020.replace("-", "")): _read("meta_fy2020"),
                _URL.format(folder=_FY2025.replace("-", "")): _read("meta_fy2025"),
            }
        )

    def json(self, url: str, *, headers: Mapping[str, str], not_found: ProviderFailureKind, provider_id: str) -> object:  # noqa: ARG002
        if url.endswith("company_tickers.json"):
            return {"0": {"cik_str": 1326801, "ticker": "META", "title": "Meta Platforms, Inc."}}
        if "/companyfacts/" in url:
            return {"cik": 1326801, "entityName": "Meta", "facts": {"us-gaap": {}}}
        accepted = [item[2] for item in self.filings]
        return {
            "tickers": ["META"],
            "filings": {
                "recent": {
                    "accessionNumber": [item[0] for item in self.filings],
                    "form": [item[1] for item in self.filings],
                    "filingDate": [stamp[:10] for stamp in accepted],
                    "acceptanceDateTime": accepted,
                    "primaryDocument": ["a.htm"] * len(self.filings),
                }
            },
        }

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


def _resolve(adapter: SecEdgarFinancialFactsAdapter, ticker: str, as_of: datetime | None) -> Any:
    with adapter.analysis_scope(subject_id=ticker, provider_id=SEC_PROVIDER_ID, as_of=as_of):
        return adapter.resolve_cover_listing(CoverListingRequest(ticker, SEC_PROVIDER_ID))


def test_with_an_as_of_the_renamed_ticker_reads_the_anchor_cover_and_one_more_and_is_affirmed() -> None:
    sec = _Sec()
    adapter = sec.adapter()

    with adapter.analysis_scope(subject_id="META", provider_id=SEC_PROVIDER_ID, as_of=_BOUNDARY_2021):
        first = adapter.resolve_cover_listing(CoverListingRequest("META", SEC_PROVIDER_ID))
        second = adapter.resolve_cover_listing(CoverListingRequest("META", SEC_PROVIDER_ID))

    assert first == second
    assert first.evidence is not None
    assert first.evidence.rename == ListingRename(_FY2020, "10-K", "FB", _FY2025, "10-K", "META")
    assert len(sec.cover_urls) == 2
    check = listing_check_from_resolution(first)
    assert check.affirmed
    assert check.accession == _FY2020


def test_no_second_cover_is_read_when_the_ticker_is_on_the_anchor_cover_or_there_is_no_as_of() -> None:
    on_anchor = _Sec()
    result = _resolve(on_anchor.adapter({"FB": "0001326801"}), "FB", _BOUNDARY_2021)
    assert result.evidence.kind is SecurityKind.SHARE
    assert result.evidence.rename is None
    assert len(on_anchor.cover_urls) == 1

    without_as_of = _Sec()
    result = _resolve(without_as_of.adapter(), "META", None)
    assert result.evidence.kind is SecurityKind.SHARE
    assert result.evidence.rename is None
    assert len(without_as_of.cover_urls) == 1


def test_a_ticker_that_is_on_neither_cover_stays_not_listed_after_both_are_read() -> None:
    sec = _Sec()
    result = _resolve(sec.adapter({"ZZZ": "0001326801"}), "ZZZ", _BOUNDARY_2021)

    assert result.evidence.kind is SecurityKind.NOT_LISTED
    assert len(sec.cover_urls) == 2
    assert listing_check_from_resolution(result).reason_code is ReasonCode.MISSING_FACT


def test_a_latest_cover_that_is_missing_leaves_the_ticker_not_listed() -> None:
    sec = _Sec(covers={_URL.format(folder=_FY2020.replace("-", "")): _read("meta_fy2020")})
    result = _resolve(sec.adapter(), "META", _BOUNDARY_2021)

    assert result.evidence.kind is SecurityKind.NOT_LISTED
    assert result.evidence.rename is None


def _anchor_url(accession: str) -> str:
    return _URL.format(folder=accession.replace("-", ""))


def _foreign_anchor_cover() -> str:
    return _cover("0001326801", ("Ordinary Shares", "FBX"), form="20-F")


def test_an_anchor_that_is_not_a_10_k_makes_no_second_request_even_when_a_later_10_k_exists() -> None:
    anchor_20f = "0001326801-21-000020"
    sec = _Sec(
        covers={_anchor_url(anchor_20f): _foreign_anchor_cover(), _anchor_url(_FY2025): _read("meta_fy2025")},
        filings=((_FY2025, "10-K", _ACCEPTED_2025), (anchor_20f, "20-F", _ACCEPTED_2020)),
    )

    result = _resolve(sec.adapter(), "META", _BOUNDARY_2021)

    assert result.evidence.kind is SecurityKind.NOT_LISTED
    assert result.evidence.rename is None
    assert sec.cover_urls == [_anchor_url(anchor_20f)]


def test_a_registrant_with_no_10_k_at_all_makes_no_second_request() -> None:
    anchor_20f = "0001326801-21-000020"
    sec = _Sec(
        covers={_anchor_url(anchor_20f): _foreign_anchor_cover()},
        filings=((anchor_20f, "20-F", _ACCEPTED_2020),),
    )

    result = _resolve(sec.adapter(), "META", _BOUNDARY_2021)

    assert result.evidence.kind is SecurityKind.NOT_LISTED
    assert sec.cover_urls == [_anchor_url(anchor_20f)]


def test_a_ticker_on_neither_cover_when_the_anchor_is_the_latest_10_k_makes_no_second_request() -> None:
    sec = _Sec()

    result = _resolve(sec.adapter({"ZZZ": "0001326801"}), "ZZZ", None)

    assert result.evidence.kind is SecurityKind.NOT_LISTED
    assert result.evidence.rename is None
    assert sec.cover_urls == [_anchor_url(_FY2025)]


def test_a_latest_10_k_not_accepted_after_the_anchor_leaves_the_ticker_not_listed() -> None:
    """Two 10-Ks accepted at one instant leave a hand-built snapshot whose anchor is the lower accession.

    The adapter itself picks the higher accession as the anchor, so only such a snapshot reaches this guard.
    """
    lower, higher = "0001326801-21-000001", "0001326801-21-000002"
    moment = datetime(2021, 1, 28, 2, 13, 48, tzinfo=UTC)
    sec = _Sec(covers={_anchor_url(lower): _read("meta_fy2020"), _anchor_url(higher): _read("meta_fy2025")})
    adapter = sec.adapter()
    snapshot = SecEdgarAnalysisSnapshot(
        subject_id="META",
        cik="0001326801",
        as_of=_BOUNDARY_2021,
        retrieved_at=NOW,
        company_facts={},
        acceptance_by_accession={lower: moment, higher: moment},
        accession_taxonomies={},
        latest_annual_accession=lower,
        eligible_annual_accessions=(lower,),
        taxonomy=None,
        filing_forms={lower: "10-K", higher: "10-K"},
    )
    fallback = ListingResolution(reason=CoverUnavailableReason.COVER_UNREADABLE)

    result = adapter._renamed_listing(  # noqa: SLF001
        CoverListingRequest("META", SEC_PROVIDER_ID),
        snapshot,
        anchor=(lower, "10-K", _read("meta_fy2020")),
        fallback=fallback,
    )

    assert result is fallback
    assert sec.cover_urls == []
