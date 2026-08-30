"""Focused C2 tests for deterministic annual-series resolution."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from src.analysis.fcf_earnings_growth.input_resolver import (
    CACHE_SCHEMA_VERSION,
    AnnualGrowthSeriesAssembly,
    FinancialFieldProvider,
    resolve_annual_growth_series,
)
from src.analysis.fcf_earnings_growth.models import (
    FCFClassificationBasis,
    FCFEarningsGrowthPolicy,
    HistoricalHorizon,
    MetricStatus,
    ReasonCode,
)
from src.core.analysis_status import CalculationStatus
from src.data.financial.cache import InMemoryResolvedInputCache
from src.data.financial.facts import FinancialField
from src.data.financial.provenance import AccountingScope, CapitalExpenditureSign
from tests.analysis.fcf_earnings_growth.fixture_financial_facts_provider import (
    PROVIDER_ID,
    FixtureAnnualFinancialFactsProvider,
    annual_fact,
    annual_series,
)

NOW = datetime(2026, 3, 1, tzinfo=UTC)


def _bindings(provider: FixtureAnnualFinancialFactsProvider) -> dict[FinancialField, FinancialFieldProvider]:
    binding = FinancialFieldProvider(PROVIDER_ID, provider)
    return dict.fromkeys(
        (
            FinancialField.OPERATING_CASH_FLOW,
            FinancialField.CAPITAL_EXPENDITURES,
            FinancialField.EPS,
            FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES,
        ),
        binding,
    )


def _resolve(
    provider: FixtureAnnualFinancialFactsProvider,
    *,
    horizon: HistoricalHorizon = HistoricalHorizon.LONGEST_AVAILABLE,
    cache: InMemoryResolvedInputCache | None = None,
) -> AnnualGrowthSeriesAssembly:
    return resolve_annual_growth_series(
        policy=FCFEarningsGrowthPolicy(historical_horizon=horizon),
        subject_id="ACME",
        currency="USD",
        as_of=None,
        providers=_bindings(provider),
        cache=cache,
        clock=lambda: NOW,
    )


def test_resolves_five_year_span_oldest_to_newest_with_lineage() -> None:
    provider = FixtureAnnualFinancialFactsProvider(annual_series(range(2020, 2026)))
    result = _resolve(provider)
    assert result.status is CalculationStatus.OK
    assert result.selected_horizon_years == 5
    assert [item.fiscal_year for item in result.observations] == [2020, 2021, 2022, 2023, 2024, 2025]
    assert result.fcf_cagr.status is MetricStatus.OK
    assert result.eps_cagr.status is MetricStatus.OK
    for item in result.observations:
        assert item.free_cash_flow.lineage is not None
        assert len(item.free_cash_flow.lineage.components) == 2


def test_longest_available_falls_back_to_three_years() -> None:
    result = _resolve(FixtureAnnualFinancialFactsProvider(annual_series(range(2022, 2026))))
    assert result.status is CalculationStatus.OK
    assert result.selected_horizon_years == 3
    assert result.used_horizon_fallback


def test_explicit_five_year_horizon_is_strict() -> None:
    result = _resolve(
        FixtureAnnualFinancialFactsProvider(annual_series(range(2022, 2026))),
        horizon=HistoricalHorizon.FIVE_YEARS,
    )
    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.reason_code is ReasonCode.INSUFFICIENT_HISTORY


def test_interior_fcf_sign_change_is_nonmeaningful() -> None:
    values = (5.0, -2.0, 7.0, 8.0)
    result = _resolve(FixtureAnnualFinancialFactsProvider(annual_series(range(2022, 2026), fcf_values=values)))
    assert result.status is CalculationStatus.OK
    assert result.span_sign_change_fcf
    assert result.fcf_cagr.reason_code is ReasonCode.SIGN_CHANGE


def test_negative_cash_outflow_capex_is_normalized() -> None:
    facts = list(annual_series(range(2020, 2026)))
    facts = [
        annual_fact(
            FinancialField.CAPITAL_EXPENDITURES,
            fact.fiscal_year or 0,
            -fact.value,
            capex_sign=CapitalExpenditureSign.NEGATIVE_CASH_OUTFLOW,
        )
        if fact.field_name is FinancialField.CAPITAL_EXPENDITURES
        else fact
        for fact in facts
    ]
    result = _resolve(FixtureAnnualFinancialFactsProvider(tuple(facts)))
    assert result.status is CalculationStatus.OK
    assert all(item.normalized_capital_expenditures.value == 20.0 for item in result.observations)


def test_contradictory_capex_sign_is_ambiguous() -> None:
    facts = list(annual_series(range(2020, 2026)))
    capex = next(fact for fact in facts if fact.field_name is FinancialField.CAPITAL_EXPENDITURES)
    facts.remove(capex)
    facts.append(
        annual_fact(
            FinancialField.CAPITAL_EXPENDITURES,
            capex.fiscal_year or 0,
            -20.0,
            capex_sign=CapitalExpenditureSign.POSITIVE_EXPENDITURE,
        )
    )
    result = _resolve(FixtureAnnualFinancialFactsProvider(tuple(facts)))
    assert result.reason_code is ReasonCode.AMBIGUOUS_FACT


def test_latest_restatement_wins_and_provider_order_does_not_matter() -> None:
    base = list(annual_series(range(2020, 2026)))
    original = next(fact for fact in base if fact.field_name is FinancialField.EPS and fact.fiscal_year == 2025)
    restated = annual_fact(
        FinancialField.EPS,
        2025,
        9.0,
        available_at=(original.available_at or NOW) + timedelta(days=1),
        provider_fact_id="eps-2025-restated",
    )
    first = _resolve(FixtureAnnualFinancialFactsProvider((*base, restated)))
    second = _resolve(FixtureAnnualFinancialFactsProvider(tuple(reversed((*base, restated)))))
    assert first.status is CalculationStatus.OK
    assert first.observations[-1].diluted_eps.value == 9.0
    assert first.eps_cagr == second.eps_cagr


def test_conflicting_latest_values_are_ambiguous() -> None:
    facts = list(annual_series(range(2020, 2026)))
    facts.append(annual_fact(FinancialField.EPS, 2025, 99.0, provider_fact_id="eps-conflict"))
    result = _resolve(FixtureAnnualFinancialFactsProvider(tuple(facts)))
    assert result.reason_code is ReasonCode.AMBIGUOUS_FACT


def test_identical_latest_duplicate_is_harmless() -> None:
    facts = list(annual_series(range(2020, 2026)))
    duplicate = next(fact for fact in facts if fact.field_name is FinancialField.EPS and fact.fiscal_year == 2025)
    facts.append(replace(duplicate, provider_fact_id="eps-2025-duplicate"))
    result = _resolve(FixtureAnnualFinancialFactsProvider(tuple(reversed(facts))))
    assert result.status is CalculationStatus.OK
    assert result.observations[-1].diluted_eps.value == duplicate.value


def test_provider_fact_id_collision_is_ambiguous() -> None:
    facts = list(annual_series(range(2020, 2026)))
    facts.append(annual_fact(FinancialField.EPS, 2024, 99.0, provider_fact_id="eps-2025"))
    result = _resolve(FixtureAnnualFinancialFactsProvider(tuple(facts)))
    assert result.reason_code is ReasonCode.AMBIGUOUS_FACT


def test_missing_annual_metadata_is_rejected() -> None:
    facts = tuple(
        replace(fact, fiscal_year=None) if fact.field_name is FinancialField.EPS else fact
        for fact in annual_series(range(2020, 2026))
    )
    result = _resolve(FixtureAnnualFinancialFactsProvider(facts))
    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.reason_code is ReasonCode.INCOMPATIBLE_PERIOD


def test_incompatible_accounting_scope_is_rejected() -> None:
    facts = tuple(
        replace(fact, accounting_scope=AccountingScope.PARENT)
        if fact.field_name is FinancialField.OPERATING_CASH_FLOW
        else fact
        for fact in annual_series(range(2020, 2026))
    )
    result = _resolve(FixtureAnnualFinancialFactsProvider(facts))
    assert result.reason_code is ReasonCode.INCOMPATIBLE_SCOPE


def test_provider_error_is_typed() -> None:
    provider = FixtureAnnualFinancialFactsProvider(
        annual_series(range(2020, 2026)),
        error_field=FinancialField.OPERATING_CASH_FLOW,
    )
    result = _resolve(provider)
    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert result.reason_code is ReasonCode.PROVIDER_ERROR


def test_missing_capex_year_prevents_contiguous_five_year_span() -> None:
    facts = tuple(
        fact
        for fact in annual_series(range(2020, 2026))
        if not (fact.field_name is FinancialField.CAPITAL_EXPENDITURES and fact.fiscal_year == 2023)
    )
    result = _resolve(FixtureAnnualFinancialFactsProvider(facts), horizon=HistoricalHorizon.FIVE_YEARS)
    assert result.reason_code is ReasonCode.NON_CONTIGUOUS_HISTORY


def test_complete_cache_avoids_provider_and_partial_cache_refreshes_field() -> None:
    cache = InMemoryResolvedInputCache(clock=lambda: NOW)
    first_provider = FixtureAnnualFinancialFactsProvider(annual_series(range(2020, 2026)))
    first = _resolve(first_provider, cache=cache)
    assert first.status is CalculationStatus.OK
    assert len(first_provider.requests) == 4

    hit_provider = FixtureAnnualFinancialFactsProvider(())
    hit = _resolve(hit_provider, cache=cache)
    assert hit.status is CalculationStatus.OK
    assert hit_provider.requests == []


def test_partial_cached_series_causes_complete_field_refresh() -> None:
    cache = InMemoryResolvedInputCache(clock=lambda: NOW)
    short = FixtureAnnualFinancialFactsProvider(annual_series(range(2022, 2026)))
    seeded = _resolve(short, horizon=HistoricalHorizon.THREE_YEARS, cache=cache)
    assert seeded.status is CalculationStatus.OK

    full = FixtureAnnualFinancialFactsProvider(annual_series(range(2020, 2026)))
    refreshed = _resolve(full, cache=cache)
    assert refreshed.status is CalculationStatus.OK
    assert refreshed.selected_horizon_years == 5
    assert len(full.requests) == 4


def test_stale_cache_refreshes_all_fields() -> None:
    now = [NOW]
    cache = InMemoryResolvedInputCache(clock=lambda: now[0], ttl=timedelta(days=1))
    seed = FixtureAnnualFinancialFactsProvider(annual_series(range(2020, 2026)))
    result = resolve_annual_growth_series(
        policy=FCFEarningsGrowthPolicy(),
        subject_id="ACME",
        currency="USD",
        as_of=None,
        providers=_bindings(seed),
        cache=cache,
        clock=lambda: now[0],
    )
    assert result.status is CalculationStatus.OK
    now[0] += timedelta(days=2)
    refresh = FixtureAnnualFinancialFactsProvider(annual_series(range(2020, 2026)))
    result = resolve_annual_growth_series(
        policy=FCFEarningsGrowthPolicy(),
        subject_id="ACME",
        currency="USD",
        as_of=None,
        providers=_bindings(refresh),
        cache=cache,
        clock=lambda: now[0],
    )
    assert result.status is CalculationStatus.OK
    assert len(refresh.requests) == 4


def test_historical_boundary_excludes_later_restatement() -> None:
    boundary = datetime(2026, 2, 15, tzinfo=UTC)
    facts = list(annual_series(range(2020, 2026)))
    facts.append(
        annual_fact(
            FinancialField.EPS,
            2025,
            99.0,
            available_at=boundary + timedelta(days=1),
            provider_fact_id="future-restatement",
        )
    )
    provider = FixtureAnnualFinancialFactsProvider(tuple(facts))
    result = resolve_annual_growth_series(
        policy=FCFEarningsGrowthPolicy(),
        subject_id="ACME",
        currency="USD",
        as_of=boundary,
        providers=_bindings(provider),
        clock=lambda: NOW,
    )
    assert result.status is CalculationStatus.OK
    assert result.observations[-1].diluted_eps.value != 99.0


def test_non_calendar_fiscal_periods_are_contiguous() -> None:
    facts = []
    for fact in annual_series(range(2020, 2026)):
        assert fact.fiscal_year is not None
        facts.append(
            replace(
                fact,
                observation_period_start=datetime(fact.fiscal_year - 1, 10, 1, tzinfo=UTC),
                observation_period_end=datetime(fact.fiscal_year, 10, 1, tzinfo=UTC),
            )
        )
    result = _resolve(FixtureAnnualFinancialFactsProvider(tuple(facts)))
    assert result.status is CalculationStatus.OK
    assert result.selected_horizon_years == 5


def test_cache_schema_version_is_period_series_version() -> None:
    assert CACHE_SCHEMA_VERSION == 2


def test_derives_fcf_per_share_cagr_with_provenance() -> None:
    facts = list(annual_series(range(2020, 2026), fcf_values=(100.0, 110.0, 120.0, 130.0, 140.0, 150.0)))
    result = _resolve(FixtureAnnualFinancialFactsProvider(tuple(facts)))
    assert result.status is CalculationStatus.OK
    assert result.fcf_per_share_cagr.status is MetricStatus.OK
    assert result.fcf_per_share_cagr.value == pytest.approx(result.fcf_cagr.value)
    assert all(item.free_cash_flow_per_diluted_share is not None for item in result.observations)
    assert all(
        item.free_cash_flow_per_diluted_share is not None and item.free_cash_flow_per_diluted_share.lineage is not None
        for item in result.observations
    )


def test_selected_fcf_per_share_requires_share_evidence() -> None:
    facts = tuple(
        fact
        for fact in annual_series(range(2020, 2026))
        if fact.field_name is not FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES
    )
    provider = FixtureAnnualFinancialFactsProvider(facts)
    result = resolve_annual_growth_series(
        policy=FCFEarningsGrowthPolicy(classification_basis=FCFClassificationBasis.FCF_PER_SHARE),
        subject_id="ACME",
        currency="USD",
        as_of=None,
        providers=_bindings(provider),
        clock=lambda: NOW,
    )
    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.reason_code is ReasonCode.MISSING_FACT


@pytest.mark.parametrize(("subject", "currency"), [("", "USD"), ("ACME", "")])
def test_invalid_request_is_typed(subject: str, currency: str) -> None:
    provider = FixtureAnnualFinancialFactsProvider(())
    result = resolve_annual_growth_series(
        policy=FCFEarningsGrowthPolicy(),
        subject_id=subject,
        currency=currency,
        as_of=None,
        providers=_bindings(provider),
        clock=lambda: NOW,
    )
    assert result.status is CalculationStatus.INVALID_INPUT
    assert result.reason_code is ReasonCode.INVALID_REQUEST
