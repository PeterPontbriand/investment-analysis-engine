"""FCF-Growth reads its annual series through the shared resolver entry and keeps its own cache around it."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.financial.cache import (
    InMemoryResolvedInputCache,
    ResolvedInputCacheKey,
    ResolvedInputSeriesCacheQuery,
)
from investment_analysis_engine.data.financial.facts import (
    FinancialFactRequest,
    FinancialFactsProvider,
    FinancialField,
    FinancialUnit,
    ProviderFact,
)
from investment_analysis_engine.data.financial.provenance import (
    AccountingScope,
    CapitalExpenditureSign,
    FinancialSubjectKind,
    PeriodKind,
    ResolvedInput,
    SourceKind,
)
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from investment_analysis_engine.evaluation.fixtures.fcf_earnings_growth import (
    RETRIEVED_AT,
    FixtureAnnualFinancialFactsProvider,
)
from investment_analysis_engine.strategies.fcf_growth.input_resolver import (
    CACHE_SCHEMA_VERSION,
    AnnualGrowthSeriesAssembly,
    resolve_annual_growth_series,
)
from investment_analysis_engine.strategies.fcf_growth.models import FCFEarningsGrowthPolicy
from tests._sec_labeled_annual import sec_annual_fact

NOW = datetime(2026, 3, 1, tzinfo=UTC)
YEARS = range(2020, 2026)
FIELDS = (
    FinancialField.OPERATING_CASH_FLOW,
    FinancialField.CAPITAL_EXPENDITURES,
    FinancialField.EPS,
    FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES,
)


def _value(field: FinancialField, year: int) -> float:
    index = year - YEARS.start
    return {
        FinancialField.OPERATING_CASH_FLOW: 100.0 + 10.0 * index,
        FinancialField.CAPITAL_EXPENDITURES: 20.0,
        FinancialField.EPS: 1.0 + 0.25 * index,
        FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES: 50.0,
    }[field]


def _facts() -> tuple[ProviderFact, ...]:
    return tuple(
        sec_annual_fact(
            field,
            year,
            _value(field, year),
            provider_fact_id=f"annual-{year}:{field.value}",
            capex_sign=(
                CapitalExpenditureSign.POSITIVE_EXPENDITURE if field is FinancialField.CAPITAL_EXPENDITURES else None
            ),
        )
        for year in YEARS
        for field in FIELDS
    )


def _stored(field: FinancialField, year: int) -> tuple[ResolvedInputCacheKey, ResolvedInput]:
    """Return one cache entry spelled out in the form FCF-Growth stored before it used the shared entry."""
    start, end = datetime(year - 1, 1, 1, tzinfo=UTC), datetime(year, 1, 1, tzinfo=UTC)
    units = {
        FinancialField.EPS: "currency_per_share",
        FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES: "shares",
    }.get(field, "currency")
    is_capex = field is FinancialField.CAPITAL_EXPENDITURES
    key = ResolvedInputCacheKey(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="ACME",
        field_name=field.value,
        basis="fiscal_year",
        provider_id=SEC_PROVIDER_ID,
        analysis_as_of=None,
        schema_version=3,
        observation_period_start=start,
        observation_period_end=end,
    )
    entry = ResolvedInput(
        field_name=field.value,
        value=_value(field, year),
        source_kind=SourceKind.PROVIDER,
        resolved_at=NOW,
        basis="fiscal_year",
        units=units,
        currency=None if field is FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES else "USD",
        provider_id=SEC_PROVIDER_ID,
        provider_field=f"fixture.{field.value}",
        observation_period_start=start,
        observation_period_end=end,
        available_at=datetime(year, 2, 1, tzinfo=UTC),
        as_of=None,
        retrieved_at=RETRIEVED_AT,
        notes=("Capital expenditure normalized from raw value 20.0.",) if is_capex else (),
        fiscal_year=year,
        period_kind=PeriodKind.COMPLETED_ANNUAL,
        accounting_scope=AccountingScope.CONSOLIDATED,
        capital_expenditure_sign=CapitalExpenditureSign.POSITIVE_EXPENDITURE if is_capex else None,
        provider_fact_id=f"annual-{year}:{field.value}",
    )
    return key, entry


class _ForbiddenProvider:
    """A provider that fails the test when asked for anything."""

    def fetch_facts(self, request: FinancialFactRequest, *, effective_as_of: datetime) -> tuple[ProviderFact, ...]:  # noqa: ARG002
        raise AssertionError(f"a cache hit must not fetch {request.field_name.value}")


class _AnswerProvider:
    """A provider that answers every field with its own facts plus the given extra fact for operating cash flow."""

    def __init__(self, extra: ProviderFact | None) -> None:
        self._extra = extra

    def fetch_facts(self, request: FinancialFactRequest, *, effective_as_of: datetime) -> tuple[ProviderFact, ...]:  # noqa: ARG002
        facts = tuple(fact for fact in _facts() if fact.field_name is request.field_name)
        if self._extra is not None and request.field_name is FinancialField.OPERATING_CASH_FLOW:
            return (*facts, self._extra)
        return facts


def _resolve(
    provider: FinancialFactsProvider, cache: InMemoryResolvedInputCache | None = None
) -> AnnualGrowthSeriesAssembly:
    return resolve_annual_growth_series(
        policy=FCFEarningsGrowthPolicy(),
        subject_id="ACME",
        currency="USD",
        as_of=None,
        effective_as_of=NOW,
        provider=provider,
        cache=cache,
        clock=lambda: NOW,
    )


def _series(cache: InMemoryResolvedInputCache, field: FinancialField, version: int) -> tuple[ResolvedInput, ...]:
    return tuple(
        entry.resolved_input
        for entry in cache.get_series(
            ResolvedInputSeriesCacheQuery(
                subject_kind=FinancialSubjectKind.SECURITY,
                subject_id="ACME",
                field_name=field.value,
                basis="fiscal_year",
                provider_id=SEC_PROVIDER_ID,
                analysis_as_of=None,
                schema_version=version,
            )
        )
    )


def test_an_entry_stored_before_the_shared_entry_is_reused_unchanged() -> None:
    cache = InMemoryResolvedInputCache(clock=lambda: NOW)
    for field in FIELDS:
        for year in YEARS:
            cache.put(*_stored(field, year))
    result = _resolve(_ForbiddenProvider(), cache)
    assert result.status is CalculationStatus.OK
    assert [item.fiscal_year for item in result.observations] == list(YEARS)
    assert CACHE_SCHEMA_VERSION == 3
    reused = {
        FinancialField.OPERATING_CASH_FLOW: [item.operating_cash_flow for item in result.observations],
        FinancialField.CAPITAL_EXPENDITURES: [item.normalized_capital_expenditures for item in result.observations],
        FinancialField.EPS: [item.diluted_eps for item in result.observations],
    }
    for field, inputs in reused.items():
        expected = [
            replace(
                _stored(field, year)[1],
                source_kind=SourceKind.CACHE,
                origin_source_kind=SourceKind.PROVIDER,
                cache_schema_version=3,
            )
            for year in YEARS
        ]
        assert inputs == expected
    for field in FIELDS:
        assert _series(cache, field, 3) == tuple(_stored(field, year)[1] for year in YEARS)


def test_a_miss_fetches_each_field_once_and_stores_the_entries_in_the_stored_form() -> None:
    cache = InMemoryResolvedInputCache(clock=lambda: NOW)
    provider = FixtureAnnualFinancialFactsProvider(_facts())
    assert _resolve(provider, cache).status is CalculationStatus.OK
    assert [request.field_name for request in provider.requests] == list(FIELDS)
    for field in FIELDS:
        assert _series(cache, field, 3) == tuple(_stored(field, year)[1] for year in YEARS)
    provider.requests.clear()
    assert _resolve(provider, cache).status is CalculationStatus.OK
    assert provider.requests == []


def test_an_entry_under_another_schema_version_is_refused_and_fetched_again() -> None:
    cache = InMemoryResolvedInputCache(clock=lambda: NOW)
    for field in FIELDS:
        for year in YEARS:
            key, entry = _stored(field, year)
            cache.put(replace(key, schema_version=2), entry)
    provider = FixtureAnnualFinancialFactsProvider(_facts())
    assert _resolve(provider, cache).status is CalculationStatus.OK
    assert [request.field_name for request in provider.requests] == list(FIELDS)
    assert _series(cache, FinancialField.OPERATING_CASH_FLOW, 3) == tuple(
        _stored(FinancialField.OPERATING_CASH_FLOW, year)[1] for year in YEARS
    )


def _another_subject(fact: ProviderFact) -> ProviderFact:
    return replace(fact, subject_id="OTHER")


def _another_field(fact: ProviderFact) -> ProviderFact:
    return replace(fact, field_name=FinancialField.EPS, units=FinancialUnit.CURRENCY_PER_SHARE)


def _another_basis(fact: ProviderFact) -> ProviderFact:
    return replace(fact, basis="fiscal_year_end")


def _not_annual(fact: ProviderFact) -> ProviderFact:
    return replace(fact, period_kind=PeriodKind.QUARTERLY, fiscal_year=None)


def _unbounded(fact: ProviderFact) -> ProviderFact:
    return replace(fact, observation_period_start=None)


@pytest.mark.parametrize(
    "corrupt",
    [_another_subject, _another_field, _another_basis, _not_annual, _unbounded],
    ids=["subject", "field", "basis", "period_kind", "period_bounds"],
)
def test_an_incoherent_answer_is_a_provider_error_as_a_whole(corrupt: Callable[[ProviderFact], ProviderFact]) -> None:
    extra = corrupt(sec_annual_fact(FinancialField.OPERATING_CASH_FLOW, 2019, 90.0))
    result = _resolve(_AnswerProvider(extra))
    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert result.reason_code is ReasonCode.PROVIDER_ERROR
    assert result.provider_failure is not None
    assert result.provider_failure.kind is ProviderFailureKind.UNEXPECTED_RESPONSE
    assert result.observations == ()


def test_a_coherent_answer_with_the_same_facts_resolves() -> None:
    assert _resolve(_AnswerProvider(None)).status is CalculationStatus.OK
