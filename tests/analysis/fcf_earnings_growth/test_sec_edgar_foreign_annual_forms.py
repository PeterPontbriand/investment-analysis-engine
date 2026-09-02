"""Step 2.5A A1 regressions for US-GAAP foreign annual forms."""

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from src.data.financial.facts import FinancialFactRequest, FinancialField
from src.data.financial.provenance import FinancialSubjectKind
from src.data.sec_edgar.financial_facts import SEC_PROVIDER_ID, SecEdgarFinancialFactsAdapter

NOW = datetime(2026, 9, 1, 14, 0, tzinfo=UTC)
FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "sec_edgar" / "step_2_5a_d0"
ANNUAL_DURATION_FIELDS = (
    FinancialField.EPS,
    FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES,
    FinancialField.OPERATING_CASH_FLOW,
    FinancialField.CAPITAL_EXPENDITURES,
)


def _fixture(name: str) -> Any:
    """Load one approved D0 evidence fragment."""
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


class _FrozenSecFetcher:
    """Serve deterministic ASML SEC evidence without external calls."""

    def __init__(self, company_facts: object) -> None:
        self._company_facts = company_facts

    def __call__(self, url: str, *, headers: Mapping[str, str]) -> object:
        assert headers["User-Agent"] == "A1 fixture tests@example.invalid"
        if "company_tickers.json" in url:
            rows = _fixture("company_tickers.json")
            return {key: row for key, row in rows.items() if row["ticker"] == "ASML"}
        if "/companyfacts/" in url:
            return self._company_facts
        if "/submissions/" in url:
            return _fixture("asml_submissions.json")
        raise AssertionError(f"Unexpected SEC URL: {url}")


def _adapter(payload: object) -> SecEdgarFinancialFactsAdapter:
    return SecEdgarFinancialFactsAdapter(
        json_fetcher=_FrozenSecFetcher(payload),
        clock=lambda: NOW,
        user_agent="A1 fixture tests@example.invalid",
    )


def _request(field: FinancialField, *, basis: str = "fiscal_year") -> FinancialFactRequest:
    return FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="ASML",
        field_name=field,
        provider_id=SEC_PROVIDER_ID,
        basis=basis,
        observation_count=1,
    )


def _payload_with_form(form: str, *, fp: str = "FY") -> dict[str, Any]:
    payload: dict[str, Any] = deepcopy(_fixture("asml_companyfacts.json"))
    for concept in payload["facts"]["us-gaap"].values():
        for observations in concept["units"].values():
            for observation in observations:
                observation["form"] = form
                observation["fp"] = fp
    return payload


@pytest.mark.parametrize("form", ["10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"])
@pytest.mark.parametrize("field", ANNUAL_DURATION_FIELDS)
def test_completed_annual_duration_fields_accept_approved_forms(form: str, field: FinancialField) -> None:
    facts = _adapter(_payload_with_form(form)).fetch_facts(_request(field))

    assert len(facts) == 1
    assert facts[0].field_name is field
    assert facts[0].basis == "fiscal_year"


@pytest.mark.parametrize("form", ["6-K", "8-K"])
@pytest.mark.parametrize("field", ANNUAL_DURATION_FIELDS)
def test_non_annual_forms_remain_ineligible(form: str, field: FinancialField) -> None:
    assert _adapter(_payload_with_form(form)).fetch_facts(_request(field)) == ()


@pytest.mark.parametrize("field", ANNUAL_DURATION_FIELDS)
def test_non_fiscal_year_observations_remain_ineligible(field: FinancialField) -> None:
    assert _adapter(_payload_with_form("20-F", fp="Q4")).fetch_facts(_request(field)) == ()


def test_foreign_annual_forms_do_not_expand_balance_sheet_eligibility() -> None:
    payload = _payload_with_form("20-F")
    payload["facts"]["us-gaap"]["StockholdersEquity"] = {
        "units": {
            "EUR": [
                {
                    "end": "2025-12-31",
                    "val": 42_000_000_000,
                    "accn": "0001628280-26-011378",
                    "fy": 2025,
                    "fp": "FY",
                    "form": "20-F",
                    "filed": "2026-02-25",
                }
            ]
        }
    }

    facts = _adapter(payload).fetch_facts(_request(FinancialField.STOCKHOLDERS_EQUITY, basis="fiscal_year_end"))

    assert facts == ()
