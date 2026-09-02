"""Fixture-focused checks for reviewed FCF/Earnings Growth expectation inputs."""

import math
from collections.abc import Iterable
from datetime import UTC, datetime

import pytest

from src.data.financial.facts import FinancialField, ProviderFact
from src.data.financial.provenance import AccountingScope, CapitalExpenditureSign, PeriodKind
from src.evaluation.fixtures.fcf_earnings_growth import (
    FCF_GROWTH_CAPEX,
    FCF_GROWTH_DILUTED_SHARES,
    FCF_GROWTH_EPS_VALUES,
    FCF_GROWTH_FCF_VALUES,
    FCF_GROWTH_HISTORICAL_AS_OF,
    FCF_GROWTH_MISALIGNED_FISCAL_YEAR,
    FCF_GROWTH_NONMEANINGFUL_FCF_VALUES,
    FCF_GROWTH_YEARS,
    fcf_growth_nonmeaningful_facts,
    fcf_growth_period_as_of_facts,
    fcf_growth_success_facts,
)


def _field_facts(facts: Iterable[ProviderFact], field: FinancialField) -> tuple[ProviderFact, ...]:
    return tuple(fact for fact in facts if fact.field_name is field)


def _values(facts: Iterable[ProviderFact], field: FinancialField) -> tuple[float, ...]:
    return tuple(fact.value for fact in _field_facts(facts, field))


def _periods(facts: Iterable[ProviderFact], field: FinancialField) -> set[tuple[datetime, datetime]]:
    result: set[tuple[datetime, datetime]] = set()
    for fact in _field_facts(facts, field):
        assert fact.observation_period_start is not None
        assert fact.observation_period_end is not None
        result.add((fact.observation_period_start, fact.observation_period_end))
    return result


def _cagr(beginning: float, ending: float, elapsed_years: int) -> float:
    return (math.pow(ending / beginning, 1.0 / elapsed_years) - 1.0) * 100.0


def test_success_fixture_has_exact_reviewed_annual_evidence() -> None:
    facts = fcf_growth_success_facts()

    assert len(facts) == len(FCF_GROWTH_YEARS) * 4
    assert tuple(fact.fiscal_year for fact in _field_facts(facts, FinancialField.EPS)) == FCF_GROWTH_YEARS
    assert _values(facts, FinancialField.CAPITAL_EXPENDITURES) == (FCF_GROWTH_CAPEX,) * 6
    assert _values(facts, FinancialField.EPS) == FCF_GROWTH_EPS_VALUES
    assert _values(facts, FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES) == (FCF_GROWTH_DILUTED_SHARES,) * 6

    for fact in facts:
        assert fact.fiscal_year is not None
        assert fact.observation_period_start == datetime(fact.fiscal_year - 1, 1, 1, tzinfo=UTC)
        assert fact.observation_period_end == datetime(fact.fiscal_year, 1, 1, tzinfo=UTC)
        assert fact.available_at == datetime(fact.fiscal_year, 2, 1, tzinfo=UTC)
        assert fact.period_kind is PeriodKind.COMPLETED_ANNUAL
        assert fact.accounting_scope is AccountingScope.CONSOLIDATED
    assert all(
        fact.capital_expenditure_sign is CapitalExpenditureSign.POSITIVE_EXPENDITURE
        for fact in _field_facts(facts, FinancialField.CAPITAL_EXPENDITURES)
    )

    operating_cash_flow = _values(facts, FinancialField.OPERATING_CASH_FLOW)
    derived_fcf = tuple(value - FCF_GROWTH_CAPEX for value in operating_cash_flow)
    assert derived_fcf == FCF_GROWTH_FCF_VALUES


def test_success_reference_cagrs_use_five_elapsed_years() -> None:
    elapsed_years = len(FCF_GROWTH_YEARS) - 1
    fcf_cagr = _cagr(FCF_GROWTH_FCF_VALUES[0], FCF_GROWTH_FCF_VALUES[-1], elapsed_years)
    eps_cagr = _cagr(FCF_GROWTH_EPS_VALUES[0], FCF_GROWTH_EPS_VALUES[-1], elapsed_years)

    assert elapsed_years == 5
    assert fcf_cagr == pytest.approx(10.197228772148015, abs=1e-12)
    assert eps_cagr == pytest.approx(17.607902252467357, abs=1e-12)
    assert fcf_cagr > 0.0
    assert eps_cagr > 0.0


def test_nonmeaningful_fixture_has_interior_fcf_sign_change() -> None:
    facts = fcf_growth_nonmeaningful_facts()
    operating_cash_flow = _values(facts, FinancialField.OPERATING_CASH_FLOW)
    derived_fcf = tuple(value - FCF_GROWTH_CAPEX for value in operating_cash_flow)

    assert derived_fcf == FCF_GROWTH_NONMEANINGFUL_FCF_VALUES
    assert derived_fcf[0] > 0.0
    assert derived_fcf[-1] > 0.0
    assert any(left * right < 0.0 for left, right in zip(derived_fcf, derived_fcf[1:], strict=False))
    assert _cagr(FCF_GROWTH_EPS_VALUES[0], FCF_GROWTH_EPS_VALUES[-1], 5) == pytest.approx(
        17.607902252467357,
        abs=1e-12,
    )


def test_period_as_of_fixture_proves_both_filters_without_lookahead() -> None:
    facts = fcf_growth_period_as_of_facts()
    latest = tuple(fact for fact in facts if fact.fiscal_year == 2025)
    eligible = tuple(
        fact for fact in facts if fact.available_at is not None and fact.available_at <= FCF_GROWTH_HISTORICAL_AS_OF
    )

    assert len(latest) == 4
    assert all(fact.available_at is not None and fact.available_at > FCF_GROWTH_HISTORICAL_AS_OF for fact in latest)
    assert all(fact.fiscal_year != 2025 for fact in eligible)

    misaligned_eps = next(
        fact
        for fact in eligible
        if fact.field_name is FinancialField.EPS and fact.fiscal_year == FCF_GROWTH_MISALIGNED_FISCAL_YEAR
    )
    aligned_ocf = next(
        fact
        for fact in eligible
        if fact.field_name is FinancialField.OPERATING_CASH_FLOW
        and fact.fiscal_year == FCF_GROWTH_MISALIGNED_FISCAL_YEAR
    )
    assert misaligned_eps.observation_period_start != aligned_ocf.observation_period_start
    assert misaligned_eps.observation_period_end == aligned_ocf.observation_period_end

    common_periods = set.intersection(
        _periods(eligible, FinancialField.OPERATING_CASH_FLOW),
        _periods(eligible, FinancialField.CAPITAL_EXPENDITURES),
        _periods(eligible, FinancialField.EPS),
    )
    assert len(common_periods) == 4
    assert tuple(period_end.year for _, period_end in sorted(common_periods)) == (2020, 2021, 2022, 2024)
    assert len(common_periods) < 5


def test_fixture_factories_return_fresh_immutable_fact_tuples() -> None:
    assert fcf_growth_success_facts() is not fcf_growth_success_facts()
    assert fcf_growth_success_facts() == fcf_growth_success_facts()
    assert isinstance(fcf_growth_success_facts(), tuple)
