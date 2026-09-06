"""Shared series-cache and annual resolver contracts for memory and SQLite."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from alembic.config import Config

from alembic import command
from src.analysis.fcf_earnings_growth.input_resolver import (
    AnnualGrowthSeriesAssembly,
    FinancialFieldProvider,
    resolve_annual_growth_series,
)
from src.analysis.fcf_earnings_growth.models import FCFEarningsGrowthPolicy, HistoricalHorizon
from src.config import ProjectSettings
from src.core.analysis_status import CalculationStatus
from src.data.financial.cache import (
    InMemoryResolvedInputCache,
    ResolvedInputCacheEntry,
    ResolvedInputCacheKey,
    ResolvedInputSeriesCacheProtocol,
    ResolvedInputSeriesCacheQuery,
)
from src.data.financial.facts import FinancialField
from src.data.financial.provenance import FinancialSubjectKind, ResolvedInput, SourceKind
from src.data.repositories import SQLiteDatabase, SQLiteResolvedInputCache
from src.evaluation.fixtures.fcf_earnings_growth import (
    PROVIDER_ID,
    FixtureAnnualFinancialFactsProvider,
    annual_series,
)

NOW = datetime(2026, 3, 1, tzinfo=UTC)
CacheFactory = Callable[[timedelta | None], ResolvedInputSeriesCacheProtocol]


@dataclass
class Clock:
    now: datetime = NOW

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture(params=["memory", "sqlite"])
def cache_factory(request: pytest.FixtureRequest, tmp_path: Path, clock: Clock) -> Iterator[CacheFactory]:
    if request.param == "memory":
        yield lambda ttl: InMemoryResolvedInputCache(clock=clock, ttl=ttl)
        return
    url = f"sqlite:///{(tmp_path / 'series.sqlite3').as_posix()}"
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        yield lambda ttl: SQLiteResolvedInputCache(database, clock=clock, ttl=ttl)
    finally:
        database.close()


def key_for(year: int) -> ResolvedInputCacheKey:
    return ResolvedInputCacheKey(
        FinancialSubjectKind.SECURITY,
        "ACME",
        "eps",
        None,
        "fixture",
        None,
        2,
        datetime(year, 1, 1, tzinfo=UTC),
        datetime(year, 12, 31, tzinfo=UTC),
    )


def query_for(key: ResolvedInputCacheKey) -> ResolvedInputSeriesCacheQuery:
    return ResolvedInputSeriesCacheQuery(
        key.subject_kind,
        key.subject_id,
        key.field_name,
        key.basis,
        key.analysis_as_of,
        key.schema_version,
        key.provider_id,
    )


def fact_for(key: ResolvedInputCacheKey) -> ResolvedInput:
    return ResolvedInput(
        field_name=key.field_name,
        value=0,
        source_kind=SourceKind.PROVIDER,
        resolved_at=NOW,
        basis=key.basis,
        provider_id=key.provider_id,
        as_of=key.analysis_as_of,
        observation_period_start=key.observation_period_start,
        observation_period_end=key.observation_period_end,
        available_at=NOW - timedelta(days=1),
        notes=("Original provider fact",),
    )


def test_order_gaps_unscoped_exclusion_and_scalar_preservation(cache_factory: CacheFactory) -> None:
    cache = cache_factory(None)
    assert isinstance(cache, ResolvedInputSeriesCacheProtocol)
    first = key_for(2021)
    second = key_for(2024)
    third = replace(second, observation_period_start=datetime(2024, 6, 1, tzinfo=UTC))
    unscoped = replace(first, observation_period_start=None, observation_period_end=None)
    for key in (third, unscoped, second, first):
        cache.put(key, fact_for(key))
    expected = tuple(ResolvedInputCacheEntry(key, fact_for(key), NOW) for key in (first, second, third))
    assert cache.get_series(query_for(first)) == expected
    assert cache.get(unscoped) == ResolvedInputCacheEntry(unscoped, fact_for(unscoped), NOW)
    assert [item.resolved_input.value for item in expected] == [0, 0, 0]
    assert cache.get_series(replace(query_for(first), subject_id="MISSING")) == ()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("subject_kind", FinancialSubjectKind.MACRO),
        ("subject_id", "OTHER"),
        ("field_name", "other"),
        ("basis", "null"),
        ("provider_id", "other"),
        ("analysis_as_of", NOW),
        ("schema_version", 1),
    ],
)
def test_all_query_identity_fields_match(cache_factory: CacheFactory, field: str, value: object) -> None:
    cache = cache_factory(None)
    key = key_for(2024)
    cache.put(key, fact_for(key))
    changes: dict[str, Any] = {field: value}
    assert cache.get_series(replace(query_for(key), **changes)) == ()


def test_normalization_offsets_and_macro_case(cache_factory: CacheFactory) -> None:
    cache = cache_factory(None)
    key = replace(key_for(2024), basis=" annual ", analysis_as_of=NOW)
    cache.put(key, fact_for(key))
    query = replace(
        query_for(key),
        subject_id=" acme ",
        field_name=" eps ",
        provider_id=" FIXTURE ",
        basis=" annual ",
        analysis_as_of=NOW.astimezone(timezone(timedelta(hours=-4))),
    )
    assert cache.get_series(query) == (ResolvedInputCacheEntry(key, fact_for(key), NOW),)
    macro = replace(key, subject_kind=FinancialSubjectKind.MACRO, subject_id="MacroCase")
    cache.put(macro, fact_for(macro))
    assert len(cache.get_series(query_for(macro))) == 1
    assert cache.get_series(replace(query_for(macro), subject_id="MACROCASE")) == ()


@pytest.mark.parametrize(
    "case",
    [(None, 100, True), (10, 10, True), (10, 10.000001, False), (0, 0, True), (0, 0.000001, False), (0, -1, True)],
)
def test_ttl_contract(cache_factory: CacheFactory, clock: Clock, case: tuple[int | None, float, bool]) -> None:
    seconds, age, hit = case
    cache = cache_factory(None if seconds is None else timedelta(seconds=seconds))
    key = key_for(2024)
    cache.put(key, fact_for(key))
    clock.now += timedelta(seconds=age)
    expected = (ResolvedInputCacheEntry(key, fact_for(key), NOW),) if hit else ()
    assert cache.get_series(query_for(key)) == expected
    assert (cache.get(key) is not None) is hit
    # Stale reads must not delete the stored fact.
    clock.now = NOW
    assert len(cache.get_series(query_for(key))) == 1


def test_each_entry_has_its_own_age(cache_factory: CacheFactory, clock: Clock) -> None:
    cache = cache_factory(timedelta(seconds=10))
    old = key_for(2023)
    fresh = key_for(2024)
    cache.put(old, fact_for(old))
    clock.now += timedelta(seconds=5)
    cache.put(fresh, fact_for(fresh))
    clock.now += timedelta(seconds=6)
    assert cache.get_series(query_for(old)) == (
        ResolvedInputCacheEntry(fresh, fact_for(fresh), NOW + timedelta(seconds=5)),
    )


@pytest.mark.parametrize("available", [None, NOW, NOW + timedelta(microseconds=1)])
def test_historical_eligibility(cache_factory: CacheFactory, available: datetime | None) -> None:
    cache = cache_factory(None)
    historical = replace(key_for(2024), analysis_as_of=NOW)
    fact = replace(fact_for(historical), available_at=available)
    cache.put(historical, fact)
    cache.put(key_for(2024), fact_for(key_for(2024)))
    expected = (ResolvedInputCacheEntry(historical, fact, NOW),) if available == NOW else ()
    assert cache.get_series(query_for(historical)) == expected
    assert len(cache.get_series(query_for(key_for(2024)))) == 1


def test_replacement_changes_series_without_duplicates(cache_factory: CacheFactory, clock: Clock) -> None:
    cache = cache_factory(None)
    key = key_for(2024)
    cache.put(key, fact_for(key))
    clock.now += timedelta(seconds=1)
    updated = replace(fact_for(key), value=7, provider_fact_id="restated")
    cache.put(key, updated)
    assert cache.get_series(query_for(key)) == (ResolvedInputCacheEntry(key, updated, clock.now),)


def test_naive_clock_fails_when_used(cache_factory: CacheFactory, clock: Clock) -> None:
    cache = cache_factory(timedelta(seconds=10))
    key = key_for(2024)
    cache.put(key, fact_for(key))
    clock.now = NOW.replace(tzinfo=None)
    with pytest.raises(ValueError, match="naive|timezone-aware"):
        cache.get_series(query_for(key))


def resolve(
    provider: FixtureAnnualFinancialFactsProvider,
    cache: ResolvedInputSeriesCacheProtocol,
    clock: Clock,
    horizon: HistoricalHorizon = HistoricalHorizon.LONGEST_AVAILABLE,
) -> AnnualGrowthSeriesAssembly:
    fields = (
        FinancialField.OPERATING_CASH_FLOW,
        FinancialField.CAPITAL_EXPENDITURES,
        FinancialField.EPS,
        FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES,
    )
    return resolve_annual_growth_series(
        policy=FCFEarningsGrowthPolicy(historical_horizon=horizon),
        subject_id="ACME",
        currency="USD",
        as_of=None,
        providers=dict.fromkeys(fields, FinancialFieldProvider(PROVIDER_ID, provider)),
        cache=cache,
        clock=clock,
    )


@pytest.mark.parametrize("scenario", ["hit", "partial", "stale"])
def test_annual_resolver_uses_both_cache_implementations(
    cache_factory: CacheFactory, clock: Clock, scenario: str
) -> None:
    cache = cache_factory(timedelta(seconds=10))
    partial = scenario == "partial"
    seed = FixtureAnnualFinancialFactsProvider(annual_series(range(2022 if partial else 2020, 2026)))
    initial = resolve(seed, cache, clock, HistoricalHorizon.THREE_YEARS if partial else HistoricalHorizon.FIVE_YEARS)
    assert initial.status is CalculationStatus.OK
    assert len(seed.requests) == 4
    if scenario == "stale":
        clock.now += timedelta(seconds=11)
    provider = FixtureAnnualFinancialFactsProvider(() if scenario == "hit" else annual_series(range(2020, 2026)))
    result = resolve(provider, cache, clock)
    assert result.status is CalculationStatus.OK
    assert result.selected_horizon_years == 5
    assert [item.fiscal_year for item in result.observations] == list(range(2020, 2026))
    assert len(provider.requests) == (0 if scenario == "hit" else 4)
    if scenario == "hit":
        assert result.fcf_cagr == initial.fcf_cagr
        assert result.eps_cagr == initial.eps_cagr
