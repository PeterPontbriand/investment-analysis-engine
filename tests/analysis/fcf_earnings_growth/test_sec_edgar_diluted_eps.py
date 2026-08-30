"""Deterministic D3 regressions for SEC completed-annual diluted EPS."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from src.data.financial.facts import FinancialFactRequest, FinancialField, FinancialUnit
from src.data.financial.provenance import AccountingScope, FinancialSubjectKind, PeriodKind
from src.data.sec_edgar.financial_facts import SEC_EPS_FIELD, SEC_PROVIDER_ID, SecEdgarFinancialFactsAdapter

NOW = datetime(2026, 8, 29, 16, 0, tzinfo=UTC)
CIK = 320193


class FakeSecFetcher:
    """Return bounded SEC fixtures without external calls."""

    def __init__(self, company_facts: object, *, ticker_rows: object | None = None) -> None:
        """Initialize deterministic endpoint responses."""
        self._company_facts = company_facts
        self._ticker_rows = ticker_rows or {"0": {"cik_str": CIK, "ticker": "AAPL", "title": "Apple"}}

    def __call__(self, url: str, *, headers: Mapping[str, str]) -> object:
        """Return the fixture associated with an SEC URL."""
        assert headers["User-Agent"] == "D3 fixture tests@example.invalid"
        if "company_tickers.json" in url:
            return self._ticker_rows
        if "/companyfacts/" in url:
            return self._company_facts
        if "/submissions/" in url:
            return {"filings": {"recent": {}}}
        raise AssertionError(f"Unexpected SEC URL: {url}")


def _observation(  # noqa: PLR0913
    value: float,
    *,
    accession: str,
    start: str,
    end: str,
    filed: str,
    form: str = "10-K",
    fp: str = "FY",
) -> dict[str, Any]:
    return {
        "val": value,
        "start": start,
        "end": end,
        "accn": accession,
        "filed": filed,
        "fy": int(end[:4]),
        "fp": fp,
        "form": form,
    }


def _payload(observations: list[dict[str, Any]], *, unit: str = "USD/shares", cik: int = CIK) -> dict[str, Any]:
    return {
        "cik": cik,
        "entityName": "Apple",
        "facts": {"us-gaap": {"EarningsPerShareDiluted": {"units": {unit: observations}}}},
    }


def _request(*, observation_count: int = 3, as_of: datetime | None = None) -> FinancialFactRequest:
    return FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="aapl",
        field_name=FinancialField.EPS,
        provider_id=SEC_PROVIDER_ID,
        basis="fiscal_year",
        as_of=as_of,
        observation_count=observation_count,
    )


def _adapter(payload: object, *, ticker_rows: object | None = None) -> SecEdgarFinancialFactsAdapter:
    return SecEdgarFinancialFactsAdapter(
        json_fetcher=FakeSecFetcher(payload, ticker_rows=ticker_rows),
        clock=lambda: NOW,
        user_agent="D3 fixture tests@example.invalid",
    )


def test_returns_exact_annual_diluted_eps_with_complete_metadata() -> None:
    observation = _observation(
        6.08,
        accession="2025-report",
        start="2024-09-29",
        end="2025-09-27",
        filed="2025-10-31",
    )

    facts = _adapter(_payload([observation])).fetch_facts(_request(observation_count=1))

    assert len(facts) == 1
    fact = facts[0]
    assert fact.value == pytest.approx(6.08)
    assert fact.provider_field == SEC_EPS_FIELD
    assert fact.units is FinancialUnit.CURRENCY_PER_SHARE
    assert fact.currency == "USD"
    assert fact.fiscal_year == 2025
    assert fact.period_kind is PeriodKind.COMPLETED_ANNUAL
    assert fact.accounting_scope is AccountingScope.CONSOLIDATED
    assert fact.provider_fact_id == "2025-report:us-gaap:EarningsPerShareDiluted:USD:2024-09-29:2025-09-27"


def test_uses_one_common_split_basis_for_an_apple_like_span() -> None:
    observations = [
        _observation(11.91, accession="2018-original", start="2017-10-01", end="2018-09-29", filed="2018-11-05"),
        _observation(11.89, accession="2019-original", start="2018-09-30", end="2019-09-28", filed="2019-10-31"),
        _observation(2.98, accession="2020-represented-2018", start="2017-10-01", end="2018-09-29", filed="2020-10-30"),
        _observation(2.97, accession="2020-represented-2019", start="2018-09-30", end="2019-09-28", filed="2020-10-30"),
        _observation(3.28, accession="2020-current", start="2019-09-29", end="2020-09-26", filed="2020-10-30"),
    ]

    facts = _adapter(_payload(observations)).fetch_facts(_request())

    assert [fact.value for fact in facts] == pytest.approx([2.98, 2.97, 3.28])
    expected_accessions = ("2020-represented-2018", "2020-represented-2019", "2020-current")
    for fact, expected_accession in zip(facts, expected_accessions, strict=True):
        assert fact.provider_fact_id is not None
        assert fact.provider_fact_id.split(":", maxsplit=1)[0] == expected_accession


def test_rejects_span_when_oldest_period_was_not_represented_after_split() -> None:
    observations = [
        _observation(9.21, accession="2017-original", start="2016-09-25", end="2017-09-30", filed="2017-11-03"),
        _observation(11.91, accession="2018-original", start="2017-10-01", end="2018-09-29", filed="2018-11-05"),
        _observation(2.98, accession="2020-represented-2018", start="2017-10-01", end="2018-09-29", filed="2020-10-30"),
        _observation(3.28, accession="2020-current", start="2019-09-29", end="2020-09-26", filed="2020-10-30"),
    ]

    assert _adapter(_payload(observations)).fetch_facts(_request()) == ()


def test_respects_historical_boundary_before_remeasurement() -> None:
    observations = [
        _observation(11.91, accession="2018-original", start="2017-10-01", end="2018-09-29", filed="2018-11-05"),
        _observation(11.89, accession="2019-current", start="2018-09-30", end="2019-09-28", filed="2019-10-31"),
        _observation(2.98, accession="2020-represented", start="2017-10-01", end="2018-09-29", filed="2020-10-30"),
    ]
    boundary = datetime(2020, 1, 1, tzinfo=UTC)

    facts = _adapter(_payload(observations)).fetch_facts(_request(observation_count=2, as_of=boundary))

    assert [fact.value for fact in facts] == pytest.approx([11.91, 11.89])


def test_rejects_conflicting_equal_rank_and_unsupported_shapes() -> None:
    conflict = [
        _observation(6.0, accession="same-a", start="2024-09-29", end="2025-09-27", filed="2025-10-31"),
        _observation(7.0, accession="same-b", start="2024-09-29", end="2025-09-27", filed="2025-10-31"),
    ]
    multi_ticker = {
        "0": {"cik_str": CIK, "ticker": "AAPL", "title": "Apple"},
        "1": {"cik_str": CIK, "ticker": "AAPL-A", "title": "Apple"},
    }

    assert _adapter(_payload(conflict)).fetch_facts(_request(observation_count=1)) == ()
    assert _adapter(_payload(conflict, unit="shares")).fetch_facts(_request(observation_count=1)) == ()
    assert _adapter(_payload(conflict), ticker_rows=multi_ticker).fetch_facts(_request(observation_count=1)) == ()
