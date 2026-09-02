"""Security-unit enforcement at the Graham quote-comparison boundary."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from src.analysis.graham_value.service import _margin_of_safety
from src.data.financial.provenance import ResolvedInput, SourceKind
from src.data.security_unit import SecurityUnitEvidence, SecurityUnitKind


def _quote(currency: str) -> ResolvedInput:
    return ResolvedInput(
        field_name="current_price",
        value=80.0,
        source_kind=SourceKind.PROVIDER,
        resolved_at=datetime(2026, 9, 1, tzinfo=UTC),
        units="currency_per_share",
        currency=currency,
        provider_id="fixture",
        provider_field="quote",
        retrieved_at=datetime(2026, 9, 1, tzinfo=UTC),
    )


def _ordinary_evidence() -> SecurityUnitEvidence:
    return SecurityUnitEvidence(
        ticker="TEST",
        filing_unit_kind=SecurityUnitKind.ORDINARY_SHARE,
        quoted_unit_kind=SecurityUnitKind.ORDINARY_SHARE,
        underlying_shares_per_quoted_unit=1.0,
        provider_id="fixture",
        source="C-02 deterministic evidence",
    )


def test_affirmative_ordinary_share_evidence_permits_comparison() -> None:
    margin = _margin_of_safety(
        100.0,
        _quote("USD"),
        valuation_currency="USD",
        security_unit_evidence=_ordinary_evidence(),
        require_security_unit_evidence=True,
    )

    assert margin == 20.0


def test_missing_adr_or_currency_mismatch_evidence_suppresses_comparison() -> None:
    evidence = _ordinary_evidence()

    assert (
        _margin_of_safety(
            100.0,
            _quote("USD"),
            valuation_currency="USD",
            security_unit_evidence=None,
            require_security_unit_evidence=True,
        )
        is None
    )
    assert (
        _margin_of_safety(
            100.0,
            _quote("USD"),
            valuation_currency="USD",
            security_unit_evidence=replace(evidence, quoted_unit_kind=SecurityUnitKind.ADR),
            require_security_unit_evidence=True,
        )
        is None
    )
    assert (
        _margin_of_safety(
            100.0,
            _quote("USD"),
            valuation_currency="DKK",
            security_unit_evidence=evidence,
            require_security_unit_evidence=True,
        )
        is None
    )
