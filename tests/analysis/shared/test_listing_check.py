"""The pure step from a cover's listing evidence to the listing check the market-cap function takes."""

from datetime import UTC, datetime
from typing import Any

import pytest

from investment_analysis_engine.analysis.shared.market_cap import (
    _UNAVAILABLE_REASONS,  # noqa: PLC2701
    listing_check_from_resolution,
)
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.data.sec_edgar.cover_listing import (
    CoverUnavailableReason,
    ListingEvidence,
    ListingResolution,
    SecurityKind,
)

NOW = datetime(2026, 10, 25, tzinfo=UTC)
ACCESSION = "0001628280-26-008131"


def _resolution(kind: SecurityKind, title: str | None, ticker: str = "JPM") -> ListingResolution:
    return ListingResolution(
        evidence=ListingEvidence(
            ticker=ticker,
            kind=kind,
            title=title,
            cik="0000019617",
            accession=ACCESSION,
            form="10-K",
            accepted_at=NOW,
            source_url="https://www.sec.gov/Archives/edgar/data/19617/000162828026008131/R1.htm",
            retrieved_at=NOW,
        )
    )


def test_a_share_of_the_issuer_is_affirmed_with_the_accession_read() -> None:
    check = listing_check_from_resolution(_resolution(SecurityKind.SHARE, "Common stock"))
    assert check.affirmed
    assert check.accession == ACCESSION
    assert check.reason_code is None
    assert check.reason is None


@pytest.mark.parametrize(
    ("kind", "title", "noun"),
    [
        (SecurityKind.DEPOSITARY_SHARE, "American Depositary Shares, each representing", "a depositary share"),
        (SecurityKind.UNIT, "Units", "a unit"),
        (SecurityKind.WARRANT, "Warrants", "a warrant"),
        (SecurityKind.PREFERRED, "6.95% Series F Cumulative Redeemable Preferred Stock", "a preferred security"),
    ],
)
def test_a_depositary_share_unit_warrant_or_preferred_security_is_refused_as_incompatible_units(
    kind: SecurityKind, title: str, noun: str
) -> None:
    check = listing_check_from_resolution(_resolution(kind, title))
    assert not check.affirmed
    assert check.reason_code is ReasonCode.INCOMPATIBLE_UNITS
    assert check.accession == ACCESSION
    assert check.reason is not None
    assert noun in check.reason
    assert title in check.reason


def test_a_ticker_the_cover_does_not_list_is_a_missing_fact() -> None:
    check = listing_check_from_resolution(_resolution(SecurityKind.NOT_LISTED, None, "NOPE"))
    assert not check.affirmed
    assert check.reason_code is ReasonCode.MISSING_FACT
    assert check.reason is not None
    assert "NOPE" in check.reason
    assert ACCESSION in check.reason


def test_a_title_outside_the_share_vocabulary_is_a_missing_fact_not_an_affirmation() -> None:
    check = listing_check_from_resolution(_resolution(SecurityKind.OTHER, "Class B Common Stock, $0.01 par value"))
    assert not check.affirmed
    assert check.reason_code is ReasonCode.MISSING_FACT
    assert check.reason is not None
    assert "Class B Common Stock" in check.reason


@pytest.mark.parametrize("reason", list(CoverUnavailableReason))
def test_a_cover_that_could_not_be_read_is_a_missing_fact_with_its_own_explanation(
    reason: CoverUnavailableReason,
) -> None:
    check = listing_check_from_resolution(ListingResolution(reason=reason))
    assert not check.affirmed
    assert check.accession is None
    assert check.reason_code is ReasonCode.MISSING_FACT
    assert check.reason is not None
    assert _UNAVAILABLE_REASONS[reason] in check.reason


def test_every_unavailable_reason_has_an_explanation() -> None:
    assert set(_UNAVAILABLE_REASONS) == set(CoverUnavailableReason)
    assert all(text.strip() for text in _UNAVAILABLE_REASONS.values())


def test_only_a_share_is_ever_affirmed() -> None:
    kinds: dict[SecurityKind, Any] = {
        kind: listing_check_from_resolution(_resolution(kind, None if kind is SecurityKind.NOT_LISTED else "Title"))
        for kind in SecurityKind
    }
    assert {kind for kind, check in kinds.items() if check.affirmed} == {SecurityKind.SHARE}
