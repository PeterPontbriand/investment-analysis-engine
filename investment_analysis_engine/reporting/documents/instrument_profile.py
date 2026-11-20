"""The instrument profile document: what the engine knows about the instrument a ticker names.

One document serves both the read of the stored profile and the live lookup, and the command line writes it with
``--json``. It always describes a resolved profile; a ticker with no profile is a failure, not a document.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from investment_analysis_engine.data.instrument_profile import InstrumentKind
from investment_analysis_engine.data.instrument_profile_cache import StoredInstrumentProfile
from investment_analysis_engine.reporting.documents.timestamp import DocumentTimestamp
from investment_analysis_engine.reporting.presentation import provider_display_name

_UNKNOWN = "unknown"
_KIND_NAMES = {
    InstrumentKind.EQUITY: "equity",
    InstrumentKind.ETF: "ETF",
    InstrumentKind.CRYPTOCURRENCY: "cryptocurrency",
}


class InstrumentProfileDocument(BaseModel):
    """One ticker's instrument profile: its identity, its kind and the currency its price is quoted in.

    ``schema_version`` is this document's own lineage and is independent of every other document's.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    ticker: str = Field(description="The ticker the profile describes, trimmed and upper-cased.")
    refreshed_at: DocumentTimestamp = Field(
        description=(
            "When the profile was last checked with a data provider, as an ISO 8601 instant with its offset. "
            "A profile that has not been checked within the configured freshness window is still served."
        )
    )
    instrument_name: str | None = Field(description="The instrument's name; null when no provider gave one.")
    listing_venue: str | None = Field(
        description="The exchange or venue the instrument is listed on; null when unknown."
    )
    issuer_identifier: str | None = Field(
        description="The identifier of the issuer, such as an SEC central index key; null when unknown."
    )
    instrument_identifier: str | None = Field(
        description="The data provider's own identifier of the instrument; null when it gave none."
    )
    kind: InstrumentKind | None = Field(
        description="The kind of instrument, from the reviewed list; null when the provider's value is not on it."
    )
    quote_currency: str | None = Field(
        description=(
            "The currency the listing's price is quoted in, as the provider reports it, such as USD; null when "
            "the provider reported none."
        )
    )
    provider_id: str = Field(
        description="The data provider that gave the identity; /v1/info lists the providers with their names."
    )


def build_instrument_profile_document(stored: StoredInstrumentProfile) -> InstrumentProfileDocument:
    """Build the document of a stored or freshly looked-up profile.

    Raises:
        ValueError: If the profile has no identity, which no stored profile lacks because only an identity-anchored
            profile is stored.
    """
    profile = stored.profile
    identity = profile.identity
    if identity is None:
        raise ValueError("An instrument profile document needs a profile with an identity.")
    evidence = profile.kind_evidence
    return InstrumentProfileDocument(
        ticker=profile.ticker,
        refreshed_at=stored.refreshed_at,
        instrument_name=identity.instrument_name,
        listing_venue=identity.listing_venue,
        issuer_identifier=identity.issuer_identifier,
        instrument_identifier=identity.instrument_identifier,
        kind=None if evidence is None else evidence.kind,
        quote_currency=profile.quote_currency,
        provider_id=identity.provider_id,
    )


def render_instrument_profile_text(document: InstrumentProfileDocument) -> str:
    """Render the document as the lines the command line prints: the heading, then one line for each fact."""
    heading = document.ticker if document.instrument_name is None else f"{document.instrument_name} ({document.ticker})"
    kind = _UNKNOWN if document.kind is None else _KIND_NAMES[document.kind]
    lines = (
        heading,
        f"Kind: {kind}",
        f"Listing venue: {document.listing_venue or _UNKNOWN}",
        f"Quote currency: {document.quote_currency or _UNKNOWN}",
        f"Issuer identifier: {document.issuer_identifier or _UNKNOWN}",
        f"Instrument identifier: {document.instrument_identifier or _UNKNOWN}",
        f"Identity from: {provider_display_name(document.provider_id)}",
        f"Last checked: {document.refreshed_at.isoformat()}",
    )
    return "\n".join(lines)


__all__ = ["InstrumentProfileDocument", "build_instrument_profile_document", "render_instrument_profile_text"]
