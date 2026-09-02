"""Step 2.5A B1-B exact IFRS duration-fact mapping tests."""

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from src.data.financial.facts import FinancialFactRequest, FinancialField
from src.data.financial.provenance import CapitalExpenditureSign, FinancialSubjectKind
from src.data.sec_edgar.financial_facts import (
    SEC_IFRS_CAPITAL_EXPENDITURES_FIELD,
    SEC_IFRS_EPS_FIELD,
    SEC_IFRS_OPERATING_CASH_FLOW_FIELD,
    SEC_IFRS_WEIGHTED_AVERAGE_DILUTED_SHARES_FIELD,
    SEC_PROVIDER_ID,
    SecEdgarFinancialFactsAdapter,
)

NOW = datetime(2026, 9, 1, 14, 0, tzinfo=UTC)
FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "sec_edgar" / "step_2_5a_d0"


def _fixture(name: str) -> Any:
    """Load one approved minimized D0 evidence fragment."""
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


class _IfrsFetcher:
    """Serve one deterministic foreign-private-issuer fixture set."""

    def __init__(self, *, company_facts: object, submissions: object) -> None:
        self._company_facts = company_facts
        self._submissions = submissions

    def __call__(self, url: str, *, headers: Mapping[str, str]) -> object:
        assert headers["User-Agent"] == "B1-B fixture tests@example.invalid"
        if "company_tickers.json" in url:
            return _fixture("company_tickers.json")
        if "/companyfacts/" in url:
            return self._company_facts
        if "/submissions/" in url:
            return self._submissions
        raise AssertionError(f"Unexpected SEC URL: {url}")


def _adapter(issuer: str, *, company_facts: object | None = None) -> SecEdgarFinancialFactsAdapter:
    return SecEdgarFinancialFactsAdapter(
        json_fetcher=_IfrsFetcher(
            company_facts=company_facts or _fixture(f"{issuer}_companyfacts.json"),
            submissions=_fixture(f"{issuer}_submissions.json"),
        ),
        clock=lambda: NOW,
        user_agent="B1-B fixture tests@example.invalid",
    )


def _request(ticker: str, field: FinancialField) -> FinancialFactRequest:
    return FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id=ticker,
        field_name=field,
        provider_id=SEC_PROVIDER_ID,
        basis="fiscal_year",
        observation_count=1,
    )


@pytest.mark.parametrize(
    ("field", "expected_value", "provider_field"),
    [
        (FinancialField.EPS, 4.66, SEC_IFRS_EPS_FIELD),
        (
            FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES,
            486_518_000.0,
            SEC_IFRS_WEIGHTED_AVERAGE_DILUTED_SHARES_FIELD,
        ),
        (FinancialField.OPERATING_CASH_FLOW, 4_007_000_000.0, SEC_IFRS_OPERATING_CASH_FLOW_FIELD),
        (FinancialField.CAPITAL_EXPENDITURES, 1_882_000_000.0, SEC_IFRS_CAPITAL_EXPENDITURES_FIELD),
    ],
)
def test_ntr_exact_ifrs_duration_facts_preserve_lineage(
    field: FinancialField,
    expected_value: float,
    provider_field: str,
) -> None:
    adapter = _adapter("ntr")

    with adapter.analysis_scope(subject_id="NTR", provider_id=SEC_PROVIDER_ID, as_of=None):
        facts = adapter.fetch_facts(_request("NTR", field))

    assert len(facts) == 1
    assert facts[0].value == pytest.approx(expected_value)
    assert facts[0].provider_field == provider_field
    assert facts[0].provider_fact_id is not None
    assert provider_field in facts[0].provider_fact_id
    assert "accession=0001193125-26-081326" in facts[0].notes
    assert facts[0].fiscal_year == 2025


def test_ifrs_capex_uses_positive_expenditure_without_absolute_value() -> None:
    payload: dict[str, Any] = deepcopy(_fixture("ntr_companyfacts.json"))
    observations = payload["facts"]["ifrs-full"]["PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"][
        "units"
    ]["USD"]
    observations[0]["val"] = -1_882_000_000
    adapter = _adapter("ntr", company_facts=payload)

    with adapter.analysis_scope(subject_id="NTR", provider_id=SEC_PROVIDER_ID, as_of=None):
        facts = adapter.fetch_facts(_request("NTR", FinancialField.CAPITAL_EXPENDITURES))

    assert facts == ()


def test_ifrs_capex_lineage_declares_positive_expenditure_sign() -> None:
    adapter = _adapter("ntr")

    with adapter.analysis_scope(subject_id="NTR", provider_id=SEC_PROVIDER_ID, as_of=None):
        facts = adapter.fetch_facts(_request("NTR", FinancialField.CAPITAL_EXPENDITURES))

    assert facts[0].capital_expenditure_sign is CapitalExpenditureSign.POSITIVE_EXPENDITURE


def test_sap_broader_capex_concept_is_not_substituted_or_summed() -> None:
    adapter = _adapter("sap")

    with adapter.analysis_scope(subject_id="SAP", provider_id=SEC_PROVIDER_ID, as_of=None):
        operating_cash_flow = adapter.fetch_facts(_request("SAP", FinancialField.OPERATING_CASH_FLOW))
        capital_expenditures = adapter.fetch_facts(_request("SAP", FinancialField.CAPITAL_EXPENDITURES))

    assert len(operating_cash_flow) == 1
    assert operating_cash_flow[0].provider_field == SEC_IFRS_OPERATING_CASH_FLOW_FIELD
    assert capital_expenditures == ()


def test_ifrs_mapping_does_not_enable_instant_bvps_components() -> None:
    adapter = _adapter("ntr")
    request = FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="NTR",
        field_name=FinancialField.STOCKHOLDERS_EQUITY,
        provider_id=SEC_PROVIDER_ID,
        basis="fiscal_year_end",
        observation_count=1,
    )

    with adapter.analysis_scope(subject_id="NTR", provider_id=SEC_PROVIDER_ID, as_of=None):
        assert adapter.fetch_facts(request) == ()
