"""The listing venue of an instrument: the reviewed code behind each provider's wording of a venue.

A listing venue reaches the engine as plain text in three places: the ``exchange`` column of SEC's ticker file, Yahoo's
``fullExchangeName`` (or its ``exchange`` code when the full name is missing) and the ``SecurityExchangeName`` fact on
a filing's cover. Each source words the same market differently, and a person cannot be expected to know what ``NYSE``,
``NasdaqGS`` or ``CboeBZX`` mean. This module holds the one table of each source, the one function from a source and a
provider's text to a code, and the glossary term of each code.

A code means exactly what its source asserts. A source that names one exchange gets that exchange's code; a source
that names only a group of exchanges gets the group's code. A value that no reviewed table lists has no code, and the
provider's text is still served. Every value in a table is backed by a captured specimen, recorded in the
listing-venue mapping record.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final


class ListingVenue(StrEnum):
    """A reviewed listing venue: one exchange, a group of exchanges or the over-the-counter market."""

    NASDAQ = "nasdaq"
    NYSE = "nyse"
    NYSE_GROUP = "nyse_group"
    NYSE_ARCA = "nyse_arca"
    NYSE_AMERICAN = "nyse_american"
    CBOE = "cboe"
    CBOE_BZX = "cboe_bzx"
    TXSE = "txse"
    OTC = "otc"
    TSX = "tsx"
    TSXV = "tsxv"
    CBOE_CANADA = "cboe_canada"
    CSE = "cse"


class VenueSource(StrEnum):
    """Where a venue's text came from, which decides the table that reads it."""

    SEC_TICKER_FILE = "sec_ticker_file"
    YAHOO = "yahoo"
    FILING_COVER = "filing_cover"


_SEC_PROVIDER = "sec_edgar"
_YAHOO_PROVIDER = "yfinance"

IDENTITY_VENUE_SOURCES: Final[Mapping[str, VenueSource]] = MappingProxyType(
    {
        _SEC_PROVIDER: VenueSource.SEC_TICKER_FILE,
        _YAHOO_PROVIDER: VenueSource.YAHOO,
    }
)
"""The table that reads the venue of an identity, by the identity provider's identifier."""

SEC_TICKER_FILE_VENUES: Final[Mapping[str, ListingVenue]] = MappingProxyType(
    {
        "Nasdaq": ListingVenue.NASDAQ,
        # SEC's list names the NYSE group without saying which of its exchanges (New York Stock Exchange, NYSE
        # American or NYSE Arca) the security is listed on.
        "NYSE": ListingVenue.NYSE_GROUP,
        "OTC": ListingVenue.OTC,
        "CBOE": ListingVenue.CBOE,
        "TXSE": ListingVenue.TXSE,
    }
)
"""The values of the ``exchange`` column of SEC's ticker file, as the file writes them."""

YAHOO_VENUES: Final[Mapping[str, ListingVenue]] = MappingProxyType(
    {
        # ``fullExchangeName``.
        "NasdaqGS": ListingVenue.NASDAQ,
        "NasdaqGM": ListingVenue.NASDAQ,
        "NasdaqCM": ListingVenue.NASDAQ,
        "NYSE": ListingVenue.NYSE,
        "NYSEArca": ListingVenue.NYSE_ARCA,
        "NYSE American": ListingVenue.NYSE_AMERICAN,
        "Cboe US": ListingVenue.CBOE,
        "TXSE": ListingVenue.TXSE,
        "OTC Markets OTCPK": ListingVenue.OTC,
        "OTC Markets OTCID": ListingVenue.OTC,
        "OTC Markets OTCQX": ListingVenue.OTC,
        "Toronto": ListingVenue.TSX,
        "TSXV": ListingVenue.TSXV,
        "Cboe CA": ListingVenue.CBOE_CANADA,
        "Canadian Sec": ListingVenue.CSE,
        # ``exchange``, which the identity holds when ``fullExchangeName`` is missing.
        "NMS": ListingVenue.NASDAQ,
        "NGM": ListingVenue.NASDAQ,
        "NCM": ListingVenue.NASDAQ,
        "NYQ": ListingVenue.NYSE,
        "PCX": ListingVenue.NYSE_ARCA,
        "ASE": ListingVenue.NYSE_AMERICAN,
        "BTS": ListingVenue.CBOE,
        "TEX": ListingVenue.TXSE,
        "PNK": ListingVenue.OTC,
        "OID": ListingVenue.OTC,
        "OQX": ListingVenue.OTC,
        "TOR": ListingVenue.TSX,
        "VAN": ListingVenue.TSXV,
        "NEO": ListingVenue.CBOE_CANADA,
        "CNQ": ListingVenue.CSE,
    }
)
"""Yahoo's ``fullExchangeName`` and ``exchange`` values, as the identity stores them. ``CCC`` is deliberately absent."""

FILING_COVER_VENUES: Final[Mapping[str, ListingVenue]] = MappingProxyType(
    {
        "The Nasdaq Stock Market LLC": ListingVenue.NASDAQ,
        "New York Stock Exchange": ListingVenue.NYSE,
        # A bare "NYSE" is written by filers listed on NYSE, NYSE American and NYSE Arca alike.
        "NYSE": ListingVenue.NYSE_GROUP,
        "NYSE American": ListingVenue.NYSE_AMERICAN,
        "NYSE Arca, Inc.": ListingVenue.NYSE_ARCA,
        "Cboe BZX Exchange, Inc": ListingVenue.CBOE_BZX,
        "CboeBZX": ListingVenue.CBOE_BZX,
    }
)
"""The ``SecurityExchangeName`` text of a filing cover, as the cover shows it."""

_TABLES: Final[Mapping[VenueSource, Mapping[str, ListingVenue]]] = MappingProxyType(
    {
        VenueSource.SEC_TICKER_FILE: SEC_TICKER_FILE_VENUES,
        VenueSource.YAHOO: YAHOO_VENUES,
        VenueSource.FILING_COVER: FILING_COVER_VENUES,
    }
)

_COVER_NO_EXCHANGE = "NONE"
"""What a cover's ``SecurityExchangeName`` says when the filer states it has no exchange, in any letter case."""


@dataclass(frozen=True)
class ListingVenueReading:
    """A venue's text as a provider wrote it and the reviewed code it maps to, or ``None`` when no table lists it."""

    code: ListingVenue | None
    provider_value: str


def listing_venue_code(source: VenueSource, provider_value: str) -> ListingVenue | None:
    """Return the code of ``provider_value`` in the table of ``source``, or ``None`` when the table lacks it."""
    return _TABLES[source].get(provider_value)


def read_listing_venue(source: VenueSource | None, provider_value: str | None) -> ListingVenueReading | None:
    """Read one venue: the text and its code, or ``None`` when the source gave no venue.

    A missing or blank text gives no reading. So does a filing cover's ``NONE``, which is the filer stating that it has
    no exchange. A source with no table (``None``) gives the text with no code.
    """
    if provider_value is None or not provider_value.strip():
        return None
    if source is VenueSource.FILING_COVER and provider_value.strip().upper() == _COVER_NO_EXCHANGE:
        return None
    code = None if source is None else listing_venue_code(source, provider_value)
    return ListingVenueReading(code=code, provider_value=provider_value)


def read_identity_listing_venue(provider_id: str | None, provider_value: str | None) -> ListingVenueReading | None:
    """Read the venue an identity holds, choosing the table by the identity's provider.

    A provider with no table gives the text with no code.
    """
    source = None if provider_id is None else IDENTITY_VENUE_SOURCES.get(provider_id)
    return read_listing_venue(source, provider_value)


def unmapped_ticker_file_exchanges(ticker_map: object) -> tuple[str, ...]:
    """Return, sorted, the exchanges SEC's ticker file lists that the SEC table does not know.

    A row with no exchange is not an unknown exchange. A document that is not in the file's layout lists none, because
    the layout check reports it.
    """
    if not isinstance(ticker_map, Mapping):
        return ()
    fields = ticker_map.get("fields")
    data = ticker_map.get("data")
    if not isinstance(fields, (list, tuple)) or "exchange" not in fields or not isinstance(data, (list, tuple)):
        return ()
    at = fields.index("exchange")
    unknown: set[str] = set()
    for row in data:
        if not isinstance(row, (list, tuple)) or len(row) <= at:
            continue
        value = row[at]
        if isinstance(value, str) and value.strip() and value.strip() not in SEC_TICKER_FILE_VENUES:
            unknown.add(value.strip())
    return tuple(sorted(unknown))


def unmapped_ticker_file_message(ticker_map: object) -> str | None:
    """Return the live check's failure message for a ticker file with unknown exchanges, naming each, or ``None``."""
    unknown = unmapped_ticker_file_exchanges(ticker_map)
    if not unknown:
        return None
    names = ", ".join(repr(name) for name in unknown)
    return (
        f"SEC's ticker file lists exchanges that the SEC listing-venue table does not know: {names}. "
        "Review each against the filings and Yahoo, then add it to SEC_TICKER_FILE_VENUES in data/listing_venue.py "
        "with its captured specimen in the listing-venue mapping record."
    )


LISTING_VENUE_TERMS: Final[Mapping[str, str]] = MappingProxyType(
    {
        ListingVenue.NASDAQ.value: "listing-venue-nasdaq",
        ListingVenue.NYSE.value: "listing-venue-nyse",
        ListingVenue.NYSE_GROUP.value: "listing-venue-nyse-group",
        ListingVenue.NYSE_ARCA.value: "listing-venue-nyse-arca",
        ListingVenue.NYSE_AMERICAN.value: "listing-venue-nyse-american",
        ListingVenue.CBOE.value: "listing-venue-cboe",
        ListingVenue.CBOE_BZX.value: "listing-venue-cboe-bzx",
        ListingVenue.TXSE.value: "listing-venue-txse",
        ListingVenue.OTC.value: "listing-venue-otc",
        ListingVenue.TSX.value: "listing-venue-tsx",
        ListingVenue.TSXV.value: "listing-venue-tsxv",
        ListingVenue.CBOE_CANADA.value: "listing-venue-cboe-canada",
        ListingVenue.CSE.value: "listing-venue-cse",
    }
)
"""The glossary term that explains each listing venue, one entry for each value."""

LISTING_VENUE_FIELD_TERM: Final = "listing-venue"
"""The glossary term that explains the listing-venue field itself, which every venue has, mapped or not."""
