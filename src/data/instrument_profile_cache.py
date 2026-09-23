"""Durable freshness/refresh/ticker-reuse cache over live instrument-profile composition.

Provider precedence and disagreement handling belong entirely to
:func:`compose_instrument_profile` (P2-Profiles contract §3: "reuse the
ordering already established... unchanged"); this module owns only the
freshness/TTL/refresh decision and the identity-anchor persistence rule
layered on top of it (contract §2, §4). Only identity-anchored resolutions
become durable (contract §9-4): a ticker whose identity cannot be anchored is
resolved live on every call, exactly as ``compose_instrument_profile`` does
unwrapped, and nothing is written to the durable repository for it.
"""

import threading
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, runtime_checkable

from src.data.instrument_profile import (
    InstrumentKind,
    InstrumentKindEvidence,
    InstrumentProfile,
    InstrumentProfileCandidate,
    InstrumentProfileCapability,
    InstrumentProfileDiagnostic,
    InstrumentProfileResolutionStatus,
    compose_instrument_profile,
    instrument_kind_evidence_payload,
)
from src.data.quality import FreshnessPolicy, QualityContext, QualityOutcome, evaluate_freshness
from src.data.quality_reporting import publish_quality
from src.data.repositories.instrument_profiles import InstrumentProfileRecord, SQLiteInstrumentProfileRepository
from src.data.security_identity import SecurityIdentity, _normalized_required

_CACHE_PROVIDER_ID = "instrument_profile_cache"


def _identity_payload(identity: SecurityIdentity | None) -> dict[str, Any] | None:
    """Encode a raw identity snapshot for durable evidence storage."""
    if identity is None:
        return None
    return {
        "ticker": identity.ticker,
        "provider_id": identity.provider_id,
        "resolved_at": identity.resolved_at.isoformat(),
        "instrument_name": identity.instrument_name,
        "listing_venue": identity.listing_venue,
        "issuer_identifier": identity.issuer_identifier,
        "instrument_identifier": identity.instrument_identifier,
    }


def _identity_from_payload(payload: Mapping[str, Any] | None) -> SecurityIdentity | None:
    """Decode a raw identity snapshot from durable evidence storage."""
    if payload is None:
        return None
    return SecurityIdentity(
        ticker=payload["ticker"],
        provider_id=payload["provider_id"],
        resolved_at=datetime.fromisoformat(payload["resolved_at"]),
        instrument_name=payload["instrument_name"],
        listing_venue=payload["listing_venue"],
        issuer_identifier=payload["issuer_identifier"],
        instrument_identifier=payload["instrument_identifier"],
    )


def _kind_evidence_from_payload(ticker: str, payload: Mapping[str, Any] | None) -> InstrumentKindEvidence | None:
    """Decode raw instrument-kind evidence, reconstructing it against ``ticker``."""
    if payload is None:
        return None
    kind = payload["kind"]
    return InstrumentKindEvidence(
        ticker=ticker,
        kind=None if kind is None else InstrumentKind(kind),
        provider_value=payload["provider_value"],
        provider_id=payload["provider_id"],
        resolved_at=datetime.fromisoformat(payload["resolved_at"]),
    )


def _diagnostics_payload(diagnostics: tuple[InstrumentProfileDiagnostic, ...]) -> list[dict[str, Any]]:
    """Encode every diagnostic exactly as composed, preserving capability/provider/status."""
    return [
        {
            "capability": item.capability.value,
            "provider_id": item.provider_id,
            "status": item.status.value,
            "message": item.message,
        }
        for item in diagnostics
    ]


def _diagnostics_from_payload(payload: list[dict[str, Any]]) -> tuple[InstrumentProfileDiagnostic, ...]:
    """Decode diagnostics, preserving their original order and content."""
    return tuple(
        InstrumentProfileDiagnostic(
            InstrumentProfileCapability(item["capability"]),
            item["provider_id"],
            InstrumentProfileResolutionStatus(item["status"]),
            item["message"],
        )
        for item in payload
    )


def _encode_profile(profile: InstrumentProfile) -> dict[str, Any]:
    """Encode exactly what ``compose_instrument_profile`` produces, nothing more.

    Security-unit evidence is intentionally excluded: it is completed by a
    later, separate step (``complete_security_unit_profile``) after a profile
    is obtained, whether that profile came from cache or a live call.
    """
    return {
        "identity": _identity_payload(profile.identity),
        "kind_evidence": instrument_kind_evidence_payload(profile.kind_evidence),
        "diagnostics": _diagnostics_payload(profile.diagnostics),
    }


def _decode_profile(ticker: str, evidence: Mapping[str, Any]) -> InstrumentProfile:
    """Reconstruct the composed profile last durably persisted for ``ticker``."""
    return InstrumentProfile(
        ticker=ticker,
        identity=_identity_from_payload(evidence["identity"]),
        kind_evidence=_kind_evidence_from_payload(ticker, evidence["kind_evidence"]),
        diagnostics=_diagnostics_from_payload(evidence["diagnostics"]),
    )


def _with_diagnostic(profile: InstrumentProfile, diagnostic: InstrumentProfileDiagnostic) -> InstrumentProfile:
    """Append one cache-provenance diagnostic without disturbing composed evidence."""
    return replace(profile, diagnostics=(*profile.diagnostics, diagnostic))


@runtime_checkable
class InstrumentProfileResolver(Protocol):
    """Narrow capability consumed by production composition call sites.

    Callers that only need "resolve me a profile, cached or not" (Slice D's
    production wiring) depend on this instead of the concrete
    :class:`CachedInstrumentProfileResolver`, matching this project's existing
    narrow-Protocol convention (``SecurityIdentityProvider``,
    ``InstrumentKindProvider``) rather than a direct class dependency.
    """

    def resolve(
        self,
        ticker: str,
        *,
        identity_candidates: tuple[InstrumentProfileCandidate, ...],
        kind_candidate: InstrumentProfileCandidate | None,
        force_refresh: bool = False,
    ) -> InstrumentProfile:
        """Return a durable or live profile for ``ticker``."""
        ...


class CachedInstrumentProfileResolver:
    """Layer durable freshness/refresh/ticker-reuse over live profile composition.

    ``resolve`` has the same identity/kind-candidate contract as
    :func:`compose_instrument_profile`, plus ``force_refresh``. A fresh durable
    profile is reused without a live call; a stale or missing one triggers a
    live resolution. A resolution that yields a verified identity anchor
    (``SecurityIdentity.issuer_identifier``) is persisted through the Gate B
    repository, which mints, updates in place, or supersedes-and-mints per the
    accepted identity/ticker-reuse rule. A resolution with no anchor is never
    persisted; if a durable profile already exists for the ticker, it is
    reused (fail-open) with an explicit staleness diagnostic rather than
    discarded, since a provider capability failure is absence of evidence, not
    rejected evidence.

    Thread safety: one instance may be shared across concurrent worker
    threads (as watchlist refresh does). ``resolve()`` serializes its
    critical section per ticker: reading "is there a current row" and acting
    on that answer (mint, update, or supersede) is not atomic at the SQLite
    level once the partial-unique-index approach was ruled out (P2-Profiles
    contract §6), so two overlapping resolutions for the *same* ticker could
    otherwise both observe no current row and each mint a competing one.
    Resolutions for different tickers proceed fully in parallel.
    """

    def __init__(
        self,
        repository: SQLiteInstrumentProfileRepository,
        *,
        ttl: timedelta | None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Retain the caller-owned repository and an explicit, named TTL policy."""
        self._repository = repository
        self._ttl = ttl
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)
        self._locks_guard = threading.Lock()
        self._ticker_locks: dict[str, threading.Lock] = {}

    def resolve(
        self,
        ticker: str,
        *,
        identity_candidates: tuple[InstrumentProfileCandidate, ...],
        kind_candidate: InstrumentProfileCandidate | None,
        force_refresh: bool = False,
    ) -> InstrumentProfile:
        """Return a fresh durable profile, a live one, or a fail-open stale one.

        Args:
            ticker: The instrument ticker; normalized before lookup/storage.
            identity_candidates: Ordered identity providers, passed through
                unchanged to ``compose_instrument_profile`` on a live call.
            kind_candidate: The single instrument-kind provider, passed
                through unchanged to ``compose_instrument_profile``.
            force_refresh: Bypass durable reuse unconditionally; a resolved
                anchor still applies the identity/ticker-reuse rule on write.
        """
        normalized_ticker = _normalized_required(ticker, "ticker", uppercase=True)
        with self._lock_for(normalized_ticker):
            now = self._now()
            stored = self._repository.get(normalized_ticker)
            if not force_refresh and stored is not None and self._is_fresh(stored, now):
                return _with_diagnostic(
                    _decode_profile(normalized_ticker, stored.evidence),
                    InstrumentProfileDiagnostic(
                        InstrumentProfileCapability.CACHE,
                        _CACHE_PROVIDER_ID,
                        InstrumentProfileResolutionStatus.RESOLVED,
                        f"Reused the durable instrument profile last refreshed at {stored.refreshed_at.isoformat()}.",
                    ),
                )

            live = compose_instrument_profile(
                normalized_ticker, identity_candidates=identity_candidates, kind_candidate=kind_candidate
            )
            anchor = live.identity.issuer_identifier if live.identity is not None else None
            if anchor is not None:
                self._repository.put(normalized_ticker, identity_anchor=anchor, evidence=_encode_profile(live))
                return live

            if stored is not None:
                return _with_diagnostic(
                    _decode_profile(normalized_ticker, stored.evidence),
                    InstrumentProfileDiagnostic(
                        InstrumentProfileCapability.CACHE,
                        _CACHE_PROVIDER_ID,
                        InstrumentProfileResolutionStatus.UNAVAILABLE,
                        "Refresh could not confirm an identity anchor; reused the durable instrument profile last "
                        f"refreshed at {stored.refreshed_at.isoformat()}.",
                    ),
                )
            return live

    def _lock_for(self, ticker: str) -> threading.Lock:
        """Return this instance's serialization lock for one normalized ticker.

        ``_ticker_locks`` is never pruned: it grows by one entry per distinct
        ticker ever resolved through this instance. That is a deliberate,
        bounded assumption for today's callers — one resolver per CLI
        invocation or per watchlist refresh, both short-lived processes — not
        an oversight. Reusing one instance across a long-lived process with
        an unbounded ticker universe would need eviction added here.
        """
        with self._locks_guard:
            lock = self._ticker_locks.get(ticker)
            if lock is None:
                lock = threading.Lock()
                self._ticker_locks[ticker] = lock
            return lock

    def current_record(self, ticker: str) -> InstrumentProfileRecord | None:
        """Return the durable record for ``ticker`` without a live call or TTL check."""
        return self._repository.get(_normalized_required(ticker, "ticker", uppercase=True))

    def _now(self) -> datetime:
        now = self._clock()
        if now.utcoffset() is None:
            raise ValueError("Instrument profile cache clock must be timezone-aware.")
        return now

    def _is_fresh(self, stored: InstrumentProfileRecord, now: datetime) -> bool:
        """Apply the configured TTL to the durable record's last refresh time."""
        context = QualityContext(f"instrument_profile:{stored.ticker}", now)
        decisions = evaluate_freshness(
            context=context, policy=FreshnessPolicy(cache_ttl=self._ttl), cached_at=stored.refreshed_at
        )
        publish_quality(decisions)
        return not any(item.outcome is QualityOutcome.FAIL for item in decisions)


__all__ = ["CachedInstrumentProfileResolver", "InstrumentProfileResolver"]
