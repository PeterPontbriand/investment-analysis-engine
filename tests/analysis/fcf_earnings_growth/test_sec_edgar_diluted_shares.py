"""Deterministic E2 regressions for SEC annual diluted-share evidence."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from src.data.financial.facts import FinancialFactRequest, FinancialField, FinancialUnit, ProviderFact
from src.data.financial.provenance import FinancialSubjectKind
from src.data.sec_edgar.financial_facts import (
    SEC_PROVIDER_ID,
    SEC_WEIGHTED_AVERAGE_DILUTED_SHARES_FIELD,
    SecEdgarFinancialFactsAdapter,
)

NOW = datetime(2026, 8, 29, 16, 0, tzinfo=UTC)
CIK = 320193


class _Fetcher:
    def __init__(self, observations: list[dict[str, Any]]) -> None:
        self._observations = observations

    def __call__(self, url: str, *, headers: Mapping[str, str]) -> object:
        assert headers["User-Agent"] == "E2 fixture tests@example.invalid"
        if "company_tickers.json" in url:
            return {"0": {"cik_str": CIK, "ticker": "AAPL", "title": "Apple"}}
        if "/companyfacts/" in url:
            return {
                "cik": CIK,
                "entityName": "Apple",
                "facts": {
                    "us-gaap": {
                        "WeightedAverageNumberOfDilutedSharesOutstanding": {"units": {"shares": self._observations}}
                    }
                },
            }
        if "/submissions/" in url:
            return {"filings": {"recent": {}}}
        raise AssertionError(f"Unexpected SEC URL: {url}")


def _observation(value: float, accession: str, start: str, end: str, filed: str) -> dict[str, Any]:
    return {
        "val": value,
        "start": start,
        "end": end,
        "accn": accession,
        "filed": filed,
        "fy": int(end[:4]),
        "fp": "FY",
        "form": "10-K",
    }


def _facts(observations: list[dict[str, Any]], count: int) -> tuple[ProviderFact, ...]:
    adapter = SecEdgarFinancialFactsAdapter(
        json_fetcher=_Fetcher(observations),
        clock=lambda: NOW,
        user_agent="E2 fixture tests@example.invalid",
    )
    request = FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="aapl",
        field_name=FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES,
        provider_id=SEC_PROVIDER_ID,
        basis="fiscal_year",
        observation_count=count,
    )
    return adapter.fetch_facts(request)


def test_returns_exact_positive_share_fact() -> None:
    facts = _facts([_observation(15_004_697_000, "2025", "2024-09-29", "2025-09-27", "2025-10-31")], 1)
    assert len(facts) == 1
    fact = facts[0]
    assert fact.value == pytest.approx(15_004_697_000)
    assert fact.units is FinancialUnit.SHARES
    assert fact.currency is None
    assert fact.provider_field == SEC_WEIGHTED_AVERAGE_DILUTED_SHARES_FIELD


def test_uses_common_post_split_basis_and_rejects_unrepresented_endpoint() -> None:
    complete = [
        _observation(5_000, "2018", "2017-10-01", "2018-09-29", "2018-11-05"),
        _observation(20_000, "2020-r18", "2017-10-01", "2018-09-29", "2020-10-30"),
        _observation(4_500, "2019", "2018-09-30", "2019-09-28", "2019-10-31"),
        _observation(18_000, "2020-r19", "2018-09-30", "2019-09-28", "2020-10-30"),
        _observation(17_000, "2020", "2019-09-29", "2020-09-26", "2020-10-30"),
    ]
    assert [fact.value for fact in _facts(complete, 3)] == pytest.approx([20_000, 18_000, 17_000])
    assert _facts([complete[0], complete[2], complete[3], complete[4]], 3) == ()


def test_rejects_nonpositive_share_count() -> None:
    observation = _observation(0, "2025", "2024-09-29", "2025-09-27", "2025-10-31")
    assert _facts([observation], 1) == ()
