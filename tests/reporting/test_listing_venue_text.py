"""How a listing venue is written: the glossary term's name, the provider's wording when it differs, or the wording."""

from datetime import UTC, datetime

import pytest

from investment_analysis_engine.analysis.shared.financial_resolution import PriceComparison
from investment_analysis_engine.data.listing_venue import LISTING_VENUE_TERMS, ListingVenue
from investment_analysis_engine.data.security_identity import (
    IdentityResolutionStatus,
    SecurityIdentity,
    SecurityIdentityResolution,
)
from investment_analysis_engine.data.security_unit import (
    SecurityUnitDocument,
    SecurityUnitEvidence,
    SecurityUnitKind,
    SecurityUnitProvenance,
    SecurityUnitResolution,
    SecurityUnitResolutionReason,
)
from investment_analysis_engine.help.bundle import load_help_bundle
from investment_analysis_engine.help.locales import DEFAULT_LOCALE
from investment_analysis_engine.reporting.documents.shared_parts import (
    ListingVenuePart,
    filing_cover_venue_part,
    identity_listing_venue_part,
    price_comparison_part,
    security_identity_part,
)
from investment_analysis_engine.reporting.evidence_presentation import identity_detail_lines
from investment_analysis_engine.reporting.listing_venue_text import (
    cover_venue_text,
    identity_venue_text,
    listing_venue_name,
    listing_venue_text,
    part_venue_text,
)
from investment_analysis_engine.reporting.valuation_presentation import comparison_details, investor_comparison_evidence


def _resolution(provider_id: str, venue: str | None) -> SecurityIdentityResolution:
    identity = SecurityIdentity(
        ticker="KO",
        provider_id=provider_id,
        resolved_at=datetime(2026, 1, 2, tzinfo=UTC),
        instrument_name="The Coca-Cola Company",
        listing_venue=venue,
    )
    return SecurityIdentityResolution(IdentityResolutionStatus.RESOLVED, identity, "Resolved.")


def test_a_name_is_the_name_of_the_codes_glossary_term() -> None:
    terms = load_help_bundle(DEFAULT_LOCALE).terms
    assert {code: listing_venue_name(code) for code in ListingVenue} == {
        code: terms[LISTING_VENUE_TERMS[code.value]].name for code in ListingVenue
    }
    assert listing_venue_name(ListingVenue.NYSE_GROUP) == "NYSE Group Exchange"
    assert listing_venue_name(ListingVenue.CBOE_BZX) == "Cboe BZX Exchange"


def test_the_names_are_read_from_the_english_bundle_loaded_once() -> None:
    load_help_bundle.cache_clear()
    listing_venue_name(ListingVenue.NASDAQ)
    listing_venue_name(ListingVenue.NYSE)
    info = load_help_bundle.cache_info()
    assert (info.misses, info.hits) == (1, 1)
    assert load_help_bundle(DEFAULT_LOCALE) is load_help_bundle("en")


def test_the_provider_wording_follows_in_parentheses_when_it_differs_from_the_name() -> None:
    assert listing_venue_text(ListingVenue.NASDAQ, "NasdaqGS") == "Nasdaq Stock Market (NasdaqGS)"
    assert listing_venue_text(ListingVenue.NYSE, "NYSE") == "New York Stock Exchange (NYSE)"


def test_the_wording_is_not_repeated_when_it_equals_the_name_exactly() -> None:
    assert listing_venue_text(ListingVenue.NYSE, "New York Stock Exchange") == "New York Stock Exchange"
    assert listing_venue_text(ListingVenue.NYSE_AMERICAN, "NYSE American") == "NYSE American"
    assert listing_venue_text(ListingVenue.NYSE, "new york stock exchange") == (
        "New York Stock Exchange (new york stock exchange)"
    )


def test_an_unmapped_value_is_the_providers_wording() -> None:
    assert listing_venue_text(None, "Toronto") == "Toronto"
    assert part_venue_text(ListingVenuePart(code=None, provider_value="CCC")) == "CCC"


def test_an_identity_venue_is_read_with_its_providers_table() -> None:
    assert identity_venue_text("yfinance", "NYSE") == "New York Stock Exchange (NYSE)"
    assert identity_venue_text("sec_edgar", "NYSE") == "NYSE Group Exchange (NYSE)"
    assert identity_venue_text("yfinance", "Toronto") == "Toronto"
    assert identity_venue_text("yfinance", None) is None


def test_a_cover_venue_is_read_with_the_cover_table_and_no_exchange_gives_none() -> None:
    assert cover_venue_text("New York Stock Exchange") == "New York Stock Exchange"
    assert cover_venue_text("NYSE") == "NYSE Group Exchange (NYSE)"
    assert cover_venue_text("The Nasdaq Stock Market LLC") == "Nasdaq Stock Market (The Nasdaq Stock Market LLC)"
    assert cover_venue_text("NYSE; NASDAQ") == "NYSE; NASDAQ"
    assert cover_venue_text("NONE") is None
    assert cover_venue_text(None) is None


def test_the_identity_lines_of_a_run_write_the_venue_the_same_way() -> None:
    assert "Current listing venue: Nasdaq Stock Market (NasdaqGS)" in identity_detail_lines(
        _resolution("yfinance", "NasdaqGS")
    )
    assert "Current listing venue: Toronto" in identity_detail_lines(_resolution("yfinance", "Toronto"))
    assert "Current listing venue: not supplied by selected identity provider" in identity_detail_lines(
        _resolution("yfinance", None)
    )


def test_the_part_is_null_exactly_when_the_source_gave_no_venue() -> None:
    assert identity_listing_venue_part("yfinance", None) is None
    assert security_identity_part("KO", _resolution("yfinance", None)).listing_venue is None
    assert security_identity_part("KO", None).listing_venue is None
    assert filing_cover_venue_part("NONE") is None
    assert filing_cover_venue_part("none") is None
    assert filing_cover_venue_part(None) is None


def test_the_part_carries_the_code_and_the_wording_or_no_code_with_the_wording() -> None:
    assert security_identity_part("KO", _resolution("yfinance", "NYSE")).listing_venue == ListingVenuePart(
        code=ListingVenue.NYSE, provider_value="NYSE"
    )
    assert security_identity_part("KO", _resolution("sec_edgar", "NYSE")).listing_venue == ListingVenuePart(
        code=ListingVenue.NYSE_GROUP, provider_value="NYSE"
    )
    assert filing_cover_venue_part("CboeBZX") == ListingVenuePart(code=ListingVenue.CBOE_BZX, provider_value="CboeBZX")
    assert filing_cover_venue_part("A; B") == ListingVenuePart(code=None, provider_value="A; B")


@pytest.mark.parametrize("code", list(ListingVenue))
def test_a_part_serializes_the_code_as_its_value(code: ListingVenue) -> None:
    part = ListingVenuePart(code=code, provider_value="x")
    assert part.model_dump(mode="json") == {"code": code.value, "provider_value": "x"}


_STAMP = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)


def _comparison(venue: str | None) -> PriceComparison:
    unit = SecurityUnitEvidence(
        "KO", SecurityUnitKind.ORDINARY_SHARE, SecurityUnitKind.ORDINARY_SHARE, 1.0, "sec_edgar", "Annual filing"
    )
    provenance = SecurityUnitProvenance(
        "single_common_class",
        "123",
        "Common stock",
        (SecurityUnitDocument("001", "https://www.sec.gov/example", ("c1",), _STAMP, _STAMP, venue),),
    )
    resolution = SecurityUnitResolution(SecurityUnitResolutionReason.RESOLVED, unit, provenance)
    return PriceComparison("available", "verified", 10.0, resolution)


@pytest.mark.parametrize(
    ("cover_text", "written"),
    [
        ("New York Stock Exchange", "New York Stock Exchange"),
        ("NYSE", "NYSE Group Exchange (NYSE)"),
        ("Toronto Stock Exchange", "Toronto Stock Exchange"),
    ],
)
def test_the_filing_venue_lines_write_the_cover_venue_the_same_way(cover_text: str, written: str) -> None:
    comparison = _comparison(cover_text)
    assert f"Filing lists {written}; current venue not independently verified." in investor_comparison_evidence(
        comparison
    )
    assert any(
        line.startswith(f"Filing listing venue: {written} (filing available") for line in comparison_details(comparison)
    )
    part = price_comparison_part(comparison)
    assert part is not None
    assert part.provenance is not None
    assert part.provenance.documents[0].listing_venue is not None
    assert part_venue_text(part.provenance.documents[0].listing_venue) == written


@pytest.mark.parametrize("cover_text", [None, "NONE", "none"])
def test_a_cover_that_states_no_exchange_has_no_filing_venue_line_and_a_null_part(cover_text: str | None) -> None:
    comparison = _comparison(cover_text)
    assert not any("Filing lists" in line for line in investor_comparison_evidence(comparison))
    assert not any("Filing listing venue" in line for line in comparison_details(comparison))
    part = price_comparison_part(comparison)
    assert part is not None
    assert part.provenance is not None
    assert part.provenance.documents[0].listing_venue is None
