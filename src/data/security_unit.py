"""Typed evidence for filing-share and quoted-security compatibility.

The initial reviewed boundary is intentionally narrow: only an ordinary share
quoted one-for-one against the filing per-share unit can be affirmed.  This
module performs no ADR/ADS or currency conversion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from src.data.financial.provenance import ResolvedInput
from src.data.security_identity import _normalized_required


class SecurityUnitKind(StrEnum):
    """Reviewed filing and quoted-security unit kinds."""

    ORDINARY_SHARE = "ordinary_share"
    ADR = "adr"
    ADS = "ads"


class SecurityUnitCompatibilityStatus(StrEnum):
    """Outcome of the fail-closed security-unit predicate."""

    COMPATIBLE = "compatible"
    UNAVAILABLE = "unavailable"


class SecurityUnitCompatibilityReason(StrEnum):
    """Stable reason for a security-unit compatibility outcome."""

    AFFIRMATIVE_ORDINARY_SHARE_1_TO_1 = "affirmative_ordinary_share_1_to_1"
    MISSING_EVIDENCE = "missing_evidence"
    CURRENCY_MISMATCH = "currency_mismatch"
    MULTI_CLASS_AMBIGUITY = "multi_class_ambiguity"
    UNKNOWN_RATIO = "unknown_ratio"
    UNSUPPORTED_UNIT_KIND = "unsupported_unit_kind"
    NON_UNIT_RATIO = "non_unit_ratio"


class SecurityUnitResolutionReason(StrEnum):
    """Stable acquisition outcomes, distinct from numeric compatibility."""

    RESOLVED = "resolved"
    MISSING_EVIDENCE = "missing_evidence"
    PROVIDER_UNSUPPORTED = "provider_unsupported"
    PROVIDER_ERROR = "provider_error"
    UNSUPPORTED_TEMPORAL_EVIDENCE = "unsupported_temporal_evidence"
    SOURCE_MISMATCH = "source_mismatch"
    AMBIGUOUS_CLASS = "ambiguous_class"
    UNSUPPORTED_EVIDENCE = "unsupported_evidence"


@dataclass(frozen=True)
class SecurityUnitRequest:
    """Borrow resolved inputs for one ticker's share-unit verification."""

    ticker: str
    provider_id: str
    as_of: datetime | None
    inputs: tuple[ResolvedInput, ...]
    quote: ResolvedInput

    def __post_init__(self) -> None:
        """Normalize identity and validate the explicit temporal boundary."""
        object.__setattr__(self, "ticker", _normalized_required(self.ticker, "ticker", uppercase=True))
        object.__setattr__(self, "provider_id", _normalized_required(self.provider_id, "provider_id"))
        if self.as_of is not None and self.as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware.")


@dataclass(frozen=True)
class SecurityUnitDocument:
    """Immutable provenance for a verified filing document."""

    accession: str
    url: str
    context_ids: tuple[str, ...]
    available_at: datetime
    retrieved_at: datetime
    listing_venue: str | None = None


@dataclass(frozen=True)
class SecurityUnitProvenance:
    """Evidence scope for the reviewed single-common-class inference."""

    mapping_id: str
    cik: str
    class_title: str
    documents: tuple[SecurityUnitDocument, ...]


@dataclass(frozen=True)
class SecurityUnitResolution:
    """Retain acquisition failures without discarding financial results."""

    reason: SecurityUnitResolutionReason
    evidence: SecurityUnitEvidence | None = None
    provenance: SecurityUnitProvenance | None = None

    def __post_init__(self) -> None:
        """Require evidence exactly when acquisition succeeds."""
        if (self.reason is SecurityUnitResolutionReason.RESOLVED) != (self.evidence is not None):
            raise ValueError("Resolved unit evidence must agree with its acquisition reason.")
        if self.provenance is not None and self.evidence is None:
            raise ValueError("Unit provenance requires resolved evidence.")

    @property
    def status(self) -> str:
        """Return the stable acquisition status."""
        return "resolved" if self.evidence is not None else "unavailable"


@runtime_checkable
class SecurityUnitProvider(Protocol):
    """Optional request-scoped provider capability, independent of quotes."""

    def resolve_security_unit(self, request: SecurityUnitRequest) -> SecurityUnitResolution:
        """Return reviewed unit evidence or a classified absence."""
        ...


@dataclass(frozen=True)
class SecurityUnitEvidence:
    """Request-scoped evidence relating filing and quoted security units."""

    ticker: str
    filing_unit_kind: SecurityUnitKind
    quoted_unit_kind: SecurityUnitKind
    underlying_shares_per_quoted_unit: float | None
    provider_id: str
    source: str
    multi_class_ambiguous: bool = False

    def __post_init__(self) -> None:
        """Normalize identifiers and reject invalid affirmative ratios."""
        object.__setattr__(self, "ticker", _normalized_required(self.ticker, "ticker", uppercase=True))
        object.__setattr__(self, "provider_id", _normalized_required(self.provider_id, "provider_id"))
        object.__setattr__(self, "source", _normalized_required(self.source, "source"))
        ratio = self.underlying_shares_per_quoted_unit
        if ratio is not None and (not math.isfinite(ratio) or ratio <= 0):
            raise ValueError("underlying_shares_per_quoted_unit must be finite and positive when supplied.")


@dataclass(frozen=True)
class SecurityUnitCompatibility:
    """Typed result of evaluating one filing/quote unit relationship."""

    status: SecurityUnitCompatibilityStatus
    reason: SecurityUnitCompatibilityReason

    @property
    def is_compatible(self) -> bool:
        """Return whether the initial predicate affirmatively permits comparison."""
        return self.status is SecurityUnitCompatibilityStatus.COMPATIBLE


def evaluate_security_unit_compatibility(  # noqa: PLR0911
    evidence: SecurityUnitEvidence | None,
    *,
    filing_currency: str | None,
    quote_currency: str | None,
) -> SecurityUnitCompatibility:
    """Affirm only matching-currency ordinary-share evidence at exactly 1:1."""
    if evidence is None:
        return _unavailable(SecurityUnitCompatibilityReason.MISSING_EVIDENCE)
    normalized_filing_currency = _normalize_currency(filing_currency)
    normalized_quote_currency = _normalize_currency(quote_currency)
    if normalized_filing_currency is None or normalized_quote_currency is None:
        return _unavailable(SecurityUnitCompatibilityReason.MISSING_EVIDENCE)
    if normalized_filing_currency != normalized_quote_currency:
        return _unavailable(SecurityUnitCompatibilityReason.CURRENCY_MISMATCH)
    if evidence.multi_class_ambiguous:
        return _unavailable(SecurityUnitCompatibilityReason.MULTI_CLASS_AMBIGUITY)
    ratio = evidence.underlying_shares_per_quoted_unit
    if ratio is None:
        return _unavailable(SecurityUnitCompatibilityReason.UNKNOWN_RATIO)
    if (
        evidence.filing_unit_kind is not SecurityUnitKind.ORDINARY_SHARE
        or evidence.quoted_unit_kind is not SecurityUnitKind.ORDINARY_SHARE
    ):
        return _unavailable(SecurityUnitCompatibilityReason.UNSUPPORTED_UNIT_KIND)
    if ratio != 1.0:
        return _unavailable(SecurityUnitCompatibilityReason.NON_UNIT_RATIO)
    return SecurityUnitCompatibility(
        SecurityUnitCompatibilityStatus.COMPATIBLE,
        SecurityUnitCompatibilityReason.AFFIRMATIVE_ORDINARY_SHARE_1_TO_1,
    )


def _normalize_currency(currency: str | None) -> str | None:
    """Normalize a supplied currency without inferring a missing value."""
    if currency is None:
        return None
    normalized = currency.strip().upper()
    return normalized or None


def _unavailable(reason: SecurityUnitCompatibilityReason) -> SecurityUnitCompatibility:
    """Build one fail-closed compatibility result."""
    return SecurityUnitCompatibility(SecurityUnitCompatibilityStatus.UNAVAILABLE, reason)
