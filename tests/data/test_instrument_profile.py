"""Deterministic tests for instrument-kind evidence and profile composition."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from src.data.instrument_profile import (
    InstrumentKind,
    InstrumentKindEvidence,
    InstrumentKindRequest,
    InstrumentProfileCandidate,
    InstrumentProfileCapability,
    InstrumentProfileResolutionStatus,
    compose_instrument_profile,
    instrument_kind_evidence_payload,
)
from src.data.security_identity import SecurityIdentity, SecurityIdentityRequest
from src.data.yfinance import YFINANCE_PROVIDER_ID, YFinanceClient

NOW = datetime(2026, 8, 30, 18, 0, tzinfo=UTC)


class _IdentityProvider:
    """Identity provider spy with one configured response."""

    def __init__(self, identity: SecurityIdentity | None) -> None:
        self.identity = identity
        self.calls = 0

    def resolve_security_identity(self, _request: SecurityIdentityRequest) -> SecurityIdentity | None:
        self.calls += 1
        return self.identity


class _KindProvider:
    """Instrument-kind provider spy with one configured response or failure."""

    def __init__(self, evidence: InstrumentKindEvidence | None, *, fails: bool = False) -> None:
        self.evidence = evidence
        self.fails = fails
        self.calls = 0

    def resolve_instrument_kind(self, _request: InstrumentKindRequest) -> InstrumentKindEvidence | None:
        self.calls += 1
        if self.fails:
            raise RuntimeError("simulated kind provider failure")
        return self.evidence


class _IdentityAndKindProvider(_IdentityProvider, _KindProvider):
    """Combined spy proving independent capability call counts."""

    def __init__(self, identity: SecurityIdentity, evidence: InstrumentKindEvidence) -> None:
        _IdentityProvider.__init__(self, identity)
        self.evidence = evidence
        self.fails = False
        self.kind_calls = 0

    def resolve_instrument_kind(self, _request: InstrumentKindRequest) -> InstrumentKindEvidence | None:
        self.kind_calls += 1
        return self.evidence


@pytest.mark.parametrize(
    ("provider_value", "expected_kind"),
    [
        ("EQUITY", InstrumentKind.EQUITY),
        ("ETF", InstrumentKind.ETF),
        ("CRYPTOCURRENCY", InstrumentKind.CRYPTOCURRENCY),
        ("MUTUALFUND", None),
    ],
)
def test_kind_evidence_retains_exact_reviewed_mapping(
    provider_value: str,
    expected_kind: InstrumentKind | None,
) -> None:
    evidence = InstrumentKindEvidence(
        ticker=" flsw ",
        kind=expected_kind,
        provider_value=f"  {provider_value}  ",
        provider_id=" yfinance ",
        resolved_at=NOW,
    )

    assert evidence.ticker == "FLSW"
    assert evidence.provider_value == provider_value
    assert evidence.kind is expected_kind


def test_kind_evidence_rejects_unreviewed_mapping_and_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="reviewed provider-value mapping"):
        InstrumentKindEvidence("FLSW", InstrumentKind.ETF, "MUTUALFUND", YFINANCE_PROVIDER_ID, NOW)
    with pytest.raises(ValueError, match="timezone-aware"):
        InstrumentKindEvidence(
            "FLSW",
            InstrumentKind.ETF,
            "ETF",
            YFINANCE_PROVIDER_ID,
            datetime(2026, 8, 30),
        )


def test_kind_evidence_is_frozen_and_has_deterministic_payload() -> None:
    evidence = InstrumentKindEvidence(
        "FLSW",
        InstrumentKind.ETF,
        "ETF",
        YFINANCE_PROVIDER_ID,
        NOW,
    )

    with pytest.raises(FrozenInstanceError):
        evidence.provider_value = "EQUITY"  # type: ignore[misc]

    assert instrument_kind_evidence_payload(evidence) == {
        "kind": "etf",
        "provider_value": "ETF",
        "provider_id": YFINANCE_PROVIDER_ID,
        "resolved_at": NOW.isoformat(),
    }
    assert instrument_kind_evidence_payload(None) is None


def test_profile_keeps_sec_identity_and_yahoo_kind_provenance_separate() -> None:
    sec_identity = SecurityIdentity(
        ticker="FLSW",
        provider_id="sec_edgar",
        resolved_at=NOW,
        instrument_name="Franklin FTSE Switzerland ETF",
        issuer_identifier="0000000001",
    )
    yahoo_identity = SecurityIdentity(
        ticker="FLSW",
        provider_id=YFINANCE_PROVIDER_ID,
        resolved_at=NOW,
        instrument_name="Yahoo fallback name",
    )
    yahoo_kind = InstrumentKindEvidence(
        ticker="FLSW",
        kind=InstrumentKind.ETF,
        provider_value="ETF",
        provider_id=YFINANCE_PROVIDER_ID,
        resolved_at=NOW,
    )
    sec_provider = _IdentityProvider(sec_identity)
    yahoo_provider = _IdentityAndKindProvider(yahoo_identity, yahoo_kind)

    profile = compose_instrument_profile(
        "flsw",
        identity_candidates=(
            InstrumentProfileCandidate("sec_edgar", sec_provider),
            InstrumentProfileCandidate(YFINANCE_PROVIDER_ID, yahoo_provider),
        ),
        kind_candidate=InstrumentProfileCandidate(YFINANCE_PROVIDER_ID, yahoo_provider),
    )

    assert profile.identity is sec_identity
    assert profile.kind_evidence is yahoo_kind
    assert profile.identity.provider_id == "sec_edgar"
    assert profile.kind_evidence.provider_id == YFINANCE_PROVIDER_ID
    assert sec_provider.calls == 1
    assert yahoo_provider.calls == 0
    assert yahoo_provider.kind_calls == 1
    assert [(item.capability, item.status) for item in profile.diagnostics] == [
        (InstrumentProfileCapability.SECURITY_IDENTITY, InstrumentProfileResolutionStatus.RESOLVED),
        (InstrumentProfileCapability.INSTRUMENT_KIND, InstrumentProfileResolutionStatus.RESOLVED),
    ]


def test_identity_precedence_attempts_each_candidate_once_until_resolved() -> None:
    unavailable = _IdentityProvider(None)
    identity = SecurityIdentity("KO", "second", NOW, instrument_name="The Coca-Cola Company")
    resolved = _IdentityProvider(identity)

    profile = compose_instrument_profile(
        "KO",
        identity_candidates=(
            InstrumentProfileCandidate("first", unavailable),
            InstrumentProfileCandidate("second", resolved),
        ),
        kind_candidate=None,
    )

    assert profile.identity is identity
    assert unavailable.calls == 1
    assert resolved.calls == 1
    assert [item.status for item in profile.diagnostics] == [
        InstrumentProfileResolutionStatus.UNAVAILABLE,
        InstrumentProfileResolutionStatus.RESOLVED,
    ]


def test_profile_distinguishes_unsupported_and_provider_error_fail_open() -> None:
    failing_kind = _KindProvider(None, fails=True)

    profile = compose_instrument_profile(
        "FLSW",
        identity_candidates=(InstrumentProfileCandidate("fixture", object()),),
        kind_candidate=InstrumentProfileCandidate("kind_fixture", failing_kind),
    )

    assert profile.identity is None
    assert profile.kind_evidence is None
    assert [item.status for item in profile.diagnostics] == [
        InstrumentProfileResolutionStatus.UNSUPPORTED,
        InstrumentProfileResolutionStatus.PROVIDER_ERROR,
    ]
    assert failing_kind.calls == 1


def test_duplicate_identity_provider_is_rejected_before_any_call() -> None:
    provider = _IdentityProvider(None)
    duplicate = InstrumentProfileCandidate("fixture", provider)

    with pytest.raises(ValueError, match="must not repeat"):
        compose_instrument_profile(
            "KO",
            identity_candidates=(duplicate, duplicate),
            kind_candidate=None,
        )

    assert provider.calls == 0


def test_yahoo_identity_and_kind_share_one_metadata_retrieval() -> None:
    with patch("src.data.yfinance.client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.info = {
            "longName": "Franklin FTSE Switzerland ETF",
            "fullExchangeName": "NYSEArca",
            "quoteType": "ETF",
        }
        client = YFinanceClient(clock=lambda: NOW)
        candidate = InstrumentProfileCandidate(YFINANCE_PROVIDER_ID, client)

        profile = compose_instrument_profile(
            "FLSW",
            identity_candidates=(candidate,),
            kind_candidate=candidate,
        )

    assert mock_ticker.call_count == 1
    assert profile.identity is not None
    assert profile.identity.instrument_name == "Franklin FTSE Switzerland ETF"
    assert profile.kind_evidence is not None
    assert profile.kind_evidence.kind is InstrumentKind.ETF
    assert profile.identity.resolved_at == profile.kind_evidence.resolved_at == NOW


@pytest.mark.parametrize(
    ("raw_value", "expected_kind"),
    [
        (" EQUITY ", InstrumentKind.EQUITY),
        (" ETF ", InstrumentKind.ETF),
        (" CRYPTOCURRENCY ", InstrumentKind.CRYPTOCURRENCY),
        (" MUTUALFUND ", None),
    ],
)
def test_yahoo_retains_raw_kind_and_applies_only_reviewed_mappings(
    raw_value: str,
    expected_kind: InstrumentKind | None,
) -> None:
    with patch("src.data.yfinance.client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.info = {"quoteType": raw_value}
        evidence = YFinanceClient(clock=lambda: NOW).resolve_instrument_kind(
            InstrumentKindRequest("FLSW", YFINANCE_PROVIDER_ID)
        )

    assert evidence is not None
    assert evidence.provider_value == raw_value.strip()
    assert evidence.kind is expected_kind


@pytest.mark.parametrize("raw_value", [None, "", "   ", 3])
def test_yahoo_missing_blank_or_malformed_kind_is_absent(raw_value: object) -> None:
    with patch("src.data.yfinance.client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.info = {"quoteType": raw_value}
        evidence = YFinanceClient(clock=lambda: NOW).resolve_instrument_kind(
            InstrumentKindRequest("FLSW", YFINANCE_PROVIDER_ID)
        )

    assert evidence is None
    assert mock_ticker.call_count == 1


def test_yahoo_metadata_failure_is_cached_across_both_capabilities() -> None:
    with patch("src.data.yfinance.client.yf.Ticker", side_effect=RuntimeError("offline")) as mock_ticker:
        client = YFinanceClient(clock=lambda: NOW)
        candidate = InstrumentProfileCandidate(YFINANCE_PROVIDER_ID, client)

        profile = compose_instrument_profile(
            "FLSW",
            identity_candidates=(candidate,),
            kind_candidate=candidate,
        )

    assert mock_ticker.call_count == 1
    assert profile.identity is None
    assert profile.kind_evidence is None
    assert [item.status for item in profile.diagnostics] == [
        InstrumentProfileResolutionStatus.PROVIDER_ERROR,
        InstrumentProfileResolutionStatus.PROVIDER_ERROR,
    ]
