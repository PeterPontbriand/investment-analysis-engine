"""Deterministic instrument-profile evidence for evaluation and tests."""

from __future__ import annotations

from datetime import UTC, datetime

from src.data.instrument_profile import InstrumentKind, InstrumentKindEvidence, InstrumentProfile
from src.data.security_identity import SecurityIdentity

FIXTURE_PROFILE_RESOLVED_AT = datetime(2026, 8, 30, 18, 0, tzinfo=UTC)
GOLDEN_ETF_TICKER = "FLSW"
GOLDEN_ETF_NAME = "Franklin FTSE Switzerland ETF"


def fixture_known_etf_profile() -> InstrumentProfile:
    """Return affirmative provider-backed ETF evidence for the cross-strategy case."""
    return fixture_instrument_profile(
        GOLDEN_ETF_TICKER,
        kind=InstrumentKind.ETF,
        provider_value="ETF",
        instrument_name=GOLDEN_ETF_NAME,
    )


def fixture_instrument_profile(
    ticker: str,
    *,
    kind: InstrumentKind | None,
    provider_value: str,
    instrument_name: str | None = None,
    resolved_at: datetime = FIXTURE_PROFILE_RESOLVED_AT,
) -> InstrumentProfile:
    """Return independently sourced fixture identity and Yahoo kind evidence."""
    identity = SecurityIdentity(
        ticker=ticker,
        provider_id="fixture_identity",
        resolved_at=resolved_at,
        instrument_name=instrument_name,
    )
    evidence = InstrumentKindEvidence(
        ticker=ticker,
        kind=kind,
        provider_value=provider_value,
        provider_id="yfinance",
        resolved_at=resolved_at,
    )
    return InstrumentProfile(
        ticker=ticker,
        identity=identity,
        kind_evidence=evidence,
        diagnostics=(),
    )
