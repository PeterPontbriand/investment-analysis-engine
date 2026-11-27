"""The reviewed listing-venue tables: each captured value maps to its code, and anything else maps to none."""

import pytest

from investment_analysis_engine.data.listing_venue import (
    FILING_COVER_VENUES,
    IDENTITY_VENUE_SOURCES,
    LISTING_VENUE_FIELD_TERM,
    LISTING_VENUE_TERMS,
    SEC_TICKER_FILE_VENUES,
    YAHOO_VENUES,
    ListingVenue,
    ListingVenueReading,
    VenueSource,
    listing_venue_code,
    read_identity_listing_venue,
    read_listing_venue,
    unmapped_ticker_file_exchanges,
    unmapped_ticker_file_message,
)
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from investment_analysis_engine.data.yfinance.client import YFINANCE_PROVIDER_ID
from investment_analysis_engine.help.bundle import load_help_bundle
from investment_analysis_engine.help.locales import DEFAULT_LOCALE

_SEC = [
    ("Nasdaq", ListingVenue.NASDAQ),
    ("NYSE", ListingVenue.NYSE_GROUP),
    ("OTC", ListingVenue.OTC),
    ("CBOE", ListingVenue.CBOE),
    ("TXSE", ListingVenue.TXSE),
]
_YAHOO = [
    ("NasdaqGS", ListingVenue.NASDAQ),
    ("NasdaqGM", ListingVenue.NASDAQ),
    ("NasdaqCM", ListingVenue.NASDAQ),
    ("NYSE", ListingVenue.NYSE),
    ("NYSEArca", ListingVenue.NYSE_ARCA),
    ("NYSE American", ListingVenue.NYSE_AMERICAN),
    ("Cboe US", ListingVenue.CBOE),
    ("TXSE", ListingVenue.TXSE),
    ("OTC Markets OTCPK", ListingVenue.OTC),
    ("OTC Markets OTCID", ListingVenue.OTC),
    ("OTC Markets OTCQX", ListingVenue.OTC),
    ("NMS", ListingVenue.NASDAQ),
    ("NGM", ListingVenue.NASDAQ),
    ("NCM", ListingVenue.NASDAQ),
    ("NYQ", ListingVenue.NYSE),
    ("PCX", ListingVenue.NYSE_ARCA),
    ("ASE", ListingVenue.NYSE_AMERICAN),
    ("BTS", ListingVenue.CBOE),
    ("TEX", ListingVenue.TXSE),
    ("PNK", ListingVenue.OTC),
    ("OID", ListingVenue.OTC),
    ("OQX", ListingVenue.OTC),
    ("Toronto", ListingVenue.TSX),
    ("TOR", ListingVenue.TSX),
    ("TSXV", ListingVenue.TSXV),
    ("VAN", ListingVenue.TSXV),
    ("Cboe CA", ListingVenue.CBOE_CANADA),
    ("NEO", ListingVenue.CBOE_CANADA),
    ("Canadian Sec", ListingVenue.CSE),
    ("CNQ", ListingVenue.CSE),
]
_COVER = [
    ("The Nasdaq Stock Market LLC", ListingVenue.NASDAQ),
    ("New York Stock Exchange", ListingVenue.NYSE),
    ("NYSE", ListingVenue.NYSE_GROUP),
    ("NYSE American", ListingVenue.NYSE_AMERICAN),
    ("NYSE Arca, Inc.", ListingVenue.NYSE_ARCA),
    ("Cboe BZX Exchange, Inc", ListingVenue.CBOE_BZX),
    ("CboeBZX", ListingVenue.CBOE_BZX),
]


@pytest.mark.parametrize(("text", "code"), _SEC)
def test_the_sec_ticker_file_table_maps_each_captured_value(text: str, code: ListingVenue) -> None:
    assert listing_venue_code(VenueSource.SEC_TICKER_FILE, text) is code


@pytest.mark.parametrize(("text", "code"), _YAHOO)
def test_the_yahoo_table_maps_each_captured_full_name_and_fallback_code(text: str, code: ListingVenue) -> None:
    assert listing_venue_code(VenueSource.YAHOO, text) is code


@pytest.mark.parametrize(("text", "code"), _COVER)
def test_the_filing_cover_table_maps_each_captured_value(text: str, code: ListingVenue) -> None:
    assert listing_venue_code(VenueSource.FILING_COVER, text) is code


def test_each_table_holds_exactly_its_captured_values() -> None:
    assert dict(SEC_TICKER_FILE_VENUES) == dict(_SEC)
    assert dict(YAHOO_VENUES) == dict(_YAHOO)
    assert dict(FILING_COVER_VENUES) == dict(_COVER)


@pytest.mark.parametrize(
    ("source", "text"),
    [
        (VenueSource.SEC_TICKER_FILE, "Toronto"),
        (VenueSource.SEC_TICKER_FILE, "nasdaq"),
        (VenueSource.YAHOO, "CCC"),
        (VenueSource.YAHOO, "LSE"),
        (VenueSource.FILING_COVER, "NASDAQ"),
        (VenueSource.FILING_COVER, "NYSE; The Nasdaq Stock Market LLC"),
        (VenueSource.FILING_COVER, "Toronto Stock Exchange"),
    ],
)
def test_a_value_no_table_lists_has_no_code_and_keeps_its_wording(source: VenueSource, text: str) -> None:
    assert listing_venue_code(source, text) is None
    assert read_listing_venue(source, text) == ListingVenueReading(code=None, provider_value=text)


def test_a_source_that_names_only_a_group_gets_the_group_code_and_one_that_names_an_exchange_gets_its_code() -> None:
    assert listing_venue_code(VenueSource.SEC_TICKER_FILE, "NYSE") is ListingVenue.NYSE_GROUP
    assert listing_venue_code(VenueSource.FILING_COVER, "NYSE") is ListingVenue.NYSE_GROUP
    assert listing_venue_code(VenueSource.YAHOO, "NYSE") is ListingVenue.NYSE
    assert listing_venue_code(VenueSource.FILING_COVER, "New York Stock Exchange") is ListingVenue.NYSE
    assert listing_venue_code(VenueSource.SEC_TICKER_FILE, "CBOE") is ListingVenue.CBOE
    assert listing_venue_code(VenueSource.YAHOO, "Cboe US") is ListingVenue.CBOE
    assert listing_venue_code(VenueSource.FILING_COVER, "CboeBZX") is ListingVenue.CBOE_BZX


@pytest.mark.parametrize("text", [None, "", "   "])
@pytest.mark.parametrize("source", list(VenueSource))
def test_a_source_that_gave_no_venue_gives_no_reading(source: VenueSource, text: str | None) -> None:
    assert read_listing_venue(source, text) is None


@pytest.mark.parametrize("text", ["NONE", "none", "None", " NONE "])
def test_a_cover_that_states_no_exchange_gives_no_reading(text: str) -> None:
    assert read_listing_venue(VenueSource.FILING_COVER, text) is None


def test_none_is_the_wording_of_no_exchange_only_on_a_cover() -> None:
    assert read_listing_venue(VenueSource.YAHOO, "NONE") == ListingVenueReading(code=None, provider_value="NONE")
    assert read_listing_venue(VenueSource.SEC_TICKER_FILE, "NONE") == ListingVenueReading(
        code=None, provider_value="NONE"
    )


def test_an_identity_is_read_with_the_table_of_its_provider() -> None:
    assert read_identity_listing_venue(SEC_PROVIDER_ID, "NYSE") == ListingVenueReading(ListingVenue.NYSE_GROUP, "NYSE")
    assert read_identity_listing_venue(YFINANCE_PROVIDER_ID, "NYSE") == ListingVenueReading(ListingVenue.NYSE, "NYSE")
    assert read_identity_listing_venue("another_provider", "NYSE") == ListingVenueReading(None, "NYSE")
    assert read_identity_listing_venue(None, "NYSE") == ListingVenueReading(None, "NYSE")
    assert read_identity_listing_venue(SEC_PROVIDER_ID, None) is None


def test_the_identity_sources_name_the_adapters_provider_identifiers() -> None:
    assert dict(IDENTITY_VENUE_SOURCES) == {
        SEC_PROVIDER_ID: VenueSource.SEC_TICKER_FILE,
        YFINANCE_PROVIDER_ID: VenueSource.YAHOO,
    }


def test_every_code_is_reached_by_a_table_and_has_a_glossary_term() -> None:
    reached = {*SEC_TICKER_FILE_VENUES.values(), *YAHOO_VENUES.values(), *FILING_COVER_VENUES.values()}
    assert reached == set(ListingVenue)
    assert set(LISTING_VENUE_TERMS) == {code.value for code in ListingVenue}
    bundle = load_help_bundle(DEFAULT_LOCALE)
    assert all(term_id in bundle.terms for term_id in LISTING_VENUE_TERMS.values())
    assert LISTING_VENUE_FIELD_TERM in bundle.terms


def test_the_listing_venue_term_says_the_venue_is_as_reported_and_never_that_it_is_the_primary_listing() -> None:
    term = load_help_bundle(DEFAULT_LOCALE).terms[LISTING_VENUE_FIELD_TERM]
    text = f"{term.definition} {term.body}"
    assert "as the data source reports it" in text
    assert "primary" not in text.lower()
    assert "a cryptocurrency is not listed on an exchange" in text.lower()


def _ticker_file(*exchanges: object) -> dict[str, object]:
    return {
        "fields": ["cik", "name", "ticker", "exchange"],
        "data": [[index, f"Name {index}", f"T{index}", exchange] for index, exchange in enumerate(exchanges)],
    }


def test_an_exchange_the_sec_table_does_not_know_is_reported_by_name() -> None:
    document = _ticker_file("Nasdaq", "NYSE", None, "", "NYSE Texas", "Nasdaq", "IEX", " IEX ")
    assert unmapped_ticker_file_exchanges(document) == ("IEX", "NYSE Texas")


def test_a_ticker_file_of_known_exchanges_has_none_unmapped() -> None:
    assert unmapped_ticker_file_exchanges(_ticker_file(*SEC_TICKER_FILE_VENUES, None)) == ()


@pytest.mark.parametrize(
    "document",
    [None, [], {}, {"fields": ["cik"], "data": [[1]]}, {"fields": ["exchange"], "data": "x"}, {"data": []}],
)
def test_a_document_in_another_layout_lists_no_unmapped_exchange(document: object) -> None:
    assert unmapped_ticker_file_exchanges(document) == ()


def test_short_and_non_text_rows_are_skipped() -> None:
    document = {"fields": ["cik", "exchange"], "data": [[1], "x", [2, 5], [3, "Bogus"]]}
    assert unmapped_ticker_file_exchanges(document) == ("Bogus",)


def test_the_live_checks_failure_message_names_every_exchange_the_table_does_not_know() -> None:
    message = unmapped_ticker_file_message(_ticker_file("Nasdaq", "NYSE Texas", "IEX"))
    assert message is not None
    assert "'IEX'" in message
    assert "'NYSE Texas'" in message
    assert "'Nasdaq'" not in message
    assert "SEC_TICKER_FILE_VENUES" in message


def test_the_live_check_passes_a_ticker_file_of_known_exchanges() -> None:
    assert unmapped_ticker_file_message(_ticker_file("Nasdaq", "NYSE", "OTC", "CBOE", "TXSE", None)) is None


def test_the_glossary_entries_word_the_otc_market_and_nyse_arca_as_reviewed() -> None:
    terms = load_help_bundle(DEFAULT_LOCALE).terms
    otc = terms[LISTING_VENUE_TERMS[ListingVenue.OTC.value]]
    text = f"{otc.definition} {otc.body}"
    assert "OTC Markets Group operates the main US over-the-counter quotation system" in text
    assert "OTCQX, OTCID and OTCPK (Pink) are tiers of OTC Markets Group's system" in text
    assert "SEC's list writes OTC without naming a tier" in text
    assert "run by" not in text
    arca = terms[LISTING_VENUE_TERMS[ListingVenue.NYSE_ARCA.value]]
    assert "Many exchange-traded funds are listed on NYSE Arca." in f"{arca.definition} {arca.body}"
