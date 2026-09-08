"""Verify durable scalar cache identity, provenance, replacement, and eligibility."""

import json
from collections.abc import Iterator
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from alembic.config import Config
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError, OperationalError

from alembic import command
from src.config import ProjectSettings
from src.data.financial.cache import (
    InMemoryResolvedInputCache,
    ResolvedInputCacheEntry,
    ResolvedInputCacheKey,
    ResolvedInputCacheProtocol,
    ResolvedInputSeriesCacheQuery,
)
from src.data.financial.provenance import (
    AccountingScope,
    CapitalExpenditureSign,
    ComponentLineage,
    FinancialSubjectKind,
    PeriodKind,
    ResolvedInput,
    SourceKind,
)
from src.data.repositories import SQLiteDatabase, SQLiteResolvedInputCache
from src.data.repositories.schema import resolved_input_cache, schema_metadata

NOW = datetime(2026, 9, 5, 12, 0, 0, 123456, tzinfo=UTC)
START = datetime(2025, 1, 1, tzinfo=UTC)
END = datetime(2025, 12, 31, tzinfo=UTC)


def test_list_keys_pages_preserve_full_identity(
    database: SQLiteDatabase, key: ResolvedInputCacheKey, fact: ResolvedInput
) -> None:
    cache = SQLiteResolvedInputCache(database, clock=lambda: NOW)
    assert cache.list_keys(limit=2) == ()
    keys = (
        replace(key, subject_kind=FinancialSubjectKind.MACRO, subject_id="macroCase", basis=None),
        replace(key, analysis_as_of=NOW, observation_period_start=START, observation_period_end=END),
        key,
    )
    for item in reversed(keys):
        cache.put(item, replace(fact, as_of=item.analysis_as_of, basis=item.basis))
    assert cache.list_keys(limit=2) == keys[:2]
    assert cache.list_keys(limit=2, offset=2) == keys[2:]
    assert cache.list_keys(limit=1, offset=1) == keys[1:2]
    assert cache.list_keys(limit=2, offset=3) == ()


@pytest.mark.parametrize(
    ("limit", "offset"), [(0, 0), (-1, 0), (True, 0), (1.5, 0), (None, 0), (1, -1), (1, False), (1, 0.5)]
)
def test_list_keys_rejects_invalid_bounds_before_io(tmp_path: Path, limit: Any, offset: Any) -> None:
    path = tmp_path / "not-created.sqlite3"
    database = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{path.as_posix()}"))
    try:
        with pytest.raises(ValueError, match="limit|offset"):
            SQLiteResolvedInputCache(database).list_keys(limit=limit, offset=offset)
        assert not path.exists()
    finally:
        database.close()


@pytest.mark.parametrize("version", [None, 2])
def test_inspection_requires_encoding(
    database: SQLiteDatabase, key: ResolvedInputCacheKey, version: int | None
) -> None:
    with database.transaction() as connection:
        if version is None:
            connection.execute(delete(schema_metadata))
        else:
            connection.execute(update(schema_metadata).values(metadata_value=version))
    cache = SQLiteResolvedInputCache(database)
    with pytest.raises(ValueError, match="encoding version"):
        cache.list_keys(limit=1)
    with pytest.raises(ValueError, match="encoding version"):
        cache.inspect(key)


@pytest.mark.parametrize(("column", "value"), [("subject_id", "other"), ("analysis_as_of", "not-a-date")])
def test_list_keys_rejects_malformed_selected_keys(
    database: SQLiteDatabase, key: ResolvedInputCacheKey, fact: ResolvedInput, column: str, value: str
) -> None:
    cache = SQLiteResolvedInputCache(database)
    cache.put(key, fact)
    with database.transaction() as connection:
        connection.exec_driver_sql("PRAGMA ignore_check_constraints = ON")
        connection.execute(update(resolved_input_cache).values(**{column: value}))
    with pytest.raises(ValueError, match="Malformed|validation error"):
        cache.list_keys(limit=1)


@pytest.mark.parametrize(("column", "value"), [("notes_json", "{}"), ("value", float("inf")), ("subject_id", "OTHER")])
def test_inspect_rejects_corrupt_storage(
    database: SQLiteDatabase, key: ResolvedInputCacheKey, fact: ResolvedInput, column: str, value: object
) -> None:
    cache = SQLiteResolvedInputCache(database)
    cache.put(key, fact)
    with database.transaction() as connection:
        connection.execute(update(resolved_input_cache).values(**{column: value}))
    with pytest.raises(ValueError, match="Malformed|validation error"):
        cache.inspect(key)


def test_inspection_preserves_ineligible_entries_and_never_uses_clock(
    database: SQLiteDatabase, key: ResolvedInputCacheKey, fact: ResolvedInput
) -> None:
    historical = replace(key, analysis_as_of=NOW, observation_period_start=START, observation_period_end=END)
    late_fact = replace(fact, as_of=NOW, available_at=NOW + timedelta(days=1))
    writer = SQLiteResolvedInputCache(database, clock=lambda: NOW)
    writer.put(key, fact)
    writer.put(historical, late_fact)
    stale = SQLiteResolvedInputCache(database, clock=lambda: NOW + timedelta(days=1), ttl=timedelta(seconds=1))
    assert stale.get(key) is None
    assert stale.get(historical) is None
    assert (
        stale.get_series(
            ResolvedInputSeriesCacheQuery(
                historical.subject_kind,
                historical.subject_id,
                historical.field_name,
                historical.basis,
                historical.analysis_as_of,
                historical.schema_version,
                historical.provider_id,
            )
        )
        == ()
    )

    def forbidden_clock() -> datetime:
        pytest.fail("Inspection must not consult freshness or write timestamps")

    inspector = SQLiteResolvedInputCache(database, clock=forbidden_clock, ttl=timedelta(0))
    with database.read() as connection:
        before = connection.execute(select(resolved_input_cache)).all()
    assert inspector.list_keys(limit=10) == (historical, key)
    assert inspector.inspect(key) == ResolvedInputCacheEntry(key, fact, NOW)
    assert inspector.inspect(historical) == ResolvedInputCacheEntry(historical, late_fact, NOW)
    assert inspector.inspect(replace(key, subject_id="MISSING")) is None
    with database.read() as connection:
        assert connection.execute(select(resolved_input_cache)).all() == before


def test_list_keys_does_not_decode_payload(
    database: SQLiteDatabase, key: ResolvedInputCacheKey, fact: ResolvedInput
) -> None:
    cache = SQLiteResolvedInputCache(database)
    cache.put(key, fact)
    with database.transaction() as connection:
        connection.execute(update(resolved_input_cache).values(notes_json="{}"))
    assert cache.list_keys(limit=1) == (key,)
    with pytest.raises(ValueError, match="Malformed|validation error"):
        cache.inspect(key)


def test_inspect_revalidates_key_before_io(tmp_path: Path, key: ResolvedInputCacheKey) -> None:
    object.__setattr__(key, "analysis_as_of", NOW.replace(tzinfo=None))
    path = tmp_path / "not-created.sqlite3"
    database = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{path.as_posix()}"))
    try:
        with pytest.raises(ValueError, match="timezone-aware"):
            SQLiteResolvedInputCache(database).inspect(key)
        assert not path.exists()
    finally:
        database.close()


@pytest.fixture
def database(tmp_path: Path) -> Iterator[SQLiteDatabase]:
    url = f"sqlite:///{(tmp_path / 'cache.sqlite3').as_posix()}"
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    database = SQLiteDatabase(ProjectSettings(database_url=url))
    try:
        yield database
    finally:
        database.close()


@pytest.fixture
def key() -> ResolvedInputCacheKey:
    return ResolvedInputCacheKey(
        FinancialSubjectKind.SECURITY, " aapl ", "capital_expenditures", "annual", " FIXTURE ", None, 1
    )


@pytest.fixture
def fact() -> ResolvedInput:
    return ResolvedInput(
        field_name="capital_expenditures",
        value=-123.5,
        source_kind=SourceKind.PROVIDER,
        resolved_at=NOW,
        basis="annual",
        units="USD",
        currency="USD",
        provider_id=" Fixture ",
        provider_field="capex",
        observation_period_start=START,
        observation_period_end=END,
        observed_at=END,
        available_at=NOW - timedelta(days=1),
        retrieved_at=NOW - timedelta(hours=1),
        notes=("évidence", "second note"),
        fiscal_year=2025,
        period_kind=PeriodKind.COMPLETED_ANNUAL,
        accounting_scope=AccountingScope.CONSOLIDATED,
        capital_expenditure_sign=CapitalExpenditureSign.NEGATIVE_CASH_OUTFLOW,
        provider_fact_id=" fact-1 ",
    )


def test_complete_provider_round_trip_and_reopen(
    database: SQLiteDatabase, key: ResolvedInputCacheKey, fact: ResolvedInput, tmp_path: Path
) -> None:
    cache: ResolvedInputCacheProtocol = SQLiteResolvedInputCache(database, clock=lambda: NOW)
    assert cache.get(key) is None
    cache.put(key, fact)
    assert cache.get(key) == ResolvedInputCacheEntry(key, fact, NOW)
    database.close()
    reopened = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{(tmp_path / 'cache.sqlite3').as_posix()}"))
    try:
        assert SQLiteResolvedInputCache(reopened).get(key) == ResolvedInputCacheEntry(key, fact, NOW)
    finally:
        reopened.close()


def test_recursive_lineage_preserves_all_fields(
    database: SQLiteDatabase, key: ResolvedInputCacheKey, fact: ResolvedInput
) -> None:
    override = replace(fact, source_kind=SourceKind.OVERRIDE, provider_id=None, provider_field=None)
    cached = replace(fact, source_kind=SourceKind.CACHE, origin_source_kind=SourceKind.PROVIDER, cache_schema_version=3)
    nested = replace(
        fact,
        source_kind=SourceKind.DERIVED,
        provider_id="Other Provider",
        lineage=ComponentLineage("combine", (override, cached)),
    )
    cached_derived = replace(
        nested, source_kind=SourceKind.CACHE, origin_source_kind=SourceKind.DERIVED, cache_schema_version=4
    )
    derived = replace(nested, provider_id=None, lineage=ComponentLineage("nested transform", (cached_derived,)))
    cache = SQLiteResolvedInputCache(database, clock=lambda: NOW)
    cache.put(key, derived)
    assert cache.get(key) == ResolvedInputCacheEntry(key, derived, NOW)
    with database.read() as connection:
        encoded = connection.execute(select(resolved_input_cache.c.lineage_json)).scalar_one()
    component = json.loads(encoded)["components"][0]
    assert set(component) == set(asdict(fact))
    assert component["origin_source_kind"] == "derived"
    assert component["cache_schema_version"] == 4
    assert component["resolved_at"] == "2026-09-05T12:00:00.123456Z"


def test_normalized_key_and_utc_identity(
    database: SQLiteDatabase, key: ResolvedInputCacheKey, fact: ResolvedInput
) -> None:
    historical = replace(key, analysis_as_of=NOW, observation_period_start=START, observation_period_end=END)
    fact = replace(fact, as_of=NOW)
    cache = SQLiteResolvedInputCache(database, clock=lambda: NOW)
    cache.put(historical, fact)
    offset = timezone(timedelta(hours=-4))
    equivalent = replace(
        historical,
        subject_id=" aApL ",
        provider_id=" FIXTURE ",
        analysis_as_of=NOW.astimezone(offset),
        observation_period_start=START.astimezone(offset),
    )
    assert cache.get(equivalent) == ResolvedInputCacheEntry(historical, fact, NOW)
    with database.read() as connection:
        encoded = connection.execute(select(resolved_input_cache.c.cache_key)).scalar_one()
    assert json.loads(encoded) == [
        "security",
        "AAPL",
        "capital_expenditures",
        "annual",
        "fixture",
        "2026-09-05T12:00:00.123456Z",
        1,
        "2025-01-01T00:00:00.000000Z",
        "2025-12-31T00:00:00.000000Z",
    ]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("subject_kind", FinancialSubjectKind.MACRO),
        ("subject_id", "OTHER"),
        ("field_name", "eps"),
        ("basis", None),
        ("provider_id", "other"),
        ("analysis_as_of", NOW),
        ("schema_version", 2),
    ],
)
def test_key_dimensions_do_not_collide(
    database: SQLiteDatabase, key: ResolvedInputCacheKey, fact: ResolvedInput, field: str, value: object
) -> None:
    cache = SQLiteResolvedInputCache(database, clock=lambda: NOW)
    cache.put(key, fact)
    changes: dict[str, Any] = {field: value}
    assert cache.get(replace(key, **changes)) is None


def test_period_identity_and_macro_case(
    database: SQLiteDatabase, key: ResolvedInputCacheKey, fact: ResolvedInput
) -> None:
    cache = SQLiteResolvedInputCache(database, clock=lambda: NOW)
    scoped = replace(
        key,
        subject_kind=FinancialSubjectKind.MACRO,
        subject_id="macroCase",
        observation_period_start=START,
        observation_period_end=END,
    )
    cache.put(scoped, fact)
    assert cache.get(replace(scoped, subject_id="MACROCASE")) is None
    assert cache.get(replace(scoped, observation_period_start=None, observation_period_end=None)) is None
    assert cache.get(replace(scoped, observation_period_start=START + timedelta(days=1))) is None
    assert cache.get(replace(scoped, observation_period_end=END + timedelta(days=1))) is None


def test_current_and_historical_entries_coexist(
    database: SQLiteDatabase, key: ResolvedInputCacheKey, fact: ResolvedInput
) -> None:
    cache = SQLiteResolvedInputCache(database, clock=lambda: NOW)
    historical = replace(key, analysis_as_of=NOW)
    historical_fact = replace(fact, as_of=NOW, value=7)
    cache.put(key, fact)
    cache.put(historical, historical_fact)
    assert cache.get(key) == ResolvedInputCacheEntry(key, fact, NOW)
    assert cache.get(historical) == ResolvedInputCacheEntry(historical, historical_fact, NOW)


def test_replacement_refreshes_time_and_clears_old_fields(
    database: SQLiteDatabase, key: ResolvedInputCacheKey, fact: ResolvedInput
) -> None:
    now = NOW
    cache = SQLiteResolvedInputCache(database, clock=lambda: now)
    cache.put(key, fact)
    now += timedelta(seconds=1)
    cache.put(key, fact)
    assert cache.get(key) == ResolvedInputCacheEntry(key, fact, now)
    minimal = ResolvedInput(
        field_name=key.field_name,
        value=0,
        source_kind=SourceKind.PROVIDER,
        resolved_at=NOW,
        basis=key.basis,
        provider_id=key.provider_id,
    )
    cache.put(key, minimal)
    assert cache.get(key) == ResolvedInputCacheEntry(key, minimal, now)
    with database.read() as connection:
        assert len(connection.execute(select(resolved_input_cache)).all()) == 1


@pytest.mark.parametrize(
    "case",
    [
        (None, 1000, True),
        (10, 10, True),
        (10, 10.000001, False),
        (0, 0, True),
        (0, 0.000001, False),
        (0, -1, True),
    ],
)
def test_ttl_matches_memory_without_deleting(
    database: SQLiteDatabase,
    key: ResolvedInputCacheKey,
    fact: ResolvedInput,
    case: tuple[int | None, float, bool],
) -> None:
    ttl, age, hit = case
    now = NOW
    lifetime = None if ttl is None else timedelta(seconds=ttl)
    cache = SQLiteResolvedInputCache(database, clock=lambda: now, ttl=lifetime)
    memory = InMemoryResolvedInputCache(clock=lambda: now, ttl=lifetime)
    assert cache.ttl == lifetime
    cache.put(key, fact)
    memory.put(key, fact)
    now += timedelta(seconds=age)
    assert cache.get(key) == memory.get(key)
    assert (cache.get(key) is not None) is hit
    assert SQLiteResolvedInputCache(database).get(key) is not None


@pytest.mark.parametrize("available", [None, NOW - timedelta(seconds=1), NOW, NOW + timedelta(microseconds=1)])
def test_historical_availability_matches_memory(
    database: SQLiteDatabase, key: ResolvedInputCacheKey, fact: ResolvedInput, available: datetime | None
) -> None:
    key = replace(key, analysis_as_of=NOW)
    fact = replace(fact, as_of=NOW, available_at=available)
    cache = SQLiteResolvedInputCache(database, clock=lambda: NOW)
    memory = InMemoryResolvedInputCache(clock=lambda: NOW)
    cache.put(key, fact)
    memory.put(key, fact)
    assert cache.get(key) == memory.get(key)
    assert (cache.get(key) is not None) is (available is not None and available <= NOW)


@pytest.mark.parametrize("source", [SourceKind.OVERRIDE, SourceKind.CACHE])
def test_reject_noncacheable_roots(
    database: SQLiteDatabase, key: ResolvedInputCacheKey, fact: ResolvedInput, source: SourceKind
) -> None:
    invalid = (
        replace(fact, source_kind=source, provider_id=None, provider_field=None)
        if source is SourceKind.OVERRIDE
        else replace(fact, source_kind=source, origin_source_kind=SourceKind.PROVIDER, cache_schema_version=1)
    )
    cache = SQLiteResolvedInputCache(database, clock=lambda: NOW)
    with pytest.raises(ValueError, match="source_kind"):
        cache.put(key, invalid)
    assert cache.get(key) is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("field_name", "other"),
        ("basis", None),
        ("provider_id", "other"),
        ("as_of", NOW),
    ],
)
def test_incoherent_replacement_preserves_previous_row(
    database: SQLiteDatabase, key: ResolvedInputCacheKey, fact: ResolvedInput, field: str, value: object
) -> None:
    cache = SQLiteResolvedInputCache(database, clock=lambda: NOW)
    cache.put(key, fact)
    changes: dict[str, Any] = {field: value}
    changed = replace(fact, capital_expenditure_sign=None, **changes)
    with pytest.raises(ValueError, match="does not match"):
        cache.put(key, changed)
    assert cache.get(key) == ResolvedInputCacheEntry(key, fact, NOW)


def test_invalid_clock_and_negative_ttl(
    database: SQLiteDatabase, key: ResolvedInputCacheKey, fact: ResolvedInput
) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        SQLiteResolvedInputCache(database, ttl=timedelta(seconds=-1))
    now = NOW
    cache = SQLiteResolvedInputCache(database, clock=lambda: now, ttl=timedelta(seconds=1))
    cache.put(key, fact)
    now = NOW.replace(tzinfo=None)
    with pytest.raises(ValueError, match="timezone-aware"):
        cache.put(key, fact)
    with pytest.raises(ValueError, match="timezone-aware"):
        cache.get(key)
    assert SQLiteResolvedInputCache(database, clock=lambda: now).get(key) is not None


@pytest.mark.parametrize("nested", [False, True])
def test_nonfinite_values_are_revalidated(
    database: SQLiteDatabase, key: ResolvedInputCacheKey, fact: ResolvedInput, nested: bool
) -> None:
    invalid = replace(fact)
    object.__setattr__(invalid, "value", float("inf"))
    if nested:
        invalid = replace(fact, source_kind=SourceKind.DERIVED, lineage=ComponentLineage("invalid", (invalid,)))
    cache = SQLiteResolvedInputCache(database, clock=lambda: NOW)
    with pytest.raises(ValueError, match="finite"):
        cache.put(key, invalid)
    assert cache.get(key) is None


def test_failed_upsert_rolls_back(database: SQLiteDatabase, key: ResolvedInputCacheKey, fact: ResolvedInput) -> None:
    cache = SQLiteResolvedInputCache(database, clock=lambda: NOW)
    cache.put(key, fact)
    with database.transaction() as connection:
        connection.exec_driver_sql(
            "CREATE TRIGGER reject_cache_update AFTER UPDATE ON resolved_input_cache "
            "BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END"
        )
    with pytest.raises(IntegrityError, match="synthetic failure"):
        cache.put(key, replace(fact, value=42))
    assert cache.get(key) == ResolvedInputCacheEntry(key, fact, NOW)


@pytest.mark.parametrize("version", [None, 2])
def test_encoding_version_is_required(
    database: SQLiteDatabase, key: ResolvedInputCacheKey, fact: ResolvedInput, version: int | None
) -> None:
    with database.transaction() as connection:
        if version is None:
            connection.execute(delete(schema_metadata))
        else:
            connection.execute(update(schema_metadata).values(metadata_value=version))
    cache = SQLiteResolvedInputCache(database)
    with pytest.raises(ValueError, match="encoding version"):
        cache.get(key)
    with pytest.raises(ValueError, match="encoding version"):
        cache.put(key, fact)
    with database.read() as connection:
        assert connection.execute(select(resolved_input_cache)).all() == []


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("subject_id", "OTHER"),
        ("notes_json", "{}"),
        ("notes_json", "[1]"),
        ("lineage_json", "{"),
        ("value", float("inf")),
        ("input_provider_id", "different"),
    ],
)
def test_corrupt_storage_raises(
    database: SQLiteDatabase, key: ResolvedInputCacheKey, fact: ResolvedInput, column: str, value: object
) -> None:
    cache = SQLiteResolvedInputCache(database, clock=lambda: NOW)
    cache.put(key, fact)
    with database.transaction() as connection:
        connection.execute(update(resolved_input_cache).values(**{column: value}))
    with pytest.raises(ValueError, match="Malformed|validation error|Expecting"):
        cache.get(key)


def test_construction_does_not_migrate(tmp_path: Path, key: ResolvedInputCacheKey, fact: ResolvedInput) -> None:
    path = tmp_path / "unmigrated.sqlite3"
    database = SQLiteDatabase(ProjectSettings(database_url=f"sqlite:///{path.as_posix()}"))
    cache = SQLiteResolvedInputCache(database)
    assert not path.exists()
    try:
        with pytest.raises(OperationalError):
            cache.get(key)
        with pytest.raises(OperationalError):
            cache.put(key, fact)
    finally:
        database.close()


@pytest.mark.parametrize("corruption", ["row", "version"])
def test_series_read_rejects_corruption_without_partial_results(
    database: SQLiteDatabase, key: ResolvedInputCacheKey, fact: ResolvedInput, corruption: str
) -> None:
    key = replace(key, observation_period_start=START, observation_period_end=END)
    cache = SQLiteResolvedInputCache(database, clock=lambda: NOW)
    cache.put(key, fact)
    earlier = replace(
        key, observation_period_start=START - timedelta(days=365), observation_period_end=END - timedelta(days=365)
    )
    cache.put(
        earlier,
        replace(
            fact,
            observation_period_start=earlier.observation_period_start,
            observation_period_end=earlier.observation_period_end,
        ),
    )
    with database.transaction() as connection:
        if corruption == "version":
            connection.execute(update(schema_metadata).values(metadata_value=2))
        else:
            connection.execute(
                update(resolved_input_cache)
                .where(resolved_input_cache.c.key_period_start == "2025-01-01T00:00:00.000000Z")
                .values(notes_json="{}")
            )
    query = ResolvedInputSeriesCacheQuery(
        key.subject_kind,
        key.subject_id,
        key.field_name,
        key.basis,
        key.analysis_as_of,
        key.schema_version,
        key.provider_id,
    )
    with pytest.raises(ValueError, match="validation error|encoding version"):
        cache.get_series(query)
