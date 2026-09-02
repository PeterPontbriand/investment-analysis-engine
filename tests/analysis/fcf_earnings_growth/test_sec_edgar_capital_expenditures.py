"""Deterministic D2 regressions for SEC annual capital expenditures."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from src.data.financial.facts import FinancialFactRequest, FinancialField, FinancialUnit
from src.data.financial.provenance import (
    AccountingScope,
    CapitalExpenditureSign,
    FinancialSubjectKind,
    PeriodKind,
)
from src.data.sec_edgar.financial_facts import (
    SEC_CAPITAL_EXPENDITURES_FIELD,
    SEC_PROVIDER_ID,
    SecEdgarFinancialFactsAdapter,
)

NOW = datetime(2026, 8, 29, 16, 0, tzinfo=UTC)
CIK = 789019


class FakeSecFetcher:
    """Return bounded SEC fixtures without external calls."""

    def __init__(self, company_facts: object, *, ticker_rows: object | None = None) -> None:
        """Initialize deterministic endpoint responses."""
        self._company_facts = company_facts
        self._ticker_rows = ticker_rows or {"0": {"cik_str": CIK, "ticker": "MSFT", "title": "Microsoft"}}
        self.calls: list[str] = []

    def __call__(self, url: str, *, headers: Mapping[str, str]) -> object:
        """Return the fixture associated with an SEC URL."""
        assert headers["User-Agent"] == "D2 fixture tests@example.invalid"
        self.calls.append(url)
        if "company_tickers.json" in url:
            return self._ticker_rows
        if "/companyfacts/" in url:
            return self._company_facts
        if "/submissions/" in url:
            return {"filings": {"recent": {}}}
        msg = f"Unexpected SEC URL: {url}"
        raise AssertionError(msg)


def _observation(value: float, *, accession: str, start: str = "2024-07-01", end: str = "2025-06-30") -> dict[str, Any]:
    return {
        "val": value,
        "start": start,
        "end": end,
        "accn": accession,
        "filed": "2025-07-29",
        "fy": 2025,
        "fp": "FY",
        "form": "10-K",
    }


def _payload(
    observations: list[dict[str, Any]] | None = None,
    *,
    extra_concepts: Mapping[str, object] | None = None,
    cik: int = CIK,
) -> dict[str, Any]:
    us_gaap: dict[str, object] = {}
    if observations is not None:
        us_gaap["PaymentsToAcquirePropertyPlantAndEquipment"] = {"units": {"USD": observations}}
    if extra_concepts is not None:
        us_gaap.update(extra_concepts)
    return {"cik": cik, "entityName": "Microsoft", "facts": {"us-gaap": us_gaap}}


def _request(*, basis: str = "fiscal_year") -> FinancialFactRequest:
    return FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="msft",
        field_name=FinancialField.CAPITAL_EXPENDITURES,
        provider_id=SEC_PROVIDER_ID,
        basis=basis,
        observation_count=6 if basis == "fiscal_year" else 1,
    )


def _adapter(payload: object, *, ticker_rows: object | None = None) -> SecEdgarFinancialFactsAdapter:
    return SecEdgarFinancialFactsAdapter(
        json_fetcher=FakeSecFetcher(payload, ticker_rows=ticker_rows),
        clock=lambda: NOW,
        user_agent="D2 fixture tests@example.invalid",
    )


def test_returns_exact_concept_with_positive_expenditure_metadata() -> None:
    facts = _adapter(_payload([_observation(24_000_000_000.0, accession="positive")])).fetch_facts(_request())

    assert len(facts) == 1
    fact = facts[0]
    assert fact.value == pytest.approx(24_000_000_000.0)
    assert fact.field_name is FinancialField.CAPITAL_EXPENDITURES
    assert fact.provider_field == SEC_CAPITAL_EXPENDITURES_FIELD
    assert fact.units is FinancialUnit.CURRENCY
    assert fact.currency == "USD"
    assert fact.fiscal_year == 2025
    assert fact.period_kind is PeriodKind.COMPLETED_ANNUAL
    assert fact.accounting_scope is AccountingScope.CONSOLIDATED
    assert fact.capital_expenditure_sign is CapitalExpenditureSign.POSITIVE_EXPENDITURE
    assert fact.provider_fact_id == (
        "positive:us-gaap:PaymentsToAcquirePropertyPlantAndEquipment:USD:2024-07-01:2025-06-30"
    )


def test_accepts_zero_and_rejects_negative_without_absolute_value_normalization() -> None:
    facts = _adapter(
        _payload(
            [
                _observation(0.0, accession="zero", start="2023-07-01", end="2024-06-30"),
                _observation(-5.0, accession="negative"),
            ]
        )
    ).fetch_facts(_request())

    assert [fact.value for fact in facts] == pytest.approx([0.0])


def test_does_not_substitute_productive_assets_or_other_ppe_concepts() -> None:
    alternates = {
        concept: {"units": {"USD": [_observation(99.0, accession=concept)]}}
        for concept in (
            "PaymentsToAcquireProductiveAssets",
            "PaymentsToAcquireOtherPropertyPlantAndEquipment",
        )
    }

    assert _adapter(_payload(extra_concepts=alternates)).fetch_facts(_request()) == ()


def test_rejects_unsupported_period_unit_and_request_shapes() -> None:
    quarterly = _observation(5.0, accession="quarter", start="2025-04-01", end="2025-06-30")
    wrong_units = {
        "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD millions": [_observation(6.0, accession="unit")]}}
    }
    assert _adapter(_payload([quarterly])).fetch_facts(_request()) == ()
    assert _adapter(_payload(extra_concepts=wrong_units)).fetch_facts(_request()) == ()
    assert (
        _adapter(_payload([_observation(5.0, accession="basis")])).fetch_facts(_request(basis="fiscal_year_end")) == ()
    )
