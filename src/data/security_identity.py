"""Provider-neutral security identity and best-effort resolution contracts.

Ticker symbols are normalized display identifiers, not durable issuer or
instrument identifiers.  A :class:`SecurityIdentity` is therefore an immutable
snapshot of the descriptive metadata actually resolved for one analysis run.
Step 3.4 must persist that snapshot with the Analysis Run rather than looking up
the ticker again when a completed run is viewed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable


def _normalized_required(value: str, field_name: str, *, uppercase: bool = False) -> str:
    """Normalize one required short string without inventing content."""
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty.")
    return normalized.upper() if uppercase else normalized


def _normalized_optional(value: str | None, field_name: str) -> str | None:
    """Normalize optional whitespace while preserving capitalization and punctuation."""
    if value is None:
        return None
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty when supplied.")
    return normalized


@dataclass(frozen=True)
class SecurityIdentityRequest:
    """Request current descriptive identity metadata from one named provider."""

    ticker: str
    provider_id: str

    def __post_init__(self) -> None:
        """Normalize the venue-scoped ticker and provider identifier."""
        object.__setattr__(self, "ticker", _normalized_required(self.ticker, "ticker", uppercase=True))
        object.__setattr__(self, "provider_id", _normalized_required(self.provider_id, "provider_id"))


@dataclass(frozen=True)
class SecurityIdentity:
    """Immutable descriptive identity snapshot retained for one analysis run.

    ``resolved_at`` records when current metadata was obtained.  It does not
    establish that the same identity applied at a historical analysis ``as_of``.
    """

    ticker: str
    provider_id: str
    resolved_at: datetime
    instrument_name: str | None = None
    listing_venue: str | None = None
    issuer_identifier: str | None = None
    instrument_identifier: str | None = None

    def __post_init__(self) -> None:
        """Normalize metadata and require an aware resolution timestamp."""
        object.__setattr__(self, "ticker", _normalized_required(self.ticker, "ticker", uppercase=True))
        object.__setattr__(self, "provider_id", _normalized_required(self.provider_id, "provider_id"))
        for field_name in (
            "instrument_name",
            "listing_venue",
            "issuer_identifier",
            "instrument_identifier",
        ):
            object.__setattr__(self, field_name, _normalized_optional(getattr(self, field_name), field_name))
        if self.resolved_at.tzinfo is None or self.resolved_at.tzinfo.utcoffset(self.resolved_at) is None:
            raise ValueError("resolved_at must be timezone-aware.")


@runtime_checkable
class SecurityIdentityProvider(Protocol):
    """Narrow optional provider capability for descriptive security metadata."""

    def resolve_security_identity(self, request: SecurityIdentityRequest) -> SecurityIdentity | None:
        """Return current descriptive identity when supported and available."""
        ...


class IdentityResolutionStatus(StrEnum):
    """Classified outcome of a fail-open identity lookup."""

    RESOLVED = "resolved"
    UNAVAILABLE = "unavailable"
    PROVIDER_ERROR = "provider_error"


@dataclass(frozen=True)
class SecurityIdentityResolution:
    """Best-effort identity outcome carried separately from financial results."""

    status: IdentityResolutionStatus
    identity: SecurityIdentity | None
    message: str

    def __post_init__(self) -> None:
        """Keep status, identity, and diagnostic message coherent."""
        message = " ".join(self.message.split())
        if not message:
            raise ValueError("message must be non-empty.")
        object.__setattr__(self, "message", message)
        if self.status is IdentityResolutionStatus.RESOLVED and self.identity is None:
            raise ValueError("resolved identity status requires an identity snapshot.")
        if self.status is not IdentityResolutionStatus.RESOLVED and self.identity is not None:
            raise ValueError("unavailable identity status cannot carry an identity snapshot.")


def resolve_security_identity(
    provider: object,
    request: SecurityIdentityRequest,
) -> SecurityIdentityResolution:
    """Resolve identity exactly once and convert every failure to diagnostics.

    This boundary deliberately fails open: identity cannot change calculation
    status, classification, or data eligibility.
    """
    if not isinstance(provider, SecurityIdentityProvider):
        return SecurityIdentityResolution(
            IdentityResolutionStatus.UNAVAILABLE,
            None,
            f"Provider {request.provider_id!r} does not expose security identity metadata.",
        )
    try:
        identity = provider.resolve_security_identity(request)
    except Exception:
        return SecurityIdentityResolution(
            IdentityResolutionStatus.PROVIDER_ERROR,
            None,
            f"Provider {request.provider_id!r} could not resolve security identity metadata.",
        )
    if identity is None:
        return SecurityIdentityResolution(
            IdentityResolutionStatus.UNAVAILABLE,
            None,
            f"Provider {request.provider_id!r} returned no security identity metadata.",
        )
    if identity.ticker != request.ticker or identity.provider_id != request.provider_id:
        return SecurityIdentityResolution(
            IdentityResolutionStatus.PROVIDER_ERROR,
            None,
            f"Provider {request.provider_id!r} returned mismatched security identity metadata.",
        )
    return SecurityIdentityResolution(
        IdentityResolutionStatus.RESOLVED,
        identity,
        f"Resolved current descriptive security identity via {request.provider_id!r}.",
    )


def security_identity_payload(
    ticker: str,
    resolution: SecurityIdentityResolution | None,
) -> dict[str, Any]:
    """Return the stable Analysis Run identity-snapshot handoff payload.

    Optional fields remain explicit ``None`` values.  Consumers must persist
    this snapshot and must not relabel the run through a later ticker lookup.
    """
    normalized_ticker = _normalized_required(ticker, "ticker", uppercase=True)
    identity = resolution.identity if resolution is not None else None
    if identity is not None and identity.ticker != normalized_ticker:
        raise ValueError("Security identity ticker does not match the presented analysis ticker.")
    return {
        "ticker": normalized_ticker,
        "instrument_name": identity.instrument_name if identity is not None else None,
        "listing_venue": identity.listing_venue if identity is not None else None,
        "issuer_identifier": identity.issuer_identifier if identity is not None else None,
        "instrument_identifier": identity.instrument_identifier if identity is not None else None,
        "provider_id": identity.provider_id if identity is not None else None,
        "resolved_at": identity.resolved_at.isoformat() if identity is not None else None,
    }


def security_display_label(ticker: str, resolution: SecurityIdentityResolution | None) -> str:
    """Return ``Instrument Name (TICKER)`` or the normalized ticker alone."""
    normalized_ticker = _normalized_required(ticker, "ticker", uppercase=True)
    identity = resolution.identity if resolution is not None else None
    if identity is None or identity.instrument_name is None:
        return normalized_ticker
    if identity.ticker != normalized_ticker:
        raise ValueError("Security identity ticker does not match the presented analysis ticker.")
    return f"{identity.instrument_name} ({normalized_ticker})"
