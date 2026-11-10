"""Deterministic D3 regressions for SEC completed-annual diluted EPS."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any

import pytest

from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.financial.facts import FinancialFactRequest, FinancialField, FinancialUnit
from investment_analysis_engine.data.financial.provenance import AccountingScope, FinancialSubjectKind, PeriodKind
from investment_analysis_engine.data.financial.resolver import EARLIER_BASIS_MESSAGE, InputResolver, LeftOutReason
from investment_analysis_engine.data.sec_edgar.financial_facts import (
    SEC_EPS_FIELD,
    SEC_PROVIDER_ID,
    SecEdgarFinancialFactsAdapter,
)

NOW = datetime(2026, 8, 29, 16, 0, tzinfo=UTC)
CIK = 320193


class FakeSecFetcher:
    """Return bounded SEC fixtures without external calls."""

    def __init__(self, company_facts: object, *, ticker_rows: object | None = None) -> None:
        """Initialize deterministic endpoint responses."""
        self._company_facts = company_facts
        self._ticker_rows = ticker_rows or {"0": {"cik_str": CIK, "ticker": "AAPL", "title": "Apple"}}

    def __call__(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        not_found: ProviderFailureKind,  # noqa: ARG002
        provider_id: str,  # noqa: ARG002
    ) -> object:
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

    facts = _adapter(_payload([observation])).fetch_facts(_request(observation_count=1), effective_as_of=NOW)

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

    facts = _adapter(_payload(observations)).fetch_facts(_request(), effective_as_of=NOW)

    assert [fact.value for fact in facts] == pytest.approx([2.98, 2.97, 3.28])
    expected_accessions = ("2020-represented-2018", "2020-represented-2019", "2020-current")
    for fact, expected_accession in zip(facts, expected_accessions, strict=True):
        assert fact.provider_fact_id is not None
        assert fact.provider_fact_id.split(":", maxsplit=1)[0] == expected_accession


def test_returns_the_shorter_span_when_oldest_period_was_not_represented_after_split() -> None:
    observations = [
        _observation(9.21, accession="2017-original", start="2016-09-25", end="2017-09-30", filed="2017-11-03"),
        _observation(11.91, accession="2018-original", start="2017-10-01", end="2018-09-29", filed="2018-11-05"),
        _observation(2.98, accession="2020-represented-2018", start="2017-10-01", end="2018-09-29", filed="2020-10-30"),
        _observation(3.28, accession="2020-current", start="2019-09-29", end="2020-09-26", filed="2020-10-30"),
    ]
    adapter = _adapter(_payload(observations))

    assert [fact.value for fact in adapter.fetch_facts(_request(), effective_as_of=NOW)] == pytest.approx([2.98, 3.28])
    answer = adapter.fetch_annual_series(_request(), effective_as_of=NOW)
    assert [fact.value for fact in answer.facts] == pytest.approx([2.98, 3.28])
    assert [fact.value for fact in answer.earlier_basis] == pytest.approx([9.21])
    assert [fact.observation_period_end.date() for fact in answer.earlier_basis if fact.observation_period_end] == [
        date(2017, 9, 30)
    ]


def test_a_series_that_is_all_on_one_basis_reports_no_earlier_basis_period() -> None:
    observations = [
        _observation(2.98, accession="2020-represented-2018", start="2017-10-01", end="2018-09-29", filed="2020-10-30"),
        _observation(3.28, accession="2020-current", start="2019-09-29", end="2020-09-26", filed="2020-10-30"),
    ]

    answer = _adapter(_payload(observations)).fetch_annual_series(_request(), effective_as_of=NOW)

    assert len(answer.facts) == 2
    assert answer.earlier_basis == ()


def test_respects_historical_boundary_before_remeasurement() -> None:
    observations = [
        _observation(11.91, accession="2018-original", start="2017-10-01", end="2018-09-29", filed="2018-11-05"),
        _observation(11.89, accession="2019-current", start="2018-09-30", end="2019-09-28", filed="2019-10-31"),
        _observation(2.98, accession="2020-represented", start="2017-10-01", end="2018-09-29", filed="2020-10-30"),
    ]
    boundary = datetime(2020, 1, 1, tzinfo=UTC)

    facts = _adapter(_payload(observations)).fetch_facts(
        _request(observation_count=2, as_of=boundary), effective_as_of=boundary
    )

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

    assert _adapter(_payload(conflict)).fetch_facts(_request(observation_count=1), effective_as_of=NOW) == ()
    assert (
        _adapter(_payload(conflict, unit="shares")).fetch_facts(_request(observation_count=1), effective_as_of=NOW)
        == ()
    )
    assert (
        _adapter(_payload(conflict), ticker_rows=multi_ticker).fetch_facts(
            _request(observation_count=1), effective_as_of=NOW
        )
        == ()
    )


# ---------------------------------------------------------------------------
# An NVDA-shaped issuer: late-January year ends, a 4-for-1 split in 2021 and a 10-for-1 split in 2024.
# Each tuple is (period start, period end, value, accession, filed); a 10-K carries three years, so the years the
# 2024 split restated are the three newest and the older ones were last filed before it.
# ---------------------------------------------------------------------------

_NVDA_CIK = 1045810
_NVDA_PERIODS = (
    ("2020-01-27", "2021-01-31"),
    ("2021-02-01", "2022-01-30"),
    ("2022-01-31", "2023-01-29"),
    ("2023-01-30", "2024-01-28"),
    ("2024-01-29", "2025-01-26"),
    ("2025-01-27", "2026-01-25"),
)
_NVDA_FILINGS = {
    "21": ("0001045810-21-000010", "2021-02-26"),
    "22": ("0001045810-22-000036", "2022-03-18"),
    "23": ("0001045810-23-000017", "2023-02-24"),
    "24": ("0001045810-24-000029", "2024-02-21"),
    "25": ("0001045810-25-000023", "2025-02-26"),
    "26": ("0001045810-26-000021", "2026-02-25"),
}
# Period index -> the value each filing year reported for it.
_NVDA_EPS = {
    0: {"21": 6.9, "22": 1.73, "23": 1.73},
    1: {"22": 3.85, "23": 3.85, "24": 3.85},
    2: {"23": 1.74, "24": 1.74, "25": 0.17},
    3: {"24": 11.93, "25": 1.19, "26": 1.19},
    4: {"25": 2.94, "26": 2.94},
    5: {"26": 4.9},
}
_NVDA_SHARES = {
    0: {"21": 628e6, "22": 2510e6, "23": 2510e6},
    1: {"22": 2535e6, "23": 2535e6, "24": 2535e6},
    2: {"23": 2507e6, "24": 2507e6, "25": 25070e6},
    3: {"24": 2494e6, "25": 24940e6, "26": 24940e6},
    4: {"25": 24804e6, "26": 24804e6},
    5: {"26": 24514e6},
}


def _nvda_observations(series: Mapping[int, Mapping[str, float]]) -> list[dict[str, Any]]:
    return [
        _observation(
            value,
            accession=_NVDA_FILINGS[year][0],
            start=_NVDA_PERIODS[index][0],
            end=_NVDA_PERIODS[index][1],
            filed=_NVDA_FILINGS[year][1],
        )
        for index, by_year in series.items()
        for year, value in by_year.items()
    ]


def _nvda_payload() -> dict[str, Any]:
    return {
        "cik": _NVDA_CIK,
        "entityName": "NVIDIA",
        "facts": {
            "us-gaap": {
                "EarningsPerShareDiluted": {"units": {"USD/shares": _nvda_observations(_NVDA_EPS)}},
                "WeightedAverageNumberOfDilutedSharesOutstanding": {
                    "units": {"shares": _nvda_observations(_NVDA_SHARES)}
                },
            }
        },
    }


def _nvda_adapter() -> SecEdgarFinancialFactsAdapter:
    rows = {"0": {"cik_str": _NVDA_CIK, "ticker": "NVDA", "title": "NVIDIA"}}
    return _adapter(_nvda_payload(), ticker_rows=rows)


def _nvda_request(field: FinancialField) -> FinancialFactRequest:
    return FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="NVDA",
        field_name=field,
        provider_id=SEC_PROVIDER_ID,
        basis="fiscal_year",
        observation_count=6,
    )


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        (FinancialField.EPS, [0.17, 1.19, 2.94, 4.9]),
        (FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES, [25070e6, 24940e6, 24804e6, 24514e6]),
    ],
)
def test_nvda_series_is_the_four_years_on_the_latest_basis(field: FinancialField, expected: list[float]) -> None:
    answer = _nvda_adapter().fetch_annual_series(_nvda_request(field), effective_as_of=NOW)

    assert [fact.value for fact in answer.facts] == pytest.approx(expected)
    assert [fact.observation_period_end.year for fact in answer.facts if fact.observation_period_end] == [
        2023,
        2024,
        2025,
        2026,
    ]
    assert [fact.observation_period_end.year for fact in answer.earlier_basis if fact.observation_period_end] == [
        2021,
        2022,
    ]
    assert [fact.value for fact in answer.earlier_basis] == pytest.approx(
        [1.73, 3.85] if field is FinancialField.EPS else [2510e6, 2535e6]
    )


def test_nvda_series_through_the_resolver_names_the_years_left_out() -> None:
    resolver = InputResolver(_nvda_adapter(), clock=lambda: NOW)

    resolution = resolver.resolve_annual_series(_nvda_request(FinancialField.EPS))

    assert resolution.status is CalculationStatus.OK
    assert [item.observation_period_end.year for item in resolution.inputs if item.observation_period_end] == [
        2023,
        2024,
        2025,
        2026,
    ]
    assert [(item.why, item.reason) for item in resolution.left_out] == [
        (LeftOutReason.EARLIER_BASIS, EARLIER_BASIS_MESSAGE)
    ] * 2
    assert [item.observation_period_end.year for item in resolution.left_out if item.observation_period_end] == [
        2021,
        2022,
    ]
    assert resolution.resolution_trace.events[-1].message == (
        "4 fiscal-year observation(s) resolved; 2 left out as reported only on an earlier basis."
    )


def test_a_boundary_before_the_second_split_keeps_every_year_on_the_first_basis() -> None:
    boundary = datetime(2024, 6, 1, tzinfo=UTC)
    request = FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="NVDA",
        field_name=FinancialField.EPS,
        provider_id=SEC_PROVIDER_ID,
        basis="fiscal_year",
        as_of=boundary,
        observation_count=3,
    )

    answer = _nvda_adapter().fetch_annual_series(request, effective_as_of=boundary)

    assert [fact.value for fact in answer.facts] == pytest.approx([3.85, 1.74, 11.93])
    assert answer.earlier_basis == ()


def test_the_three_year_average_reads_the_nvda_series_on_its_latest_basis() -> None:
    request = _nvda_request(FinancialField.EPS)
    request = FinancialFactRequest(
        subject_kind=request.subject_kind,
        subject_id=request.subject_id,
        field_name=request.field_name,
        provider_id=request.provider_id,
        basis=request.basis,
        observation_count=3,
    )

    result = InputResolver(_nvda_adapter(), clock=lambda: NOW).resolve_three_year_average_eps(request, use_cache=False)

    assert result.status is CalculationStatus.OK
    assert result.resolved_input is not None
    assert result.resolved_input.value == pytest.approx((1.19 + 2.94 + 4.9) / 3)


def test_the_three_year_average_says_how_many_periods_a_shortened_series_has() -> None:
    observations = [
        _observation(9.21, accession="2017-original", start="2016-09-25", end="2017-09-30", filed="2017-11-03"),
        _observation(11.91, accession="2018-original", start="2017-10-01", end="2018-09-29", filed="2018-11-05"),
        _observation(2.98, accession="2020-represented-2018", start="2017-10-01", end="2018-09-29", filed="2020-10-30"),
        _observation(3.28, accession="2020-current", start="2019-09-29", end="2020-09-26", filed="2020-10-30"),
    ]

    result = InputResolver(_adapter(_payload(observations)), clock=lambda: NOW).resolve_three_year_average_eps(
        _request(), use_cache=False
    )

    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.reason == "Insufficient eligible fiscal-year EPS observations: found 2 distinct period(s), need 3."
