"""Typed evidence for filing-share and quoted-security compatibility.

The initial reviewed boundary is intentionally narrow: only an ordinary share
quoted one-for-one against the filing per-share unit can be affirmed.  This
module performs no ADR/ADS or currency conversion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

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
