"""Deterministic D2 regressions for SEC annual capital expenditures."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.financial.facts import FinancialFactRequest, FinancialField, FinancialUnit
from investment_analysis_engine.data.financial.provenance import (
    AccountingScope,
    CapitalExpenditureSign,
    FinancialSubjectKind,
    PeriodKind,
)
from investment_analysis_engine.data.sec_edgar.financial_facts import (
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

    def __call__(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        not_found: ProviderFailureKind,  # noqa: ARG002
        provider_id: str,  # noqa: ARG002
    ) -> object:
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


def _observation(  # noqa: PLR0913
    value: float,
    *,
    accession: str,
    start: str = "2024-07-01",
    end: str = "2025-06-30",
    filed: str = "2025-07-29",
) -> dict[str, Any]:
    return {
        "val": value,
        "start": start,
        "end": end,
        "accn": accession,
        "filed": filed,
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
    facts = _adapter(_payload([_observation(24_000_000_000.0, accession="positive")])).fetch_facts(
        _request(), effective_as_of=NOW
    )

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
    ).fetch_facts(_request(), effective_as_of=NOW)

    assert [fact.value for fact in facts] == pytest.approx([0.0])


def test_does_not_substitute_other_ppe_concepts() -> None:
    alternates = {
        "PaymentsToAcquireOtherPropertyPlantAndEquipment": {"units": {"USD": [_observation(99.0, accession="other")]}}
    }

    assert _adapter(_payload(extra_concepts=alternates)).fetch_facts(_request(), effective_as_of=NOW) == ()


def test_rejects_unsupported_period_unit_and_request_shapes() -> None:
    quarterly = _observation(5.0, accession="quarter", start="2025-04-01", end="2025-06-30")
    wrong_units = {
        "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD millions": [_observation(6.0, accession="unit")]}}
    }
    assert _adapter(_payload([quarterly])).fetch_facts(_request(), effective_as_of=NOW) == ()
    assert _adapter(_payload(extra_concepts=wrong_units)).fetch_facts(_request(), effective_as_of=NOW) == ()
    assert (
        _adapter(_payload([_observation(5.0, accession="basis")])).fetch_facts(
            _request(basis="fiscal_year_end"), effective_as_of=NOW
        )
        == ()
    )


# ---------------------------------------------------------------------------
# One capital-expenditure concept per request: the one that covers the longer run of the newest periods.
# ---------------------------------------------------------------------------

_PPE = "PaymentsToAcquirePropertyPlantAndEquipment"
_PRODUCTIVE = "PaymentsToAcquireProductiveAssets"
_NVDA_ENDS = (
    ("2021-02-01", "2022-01-30", 976e6),
    ("2022-01-31", "2023-01-29", 1833e6),
    ("2023-01-30", "2024-01-28", 1069e6),
    ("2024-01-29", "2025-01-26", 3236e6),
    ("2025-01-27", "2026-01-25", 6042e6),
)


def _concept(name: str, rows: list[tuple[str, str, float]]) -> dict[str, object]:
    return {
        name: {
            "units": {
                "USD": [
                    _observation(value, accession=f"{name}-{end}", start=start, end=end, filed="2026-02-25")
                    for start, end, value in rows
                ]
            }
        }
    }


def _capex(concepts: Mapping[str, object]) -> tuple[Any, ...]:
    return _adapter(_payload(extra_concepts=concepts)).fetch_facts(_request(), effective_as_of=NOW)


def test_an_nvda_shaped_issuer_whose_ppe_concept_stops_early_gets_productive_assets_only() -> None:
    ppe = [
        ("2009-01-26", "2010-01-31", 77_601_000.0),
        ("2010-02-01", "2011-01-30", 97_890_000.0),
        ("2011-01-31", "2012-01-29", 138_735_000.0),
    ]

    facts = _capex({**_concept(_PPE, ppe), **_concept(_PRODUCTIVE, list(_NVDA_ENDS))})

    assert [fact.value for fact in facts] == pytest.approx([row[2] for row in _NVDA_ENDS])
    assert {fact.provider_field for fact in facts} == {"us-gaap:PaymentsToAcquireProductiveAssets"}
    assert {fact.capital_expenditure_sign for fact in facts} == {CapitalExpenditureSign.POSITIVE_EXPENDITURE}


def test_an_apple_shaped_switch_to_ppe_returns_ppe_only() -> None:
    productive = [("2017-10-01", "2018-09-29", 14e9), ("2018-09-30", "2019-09-28", 10e9)]
    ppe = [
        ("2019-09-29", "2020-09-26", 7e9),
        ("2020-09-27", "2021-09-25", 11e9),
        ("2021-09-26", "2022-09-24", 10e9),
    ]

    facts = _capex({**_concept(_PRODUCTIVE, productive), **_concept(_PPE, ppe)})

    assert [fact.value for fact in facts] == pytest.approx([7e9, 11e9, 10e9])
    assert {fact.provider_field for fact in facts} == {"us-gaap:PaymentsToAcquirePropertyPlantAndEquipment"}


def test_a_tie_returns_ppe() -> None:
    rows = [("2022-01-31", "2023-01-29", 1.0), ("2023-01-30", "2024-01-28", 2.0)]
    other = [("2022-01-31", "2023-01-29", 9.0), ("2023-01-30", "2024-01-28", 8.0)]

    facts = _capex({**_concept(_PRODUCTIVE, other), **_concept(_PPE, rows)})

    assert [fact.value for fact in facts] == [1.0, 2.0]
    assert {fact.provider_field for fact in facts} == {"us-gaap:PaymentsToAcquirePropertyPlantAndEquipment"}


def test_the_broader_concept_wins_only_by_a_longer_run_and_the_two_are_never_combined() -> None:
    ppe = [("2024-01-29", "2025-01-26", 5.0)]
    productive = [(start, end, value) for start, end, value in _NVDA_ENDS[-3:]]

    facts = _capex({**_concept(_PPE, ppe), **_concept(_PRODUCTIVE, productive)})

    assert len(facts) == 3
    assert {fact.provider_field for fact in facts} == {"us-gaap:PaymentsToAcquireProductiveAssets"}


def test_a_negative_productive_assets_value_is_rejected() -> None:
    assert _capex(_concept(_PRODUCTIVE, [("2024-01-29", "2025-01-26", -5.0)])) == ()
