"""The text of a listing venue, written one way wherever the engine prints one.

A venue with a code shows the name of the code's glossary term, followed by the provider's wording in parentheses when
the wording is not the name itself. A venue with no code shows the provider's wording alone. The name has one home,
the glossary: it is read from the English help bundle, because the engine's text renderings are English.
"""

from investment_analysis_engine.data.listing_venue import (
    LISTING_VENUE_TERMS,
    ListingVenue,
    VenueSource,
    read_identity_listing_venue,
    read_listing_venue,
)
from investment_analysis_engine.help.bundle import load_help_bundle
from investment_analysis_engine.reporting.documents.shared_parts import ListingVenuePart

_TEXT_LOCALE = "en"
"""The tag of the locale the engine's text renderings are written in.

It is the tag itself, not ``DEFAULT_LOCALE``: that constant is the fallback for a request that names no available
locale and may change independently of the language the text renderings are written in.
"""


def listing_venue_name(code: ListingVenue) -> str:
    """Return the name of the glossary term that explains ``code``, from the cached English help bundle."""
    return load_help_bundle(_TEXT_LOCALE).terms[LISTING_VENUE_TERMS[code.value]].name


def listing_venue_text(code: ListingVenue | None, provider_value: str) -> str:
    """Return the venue as text: the term's name and the provider's wording when it differs, or the wording alone."""
    if code is None:
        return provider_value
    name = listing_venue_name(code)
    return name if name == provider_value else f"{name} ({provider_value})"


def part_venue_text(part: ListingVenuePart) -> str:
    """Return the text of a venue part."""
    return listing_venue_text(part.code, part.provider_value)


def identity_venue_text(provider_id: str | None, provider_value: str | None) -> str | None:
    """Return the text of the venue an identity holds, or ``None`` when the identity gives none."""
    reading = read_identity_listing_venue(provider_id, provider_value)
    return None if reading is None else listing_venue_text(reading.code, reading.provider_value)


def cover_venue_text(provider_value: str | None) -> str | None:
    """Return the text of a filing cover's venue, or ``None`` when the cover states no exchange."""
    reading = read_listing_venue(VenueSource.FILING_COVER, provider_value)
    return None if reading is None else listing_venue_text(reading.code, reading.provider_value)
