"""Provider-neutral instrument-kind evidence and request-scoped composition.

Security identity and instrument kind are independent evidence.  This module
composes their snapshots without rewriting field provenance or turning optional
metadata failures into analysis control flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from src.data.security_identity import (
    IdentityResolutionStatus,
    SecurityIdentity,
    SecurityIdentityProvider,
    SecurityIdentityRequest,
    SecurityIdentityResolution,
    _normalized_required,
)
from src.data.security_unit import SecurityUnitEvidence

_YFINANCE_PROVIDER_ID = "yfinance"
_YFINANCE_KIND_MAPPING = {
    "EQUITY": "equity",
    "ETF": "etf",
    "CRYPTOCURRENCY": "cryptocurrency",
}


class InstrumentKind(StrEnum):
    """Reviewed provider-neutral instrument classifications."""

    EQUITY = "equity"
    ETF = "etf"
    CRYPTOCURRENCY = "cryptocurrency"


@dataclass(frozen=True)
class InstrumentKindRequest:
    """Request current instrument-kind evidence from one named provider."""

    ticker: str
    provider_id: str

    def __post_init__(self) -> None:
        """Normalize the venue-scoped ticker and provider identifier."""
        object.__setattr__(self, "ticker", _normalized_required(self.ticker, "ticker", uppercase=True))
        object.__setattr__(self, "provider_id", _normalized_required(self.provider_id, "provider_id"))


def reviewed_instrument_kind(provider_id: str, provider_value: str) -> InstrumentKind | None:
    """Return the normalized kind for one exactly reviewed provider value.

    Unreviewed providers and values deliberately remain unclassified.  Adding
    another mapping requires a provider-evidence review rather than an inferred
    fallback category.
    """
    normalized_provider_id = _normalized_required(provider_id, "provider_id")
    normalized_provider_value = _normalized_required(provider_value, "provider_value")
    if normalized_provider_id != _YFINANCE_PROVIDER_ID:
        return None
    mapped_value = _YFINANCE_KIND_MAPPING.get(normalized_provider_value)
    return InstrumentKind(mapped_value) if mapped_value is not None else None


@dataclass(frozen=True)
class InstrumentKindEvidence:
    """Immutable raw and normalized instrument-kind evidence from one provider."""

    ticker: str
    kind: InstrumentKind | None
    provider_value: str
    provider_id: str
    resolved_at: datetime

    def __post_init__(self) -> None:
        """Normalize evidence and enforce the approved provider mapping."""
        ticker = _normalized_required(self.ticker, "ticker", uppercase=True)
        provider_id = _normalized_required(self.provider_id, "provider_id")
        provider_value = _normalized_required(self.provider_value, "provider_value")
        object.__setattr__(self, "ticker", ticker)
        object.__setattr__(self, "provider_id", provider_id)
        object.__setattr__(self, "provider_value", provider_value)
        if self.resolved_at.tzinfo is None or self.resolved_at.tzinfo.utcoffset(self.resolved_at) is None:
            raise ValueError("resolved_at must be timezone-aware.")
        reviewed_kind = reviewed_instrument_kind(provider_id, provider_value)
        if self.kind is not reviewed_kind:
            raise ValueError("kind must match the reviewed provider-value mapping.")


def instrument_kind_evidence_payload(evidence: InstrumentKindEvidence | None) -> dict[str, Any] | None:
    """Return the stable nullable serialization shape for kind evidence."""
    if evidence is None:
        return None
    return {
        "kind": evidence.kind.value if evidence.kind is not None else None,
        "provider_value": evidence.provider_value,
        "provider_id": evidence.provider_id,
        "resolved_at": evidence.resolved_at.isoformat(),
    }


@runtime_checkable
class InstrumentKindProvider(Protocol):
    """Narrow optional provider capability for instrument classification."""

    def resolve_instrument_kind(self, request: InstrumentKindRequest) -> InstrumentKindEvidence | None:
        """Return current instrument-kind evidence when supported and available."""
        ...


class InstrumentProfileCapability(StrEnum):
    """Optional evidence capability attempted during profile composition."""

    SECURITY_IDENTITY = "security_identity"
    INSTRUMENT_KIND = "instrument_kind"


class InstrumentProfileResolutionStatus(StrEnum):
    """Classified result of one profile-capability attempt."""

    RESOLVED = "resolved"
    UNSUPPORTED = "unsupported"
    UNAVAILABLE = "unavailable"
    PROVIDER_ERROR = "provider_error"


@dataclass(frozen=True)
class InstrumentProfileDiagnostic:
    """Ordered diagnostic for one provider-capability attempt."""

    capability: InstrumentProfileCapability
    provider_id: str
    status: InstrumentProfileResolutionStatus
    message: str

    def __post_init__(self) -> None:
        """Normalize diagnostic identifiers and require a useful message."""
        object.__setattr__(self, "provider_id", _normalized_required(self.provider_id, "provider_id"))
        object.__setattr__(self, "message", _normalized_required(self.message, "message"))


@dataclass(frozen=True)
class InstrumentProfile:
    """Composed request-scoped identity and kind evidence with provenance."""

    ticker: str
    identity: SecurityIdentity | None
    kind_evidence: InstrumentKindEvidence | None
    diagnostics: tuple[InstrumentProfileDiagnostic, ...]
    security_unit_evidence: SecurityUnitEvidence | None = None

    def __post_init__(self) -> None:
        """Normalize the ticker and reject evidence for another instrument."""
        normalized_ticker = _normalized_required(self.ticker, "ticker", uppercase=True)
        object.__setattr__(self, "ticker", normalized_ticker)
        if self.identity is not None and self.identity.ticker != normalized_ticker:
            raise ValueError("Security identity ticker does not match the instrument profile ticker.")
        if self.kind_evidence is not None and self.kind_evidence.ticker != normalized_ticker:
            raise ValueError("Instrument-kind ticker does not match the instrument profile ticker.")
        if self.security_unit_evidence is not None and self.security_unit_evidence.ticker != normalized_ticker:
            raise ValueError("Security-unit ticker does not match the instrument profile ticker.")


def profile_identity_resolution(profile: InstrumentProfile) -> SecurityIdentityResolution:
    """Project composed identity evidence onto the established display contract."""
    if profile.identity is not None:
        return SecurityIdentityResolution(
            IdentityResolutionStatus.RESOLVED,
            profile.identity,
            f"Resolved current descriptive security identity via {profile.identity.provider_id!r}.",
        )
    identity_diagnostics = tuple(
        item for item in profile.diagnostics if item.capability is InstrumentProfileCapability.SECURITY_IDENTITY
    )
    status = (
        IdentityResolutionStatus.PROVIDER_ERROR
        if any(item.status is InstrumentProfileResolutionStatus.PROVIDER_ERROR for item in identity_diagnostics)
        else IdentityResolutionStatus.UNAVAILABLE
    )
    return SecurityIdentityResolution(
        status,
        None,
        "No security identity metadata was resolved by the instrument-profile candidates.",
    )


@dataclass(frozen=True)
class InstrumentProfileCandidate:
    """One explicitly ordered provider candidate used during composition."""

    provider_id: str
    provider: object

    def __post_init__(self) -> None:
        """Normalize the provider identifier used to validate returned evidence."""
        object.__setattr__(self, "provider_id", _normalized_required(self.provider_id, "provider_id"))


def compose_instrument_profile(
    ticker: str,
    *,
    identity_candidates: tuple[InstrumentProfileCandidate, ...],
    kind_candidate: InstrumentProfileCandidate | None,
) -> InstrumentProfile:
    """Resolve one profile with explicit identity precedence and fail-open kind.

    Each provider/capability pair is attempted at most once.  Identity lookup
    stops at the first resolved candidate; kind lookup is independent.  The
    caller controls candidate precedence and can inject deterministic evidence
    providers without constructing any live adapter.
    """
    normalized_ticker = _normalized_required(ticker, "ticker", uppercase=True)
    _validate_identity_candidates(identity_candidates)
    diagnostics: list[InstrumentProfileDiagnostic] = []
    identity: SecurityIdentity | None = None

    for candidate in identity_candidates:
        identity, diagnostic = _resolve_identity_candidate(normalized_ticker, candidate)
        diagnostics.append(diagnostic)
        if identity is not None:
            break

    kind_evidence: InstrumentKindEvidence | None = None
    if kind_candidate is not None:
        kind_evidence, diagnostic = _resolve_kind_candidate(normalized_ticker, kind_candidate)
        diagnostics.append(diagnostic)

    return InstrumentProfile(
        ticker=normalized_ticker,
        identity=identity,
        kind_evidence=kind_evidence,
        diagnostics=tuple(diagnostics),
    )


def _validate_identity_candidates(candidates: tuple[InstrumentProfileCandidate, ...]) -> None:
    """Reject ambiguous duplicate provider entries in the precedence list."""
    provider_ids = tuple(candidate.provider_id for candidate in candidates)
    if len(provider_ids) != len(set(provider_ids)):
        raise ValueError("identity_candidates must not repeat a provider_id.")


def _resolve_identity_candidate(
    ticker: str,
    candidate: InstrumentProfileCandidate,
) -> tuple[SecurityIdentity | None, InstrumentProfileDiagnostic]:
    """Attempt one identity candidate and retain a classified diagnostic."""
    provider_id = candidate.provider_id
    if not isinstance(candidate.provider, SecurityIdentityProvider):
        return None, _diagnostic(
            InstrumentProfileCapability.SECURITY_IDENTITY,
            provider_id,
            InstrumentProfileResolutionStatus.UNSUPPORTED,
            f"Provider {provider_id!r} does not expose security identity metadata.",
        )
    try:
        identity = candidate.provider.resolve_security_identity(SecurityIdentityRequest(ticker, provider_id))
    except Exception:
        return None, _diagnostic(
            InstrumentProfileCapability.SECURITY_IDENTITY,
            provider_id,
            InstrumentProfileResolutionStatus.PROVIDER_ERROR,
            f"Provider {provider_id!r} could not resolve security identity metadata.",
        )
    if identity is None:
        return None, _diagnostic(
            InstrumentProfileCapability.SECURITY_IDENTITY,
            provider_id,
            InstrumentProfileResolutionStatus.UNAVAILABLE,
            f"Provider {provider_id!r} returned no security identity metadata.",
        )
    if identity.ticker != ticker or identity.provider_id != provider_id:
        return None, _diagnostic(
            InstrumentProfileCapability.SECURITY_IDENTITY,
            provider_id,
            InstrumentProfileResolutionStatus.PROVIDER_ERROR,
            f"Provider {provider_id!r} returned mismatched security identity metadata.",
        )
    return identity, _diagnostic(
        InstrumentProfileCapability.SECURITY_IDENTITY,
        provider_id,
        InstrumentProfileResolutionStatus.RESOLVED,
        f"Resolved current descriptive security identity via {provider_id!r}.",
    )


def _resolve_kind_candidate(
    ticker: str,
    candidate: InstrumentProfileCandidate,
) -> tuple[InstrumentKindEvidence | None, InstrumentProfileDiagnostic]:
    """Attempt one kind candidate and retain a classified diagnostic."""
    provider_id = candidate.provider_id
    if not isinstance(candidate.provider, InstrumentKindProvider):
        return None, _diagnostic(
            InstrumentProfileCapability.INSTRUMENT_KIND,
            provider_id,
            InstrumentProfileResolutionStatus.UNSUPPORTED,
            f"Provider {provider_id!r} does not expose instrument-kind metadata.",
        )
    try:
        evidence = candidate.provider.resolve_instrument_kind(InstrumentKindRequest(ticker, provider_id))
    except Exception:
        return None, _diagnostic(
            InstrumentProfileCapability.INSTRUMENT_KIND,
            provider_id,
            InstrumentProfileResolutionStatus.PROVIDER_ERROR,
            f"Provider {provider_id!r} could not resolve instrument-kind metadata.",
        )
    if evidence is None:
        return None, _diagnostic(
            InstrumentProfileCapability.INSTRUMENT_KIND,
            provider_id,
            InstrumentProfileResolutionStatus.UNAVAILABLE,
            f"Provider {provider_id!r} returned no instrument-kind metadata.",
        )
    if evidence.ticker != ticker or evidence.provider_id != provider_id:
        return None, _diagnostic(
            InstrumentProfileCapability.INSTRUMENT_KIND,
            provider_id,
            InstrumentProfileResolutionStatus.PROVIDER_ERROR,
            f"Provider {provider_id!r} returned mismatched instrument-kind metadata.",
        )
    return evidence, _diagnostic(
        InstrumentProfileCapability.INSTRUMENT_KIND,
        provider_id,
        InstrumentProfileResolutionStatus.RESOLVED,
        f"Resolved current instrument-kind metadata via {provider_id!r}.",
    )


def _diagnostic(
    capability: InstrumentProfileCapability,
    provider_id: str,
    status: InstrumentProfileResolutionStatus,
    message: str,
) -> InstrumentProfileDiagnostic:
    """Construct one normalized profile diagnostic."""
    return InstrumentProfileDiagnostic(capability, provider_id, status, message)
