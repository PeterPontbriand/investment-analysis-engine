"""FCF/Earnings Growth availability boundary and series-cache eligibility (ESC-E.5).

Annual facts carry a precise ``available_at`` (the filing's acceptance time), so this resolver compares
it with the run's boundary exactly: a live run's boundary is ``executed_at`` and an ``--as-of`` run's is
the requested instant, and neither tolerates clock skew (unlike the Graham resolvers, whose quote and
fact timestamps come from fetches that complete after the clock is frozen). These tests pin that, and
the two cache paths a stored series can take: the shared eligibility check (which looks at
``available_at`` only for an ``--as-of`` key) and the resolver's own per-fact check (which covers a live
key).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

import pytest
from alembic.config import Config

from alembic import command
from src.analysis.strategy.fcf_earnings_growth.input_resolver import (
    CACHE_SCHEMA_VERSION,
    AnnualGrowthSeriesAssembly,
    FinancialFieldProvider,
    resolve_annual_growth_series,
)
from src.analysis.strategy.fcf_earnings_growth.models import FCFEarningsGrowthPolicy
from src.config import ProjectSettings
from src.core.analysis_status import CalculationStatus
from src.data.financial.cache import (
    InMemoryResolvedInputCache,
    ResolvedInputCacheEntry,
    ResolvedInputCacheKey,
    ResolvedInputSeriesCacheQuery,
)
from src.data.financial.facts import FinancialField
from src.data.financial.provenance import FinancialSubjectKind, ResolvedInput
from src.data.repositories import SQLiteDatabase, SQLiteResolvedInputCache
from src.evaluation.fixtures.fcf_earnings_growth import (
    PROVIDER_ID,
    FixtureAnnualFinancialFactsProvider,
    annual_fact,
    annual_series,
)

NOW = datetime(2026, 3, 1, tzinfo=UTC)
BOUNDARY = datetime(2026, 2, 15, tzinfo=UTC)
ONE_SECOND = timedelta(seconds=1)
RESTATED_EPS = 99.0
FIELDS = (
    FinancialField.OPERATING_CASH_FLOW,
    FinancialField.CAPITAL_EXPENDITURES,
    FinancialField.EPS,
    FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES,
)


class _SeriesCache(Protocol):
    def get_series(self, query: ResolvedInputSeriesCacheQuery) -> tuple[ResolvedInputCacheEntry, ...]: ...

    def put(self, key: ResolvedInputCacheKey, resolved_input: ResolvedInput) -> None: ...


@pytest.fixture
def database(tmp_path: Path) -> Iterator[SQLiteDatabase]:
    url = f"sqlite:///{(tmp_path / 'resolved.sqlite3').as_posix()}"
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        yield database
    finally:
        database.close()


@pytest.fixture(params=["memory", "sqlite"])
def cache(request: pytest.FixtureRequest, database: SQLiteDatabase) -> _SeriesCache:
    """The two production-shaped series caches, which share one eligibility check."""
    if request.param == "memory":
        return InMemoryResolvedInputCache(clock=lambda: NOW)
    return SQLiteResolvedInputCache(database, clock=lambda: NOW)


def _bindings(provider: FixtureAnnualFinancialFactsProvider) -> dict[FinancialField, FinancialFieldProvider]:
    return dict.fromkeys(FIELDS, FinancialFieldProvider(PROVIDER_ID, provider))


def _resolve(
    provider: FixtureAnnualFinancialFactsProvider,
    *,
    as_of: datetime | None,
    cache: _SeriesCache | None = None,
    clock: datetime = NOW,
) -> AnnualGrowthSeriesAssembly:
    return resolve_annual_growth_series(
        policy=FCFEarningsGrowthPolicy(),
        subject_id="ACME",
        currency="USD",
        as_of=as_of,
        effective_as_of=as_of or clock,
        providers=_bindings(provider),
        cache=cache,  # type: ignore[arg-type]
        clock=lambda: clock,
    )


def _with_restated_eps(available_at: datetime) -> FixtureAnnualFinancialFactsProvider:
    facts = [*annual_series(range(2020, 2026))]
    facts.append(
        annual_fact(FinancialField.EPS, 2025, RESTATED_EPS, available_at=available_at, provider_fact_id="restated")
    )
    return FixtureAnnualFinancialFactsProvider(tuple(facts))


def _latest_eps(result: AnnualGrowthSeriesAssembly) -> float | None:
    assert result.status is CalculationStatus.OK
    return result.observations[-1].diluted_eps.value


@pytest.mark.parametrize(
    ("boundary", "as_of"),
    [(NOW, None), (BOUNDARY, BOUNDARY)],
    ids=["live", "as-of"],
)
@pytest.mark.parametrize(
    ("offset", "admitted"),
    [
        (-ONE_SECOND, True),
        (timedelta(0), True),
        (ONE_SECOND, False),
        (timedelta(minutes=10), False),
        (timedelta(days=1), False),
    ],
)
def test_a_fact_is_admitted_only_when_available_at_or_before_the_boundary_with_no_skew(
    boundary: datetime, as_of: datetime | None, offset: timedelta, admitted: bool
) -> None:
    """A later restatement replaces the original only if it was available by the boundary, exactly."""
    result = _resolve(_with_restated_eps(boundary + offset), as_of=as_of)

    assert (_latest_eps(result) == RESTATED_EPS) is admitted


def _fill(cache: _SeriesCache, *, as_of: datetime | None, clock: datetime) -> FixtureAnnualFinancialFactsProvider:
    provider = FixtureAnnualFinancialFactsProvider(annual_series(range(2020, 2026)))
    assert _resolve(provider, as_of=as_of, cache=cache, clock=clock).status is CalculationStatus.OK
    return provider


def _shift_available_at(
    cache: _SeriesCache, field: FinancialField, *, as_of: datetime | None, available_at: datetime
) -> None:
    query = ResolvedInputSeriesCacheQuery(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="ACME",
        field_name=field.value,
        basis="fiscal_year",
        provider_id=PROVIDER_ID,
        analysis_as_of=as_of,
        schema_version=CACHE_SCHEMA_VERSION,
    )
    entries = cache.get_series(query)
    assert entries
    for entry in entries:
        cache.put(entry.key, replace(entry.resolved_input, available_at=available_at))


@pytest.mark.parametrize(
    ("offset", "reused"),
    [(timedelta(0), True), (ONE_SECOND, False), (timedelta(days=1), False)],
)
def test_an_as_of_series_is_reused_only_while_every_entry_was_available_by_the_boundary(
    cache: _SeriesCache, offset: timedelta, reused: bool
) -> None:
    """The shared eligibility check reads ``available_at`` for an ``--as-of`` key, with no skew."""
    _fill(cache, as_of=BOUNDARY, clock=NOW)
    _shift_available_at(cache, FinancialField.OPERATING_CASH_FLOW, as_of=BOUNDARY, available_at=BOUNDARY + offset)
    refreshed = FixtureAnnualFinancialFactsProvider(annual_series(range(2020, 2026)))

    result = _resolve(refreshed, as_of=BOUNDARY, cache=cache, clock=NOW)

    assert result.status is CalculationStatus.OK
    refreshed_fields = [request.field_name for request in refreshed.requests]
    assert refreshed_fields == ([] if reused else [FinancialField.OPERATING_CASH_FLOW])


@pytest.mark.parametrize(
    ("offset", "reused"),
    [(timedelta(0), True), (ONE_SECOND, False), (timedelta(days=1), False)],
)
def test_a_live_series_is_reused_only_while_every_entry_was_available_by_executed_at(
    cache: _SeriesCache, offset: timedelta, reused: bool
) -> None:
    """The shared check ignores ``available_at`` on a live key; the resolver's own per-fact check does not."""
    _fill(cache, as_of=None, clock=NOW)
    _shift_available_at(cache, FinancialField.OPERATING_CASH_FLOW, as_of=None, available_at=NOW + offset)
    refreshed = FixtureAnnualFinancialFactsProvider(annual_series(range(2020, 2026)))

    result = _resolve(refreshed, as_of=None, cache=cache, clock=NOW)

    assert result.status is CalculationStatus.OK
    refreshed_fields = [request.field_name for request in refreshed.requests]
    assert refreshed_fields == ([] if reused else [FinancialField.OPERATING_CASH_FLOW])


def test_a_series_cached_after_the_run_clock_is_still_eligible(cache: _SeriesCache) -> None:
    """The run's clock is frozen at ``executed_at``; entries written during the run are stamped later."""
    _fill(cache, as_of=None, clock=NOW)
    earlier_run = NOW - timedelta(hours=1)
    unused = FixtureAnnualFinancialFactsProvider(())

    result = _resolve(unused, as_of=None, cache=cache, clock=earlier_run)

    assert result.status is CalculationStatus.OK
    assert unused.requests == []


def test_a_live_run_and_an_as_of_run_never_share_a_series(cache: _SeriesCache) -> None:
    _fill(cache, as_of=None, clock=NOW)
    provider = FixtureAnnualFinancialFactsProvider(annual_series(range(2020, 2026)))

    result = _resolve(provider, as_of=BOUNDARY, cache=cache, clock=NOW)

    assert result.status is CalculationStatus.OK
    assert len(provider.requests) == len(FIELDS)
