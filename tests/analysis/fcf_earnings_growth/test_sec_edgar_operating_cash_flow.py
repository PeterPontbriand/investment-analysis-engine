"""Deterministic D1 regressions for SEC annual operating cash flow."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from src.data.financial.facts import FinancialFactRequest, FinancialField, FinancialUnit
from src.data.financial.provenance import AccountingScope, FinancialSubjectKind, PeriodKind
from src.data.sec_edgar.financial_facts import (
    SEC_OPERATING_CASH_FLOW_FIELD,
    SEC_PROVIDER_ID,
    SecEdgarFinancialFactsAdapter,
)

NOW = datetime(2026, 8, 28, 16, 0, tzinfo=UTC)
CIK = 789019
CIK_PADDED = "0000789019"


class FakeSecFetcher:
    """Return bounded SEC fixtures without making external calls."""

    def __init__(
        self,
        *,
        company_facts: object,
        submissions: object | None = None,
        ticker_rows: object | None = None,
    ) -> None:
        """Initialize deterministic endpoint responses."""
        self._company_facts = company_facts
        self._submissions = submissions or {"filings": {"recent": {}}}
        self._ticker_rows = ticker_rows or {"0": {"cik_str": CIK, "ticker": "MSFT", "title": "Microsoft Corporation"}}
        self.calls: list[str] = []

    def __call__(self, url: str, *, headers: Mapping[str, str]) -> object:
        """Return the fixture associated with an SEC URL."""
        assert headers["User-Agent"] == "D1 fixture tests@example.invalid"
        self.calls.append(url)
        if "company_tickers.json" in url:
            return self._ticker_rows
        if "/companyfacts/" in url:
            return self._company_facts
        if "/submissions/" in url:
            return self._submissions
        msg = f"Unexpected SEC URL: {url}"
        raise AssertionError(msg)


def _observation(  # noqa: PLR0913
    value: float,
    *,
    start: str,
    end: str,
    accession: str,
    filed: str,
    fy: int = 2025,
    fp: str = "FY",
    form: str = "10-K",
) -> dict[str, Any]:
    return {
        "val": value,
        "start": start,
        "end": end,
        "accn": accession,
        "filed": filed,
        "fy": fy,
        "fp": fp,
        "form": form,
    }


def _company_facts(
    observations_by_unit: Mapping[str, list[dict[str, Any]]],
    *,
    extra_concepts: Mapping[str, object] | None = None,
    cik: int = CIK,
) -> dict[str, Any]:
    us_gaap: dict[str, object] = {"NetCashProvidedByUsedInOperatingActivities": {"units": dict(observations_by_unit)}}
    if extra_concepts is not None:
        us_gaap.update(extra_concepts)
    return {
        "cik": cik,
        "entityName": "Microsoft Corporation",
        "facts": {"us-gaap": us_gaap},
    }


def _submissions(acceptances: Mapping[str, str]) -> dict[str, object]:
    return {
        "filings": {
            "recent": {
                "accessionNumber": list(acceptances),
                "acceptanceDateTime": list(acceptances.values()),
            }
        }
    }


def _request(*, as_of: datetime | None = None, count: int = 6) -> FinancialFactRequest:
    return FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="msft",
        field_name=FinancialField.OPERATING_CASH_FLOW,
        provider_id=SEC_PROVIDER_ID,
        basis="fiscal_year",
        as_of=as_of,
        observation_count=count,
    )


def _adapter(
    payload: object,
    *,
    acceptances: Mapping[str, str] | None = None,
    ticker_rows: object | None = None,
) -> SecEdgarFinancialFactsAdapter:
    return SecEdgarFinancialFactsAdapter(
        json_fetcher=FakeSecFetcher(
            company_facts=payload,
            submissions=_submissions(acceptances or {}),
            ticker_rows=ticker_rows,
        ),
        clock=lambda: NOW,
        user_agent="D1 fixture tests@example.invalid",
    )


def test_returns_signed_exact_concept_annual_facts_with_complete_metadata() -> None:
    observations = [
        _observation(
            87_582_000_000.0,
            start="2022-07-01",
            end="2023-06-30",
            accession="0001-23",
            filed="2023-07-27",
            fy=2025,
        ),
        _observation(
            0.0,
            start="2023-07-01",
            end="2024-06-30",
            accession="0001-24",
            filed="2024-07-30",
        ),
        _observation(
            -2_500_000_000.0,
            start="2024-07-01",
            end="2025-06-30",
            accession="0001-25",
            filed="2025-07-29",
        ),
        # Apple-like 53-week fiscal year is still a completed annual duration.
        _observation(
            9_000_000_000.0,
            start="2025-06-29",
            end="2026-07-04",
            accession="0001-26",
            filed="2026-08-01",
            fy=2026,
        ),
    ]
    payload = _company_facts(
        {"USD": observations},
        extra_concepts={
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations": {
                "units": {
                    "USD": [
                        _observation(
                            999.0,
                            start="2024-07-01",
                            end="2025-06-30",
                            accession="alternate",
                            filed="2025-07-29",
                        )
                    ]
                }
            }
        },
    )
    acceptances = {
        "0001-23": "2023-07-27T16:01:02-04:00",
        "0001-24": "2024-07-30T20:05:00Z",
        "0001-25": "2025-07-29T16:10:00-04:00",
        "0001-26": "2026-08-01T12:00:00-04:00",
    }

    facts = _adapter(payload, acceptances=acceptances).fetch_facts(_request())

    assert [fact.value for fact in facts] == pytest.approx([87_582_000_000.0, 0.0, -2_500_000_000.0, 9_000_000_000.0])
    assert [fact.fiscal_year for fact in facts] == [2023, 2024, 2025, 2026]
    assert all(fact.provider_field == SEC_OPERATING_CASH_FLOW_FIELD for fact in facts)
    assert all(fact.units is FinancialUnit.CURRENCY and fact.currency == "USD" for fact in facts)
    assert all(fact.basis == "fiscal_year" for fact in facts)
    assert all(fact.period_kind is PeriodKind.COMPLETED_ANNUAL for fact in facts)
    assert all(fact.accounting_scope is AccountingScope.CONSOLIDATED for fact in facts)
    assert all(fact.provider_fact_id is not None for fact in facts)
    assert facts[0].observation_period_start == datetime(2022, 7, 1, tzinfo=UTC)
    assert facts[0].observation_period_end == datetime(2023, 6, 30, 23, 59, 59, 999999, tzinfo=UTC)
    assert f"cik={CIK_PADDED}" in facts[0].notes
    assert "provider_fiscal_year=2025" in facts[0].notes


def test_preserves_comparative_and_amended_candidates_until_c2_selection() -> None:
    observations = [
        _observation(
            10.0,
            start="2023-01-01",
            end="2023-12-31",
            accession="original",
            filed="2024-02-01",
            fy=2023,
        ),
        _observation(
            11.0,
            start="2023-01-01",
            end="2023-12-31",
            accession="comparative",
            filed="2025-02-01",
            fy=2024,
        ),
        _observation(
            12.0,
            start="2023-01-01",
            end="2023-12-31",
            accession="amendment",
            filed="2025-03-01",
            fy=2024,
            form="10-K/A",
        ),
    ]
    acceptances = {
        "original": "2024-02-01T17:00:00Z",
        "comparative": "2025-02-01T17:00:00Z",
        "amendment": "2025-03-01T17:00:00Z",
    }
    adapter = _adapter(_company_facts({"USD": observations}), acceptances=acceptances)

    before_amendment = adapter.fetch_facts(_request(as_of=datetime(2025, 2, 15, 23, 59, tzinfo=UTC)))
    after_amendment = adapter.fetch_facts(_request(as_of=datetime(2025, 3, 2, 23, 59, tzinfo=UTC)))

    assert [fact.value for fact in before_amendment] == pytest.approx([10.0, 11.0])
    assert [fact.value for fact in after_amendment] == pytest.approx([10.0, 11.0, 12.0])
    assert len({(fact.observation_period_start, fact.observation_period_end) for fact in after_amendment}) == 1


def test_preserves_conflicting_equal_rank_candidates_for_typed_resolver_ambiguity() -> None:
    observations = [
        _observation(
            value,
            start="2024-01-01",
            end="2024-12-31",
            accession=accession,
            filed="2025-02-10",
            fy=2024,
        )
        for value, accession in ((100.0, "conflict-a"), (101.0, "conflict-b"))
    ]
    acceptances = {
        "conflict-a": "2025-02-10T17:00:00Z",
        "conflict-b": "2025-02-10T17:00:00Z",
    }

    facts = _adapter(_company_facts({"USD": observations}), acceptances=acceptances).fetch_facts(_request())

    assert [fact.value for fact in facts] == pytest.approx([100.0, 101.0])
    assert len({fact.available_at for fact in facts}) == 1
    assert len({fact.provider_fact_id for fact in facts}) == 2


def test_acceptance_and_filed_date_availability_follow_sec_eastern_rules() -> None:
    observations = [
        _observation(
            1.0,
            start="2022-01-01",
            end="2022-12-31",
            accession="offset",
            filed="2023-02-01",
            fy=2022,
        ),
        _observation(
            2.0,
            start="2023-01-01",
            end="2023-12-31",
            accession="legacy-naive",
            filed="2024-02-01",
            fy=2023,
        ),
        _observation(
            3.0,
            start="2024-01-01",
            end="2024-12-31",
            accession="filed-fallback",
            filed="2025-07-01",
            fy=2024,
        ),
    ]
    acceptances = {
        "offset": "2023-02-01T16:30:00-05:00",
        "legacy-naive": "2024-02-01T16:30:00",
    }

    facts = _adapter(_company_facts({"USD": observations}), acceptances=acceptances).fetch_facts(_request())

    assert [fact.available_at for fact in facts] == [
        datetime(2023, 2, 1, 21, 30, tzinfo=UTC),
        datetime(2024, 2, 1, 21, 30, tzinfo=UTC),
        datetime(2025, 7, 2, 3, 59, 59, 999999, tzinfo=UTC),
    ]
    assert "acceptanceDateTime" in facts[0].notes[-1]
    assert "America/New_York" in facts[-1].notes[-1]


def test_rejects_nonannual_malformed_and_unsupported_unit_shapes() -> None:
    valid = _observation(
        50.0,
        start="2024-01-01",
        end="2024-12-31",
        accession="valid",
        filed="2025-02-01",
        fy=2024,
    )
    invalid = [
        _observation(
            1.0,
            start="2024-10-01",
            end="2024-12-31",
            accession="quarter",
            filed="2025-02-01",
            fy=2024,
        ),
        _observation(
            2.0,
            start="2024-01-01",
            end="2024-12-31",
            accession="wrong-form",
            filed="2025-02-01",
            fy=2024,
            form="10-Q",
        ),
        _observation(
            3.0,
            start="not-a-date",
            end="2024-12-31",
            accession="bad-date",
            filed="2025-02-01",
            fy=2024,
        ),
    ]
    payload = _company_facts({"USD": [valid, *invalid], "USD millions": [valid], "pure": [valid]})

    facts = _adapter(payload).fetch_facts(_request())

    assert len(facts) == 1
    assert facts[0].value == pytest.approx(50.0)


def test_rejects_company_facts_cik_mismatch() -> None:
    payload = _company_facts(
        {
            "USD": [
                _observation(
                    1.0,
                    start="2024-01-01",
                    end="2024-12-31",
                    accession="one",
                    filed="2025-02-01",
                    fy=2024,
                )
            ]
        },
        cik=123456,
    )

    assert _adapter(payload).fetch_facts(_request()) == ()


def test_unsupported_request_shape_returns_empty_without_fetching() -> None:
    payload = _company_facts({"USD": []})
    fetcher = FakeSecFetcher(company_facts=payload)
    adapter = SecEdgarFinancialFactsAdapter(
        json_fetcher=fetcher,
        clock=lambda: NOW,
        user_agent="D1 fixture tests@example.invalid",
    )
    request = FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="MSFT",
        field_name=FinancialField.OPERATING_CASH_FLOW,
        provider_id=SEC_PROVIDER_ID,
        basis="fiscal_year_end",
    )

    assert adapter.fetch_facts(request) == ()
    assert fetcher.calls == []
