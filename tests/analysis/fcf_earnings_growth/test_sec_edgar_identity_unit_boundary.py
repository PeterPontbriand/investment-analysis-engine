"""Step 2.5A A0 regressions for SEC identity and security-unit scope."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from src.data.financial.facts import FinancialFactRequest, FinancialField
from src.data.financial.provenance import FinancialSubjectKind
from src.data.sec_edgar.financial_facts import SEC_PROVIDER_ID, SecEdgarFinancialFactsAdapter

NOW = datetime(2026, 9, 1, 2, 0, tzinfo=UTC)
FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "sec_edgar" / "step_2_5a_d0"


def _fixture(name: str) -> Any:
    """Load one approved D0 fixture without a live provider call."""
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


class _FrozenSecFetcher:
    """Serve one issuer from the approved D0 evidence fragments."""

    def __init__(self, *, company_facts: object, submissions: object, ticker_rows: object) -> None:
        self._company_facts = company_facts
        self._submissions = submissions
        self._ticker_rows = ticker_rows

    def __call__(self, url: str, *, headers: Mapping[str, str]) -> object:
        assert headers["User-Agent"] == "A0 fixture tests@example.invalid"
        if "company_tickers.json" in url:
            return self._ticker_rows
        if "/companyfacts/" in url:
            return self._company_facts
        if "/submissions/" in url:
            return self._submissions
        raise AssertionError(f"Unexpected SEC URL: {url}")


def _asml_payload_with_legacy_form() -> dict[str, Any]:
    """Mutate only the form so A0 tests identity independently from A1."""
    payload: dict[str, Any] = deepcopy(_fixture("asml_companyfacts.json"))
    for concept in payload["facts"]["us-gaap"].values():
        for observations in concept["units"].values():
            for observation in observations:
                observation["form"] = "10-K"
    return payload


def _adapter(*, company_facts: object, ticker_rows: object | None = None) -> SecEdgarFinancialFactsAdapter:
    return SecEdgarFinancialFactsAdapter(
        json_fetcher=_FrozenSecFetcher(
            company_facts=company_facts,
            submissions=_fixture("asml_submissions.json"),
            ticker_rows=ticker_rows or _fixture("company_tickers.json"),
        ),
        clock=lambda: NOW,
        user_agent="A0 fixture tests@example.invalid",
    )


def _request(field: FinancialField, *, ticker: str = "ASML") -> FinancialFactRequest:
    return FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id=ticker,
        field_name=field,
        provider_id=SEC_PROVIDER_ID,
        basis="fiscal_year",
        observation_count=1,
    )


def test_frozen_ticker_rows_preserve_single_and_multi_ticker_cik_shapes() -> None:
    rows_by_cik: defaultdict[int, set[str]] = defaultdict(set)
    for row in _fixture("company_tickers.json").values():
        rows_by_cik[row["cik_str"]].add(row["ticker"])

    assert rows_by_cik[1725964] == {"NTR"}
    assert rows_by_cik[1000184] == {"SAP", "SAPGF"}
    assert rows_by_cik[353278] == {"NONOF", "NVO"}
    assert rows_by_cik[937966] == {"ASML", "ASMLF"}


@pytest.mark.parametrize(
    ("field", "expected_value"),
    [
        (FinancialField.OPERATING_CASH_FLOW, 12_658_500_000.0),
        (FinancialField.CAPITAL_EXPENDITURES, 1_573_600_000.0),
    ],
)
def test_multi_ticker_cik_does_not_erase_issuer_level_facts(
    field: FinancialField,
    expected_value: float,
) -> None:
    facts = _adapter(company_facts=_asml_payload_with_legacy_form()).fetch_facts(_request(field))

    assert len(facts) == 1
    assert facts[0].value == pytest.approx(expected_value)


@pytest.mark.parametrize(
    "field",
    [FinancialField.EPS, FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES],
)
def test_multi_ticker_cik_keeps_per_share_facts_fail_closed(field: FinancialField) -> None:
    facts = _adapter(company_facts=_asml_payload_with_legacy_form()).fetch_facts(_request(field))

    assert facts == ()


@pytest.mark.parametrize("ticker", ["MISSING", "ASML"])
def test_unknown_ticker_and_company_facts_cik_mismatch_remain_unavailable(ticker: str) -> None:
    payload = _asml_payload_with_legacy_form()
    if ticker == "ASML":
        payload["cik"] = 123456

    assert (
        _adapter(company_facts=payload).fetch_facts(_request(FinancialField.OPERATING_CASH_FLOW, ticker=ticker)) == ()
    )
