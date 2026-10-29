"""The success golden case has its FCF yield; every other expected value of every FCF-Growth case is unchanged."""

import socket
from datetime import UTC, datetime

import pytest

from investment_analysis_engine.core.metric_result import MetricStatus, ReasonCode
from investment_analysis_engine.evaluation.cases.fcf_growth import (
    FCF_01,
    FCF_02,
    FCF_03,
    FCF_ETF_01,
    FCF_GROWTH_ARGUMENTS,
    FCF_GROWTH_CASES,
    FPI_03,
)
from investment_analysis_engine.evaluation.composition import dispatch_fixture_case
from investment_analysis_engine.evaluation.models import Case
from investment_analysis_engine.strategies.fcf_growth.models import FCFEarningsGrowthResult

EXECUTED_AT = datetime(2026, 8, 31, 18, 30, tzinfo=UTC)

NUMERICAL = {
    "FCF-01": {
        "selected_horizon_years": 5.0,
        "selected_observation_count": 6.0,
        "fcf_cagr.value": 10.197228772148015,
        "fcf_per_share_cagr.value": 10.197228772148015,
        "eps_cagr.value": 17.607902252467357,
    },
    "FCF-02": {
        "selected_horizon_years": 5.0,
        "selected_observation_count": 6.0,
        "eps_cagr.value": 17.607902252467357,
    },
    "FCF-03": {},
    "FCF-ETF-01": {},
    "FPI-03": {},
}
DOMAIN = {
    "FCF-01": {},
    "FCF-02": {
        "classification": "indeterminate",
        "classification_reason_code": "sign_change",
        "execution_status": "ok",
        "fcf_cagr.reason_code": "sign_change",
        "fcf_cagr.status": "unavailable",
        "fcf_per_share_cagr.reason_code": "sign_change",
        "fcf_per_share_cagr.status": "unavailable",
        "trend_classification": "insufficient_or_nonmeaningful_growth",
    },
    "FCF-03": {
        "classification": "indeterminate",
        "classification_reason_code": "non_contiguous_history",
        "execution_status": "input_unavailable",
        "fcf_cagr.reason_code": "non_contiguous_history",
        "fcf_cagr.status": "unavailable",
        "fcf_per_share_cagr.reason_code": "non_contiguous_history",
        "fcf_per_share_cagr.status": "unavailable",
        "selected_horizon_years": None,
        "trend_classification": "insufficient_or_nonmeaningful_growth",
    },
    "FCF-ETF-01": {
        "classification": "indeterminate",
        "classification_reason_code": "instrument_kind_not_applicable",
        "execution_status": "not_applicable",
        "fcf_cagr.reason_code": "instrument_kind_not_applicable",
        "fcf_cagr.status": "not_applicable",
        "fcf_per_share_cagr.reason_code": "instrument_kind_not_applicable",
        "fcf_per_share_cagr.status": "not_applicable",
        "selected_horizon_years": None,
        "trend_classification": "insufficient_or_nonmeaningful_growth",
    },
    "FPI-03": {"execution_status": "input_unavailable", "classification": "indeterminate"},
}
"""Every expected value the cases held before the FCF yield was valued: pinned here, field by field."""


@pytest.mark.parametrize("case", FCF_GROWTH_CASES, ids=lambda case: case.case_id)
def test_every_expected_value_of_every_case_is_unchanged(case: Case) -> None:
    expectation = case.expectation

    assert {item.field_path: item.expected_value for item in expectation.numerical_expectations} == NUMERICAL[
        case.case_id
    ]
    assert {item.field_path: item.expected_value for item in expectation.domain_outcome_expectations} == DOMAIN[
        case.case_id
    ]
    paths = [
        *(item.field_path for item in expectation.numerical_expectations),
        *(item.field_path for item in expectation.domain_outcome_expectations),
    ]
    assert not [path for path in paths if "yield" in path or "market_cap" in path]


async def _run(case: Case) -> FCFEarningsGrowthResult:
    dispatched = await dispatch_fixture_case(case, FCF_GROWTH_ARGUMENTS[case.case_id], clock_at=EXECUTED_AT)
    assert isinstance(dispatched.result, FCFEarningsGrowthResult)
    return dispatched.result


@pytest.mark.asyncio
async def test_the_success_case_has_its_yield_with_the_evidence_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("The golden suite must not access the network.")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket.socket, "connect", reject_network)

    result = await _run(FCF_01)

    assert result.fcf_yield.status is MetricStatus.OK
    assert result.fcf_yield.value == pytest.approx(10.0)
    evidence = result.market_capitalization
    assert evidence is not None
    assert evidence.result.value == pytest.approx(1300.0)
    assert (evidence.scaled_share_count, evidence.price) == (400.0, 3.25)
    assert [event.ratio for event in evidence.provider_adjustments] == [2.0]
    assert evidence.listing_check is not None
    assert evidence.listing_check.affirmed
    assert evidence.price_date == EXECUTED_AT.date()


@pytest.mark.asyncio
@pytest.mark.parametrize("case", [FCF_02, FCF_03, FPI_03], ids=lambda case: case.case_id)
async def test_the_other_cases_hold_no_market_data_and_an_unavailable_yield(case: Case) -> None:
    result = await _run(case)

    assert result.market_capitalization is None
    assert result.fcf_yield.status is MetricStatus.UNAVAILABLE
    assert result.fcf_yield.reason_code is ReasonCode.MISSING_FACT


@pytest.mark.asyncio
async def test_the_etf_case_holds_no_market_data() -> None:
    result = await _run(FCF_ETF_01)

    assert result.market_capitalization is None
    assert result.fcf_yield.status is MetricStatus.NOT_APPLICABLE
