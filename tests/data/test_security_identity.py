"""Deterministic tests for provider-neutral, fail-open security identity."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.data.security_identity import (
    IdentityResolutionStatus,
    SecurityIdentity,
    SecurityIdentityRequest,
    SecurityIdentityResolution,
    resolve_security_identity,
    security_display_label,
    security_identity_payload,
)

NOW = datetime(2026, 8, 29, 20, 0, tzinfo=UTC)


class _CountingProvider:
    """Identity provider spy that returns one configured outcome."""

    def __init__(self, identity: SecurityIdentity | None, *, fails: bool = False) -> None:
        self.identity = identity
        self.fails = fails
        self.calls = 0

    def resolve_security_identity(self, _request: SecurityIdentityRequest) -> SecurityIdentity | None:
        self.calls += 1
        if self.fails:
            raise RuntimeError("simulated identity failure")
        return self.identity


def test_identity_normalizes_whitespace_without_changing_official_case_or_punctuation() -> None:
    identity = SecurityIdentity(
        ticker="  brk-b ",
        instrument_name="  Berkshire   Hathaway Inc.  ",
        listing_venue=" New   York Stock Exchange ",
        issuer_identifier=" 0001067983 ",
        instrument_identifier="  instrument:brk-b ",
        provider_id=" sec_edgar ",
        resolved_at=NOW,
    )

    assert identity.ticker == "BRK-B"
    assert identity.instrument_name == "Berkshire Hathaway Inc."
    assert identity.listing_venue == "New York Stock Exchange"
    assert security_display_label("brk-b", _resolved(identity)) == "Berkshire Hathaway Inc. (BRK-B)"


def test_non_company_instrument_uses_instrument_name_and_snapshot_payload() -> None:
    identity = SecurityIdentity(
        ticker="btc-usd",
        instrument_name="Bitcoin USD",
        listing_venue="CCC",
        instrument_identifier="BTC-USD",
        provider_id="yfinance",
        resolved_at=NOW,
    )
    resolution = _resolved(identity)

    assert security_display_label("BTC-USD", resolution) == "Bitcoin USD (BTC-USD)"
    assert security_identity_payload("BTC-USD", resolution) == {
        "ticker": "BTC-USD",
        "instrument_name": "Bitcoin USD",
        "listing_venue": "CCC",
        "issuer_identifier": None,
        "instrument_identifier": "BTC-USD",
        "provider_id": "yfinance",
        "resolved_at": NOW.isoformat(),
    }


def test_best_effort_lookup_calls_provider_once_and_classifies_failure() -> None:
    provider = _CountingProvider(None, fails=True)
    request = SecurityIdentityRequest(ticker="KO", provider_id="sec_edgar")

    resolution = resolve_security_identity(provider, request)

    assert provider.calls == 1
    assert resolution.status is IdentityResolutionStatus.PROVIDER_ERROR
    assert resolution.identity is None
    assert security_display_label("KO", resolution) == "KO"


def test_unavailable_identity_payload_has_explicit_null_optional_fields() -> None:
    resolution = resolve_security_identity(object(), SecurityIdentityRequest("KO", "fixture"))

    assert resolution.status is IdentityResolutionStatus.UNAVAILABLE
    assert security_identity_payload("KO", resolution) == {
        "ticker": "KO",
        "instrument_name": None,
        "listing_venue": None,
        "issuer_identifier": None,
        "instrument_identifier": None,
        "provider_id": None,
        "resolved_at": None,
    }


def test_identity_rejects_naive_resolution_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        SecurityIdentity(ticker="KO", provider_id="fixture", resolved_at=datetime(2026, 8, 29))


def _resolved(identity: SecurityIdentity) -> SecurityIdentityResolution:
    """Resolve one snapshot through the public fail-open boundary."""
    return resolve_security_identity(
        _CountingProvider(identity),
        SecurityIdentityRequest(identity.ticker, identity.provider_id),
    )
