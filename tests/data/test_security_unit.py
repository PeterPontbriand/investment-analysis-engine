"""Deterministic tests for the reviewed security-unit predicate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.data.security_unit import (
    SecurityUnitCompatibilityReason,
    SecurityUnitEvidence,
    SecurityUnitKind,
    evaluate_security_unit_compatibility,
)

_FIXTURE = Path("tests/fixtures/sec_edgar/step_2_5a_d0/nvo_security_unit_evidence.json")


def _ordinary_evidence(**changes: object) -> SecurityUnitEvidence:
    values: dict[str, object] = {
        "ticker": "TEST",
        "filing_unit_kind": SecurityUnitKind.ORDINARY_SHARE,
        "quoted_unit_kind": SecurityUnitKind.ORDINARY_SHARE,
        "underlying_shares_per_quoted_unit": 1.0,
        "provider_id": "deterministic_fixture",
        "source": "C-02 synthetic ordinary-share evidence",
    }
    values.update(changes)
    return SecurityUnitEvidence(**values)  # type: ignore[arg-type]


def test_matching_currency_ordinary_share_one_to_one_is_compatible() -> None:
    result = evaluate_security_unit_compatibility(
        _ordinary_evidence(),
        filing_currency="usd",
        quote_currency=" USD ",
    )

    assert result.is_compatible
    assert result.reason is SecurityUnitCompatibilityReason.AFFIRMATIVE_ORDINARY_SHARE_1_TO_1


def test_nvo_fixture_fails_closed_on_unapproved_currency_conversion() -> None:
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    evidence = SecurityUnitEvidence(
        ticker=payload["quoted_ticker"],
        filing_unit_kind=SecurityUnitKind.ORDINARY_SHARE,
        quoted_unit_kind=SecurityUnitKind(payload["depositary_receipt_kind"].lower()),
        underlying_shares_per_quoted_unit=float(payload["deposited_shares_per_adr"]),
        provider_id="sec_edgar",
        source=payload["filing_security_title"],
    )

    result = evaluate_security_unit_compatibility(
        evidence,
        filing_currency=payload["filing_per_share_currency"],
        quote_currency=payload["test_quote_currency"],
    )

    assert not result.is_compatible
    assert result.reason is SecurityUnitCompatibilityReason.CURRENCY_MISMATCH


@pytest.mark.parametrize(
    ("evidence", "expected_reason"),
    [
        (None, SecurityUnitCompatibilityReason.MISSING_EVIDENCE),
        (_ordinary_evidence(underlying_shares_per_quoted_unit=None), SecurityUnitCompatibilityReason.UNKNOWN_RATIO),
        (_ordinary_evidence(multi_class_ambiguous=True), SecurityUnitCompatibilityReason.MULTI_CLASS_AMBIGUITY),
        (
            _ordinary_evidence(quoted_unit_kind=SecurityUnitKind.ADR),
            SecurityUnitCompatibilityReason.UNSUPPORTED_UNIT_KIND,
        ),
        (_ordinary_evidence(underlying_shares_per_quoted_unit=2.0), SecurityUnitCompatibilityReason.NON_UNIT_RATIO),
    ],
)
def test_ambiguous_or_unsupported_shapes_fail_closed(
    evidence: SecurityUnitEvidence | None,
    expected_reason: SecurityUnitCompatibilityReason,
) -> None:
    result = evaluate_security_unit_compatibility(evidence, filing_currency="USD", quote_currency="USD")

    assert not result.is_compatible
    assert result.reason is expected_reason


def test_invalid_ratio_is_rejected() -> None:
    with pytest.raises(ValueError, match="finite and positive"):
        _ordinary_evidence(underlying_shares_per_quoted_unit=0.0)
