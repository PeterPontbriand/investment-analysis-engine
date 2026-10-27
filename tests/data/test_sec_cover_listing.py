"""The cover listing check: the rendered cover, its title vocabulary, the transport and the adapter's one request."""

import hashlib
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

import pytest

from investment_analysis_engine.core.package_root import PACKAGE_ROOT
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.financial.facts import FinancialProviderError
from investment_analysis_engine.data.financial.production import ProductionFinancialFactsProvider
from investment_analysis_engine.data.sec_edgar import financial_facts
from investment_analysis_engine.data.sec_edgar.cover_listing import (
    CoverListingProvider,
    CoverListingRequest,
    CoverReaderPolicy,
    CoverUnavailableReason,
    ListingEvidence,
    ListingResolution,
    SecurityKind,
    classify_title,
    cover_report_from_summary,
    cover_url,
    fetch_anchor_cover,
    fetch_cover,
    looks_like_cover,
    read_cover_listing,
    summary_url,
)
from investment_analysis_engine.data.sec_edgar.filing_document import FilingHeaderPolicy, FilingReaderPolicy
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID, SecEdgarFinancialFactsAdapter

FIXTURES = PACKAGE_ROOT / "evaluation" / "fixtures" / "sec_edgar" / "cover_pages"
NOW = datetime(2026, 10, 25, tzinfo=UTC)
_HEADERS = {"User-Agent": "Synthetic"}
_KEYWORDS: dict[str, Any] = {"not_found": ProviderFailureKind.NO_DATA, "provider_id": "sec_edgar"}


def _read(name: str) -> str:
    return (FIXTURES / f"{name}.r1.htm").read_text(encoding="utf-8")


def _listing(  # noqa: PLR0913
    markup: str,
    *,
    ticker: str,
    cik: str = "19617",
    accession: str = "0001628280-26-008131",
    form: str = "10-K",
    accepted_at: datetime = NOW,
    boundary: datetime = NOW,
) -> ListingResolution:
    return read_cover_listing(
        markup,
        ticker=ticker,
        cik=cik,
        accession=accession,
        form=form,
        accepted_at=accepted_at,
        boundary=boundary,
        source_url="https://www.sec.gov/Archives/edgar/data/19617/000162828026008131/R1.htm",
        retrieved_at=NOW,
    )


# (fixture, cik, accession, form, ticker, kind, title as filed): each is a cover captured from EDGAR.
_CASES = [
    ("jpm_fy2025", "19617", "0001628280-26-008131", "10-K", "JPM", SecurityKind.SHARE, "Common stock"),
    (
        "jpm_fy2025",
        "19617",
        "0001628280-26-008131",
        "10-K",
        "JPM PR D",
        SecurityKind.DEPOSITARY_SHARE,
        "Depositary Shares, each representing a one-four hundredth interest in a share of 5.75% Non-Cumulative "
        "Preferred Stock, Series DD",
    ),
    (
        "pld_fy2025",
        "1045609",
        "0001193125-26-051453",
        "10-K",
        "PLD",
        SecurityKind.SHARE,
        "Common Stock, $0.01 par value",
    ),
    (
        "duk_fy2025",
        "1326160",
        "0001326160-26-000014",
        "10-K",
        "DUK",
        SecurityKind.SHARE,
        "Common Stock, $0.001 par value",
    ),
    (
        "duk_fy2025",
        "1326160",
        "0001326160-26-000014",
        "10-K",
        "DUK PR A",
        SecurityKind.DEPOSITARY_SHARE,
        "Depositary Shares",
    ),
    (
        "duk_fy2025",
        "1326160",
        "0001326160-26-000014",
        "10-K",
        "DUKB",
        SecurityKind.OTHER,
        "5.625% Junior Subordinated Debentures",
    ),
    ("de_fy2025", "315189", "0001104659-25-122321", "10-K", "DE", SecurityKind.SHARE, "Common stock, $1 par value"),
    ("de_fy2025", "315189", "0001104659-25-122321", "10-K", "DE28", SecurityKind.OTHER, "6.55% Debentures Due 2028"),
    (
        "wmt_fy2026",
        "104169",
        "0000104169-26-000055",
        "10-K",
        "WMT",
        SecurityKind.SHARE,
        "Common Stock, par value $0.10 per share",
    ),
    ("wmt_fy2026", "104169", "0000104169-26-000055", "10-K", "WMT26", SecurityKind.OTHER, "2.550% Notes due 2026"),
    (
        "mrna_fy2025",
        "1682852",
        "0001682852-26-000033",
        "10-K",
        "MRNA",
        SecurityKind.SHARE,
        "Common stock, par value $0.0001 per share",
    ),
    (
        "mnst_fy2025",
        "865752",
        "0001104659-26-020831",
        "10-K",
        "MNST",
        SecurityKind.SHARE,
        "Common Stock, $0.005 par value per share",
    ),
    (
        "googl_fy2025",
        "1652044",
        "0001652044-26-000018",
        "10-K",
        "GOOGL",
        SecurityKind.SHARE,
        "Class A Common Stock, $0.001 par value",
    ),
    (
        "googl_fy2025",
        "1652044",
        "0001652044-26-000018",
        "10-K",
        "GOOG",
        SecurityKind.SHARE,
        "Class C Capital Stock, $0.001 par value",
    ),
    (
        "hon_fy2025",
        "773840",
        "0000773840-26-000013",
        "10-K",
        "HON",
        SecurityKind.SHARE,
        "Common Stock, par value $1 per share",
    ),
    (
        "mdt_fy2026",
        "1613103",
        "0001628280-26-044354",
        "10-K",
        "MDT",
        SecurityKind.SHARE,
        "Ordinary shares, par value $0.0001 per share",
    ),
    (
        "mdt_fy2026",
        "1613103",
        "0001628280-26-044354",
        "10-K",
        "MDT/27",
        SecurityKind.OTHER,
        "1.125% Senior Notes due 2027",
    ),
    (
        "adap_fy2024",
        "1621227",
        "0001558370-25-003544",
        "10-K",
        "ADAP",
        SecurityKind.DEPOSITARY_SHARE,
        "American Depositary Shares, each representing",
    ),
    ("aldf_fy2025", "2031561", "0001104659-26-033988", "10-K", "ALDF", SecurityKind.SHARE, "Ordinary Shares"),
    ("aldf_fy2025", "2031561", "0001104659-26-033988", "10-K", "ALDF.U", SecurityKind.UNIT, "Units"),
    ("aldf_fy2025", "2031561", "0001104659-26-033988", "10-K", "ALDF.W", SecurityKind.WARRANT, "Warrants"),
    (
        "nly_fy2025",
        "1043219",
        "0001043219-26-000013",
        "10-K",
        "NLY",
        SecurityKind.SHARE,
        "Common Stock, par value $0.01 per share",
    ),
    (
        "nly_fy2025",
        "1043219",
        "0001043219-26-000013",
        "10-K",
        "NLY.F",
        SecurityKind.PREFERRED,
        "6.95% Series F Fixed-to-Floating Rate Cumulative Redeemable Preferred Stock",
    ),
    ("imaq_fy2026", "1846235", "0001213900-26-072115", "10-K", "IMAQ", SecurityKind.NOT_LISTED, None),
    ("imaq_fy2026_amended", "1846235", "0001213900-26-072601", "10-K/A", "IMAQ", SecurityKind.NOT_LISTED, None),
    (
        "pgac_fy2025_amended",
        "2030829",
        "0001213900-26-049303",
        "10-K/A",
        "PGAC",
        SecurityKind.SHARE,
        "Class A ordinary shares, par value $0.0001 per share",
    ),
    (
        "pgac_fy2025_amended",
        "2030829",
        "0001213900-26-049303",
        "10-K/A",
        "PGACU",
        SecurityKind.UNIT,
        "Units, consisting of one Class A ordinary share, $0.0001 par value, and one Right to acquire one-fifth of "
        "one Class A ordinary share",
    ),
    (
        "pgac_fy2025_amended",
        "2030829",
        "0001213900-26-049303",
        "10-K/A",
        "PGACR",
        SecurityKind.OTHER,
        "Rights, each whole right to acquire one-fifth of one Class A ordinary share",
    ),
    (
        "alb_fy2025_amended",
        "915913",
        "0000915913-26-000060",
        "10-K/A",
        "ALB",
        SecurityKind.SHARE,
        "COMMON STOCK, $.01 Par Value",
    ),
    (
        "alb_fy2025_amended",
        "915913",
        "0000915913-26-000060",
        "10-K/A",
        "ALB PR A",
        SecurityKind.DEPOSITARY_SHARE,
        "DEPOSITARY SHARES, each representing a 1/20th interest in a share of 7.25% Series A Mandatory Convertible "
        "Preferred Stock",
    ),
    (
        "ipgp_fy2025_amended",
        "1111928",
        "0001111928-26-000068",
        "10-K/A",
        "IPGP",
        SecurityKind.SHARE,
        "Common Stock, Par Value $0.0001 per share",
    ),
    (
        "egy_fy2025_amended",
        "894627",
        "0000894627-26-000017",
        "10-K/A",
        "EGY",
        SecurityKind.SHARE,
        "Common Stock, par value $0.10",
    ),
    (
        "ofg_fy2025_amended",
        "1030469",
        "0001030469-26-000019",
        "10-K/A",
        "OFG",
        SecurityKind.SHARE,
        "Common shares, par value $1.00 per share",
    ),
    (
        "inva_fy2025_amended",
        "1080014",
        "0001193125-26-128939",
        "10-K/A",
        "INVA",
        SecurityKind.SHARE,
        "Common Stock $0.01 Par Value",
    ),
    # The widened sample: the latest 10-K of large filers whose titles are not those above.
    ("brk_fy2025", "1067983", "0001193125-26-083899", "10-K", "BRK.B", SecurityKind.SHARE, "Class B Common Stock"),
    ("brk_fy2025", "1067983", "0001193125-26-083899", "10-K", "BRK.A", SecurityKind.SHARE, "Class A Common Stock"),
    (
        "brk_fy2025",
        "1067983",
        "0001193125-26-083899",
        "10-K",
        "BRK27",
        SecurityKind.OTHER,
        "1.125% Senior Notes due 2027",
    ),
    ("pg_fy2026", "80424", "0000080424-26-000103", "10-K", "PG", SecurityKind.SHARE, "Common Stock, without Par Value"),
    ("pg_fy2026", "80424", "0000080424-26-000103", "10-K", "PG26D", SecurityKind.OTHER, "0.110% Notes due 2026"),
    (
        "pep_fy2025",
        "77476",
        "0000077476-26-000007",
        "10-K",
        "PEP",
        SecurityKind.SHARE,
        "Common Stock, par value 1-2/3 cents per share",
    ),
    (
        "pep_fy2025",
        "77476",
        "0000077476-26-000007",
        "10-K",
        "PEP26",
        SecurityKind.OTHER,
        "2.625% Senior Notes Due 2026",
    ),
    (
        "cat_fy2025",
        "18230",
        "0000018230-26-000008",
        "10-K",
        "CAT",
        SecurityKind.SHARE,
        "Common Stock ($1.00 par value)",
    ),
    (
        "cat_fy2025",
        "18230",
        "0000018230-26-000008",
        "10-K",
        "CAT35",
        SecurityKind.OTHER,
        "5.3% Debentures due September 15, 2035",
    ),
    (
        "lin_fy2025",
        "1707925",
        "0001628280-26-011430",
        "10-K",
        "LIN",
        SecurityKind.SHARE,
        "Ordinary shares (\u20ac0.001 nominal value per share)",
    ),
    (
        "cb_fy2025",
        "896159",
        "0000896159-26-000005",
        "10-K",
        "CB",
        SecurityKind.SHARE,
        "Common Shares, par value CHF 0.50 per share",
    ),
    (
        "cb_fy2025",
        "896159",
        "0000896159-26-000005",
        "10-K",
        "CB/27",
        SecurityKind.OTHER,
        "Guarantee of Chubb INA Holdings LLC 0.875% Senior Notes due 2027",
    ),
    ("lly_fy2025", "59478", "0000059478-26-000013", "10-K", "LLY", SecurityKind.SHARE, "Common Stock (no par value)"),
    ("lly_fy2025", "59478", "0000059478-26-000013", "10-K", "LLY26", SecurityKind.OTHER, "1.625% Notes due 2026"),
    (
        "t_fy2025",
        "732717",
        "0000732717-26-000120",
        "10-K",
        "T",
        SecurityKind.SHARE,
        "Common Shares (Par Value $1.00 Per Share)",
    ),
    (
        "t_fy2025",
        "732717",
        "0000732717-26-000120",
        "10-K",
        "T PRA",
        SecurityKind.DEPOSITARY_SHARE,
        "Depositary Shares, each representing a 1/1000th interest in a share of"
        "5.000% Perpetual Preferred Stock, Series A",
    ),
    (
        "t_fy2025",
        "732717",
        "0000732717-26-000120",
        "10-K",
        "T 25B",
        SecurityKind.OTHER,
        "AT&T Inc. 3.550% Global Notes due November 18, 2025",
    ),
    (
        "wfc_fy2025",
        "72971",
        "0000072971-26-000133",
        "10-K",
        "WFC",
        SecurityKind.SHARE,
        "Common Stock, par value $1-2/3",
    ),
    (
        "wfc_fy2025",
        "72971",
        "0000072971-26-000133",
        "10-K",
        "WFC.PRL",
        SecurityKind.PREFERRED,
        "7.5% Non-Cumulative Perpetual Convertible Class A Preferred Stock, Series L",
    ),
    (
        "wfc_fy2025",
        "72971",
        "0000072971-26-000133",
        "10-K",
        "WFC.PRY",
        SecurityKind.DEPOSITARY_SHARE,
        "Depositary Shares, each representing a 1/1000th interest in a share of "
        "Non-Cumulative Perpetual Class A Preferred Stock, Series Y",
    ),
    (
        "c_fy2025",
        "831001",
        "0000831001-26-000011",
        "10-K",
        "C",
        SecurityKind.SHARE,
        "Common Stock, par value $.01 per share",
    ),
    (
        "c_fy2025",
        "831001",
        "0000831001-26-000011",
        "10-K",
        "C PR R",
        SecurityKind.DEPOSITARY_SHARE,
        "Dep Shs, represent 1/1,000th interest in a share of 6.250% Noncum Pref Stk, Ser II",
    ),
    (
        "bac_fy2025",
        "70858",
        "0000070858-26-000157",
        "10-K",
        "BAC",
        SecurityKind.SHARE,
        "Common Stock, par value $0.01 per share",
    ),
    (
        "bac_fy2025",
        "70858",
        "0000070858-26-000157",
        "10-K",
        "BAC PRL",
        SecurityKind.PREFERRED,
        "7.25% Non-Cumulative Perpetual Convertible Preferred Stock, Series L",
    ),
    (
        "bac_fy2025",
        "70858",
        "0000070858-26-000157",
        "10-K",
        "BAC PRE",
        SecurityKind.DEPOSITARY_SHARE,
        "Depositary Shares, each representing a 1/1,000th interest in a share",
    ),
]


@pytest.mark.parametrize(("name", "cik", "accession", "form", "ticker", "kind", "title"), _CASES)
def test_a_captured_cover_gives_the_kind_and_title_of_the_requested_ticker(  # noqa: PLR0913, PLR0917
    name: str, cik: str, accession: str, form: str, ticker: str, kind: SecurityKind, title: str | None
) -> None:
    resolution = _listing(_read(name), ticker=ticker, cik=cik, accession=accession, form=form)
    assert resolution.reason is None
    evidence = resolution.evidence
    assert isinstance(evidence, ListingEvidence)
    assert (evidence.kind, evidence.title) == (kind, title)
    assert (evidence.ticker, evidence.cik, evidence.accession, evidence.form) == (
        ticker,
        cik.zfill(10),
        accession,
        form,
    )


def test_alphabet_affirms_both_of_its_classes_on_their_class_titles() -> None:
    kinds = {
        ticker: _listing(_read("googl_fy2025"), ticker=ticker, cik="1652044", accession="0001652044-26-000018").evidence
        for ticker in ("GOOGL", "GOOG")
    }
    assert {ticker: item.kind for ticker, item in kinds.items() if item} == {
        "GOOGL": SecurityKind.SHARE,
        "GOOG": SecurityKind.SHARE,
    }


def test_the_requested_tickers_own_row_decides_whatever_the_other_rows_hold() -> None:
    jpm = _read("jpm_fy2025")
    assert _listing(jpm, ticker="JPM").evidence.kind is SecurityKind.SHARE  # type: ignore[union-attr]
    assert _listing(jpm, ticker="JPM PR D").evidence.kind is SecurityKind.DEPOSITARY_SHARE  # type: ignore[union-attr]
    spac = _read("aldf_fy2025")
    outcomes = {
        t: _listing(spac, ticker=t, cik="2031561", accession="0001104659-26-033988").evidence.kind  # type: ignore[union-attr]
        for t in ("ALDF", "ALDF.U", "ALDF.W")
    }
    assert outcomes == {"ALDF": SecurityKind.SHARE, "ALDF.U": SecurityKind.UNIT, "ALDF.W": SecurityKind.WARRANT}


def test_the_ticker_is_matched_case_insensitively_and_exactly() -> None:
    jpm = _read("jpm_fy2025")
    assert _listing(jpm, ticker=" jpm ").evidence.kind is SecurityKind.SHARE  # type: ignore[union-attr]
    for near in ("JP", "JPMX", "JPM-PR-D", "J P M"):
        assert _listing(jpm, ticker=near).evidence.kind is SecurityKind.NOT_LISTED  # type: ignore[union-attr]


_BRK_CIK = "1067983"
_BRK_ACCESSION = "0001193125-26-083899"


@pytest.mark.parametrize("ticker", ["BRK.B", "BRK-B", "BRK/B", " brk-b "])
def test_a_dot_a_dash_and_a_slash_are_the_same_separator_in_the_requested_ticker(ticker: str) -> None:
    evidence = _listing(_read("brk_fy2025"), ticker=ticker, cik=_BRK_CIK, accession=_BRK_ACCESSION).evidence
    assert evidence is not None
    assert (evidence.kind, evidence.title) == (SecurityKind.SHARE, "Class B Common Stock")
    assert evidence.ticker == ticker.strip().upper()


def test_a_separator_is_never_removed_or_added() -> None:
    brk = _read("brk_fy2025")
    for near in ("BRKB", "BRK B", "BRK..B", "BRK.", "BRK"):
        evidence = _listing(brk, ticker=near, cik=_BRK_CIK, accession=_BRK_ACCESSION).evidence
        assert evidence is not None
        assert evidence.kind is SecurityKind.NOT_LISTED
    nly = _read("nly_fy2025")
    # A preferred ticker whose form differs beyond the separator is not listed.
    cik, accession = "1043219", "0001043219-26-000013"
    assert _listing(nly, ticker="NLY.F", cik=cik, accession=accession).evidence.kind is SecurityKind.PREFERRED  # type: ignore[union-attr]
    assert _listing(nly, ticker="NLY-PF", cik=cik, accession=accession).evidence.kind is SecurityKind.NOT_LISTED  # type: ignore[union-attr]


def _listed(symbol: str, title: str) -> tuple[str, ...]:
    return (
        _row("Security12bTitle", "Title", title),
        _row("TradingSymbol", "Trading Symbol", symbol),
        _row("SecurityExchangeName", "Exchange", "NYSE"),
    )


def test_two_rows_that_collide_after_normalization_with_different_titles_are_ambiguous() -> None:
    collide = _cover(_CIK_ROW, *_listed("AB.C", "Class A Common Stock"), *_listed("AB-C", "Class B Common Stock"))
    assert _listing(collide, ticker="AB/C").reason is CoverUnavailableReason.AMBIGUOUS_LISTING
    assert _listing(collide, ticker="AB.C").reason is CoverUnavailableReason.AMBIGUOUS_LISTING
    same = _cover(_CIK_ROW, *_listed("AB.C", "Class A Common Stock"), *_listed("AB-C", "Class A Common Stock"))
    resolution = _listing(same, ticker="AB/C")
    assert resolution.evidence is not None
    assert resolution.evidence.kind is SecurityKind.SHARE


def test_a_separator_never_joins_the_securities_of_two_registrants() -> None:
    other_cik = _row("EntityCentralIndexKey", "Entity Central Index Key", "0000000042")
    combined = _cover(_CIK_ROW, *_listed("AB.C", "Common stock"), other_cik, *_listed("XY-Z", "Common stock"))
    assert _listing(combined, ticker="XY.Z").evidence.kind is SecurityKind.NOT_LISTED  # type: ignore[union-attr]
    assert _listing(combined, ticker="AB-C").evidence.kind is SecurityKind.SHARE  # type: ignore[union-attr]


def test_a_ticker_absent_from_the_cover_is_not_listed() -> None:
    evidence = _listing(_read("jpm_fy2025"), ticker="NOPE").evidence
    assert evidence is not None
    assert (evidence.kind, evidence.title) == (SecurityKind.NOT_LISTED, None)


def test_a_combined_covers_other_registrants_securities_are_not_the_issuers() -> None:
    prologis = _read("pld_fy2025")
    own = _listing(prologis, ticker="PLD", cik="1045609", accession="0001193125-26-051453")
    assert own.evidence is not None
    assert own.evidence.kind is SecurityKind.SHARE
    other = _listing(prologis, ticker="PLD/29", cik="1045609", accession="0001193125-26-051453")
    assert other.evidence is not None
    assert other.evidence.kind is SecurityKind.NOT_LISTED
    partnership = _listing(prologis, ticker="PLD/29", cik="1045610", accession="0001193125-26-051453")
    assert partnership.evidence is not None
    assert partnership.evidence.kind is SecurityKind.OTHER


def test_a_cover_under_another_cik_is_refused() -> None:
    for cik in ("1652044", "1"):
        assert _listing(_read("jpm_fy2025"), ticker="JPM", cik=cik).reason is CoverUnavailableReason.CIK_MISMATCH


def test_a_cover_naming_another_form_is_refused() -> None:
    for form in ("10-K/A", "20-F", "10-Q"):
        assert _listing(_read("jpm_fy2025"), ticker="JPM", form=form).reason is CoverUnavailableReason.FORM_MISMATCH


def test_the_boundary_keeps_a_filing_accepted_at_it_and_refuses_one_second_later() -> None:
    accepted = datetime(2026, 2, 13, 21, 20, tzinfo=UTC)
    kept = _listing(_read("jpm_fy2025"), ticker="JPM", accepted_at=accepted, boundary=accepted)
    assert kept.evidence is not None
    refused = _listing(
        _read("jpm_fy2025"), ticker="JPM", accepted_at=accepted, boundary=accepted - timedelta(seconds=1)
    )
    assert refused.reason is CoverUnavailableReason.ACCEPTED_AFTER_BOUNDARY


def test_a_cover_without_a_registration_table_is_refused_not_guessed_at() -> None:
    old = _listing(_read("mdt_fy2019"), ticker="MDT", cik="1613103", accession="0001613103-19-000028")
    assert old.reason is CoverUnavailableReason.NO_REGISTRATION_TABLE


def test_an_amended_cover_without_a_registration_table_is_refused_without_reading_the_original() -> None:
    stripped = "\n".join(
        line
        for line in _read("ipgp_fy2025_amended").splitlines()
        if not any(
            concept in line
            for concept in ("Security12bTitle", "TradingSymbol", "SecurityExchangeName", "Security12gTitle")
        )
    )
    resolution = _listing(stripped, ticker="IPGP", cik="1111928", accession="0001111928-26-000068", form="10-K/A")
    assert resolution.reason is CoverUnavailableReason.NO_REGISTRATION_TABLE


def test_a_captured_page_that_is_not_a_cover_is_unreadable_on_its_own() -> None:
    # Disney's first report is the audit information, not the cover.
    resolution = _listing(_read("dis_fy2025"), ticker="DIS", cik="1744489", accession="0001744489-25-000155")
    assert resolution.reason is CoverUnavailableReason.COVER_UNREADABLE
    assert not looks_like_cover(_read("dis_fy2025"))
    assert looks_like_cover(_read("dis_fy2025_cover"))
    assert not looks_like_cover("<html></html>")


def test_a_captured_cover_that_lists_the_symbol_before_the_title_gives_each_symbol_to_the_title_of_its_block() -> None:
    # BlackRock's rows run member header, symbol, title, exchange: each symbol sits above the title it belongs to.
    ids = {"cik": "2012383", "accession": "0001193125-26-071966"}
    blk = _read("blk_fy2025")
    common = _listing(blk, ticker="BLK", **ids).evidence  # type: ignore[arg-type]
    notes = _listing(blk, ticker="BLK 35", **ids).evidence  # type: ignore[arg-type]
    assert common is not None
    assert notes is not None
    assert (common.kind, common.title) == (SecurityKind.SHARE, "Common Stock, $.01 par value")
    assert (notes.kind, notes.title) == (SecurityKind.OTHER, "3.750% Notes due 2035")


def _member(label: str) -> str:
    link = (
        '<a class="a" href="javascript:void(0);" onclick="Show.showAR( this, '
        "'defref_us-gaap_StatementClassOfStockAxis=us-gaap_CommonStockMember', window );\">"
    )
    return f'<tr class="rh"><td class="pl">{link}{label}</a></td><td class="text">&#160;</td></tr>'


def _symbol(value: str) -> str:
    return _row("TradingSymbol", "Trading Symbol", value)


def _title(value: str) -> str:
    return _row("Security12bTitle", "Title", value)


def _exchange(value: str = "NYSE") -> str:
    return _row("SecurityExchangeName", "Exchange", value)


def _kind(markup: str, ticker: str) -> tuple[SecurityKind, str | None]:
    evidence = _listing(markup, ticker=ticker).evidence
    assert evidence is not None
    return evidence.kind, evidence.title


def test_one_rule_groups_title_first_symbol_first_and_headerless_covers() -> None:
    two = (("AAA", "Common stock"), ("AAA 30", "3.000% Notes due 2030"))
    title_first = _cover(_CIK_ROW, *[r for s, ti in two for r in (_member(ti), _title(ti), _symbol(s), _exchange())])
    symbol_first = _cover(_CIK_ROW, *[r for s, ti in two for r in (_member(ti), _symbol(s), _title(ti), _exchange())])
    headerless = _cover(_CIK_ROW, *[r for s, ti in two for r in (_title(ti), _symbol(s), _exchange())])
    for markup in (title_first, symbol_first, headerless):
        assert _kind(markup, "AAA") == (SecurityKind.SHARE, "Common stock")
        assert _kind(markup, "AAA 30") == (SecurityKind.OTHER, "3.000% Notes due 2030")


def test_a_symbol_above_every_title_of_its_block_belongs_to_the_first_title_of_the_block() -> None:
    markup = _cover(
        _CIK_ROW,
        _member("a"),
        _symbol("AAA"),
        _exchange(),
        _title("Common stock"),
        _member("b"),
        _symbol("BBB"),
        _title("Units"),
        _exchange(),
    )
    assert _kind(markup, "AAA") == (SecurityKind.SHARE, "Common stock")
    assert _kind(markup, "BBB") == (SecurityKind.UNIT, "Units")


def test_a_block_after_a_member_header_never_lends_its_rows_to_the_title_before_it() -> None:
    markup = _cover(
        _CIK_ROW, _member("a"), _title("Common stock"), _symbol("AAA"), _exchange(), _member("b"), _symbol("BBB")
    )
    assert _listing(markup, ticker="AAA").reason is CoverUnavailableReason.COVER_UNREADABLE


def test_the_exchange_row_of_a_block_with_no_title_belongs_to_no_security() -> None:
    entity_level = _cover(_CIK_ROW, *_COMMON, _member("registrant"), _exchange("NASDAQ"))
    assert _kind(entity_level, "JPM") == (SecurityKind.SHARE, "Common stock")
    untitled_symbol = _cover(_CIK_ROW, *_COMMON, _member("registrant"), _symbol("ZZZ"))
    assert _listing(untitled_symbol, ticker="JPM").reason is CoverUnavailableReason.COVER_UNREADABLE


# --- a ticker shared with debt ------------------------------------------------------------------------------------


def test_microsoft_lists_its_symbol_against_its_stock_and_two_notes_and_is_affirmed() -> None:
    ids = {"cik": "789019", "accession": "0001193125-26-323660"}
    evidence = _listing(_read("msft_fy2025"), ticker="MSFT", **ids).evidence  # type: ignore[arg-type]
    assert evidence is not None
    assert (evidence.kind, evidence.title) == (SecurityKind.SHARE, "Common stock, $0.00000625 par value per share")


def _shared(*titles: str) -> str:
    return _cover(_CIK_ROW, *[r for ti in titles for r in (_member(ti), _title(ti), _symbol("AAA"), _exchange())])


def test_a_share_with_debt_titles_of_an_explicit_form_on_its_symbol_is_the_shares() -> None:
    markup = _shared("Common stock", "3.125% Notes due 2028", "2.625% notes due 2033")
    assert _kind(markup, "AAA") == (SecurityKind.SHARE, "Common stock")
    assert _kind(_shared("3.125% Notes due 2028", "Common stock"), "AAA") == (SecurityKind.SHARE, "Common stock")


@pytest.mark.parametrize(
    "titles",
    [
        ("Common stock", "Depositary Shares"),
        ("Common stock", "6.50% Series D Preferred Stock"),
        ("Common stock", "Units"),
        ("Common stock", "Class B Common Stock"),
        ("Common stock", "3.125% Notes due 2028", "Depositary Shares"),
        ("Common stock", "Senior Notes due 2028"),
        ("Common stock", "3.125% Notes due 2028 and 2030"),
        ("Common stock", "3.125% Guaranteed Notes due 2028"),
        ("3.125% Notes due 2028", "2.625% Notes due 2033"),
    ],
)
def test_any_other_mix_of_titles_on_one_symbol_is_ambiguous(titles: tuple[str, ...]) -> None:
    assert _listing(_shared(*titles), ticker="AAA").reason is CoverUnavailableReason.AMBIGUOUS_LISTING


def test_the_same_share_title_on_two_exchanges_is_one_share_beside_debt() -> None:
    markup = _cover(
        _CIK_ROW,
        *_COMMON,
        _member("n"),
        _title("3.125% Notes due 2028"),
        _symbol("JPM"),
        _exchange(),
    )
    assert _kind(markup, "JPM") == (SecurityKind.SHARE, "Common stock")


def test_a_page_that_is_not_a_cover_is_unreadable() -> None:
    for markup in (
        "",
        "<html><body><p>Not found</p></body></html>",
        '<table class="report"><tr><td>Revenue</td><td>1</td></tr></table>',
    ):
        assert _listing(markup, ticker="JPM").reason is CoverUnavailableReason.COVER_UNREADABLE


def _row(concept: str, label: str, *values: str) -> str:
    link = f'<a class="a" href="javascript:void(0);" onclick="Show.showAR( this, \'defref_dei_{concept}\', window );">'
    cells = "".join(f'<td class="text">{value}</td>' for value in values)
    return f'<tr class="re"><td class="pl">{link}{label}</a></td>{cells}</tr>'


def _cover(*rows: str) -> str:
    return '<table class="report">' + _row("DocumentType", "Document Type", "10-K") + "".join(rows) + "</table>"


_CIK_ROW = _row("EntityCentralIndexKey", "Entity Central Index Key", "0000019617")
_COMMON = (
    _row("Security12bTitle", "Title of 12(b) Security", "Common stock"),
    _row("TradingSymbol", "Trading Symbol", "JPM"),
    _row("SecurityExchangeName", "Security Exchange Name", "NYSE"),
)


def test_the_cover_reader_works_from_the_concept_of_a_row_not_its_label() -> None:
    markup = _cover(_CIK_ROW, *_COMMON).replace("Title of 12(b) Security", "Title of Each Class")
    assert _listing(markup, ticker="JPM").evidence.kind is SecurityKind.SHARE  # type: ignore[union-attr]
    unnamed = _cover(_CIK_ROW, *_COMMON).replace("showAR( this, 'defref_dei_Security12bTitle', window )", "x()")
    assert _listing(unnamed, ticker="JPM").reason is CoverUnavailableReason.COVER_UNREADABLE


def test_a_row_of_another_taxonomy_prefix_is_not_a_cover_concept() -> None:
    markup = _cover(_CIK_ROW, *_COMMON).replace("defref_dei_TradingSymbol", "defref_ext_TradingSymbol")
    assert _listing(markup, ticker="JPM").evidence.kind is SecurityKind.NOT_LISTED  # type: ignore[union-attr]


def test_a_ticker_listed_under_two_different_titles_is_ambiguous() -> None:
    second = (
        _row("Security12bTitle", "Title", "Depositary Shares"),
        _row("TradingSymbol", "Trading Symbol", "JPM"),
        _row("SecurityExchangeName", "Exchange", "NYSE"),
    )
    assert (
        _listing(_cover(_CIK_ROW, *_COMMON, *second), ticker="JPM").reason is CoverUnavailableReason.AMBIGUOUS_LISTING
    )


def test_the_same_title_listed_twice_is_one_listing() -> None:
    resolution = _listing(_cover(_CIK_ROW, *_COMMON, *_COMMON), ticker="JPM")
    assert resolution.evidence is not None
    assert resolution.evidence.kind is SecurityKind.SHARE


def test_a_row_with_two_different_values_or_a_symbol_without_a_title_is_unreadable() -> None:
    two_values = _cover(_row("EntityCentralIndexKey", "CIK", "0000019617", "0000000001"), *_COMMON)
    assert _listing(two_values, ticker="JPM").reason is CoverUnavailableReason.COVER_UNREADABLE
    orphan = _cover(_CIK_ROW, _row("TradingSymbol", "Trading Symbol", "JPM"))  # no title anywhere
    assert _listing(orphan, ticker="JPM").reason is CoverUnavailableReason.COVER_UNREADABLE
    twice = _cover(_CIK_ROW, *_COMMON, _row("TradingSymbol", "Trading Symbol", "JPMX"))
    assert _listing(twice, ticker="JPM").reason is CoverUnavailableReason.COVER_UNREADABLE
    bad_key = _cover(_row("EntityCentralIndexKey", "CIK", "ABC"), *_COMMON)
    assert _listing(bad_key, ticker="JPM").reason is CoverUnavailableReason.COVER_UNREADABLE


def test_a_listed_row_without_an_exchange_is_unreadable() -> None:
    markup = _cover(_CIK_ROW, _COMMON[0], _COMMON[1])
    assert _listing(markup, ticker="JPM").reason is CoverUnavailableReason.COVER_UNREADABLE


def test_a_cover_with_two_registrants_needs_every_security_under_a_key() -> None:
    before_key = _cover(*_COMMON, _CIK_ROW, _row("EntityCentralIndexKey", "CIK", "0000000002"))
    assert _listing(before_key, ticker="JPM").reason is CoverUnavailableReason.COVER_UNREADABLE


def test_a_cover_without_a_document_type_or_registrant_key_is_unreadable() -> None:
    assert _listing('<table class="report">' + _CIK_ROW + "</table>", ticker="JPM").reason is (
        CoverUnavailableReason.COVER_UNREADABLE
    )
    assert _listing(_cover(*_COMMON), ticker="JPM").reason is CoverUnavailableReason.COVER_UNREADABLE


def test_a_second_report_table_and_nested_tables_do_not_add_rows() -> None:
    nested = _cover(_CIK_ROW, *_COMMON).replace(
        "</table>", '<table class="report"><tr><td>x</td></tr></table></table>'
    ) + _cover(_row("TradingSymbol", "Trading Symbol", "OTHER"))
    assert _listing(nested, ticker="OTHER").evidence.kind is SecurityKind.NOT_LISTED  # type: ignore[union-attr]
    assert _listing(nested, ticker="JPM").evidence.kind is SecurityKind.SHARE  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("title", "kind"),
    [
        ("Common stock", SecurityKind.SHARE),
        ("  common   STOCK,  $.01  Par Value ", SecurityKind.SHARE),
        ("Class A Ordinary Shares", SecurityKind.SHARE),
        ("Depositary Shares", SecurityKind.DEPOSITARY_SHARE),
        ("American Depositary Shares, each representing two ordinary shares", SecurityKind.DEPOSITARY_SHARE),
        ("Units", SecurityKind.UNIT),
        ("Warrants", SecurityKind.WARRANT),
        ("7.00% Series A Cumulative Preferred Stock", SecurityKind.PREFERRED),
        ("Class B Common Stock", SecurityKind.SHARE),
        ("Class B common stock, par value $0.01 per share", SecurityKind.SHARE),
        ("Common Stock, without Par Value", SecurityKind.SHARE),
        ("Common Stock (no par value)", SecurityKind.SHARE),
        ("Common Stock ($1.00 par value)", SecurityKind.SHARE),
        ("Common Shares (Par Value $1.00 Per Share)", SecurityKind.SHARE),
        ("Common Stock, par value $1-2/3", SecurityKind.SHARE),
        ("Common Stock, par value 1-2/3 cents per share", SecurityKind.SHARE),
        ("Common Shares, par value CHF 0.50 per share", SecurityKind.SHARE),
        ("Ordinary shares (€0.001 nominal value per share)", SecurityKind.SHARE),
        (
            "Dep Shs, represent 1/1,000th interest in a share of 6.250% Noncum Pref Stk, Ser II",
            SecurityKind.DEPOSITARY_SHARE,
        ),
        ("7.5% Non-Cumulative Perpetual Convertible Class A Preferred Stock, Series L", SecurityKind.PREFERRED),
        # Not on a captured cover: outside the vocabulary, so neither a share nor mistaken for one.
        ("Class B-1 common stock, par value $0.0001 per share", SecurityKind.OTHER),
        ("Class D Common Stock", SecurityKind.OTHER),
        ("Common Stock, par value 1-2/3 cents", SecurityKind.OTHER),
        ("Common Stock, par value CHF per share", SecurityKind.OTHER),
        ("Ordinary shares (€0.001 par value per share)", SecurityKind.OTHER),
        ("Preferred Stock, Series", SecurityKind.OTHER),
        ("Floating Rate Preferred Hybrid Income Term Securities", SecurityKind.OTHER),
        ("1.125% Senior Notes due 2027", SecurityKind.OTHER),
        ("Common Stock Purchase Rights", SecurityKind.OTHER),
        ("Common stock and warrants", SecurityKind.OTHER),
        ("Redeemable warrants, each exercisable for one share", SecurityKind.OTHER),
        ("Common stock, no par value", SecurityKind.OTHER),
        ("Series B Preference Shares", SecurityKind.OTHER),
        ("", SecurityKind.OTHER),
    ],
)
def test_the_title_vocabulary_is_an_explicit_list(title: str, kind: SecurityKind) -> None:
    assert classify_title(title) is kind


# --- the evidence types ------------------------------------------------------------------------------------------


def _evidence(**changes: Any) -> ListingEvidence:
    base: dict[str, Any] = {
        "ticker": "JPM",
        "kind": SecurityKind.SHARE,
        "title": "Common stock",
        "cik": "0000019617",
        "accession": "0001628280-26-008131",
        "form": "10-K",
        "accepted_at": NOW,
        "source_url": "https://www.sec.gov/x",
        "retrieved_at": NOW,
    }
    return ListingEvidence(**{**base, **changes})


def test_the_evidence_requires_a_title_exactly_when_the_ticker_is_listed() -> None:
    assert _evidence().title == "Common stock"
    assert _evidence(kind=SecurityKind.NOT_LISTED, title=None).title is None
    for changes in (
        {"title": None},
        {"kind": SecurityKind.NOT_LISTED},
        {"title": " "},
        {"cik": "19617"},
        {"accession": "000162828026008131"},
        {"form": " "},
        {"source_url": ""},
        {"accepted_at": datetime(2026, 1, 1)},  # noqa: DTZ001
        {"retrieved_at": datetime(2026, 1, 1)},  # noqa: DTZ001
    ):
        with pytest.raises(ValueError, match="Listing evidence|title"):
            _evidence(**changes)


def test_a_resolution_holds_exactly_one_of_the_evidence_and_the_reason() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        ListingResolution()
    with pytest.raises(ValueError, match="exactly one"):
        ListingResolution(evidence=_evidence(), reason=CoverUnavailableReason.COVER_MISSING)


def test_a_request_normalizes_and_requires_its_parts() -> None:
    request = CoverListingRequest(" brk b ", " sec_edgar ")
    assert (request.ticker, request.provider_id) == ("BRK B", "sec_edgar")
    with pytest.raises(ValueError, match="requires"):
        CoverListingRequest(" ", "sec_edgar")


def test_the_fixture_checksums_match_the_files() -> None:
    lines = (FIXTURES / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    listed = {line.split("  ")[1]: line.split("  ")[0] for line in lines}
    assert set(listed) == {path.name for path in FIXTURES.iterdir() if path.name != "SHA256SUMS"}
    for name, digest in listed.items():
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == digest


def test_the_fixtures_hold_no_identity_and_none_of_the_hidden_definitions() -> None:
    for path in FIXTURES.glob("*.r1.htm"):
        text = path.read_text(encoding="utf-8")
        assert "User-Agent" not in text
        assert "authRefData" not in text, path.name
        assert len(text) < 30_000, path.name


# --- transport ---------------------------------------------------------------------------------------------------

_ACCESSION = "0001628280-26-008131"
_URL = "https://www.sec.gov/Archives/edgar/data/19617/000162828026008131/R1.htm"


def _fetch(url: str = _URL, *, policy: CoverReaderPolicy | None = None, headers: Mapping[str, str] = _HEADERS) -> str:
    return fetch_cover(url, headers=headers, policy=policy or CoverReaderPolicy(), **_KEYWORDS)


def test_the_url_is_built_only_from_validated_identifiers() -> None:
    assert cover_url("0000019617", _ACCESSION) == _URL
    assert cover_url("19617", _ACCESSION) == _URL
    for cik, accession in (("0", _ACCESSION), ("1x", _ACCESSION), ("19617", "0001628280-26-00813"), ("19617", "../x")):
        with pytest.raises(ValueError, match="Invalid filing"):
            cover_url(cik, accession)


@pytest.mark.parametrize(
    "url",
    [
        _URL.replace("https://www.sec.gov", "https://example.test"),
        _URL.replace("https://", "http://"),
        _URL + "?x=1",
        _URL.replace("19617/", "19617/../"),
        _URL.replace("R1.htm", "R12345.htm"),
        _URL.replace("R1.htm", "r2.htm"),
        _URL.replace("R1.htm", "R2.htm.bak"),
        _URL.replace("R1.htm", "R.htm"),
        _URL.replace("R1.htm", "filingsummary.xml"),
        _URL.replace("000162828026008131/", "00016282802600813/"),
        _URL.replace("19617", "abc"),
        _URL.replace("/Archives", "//Archives"),
    ],
)
def test_the_transport_enforces_the_exact_url_pattern(url: str) -> None:
    with pytest.raises(ValueError, match="Unsupported cover URL"):
        _fetch(url)


def test_a_report_name_and_the_summary_are_addressed_only_from_validated_parts() -> None:
    assert cover_url("19617", _ACCESSION, "R2.htm") == _URL.replace("R1.htm", "R2.htm")
    assert summary_url("19617", _ACCESSION) == _URL.replace("R1.htm", "FilingSummary.xml")
    for report in ("../R2.htm", "R2.htm?x=1", "R.htm", "R12345.htm", "FilingSummary.xml"):
        with pytest.raises(ValueError, match="Invalid report"):
            cover_url("19617", _ACCESSION, report)
    with pytest.raises(ValueError, match="Invalid filing"):
        summary_url("0", _ACCESSION)


def test_the_summary_is_read_under_its_own_limit_and_type() -> None:
    summary = _URL.replace("R1.htm", "FilingSummary.xml")
    opener = _opener(b"<FilingSummary/>")
    with patch("investment_analysis_engine.data.sec_edgar.filing_document.build_opener", return_value=opener):
        assert _fetch(summary, policy=CoverReaderPolicy(max_cover_bytes=1, max_summary_bytes=64)) == "<FilingSummary/>"
    assert opener.open.call_args.args[0].get_header("Accept") == "application/xml"
    opener.open.return_value.__enter__.return_value.read.assert_called_once_with(65)
    with (
        patch(
            "investment_analysis_engine.data.sec_edgar.filing_document.build_opener",
            return_value=_opener(b"x" * 65),
        ),
        pytest.raises(FinancialProviderError) as oversized,
    ):
        _fetch(summary, policy=CoverReaderPolicy(max_summary_bytes=64))
    assert oversized.value.kind is ProviderFailureKind.UNEXPECTED_RESPONSE


def test_the_transport_requires_an_identity() -> None:
    with pytest.raises(ValueError, match="User-Agent"):
        _fetch(headers={})


def _opener(body: bytes | None = None, error: BaseException | None = None) -> MagicMock:
    opener = MagicMock()
    if error is not None:
        opener.open.side_effect = error
    else:
        opener.open.return_value.__enter__.return_value.read.return_value = body
    return opener


def test_the_transport_is_bounded_without_redirects() -> None:
    opener = _opener(b"<html></html>")
    with patch(
        "investment_analysis_engine.data.sec_edgar.filing_document.build_opener", return_value=opener
    ) as builder:
        assert _fetch(policy=CoverReaderPolicy(timeout_seconds=3, max_cover_bytes=64)) == "<html></html>"
    assert opener.open.call_args.kwargs["timeout"] == 3
    assert opener.open.call_args.args[0].get_header("Accept") == "text/html"
    opener.open.return_value.__enter__.return_value.read.assert_called_once_with(65)
    assert builder.call_args.args[0].redirect_request() is None


def test_an_oversized_or_undecodable_cover_is_an_unexpected_response() -> None:
    for body, match in ((b"x" * 9, "size limit"), (b"\xff\xfe\xfa", "UTF-8")):
        with (
            patch("investment_analysis_engine.data.sec_edgar.filing_document.build_opener", return_value=_opener(body)),
            pytest.raises(FinancialProviderError, match=match) as caught,
        ):
            _fetch(policy=CoverReaderPolicy(max_cover_bytes=8))
        assert caught.value.kind is ProviderFailureKind.UNEXPECTED_RESPONSE


def test_a_404_takes_the_kind_the_caller_passes_and_a_server_fault_is_unreachable() -> None:
    not_found = HTTPError(_URL, 404, "Not Found", {}, BytesIO(b""))  # type: ignore[arg-type]
    with (
        patch(
            "investment_analysis_engine.data.sec_edgar.filing_document.build_opener",
            return_value=_opener(error=not_found),
        ),
        pytest.raises(FinancialProviderError) as missing,
    ):
        _fetch()
    assert missing.value.kind is ProviderFailureKind.NO_DATA
    fault = HTTPError(_URL, 503, "Unavailable", {}, BytesIO(b""))  # type: ignore[arg-type]
    with (
        patch(
            "investment_analysis_engine.data.sec_edgar.filing_document.build_opener", return_value=_opener(error=fault)
        ),
        pytest.raises(FinancialProviderError) as down,
    ):
        _fetch()
    assert down.value.kind is ProviderFailureKind.UNREACHABLE


def test_the_default_policy_holds_the_largest_captured_cover_and_rejects_unbounded_settings() -> None:
    largest_captured = 135_601
    assert CoverReaderPolicy().max_cover_bytes > 3 * largest_captured
    assert CoverReaderPolicy().max_summary_bytes > 5 * 86_703  # Disney's FilingSummary.xml, the largest captured
    for kwargs in (
        {"timeout_seconds": 0.0},
        {"timeout_seconds": float("inf")},
        {"max_cover_bytes": 0},
        {"max_summary_bytes": 0},
    ):
        with pytest.raises(ValueError, match="Cover"):
            CoverReaderPolicy(**kwargs)


# --- the filing summary ------------------------------------------------------------------------------------------


def _summary(*reports: tuple[str, str, str]) -> str:
    body = "".join(
        f"<Report><HtmlFileName>{name}</HtmlFileName><ShortName>{short}</ShortName>"
        f"<MenuCategory>{category}</MenuCategory></Report>"
        for name, short, category in reports
    )
    return f"<FilingSummary><MyReports>{body}</MyReports></FilingSummary>"


def test_the_summary_marks_the_cover_by_its_category_and_its_short_name() -> None:
    disney = (FIXTURES / "dis_fy2025.filing_summary.xml").read_text(encoding="utf-8")
    # The category alone marks two reports, the audit information and the cover.
    assert disney.count("<MenuCategory>Cover</MenuCategory>") == 2
    assert cover_report_from_summary(disney) == "R2.htm"
    assert (
        cover_report_from_summary(_summary(("R1.htm", "COVER PAGE", "Cover"), ("R2.htm", "Audit", "Cover"))) == "R1.htm"
    )
    assert cover_report_from_summary(_summary(("R7.htm", " Cover  Page ", "cover"))) == "R7.htm"


@pytest.mark.parametrize(
    "summary",
    [
        "",
        "<FilingSummary/>",
        _summary(("R1.htm", "Audit Information", "Cover")),
        _summary(("R1.htm", "Cover", "Statements")),
        _summary(("R1.htm", "Cover", "Cover"), ("R2.htm", "Cover Page", "Cover")),
        _summary(("../R2.htm", "Cover", "Cover")),
        _summary(("R2.html", "Cover", "Cover")),
        _summary(("", "Cover", "Cover")),
    ],
)
def test_a_summary_that_marks_no_cover_or_several_or_an_unaddressable_one_names_none(summary: str) -> None:
    assert cover_report_from_summary(summary) is None


class _Pages:
    """Serve filing pages by URL and record the requests."""

    def __init__(self, pages: dict[str, str | BaseException]) -> None:
        self.pages = pages
        self.urls: list[str] = []

    def __call__(
        self,
        url: str,
        *,
        headers: Mapping[str, str],  # noqa: ARG002
        policy: CoverReaderPolicy,  # noqa: ARG002
        not_found: ProviderFailureKind,
        provider_id: str,
    ) -> str:
        self.urls.append(url)
        page = self.pages.get(url)
        if page is None:
            raise FinancialProviderError("gone", kind=not_found, provider_id=provider_id)
        if isinstance(page, BaseException):
            raise page
        return page


_DIS = {"cik": "1744489", "accession": "0001744489-25-000155"}
_DIS_BASE = "https://www.sec.gov/Archives/edgar/data/1744489/000174448925000155/"


def _anchor(pages: _Pages, **ids: str) -> tuple[str, str]:
    return fetch_anchor_cover(
        ids.get("cik", _DIS["cik"]),
        ids.get("accession", _DIS["accession"]),
        fetcher=pages,
        headers=_HEADERS,
        policy=CoverReaderPolicy(),
        not_found=ProviderFailureKind.NO_DATA,
        provider_id="sec_edgar",
    )


def _disney_pages() -> _Pages:
    return _Pages(
        {
            _DIS_BASE + "R1.htm": _read("dis_fy2025"),
            _DIS_BASE + "FilingSummary.xml": (FIXTURES / "dis_fy2025.filing_summary.xml").read_text(encoding="utf-8"),
            _DIS_BASE + "R2.htm": _read("dis_fy2025_cover"),
        }
    )


def test_a_filing_whose_first_report_is_not_the_cover_is_read_through_its_summary() -> None:
    pages = _disney_pages()
    text, url = _anchor(pages)
    assert (text, url) == (_read("dis_fy2025_cover"), _DIS_BASE + "R2.htm")
    assert pages.urls == [_DIS_BASE + "R1.htm", _DIS_BASE + "FilingSummary.xml", _DIS_BASE + "R2.htm"]
    evidence = _listing(text, ticker="DIS", **_DIS).evidence  # type: ignore[arg-type]
    assert evidence is not None
    assert (evidence.kind, evidence.title) == (SecurityKind.SHARE, "Common Stock, $0.01 par value")


def test_a_filing_whose_first_report_is_the_cover_makes_no_further_request() -> None:
    pages = _Pages({_URL: _read("jpm_fy2025")})
    assert _anchor(pages, cik="19617", accession=_ACCESSION) == (_read("jpm_fy2025"), _URL)
    assert pages.urls == [_URL]


def test_a_summary_that_cannot_name_the_cover_leaves_the_first_page_unreadable() -> None:
    first = _read("dis_fy2025")
    for summary in (
        FinancialProviderError("gone", kind=ProviderFailureKind.NO_DATA, provider_id="sec_edgar"),
        _summary(("R1.htm", "Audit Information", "Cover")),
        _summary(("R1.htm", "Cover", "Cover"), ("R2.htm", "Cover", "Cover")),
        _summary(("R1.htm", "Cover", "Cover")),
    ):
        pages = _Pages({_DIS_BASE + "R1.htm": first, _DIS_BASE + "FilingSummary.xml": summary})
        assert _anchor(pages) == (first, _DIS_BASE + "R1.htm")
        assert pages.urls == [_DIS_BASE + "R1.htm", _DIS_BASE + "FilingSummary.xml"]
    assert _listing(first, ticker="DIS", **_DIS).reason is CoverUnavailableReason.COVER_UNREADABLE  # type: ignore[arg-type]


def test_a_summary_fault_or_a_missing_marked_report_raises_and_a_missing_first_page_does_too() -> None:
    fault = FinancialProviderError("down", kind=ProviderFailureKind.UNREACHABLE, provider_id="sec_edgar")
    pages = _disney_pages()
    pages.pages[_DIS_BASE + "FilingSummary.xml"] = fault
    with pytest.raises(FinancialProviderError) as caught:
        _anchor(pages)
    assert caught.value.kind is ProviderFailureKind.UNREACHABLE
    pages = _disney_pages()
    del pages.pages[_DIS_BASE + "R2.htm"]
    with pytest.raises(FinancialProviderError) as missing:
        _anchor(pages)
    assert missing.value.kind is ProviderFailureKind.NO_DATA
    with pytest.raises(FinancialProviderError):
        _anchor(_Pages({}))


# --- the adapter -------------------------------------------------------------------------------------------------

_BOUNDARY = datetime(2026, 3, 1, tzinfo=UTC)
_ACCEPTED = "2026-02-13T21:20:00.000Z"


class _Sec:
    """Serve one issuer's submissions and count the cover, header and document requests."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        ticker: str = "JPM",
        cover: str | BaseException | dict[str, str] | None = None,
        cik: str = "19617",
        accession: str = _ACCESSION,
        form: str = "10-K",
        accepted: str = _ACCEPTED,
    ) -> None:
        self.ticker = ticker
        self.cik = cik
        self.cover_urls: list[str] = []
        self.header_urls: list[str] = []
        self.document_urls: list[str] = []
        self._cover = cover if cover is not None else _read("jpm_fy2025")
        self.submissions: dict[str, Any] = {
            "cik": cik.zfill(10),
            "tickers": [ticker],
            "filings": {
                "recent": {
                    "accessionNumber": [accession],
                    "form": [form],
                    "filingDate": [accepted[:10]],
                    "acceptanceDateTime": [accepted],
                    "primaryDocument": ["x.htm"],
                }
            },
        }

    def json(self, url: str, *, headers: Mapping[str, str], not_found: ProviderFailureKind, provider_id: str) -> object:  # noqa: ARG002
        assert headers["User-Agent"]
        if url.endswith("company_tickers.json"):
            return {"0": {"ticker": self.ticker, "cik_str": int(self.cik), "title": "Issuer"}}
        if "/companyfacts/" in url:
            return {"cik": int(self.cik), "entityName": "Issuer", "facts": {"us-gaap": {}}}
        return self.submissions

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
        if isinstance(self._cover, BaseException):
            raise self._cover
        if isinstance(self._cover, dict):
            if url not in self._cover:
                raise FinancialProviderError("gone", kind=not_found, provider_id=provider_id)
            return self._cover[url]
        return self._cover

    def header(self, url: str, **_kwargs: object) -> str:
        self.header_urls.append(url)
        return ""

    def document(
        self,
        url: str,
        *,
        headers: Mapping[str, str],  # noqa: ARG002
        policy: FilingReaderPolicy,  # noqa: ARG002
        not_found: ProviderFailureKind,  # noqa: ARG002
        provider_id: str,  # noqa: ARG002
    ) -> str:
        self.document_urls.append(url)
        return ""

    def adapter(self) -> SecEdgarFinancialFactsAdapter:
        return SecEdgarFinancialFactsAdapter(
            json_fetcher=self.json,
            clock=lambda: NOW,
            user_agent="Synthetic",
            filing_fetcher=self.document,
            header_fetcher=self.header,
            cover_fetcher=self.cover,
        )


def test_the_adapter_reads_the_anchor_cover_once_per_scope_however_often_it_is_asked_for() -> None:
    sec = _Sec()
    adapter = sec.adapter()
    with adapter.analysis_scope(subject_id="JPM", provider_id=SEC_PROVIDER_ID, as_of=_BOUNDARY):
        request = CoverListingRequest("JPM", SEC_PROVIDER_ID)
        first = adapter.resolve_cover_listing(request)
        second = adapter.resolve_cover_listing(request)
        third = adapter.resolve_cover_listing(CoverListingRequest("jpm", SEC_PROVIDER_ID))
    assert first == second == third
    assert first.evidence is not None
    assert first.evidence.kind is SecurityKind.SHARE
    assert first.evidence.retrieved_at == NOW
    assert first.evidence.accepted_at == datetime(2026, 2, 13, 21, 20, tzinfo=UTC)
    assert first.evidence.source_url == _URL
    assert sec.cover_urls == [_URL]


def test_the_adapter_reads_a_filing_whose_cover_is_not_the_first_report_once_per_scope() -> None:
    sec = _Sec(
        ticker="DIS",
        cik="1744489",
        accession="0001744489-25-000155",
        accepted="2025-11-13T11:44:29.000Z",
        cover={
            _DIS_BASE + "R1.htm": _read("dis_fy2025"),
            _DIS_BASE + "FilingSummary.xml": (FIXTURES / "dis_fy2025.filing_summary.xml").read_text(encoding="utf-8"),
            _DIS_BASE + "R2.htm": _read("dis_fy2025_cover"),
        },
    )
    adapter = sec.adapter()
    with adapter.analysis_scope(subject_id="DIS", provider_id=SEC_PROVIDER_ID, as_of=_BOUNDARY):
        request = CoverListingRequest("DIS", SEC_PROVIDER_ID)
        first = adapter.resolve_cover_listing(request)
        second = adapter.resolve_cover_listing(request)
    assert first == second
    assert first.evidence is not None
    assert (first.evidence.kind, first.evidence.source_url) == (SecurityKind.SHARE, _DIS_BASE + "R2.htm")
    assert sec.cover_urls == [_DIS_BASE + "R1.htm", _DIS_BASE + "FilingSummary.xml", _DIS_BASE + "R2.htm"]
    assert sec.document_urls == []


def test_the_adapter_works_with_and_without_as_of() -> None:
    for as_of in (None, _BOUNDARY, datetime(2026, 2, 13, 21, 20, tzinfo=UTC)):
        sec = _Sec()
        adapter = sec.adapter()
        with adapter.analysis_scope(subject_id="JPM", provider_id=SEC_PROVIDER_ID, as_of=as_of):
            resolution = adapter.resolve_cover_listing(CoverListingRequest("JPM", SEC_PROVIDER_ID))
        assert resolution.evidence is not None
        assert sec.cover_urls == [_URL]


def test_the_adapter_classifies_the_requested_tickers_row_for_a_depositary_share_filer() -> None:
    sec = _Sec(
        ticker="ADAP",
        cover=_read("adap_fy2024"),
        cik="1621227",
        accession="0001558370-25-003544",
        accepted="2025-03-24T20:00:00.000Z",
    )
    adapter = sec.adapter()
    with adapter.analysis_scope(subject_id="ADAP", provider_id=SEC_PROVIDER_ID, as_of=_BOUNDARY):
        resolution = adapter.resolve_cover_listing(CoverListingRequest("ADAP", SEC_PROVIDER_ID))
    assert resolution.evidence is not None
    assert (resolution.evidence.kind, resolution.evidence.cik) == (SecurityKind.DEPOSITARY_SHARE, "0001621227")


def test_a_filing_accepted_after_the_boundary_is_refused_and_at_it_is_kept() -> None:
    sec = _Sec()
    adapter = sec.adapter()
    with adapter.analysis_scope(subject_id="JPM", provider_id=SEC_PROVIDER_ID, as_of=_BOUNDARY):
        snapshot = financial_facts._ACTIVE_SNAPSHOT.get()  # noqa: SLF001
        assert snapshot is not None
        accepted = snapshot.acceptance_by_accession[_ACCESSION]
        request = CoverListingRequest("JPM", SEC_PROVIDER_ID)
        token = financial_facts._ACTIVE_SNAPSHOT.set(replace(snapshot, as_of=accepted))  # noqa: SLF001
        try:
            assert adapter.resolve_cover_listing(request).evidence is not None
        finally:
            financial_facts._ACTIVE_SNAPSHOT.reset(token)  # noqa: SLF001
        token = financial_facts._ACTIVE_SNAPSHOT.set(replace(snapshot, as_of=accepted - timedelta(seconds=1)))  # noqa: SLF001
        try:
            refused = adapter.resolve_cover_listing(request)
        finally:
            financial_facts._ACTIVE_SNAPSHOT.reset(token)  # noqa: SLF001
    assert refused.reason is CoverUnavailableReason.ACCEPTED_AFTER_BOUNDARY
    assert sec.cover_urls == [_URL]


def test_a_filing_that_is_not_yet_accepted_at_as_of_is_not_an_anchor() -> None:
    sec = _Sec()
    adapter = sec.adapter()
    with adapter.analysis_scope(
        subject_id="JPM", provider_id=SEC_PROVIDER_ID, as_of=datetime(2026, 2, 13, 21, 19, 59, tzinfo=UTC)
    ):
        resolution = adapter.resolve_cover_listing(CoverListingRequest("JPM", SEC_PROVIDER_ID))
    assert resolution.reason is CoverUnavailableReason.NO_ANCHOR_FILING
    assert sec.cover_urls == []


def test_the_adapter_refuses_a_cover_under_another_cik_or_form() -> None:
    other_cik = _Sec(cover=_read("googl_fy2025"))
    adapter = other_cik.adapter()
    with adapter.analysis_scope(subject_id="JPM", provider_id=SEC_PROVIDER_ID, as_of=_BOUNDARY):
        assert adapter.resolve_cover_listing(CoverListingRequest("JPM", SEC_PROVIDER_ID)).reason is (
            CoverUnavailableReason.CIK_MISMATCH
        )
    amended = _Sec(form="10-K/A")
    adapter = amended.adapter()
    with adapter.analysis_scope(subject_id="JPM", provider_id=SEC_PROVIDER_ID, as_of=_BOUNDARY):
        assert adapter.resolve_cover_listing(CoverListingRequest("JPM", SEC_PROVIDER_ID)).reason is (
            CoverUnavailableReason.FORM_MISMATCH
        )


def test_an_amended_anchor_filing_is_read_as_a_10_k_a() -> None:
    sec = _Sec(
        ticker="ALB",
        cover=_read("alb_fy2025_amended"),
        cik="915913",
        accession="0000915913-26-000060",
        form="10-K/A",
        accepted="2026-03-31T12:00:00.000Z",
    )
    adapter = sec.adapter()
    with adapter.analysis_scope(subject_id="ALB", provider_id=SEC_PROVIDER_ID, as_of=datetime(2026, 4, 1, tzinfo=UTC)):
        resolution = adapter.resolve_cover_listing(CoverListingRequest("ALB", SEC_PROVIDER_ID))
    assert resolution.evidence is not None
    assert (resolution.evidence.kind, resolution.evidence.form) == (SecurityKind.SHARE, "10-K/A")


def test_a_missing_cover_is_an_unknown_listing_and_a_fault_is_a_provider_error() -> None:
    missing = FinancialProviderError("gone", kind=ProviderFailureKind.NO_DATA, provider_id="sec_edgar")
    sec = _Sec(cover=missing)
    adapter = sec.adapter()
    with adapter.analysis_scope(subject_id="JPM", provider_id=SEC_PROVIDER_ID, as_of=_BOUNDARY):
        assert adapter.resolve_cover_listing(CoverListingRequest("JPM", SEC_PROVIDER_ID)).reason is (
            CoverUnavailableReason.COVER_MISSING
        )
    for kind in (ProviderFailureKind.UNREACHABLE, ProviderFailureKind.UNEXPECTED_RESPONSE):
        sec = _Sec(cover=FinancialProviderError("down", kind=kind, provider_id="sec_edgar"))
        adapter = sec.adapter()
        with (
            adapter.analysis_scope(subject_id="JPM", provider_id=SEC_PROVIDER_ID, as_of=_BOUNDARY),
            pytest.raises(FinancialProviderError) as caught,
        ):
            adapter.resolve_cover_listing(CoverListingRequest("JPM", SEC_PROVIDER_ID))
        assert caught.value.kind is kind


def test_the_cover_is_outside_the_four_document_limit() -> None:
    sec = _Sec()
    adapter = sec.adapter()
    policy = FilingReaderPolicy()
    for _ in range(policy.max_documents):
        sec.document("https://www.sec.gov/x", headers=_HEADERS, policy=policy, **_KEYWORDS)
    with adapter.analysis_scope(subject_id="JPM", provider_id=SEC_PROVIDER_ID, as_of=_BOUNDARY):
        assert adapter.resolve_cover_listing(CoverListingRequest("JPM", SEC_PROVIDER_ID)).evidence is not None
    assert len(sec.document_urls) == policy.max_documents
    assert sec.header_urls == []
    assert len(sec.cover_urls) == 1
    assert FilingHeaderPolicy().max_header_bytes > 0


def test_the_adapter_names_why_there_is_no_scope_or_the_scope_is_for_another_ticker() -> None:
    sec = _Sec()
    adapter = sec.adapter()
    request = CoverListingRequest("JPM", SEC_PROVIDER_ID)
    assert adapter.resolve_cover_listing(request).reason is CoverUnavailableReason.NO_ANALYSIS_SCOPE
    with adapter.analysis_scope(subject_id="JPM", provider_id=SEC_PROVIDER_ID, as_of=_BOUNDARY):
        other = adapter.resolve_cover_listing(CoverListingRequest("JPMX", SEC_PROVIDER_ID))
        assert other.reason is CoverUnavailableReason.SUBJECT_MISMATCH
        foreign = adapter.resolve_cover_listing(CoverListingRequest("JPM", "yfinance"))
        assert foreign.reason is CoverUnavailableReason.NO_ANALYSIS_SCOPE
    assert sec.cover_urls == []


def test_an_unknown_ticker_has_no_anchor_filing() -> None:
    sec = _Sec()
    adapter = sec.adapter()
    with adapter.analysis_scope(subject_id="NOPE", provider_id=SEC_PROVIDER_ID, as_of=_BOUNDARY):
        assert adapter.resolve_cover_listing(CoverListingRequest("NOPE", SEC_PROVIDER_ID)).reason is (
            CoverUnavailableReason.NO_ANCHOR_FILING
        )
    assert sec.cover_urls == []


def test_an_anchor_filing_with_no_form_or_acceptance_time_is_not_read() -> None:
    sec = _Sec()
    adapter = sec.adapter()
    request = CoverListingRequest("JPM", SEC_PROVIDER_ID)
    with adapter.analysis_scope(subject_id="JPM", provider_id=SEC_PROVIDER_ID, as_of=_BOUNDARY):
        snapshot = financial_facts._ACTIVE_SNAPSHOT.get()  # noqa: SLF001
        assert snapshot is not None
        cases: list[tuple[dict[str, Any], CoverUnavailableReason]] = [
            ({"filing_forms": {}}, CoverUnavailableReason.FORM_UNAVAILABLE),
            ({"acceptance_by_accession": {}}, CoverUnavailableReason.ACCEPTANCE_UNAVAILABLE),
        ]
        for changes, reason in cases:
            token = financial_facts._ACTIVE_SNAPSHOT.set(replace(snapshot, **changes))  # noqa: SLF001
            try:
                assert adapter.resolve_cover_listing(request).reason is reason
            finally:
                financial_facts._ACTIVE_SNAPSHOT.reset(token)  # noqa: SLF001
    assert sec.cover_urls == []


def test_a_filing_the_sec_lists_with_an_unaddressable_accession_is_an_unexpected_response() -> None:
    sec = _Sec()
    adapter = sec.adapter()
    with adapter.analysis_scope(subject_id="JPM", provider_id=SEC_PROVIDER_ID, as_of=_BOUNDARY):
        snapshot = financial_facts._ACTIVE_SNAPSHOT.get()  # noqa: SLF001
        assert snapshot is not None
        bad = replace(
            snapshot,
            latest_annual_accession="bad",
            filing_forms={"bad": "10-K"},
            acceptance_by_accession={"bad": _BOUNDARY - timedelta(days=1)},
        )
        token = financial_facts._ACTIVE_SNAPSHOT.set(bad)  # noqa: SLF001
        try:
            with pytest.raises(FinancialProviderError) as caught:
                adapter.resolve_cover_listing(CoverListingRequest("JPM", SEC_PROVIDER_ID))
        finally:
            financial_facts._ACTIVE_SNAPSHOT.reset(token)  # noqa: SLF001
    assert caught.value.kind is ProviderFailureKind.UNEXPECTED_RESPONSE


# --- production routing ------------------------------------------------------------------------------------------


def test_the_production_provider_routes_the_listing_request_to_the_sec_adapter() -> None:
    sec = _Sec()
    adapter = sec.adapter()
    production = ProductionFinancialFactsProvider(sec_edgar=adapter, yfinance=MagicMock(spec=["fetch_facts"]))
    assert isinstance(adapter, CoverListingProvider)
    with production.analysis_scope(subject_id="JPM", provider_id=SEC_PROVIDER_ID, as_of=_BOUNDARY):
        resolution = production.resolve_cover_listing(CoverListingRequest("JPM", SEC_PROVIDER_ID))
    assert resolution.evidence is not None
    assert resolution.evidence.kind is SecurityKind.SHARE


def test_the_production_provider_refuses_a_provider_without_the_capability() -> None:
    production = ProductionFinancialFactsProvider(
        sec_edgar=MagicMock(spec=["fetch_facts"]), yfinance=MagicMock(spec=["fetch_facts"])
    )
    for provider_id in ("yfinance", SEC_PROVIDER_ID, "unknown"):
        resolution = production.resolve_cover_listing(CoverListingRequest("JPM", provider_id))
        assert resolution.reason is CoverUnavailableReason.PROVIDER_UNSUPPORTED
