"""Durable scalar and period-series cache with lossless provenance storage."""

import json
import math
from collections.abc import Callable, Mapping
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from pydantic import TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.engine import Connection

from src.data.financial.cache import ResolvedInputCacheEntry, ResolvedInputCacheKey, ResolvedInputSeriesCacheQuery
from src.data.financial.provenance import ComponentLineage, ResolvedInput
from src.data.repositories.schema import resolved_input_cache, schema_metadata
from src.data.repositories.sqlite import SQLiteDatabase

_ENTRY_ADAPTER = TypeAdapter(ResolvedInputCacheEntry)
_KEY_ADAPTER = TypeAdapter(ResolvedInputCacheKey)
_QUERY_ADAPTER = TypeAdapter(ResolvedInputSeriesCacheQuery)

# Order is the version-1 cache identity encoding, including nullable members.
_KEY_COLUMNS = {
    "subject_kind": "subject_kind",
    "subject_id": "subject_id",
    "field_name": "field_name",
    "basis": "basis",
    "provider_id": "provider_id",
    "analysis_as_of": "analysis_as_of",
    "schema_version": "schema_version",
    "observation_period_start": "key_period_start",
    "observation_period_end": "key_period_end",
}
_INPUT_COLUMNS = {
    "field_name": "field_name",
    "value": "value",
    "source_kind": "source_kind",
    "resolved_at": "resolved_at",
    "basis": "basis",
    "units": "units",
    "currency": "currency",
    "provider_id": "input_provider_id",
    "provider_field": "provider_field",
    "observation_period_start": "input_period_start",
    "observation_period_end": "input_period_end",
    "observed_at": "observed_at",
    "available_at": "available_at",
    "as_of": "analysis_as_of",
    "retrieved_at": "retrieved_at",
    "fiscal_year": "fiscal_year",
    "period_kind": "period_kind",
    "accounting_scope": "accounting_scope",
    "capital_expenditure_sign": "capital_expenditure_sign",
    "provider_fact_id": "provider_fact_id",
}


def _json_value(value: object) -> object:
    """Encode supported provenance values without non-finite or naive values."""
    if isinstance(value, datetime):
        if value.utcoffset() is None:
            raise ValueError("Cache timestamps must be timezone-aware.")
        return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(value, ComponentLineage):
        return _json_value(asdict(value))
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Cache values must be finite.")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError("Unsupported cache provenance value.")


def _json(value: object) -> str:
    """Serialize canonical, Unicode-preserving provenance JSON."""
    return json.dumps(_json_value(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _key_row(key: ResolvedInputCacheKey) -> dict[str, object]:
    """Encode the complete normalized scalar identity."""
    row = {column: _json_value(getattr(key, name)) for name, column in _KEY_COLUMNS.items()}
    row["cache_key"] = _json(list(row.values()))
    return row


def _encode(entry: ResolvedInputCacheEntry) -> dict[str, object]:
    """Map every root field and recursively complete lineage to one row."""
    row = _key_row(entry.key)
    fact = entry.resolved_input
    row.update({column: _json_value(getattr(fact, name)) for name, column in _INPUT_COLUMNS.items()})
    row["cached_at"] = _json_value(entry.cached_at)
    row["lineage_json"] = None if fact.lineage is None else _json(fact.lineage)
    row["notes_json"] = _json(fact.notes)
    return row


def _decode(row: Mapping[str, object]) -> ResolvedInputCacheEntry:
    """Reconstruct domain objects and reject inconsistent stored encodings."""
    fact = {name: row[column] for name, column in _INPUT_COLUMNS.items()}
    for name in ("lineage", "notes"):
        value = row[f"{name}_json"]
        if value is not None and not isinstance(value, str):
            raise ValueError("Malformed cache JSON storage type.")
        fact[name] = None if value is None else json.loads(value)
    entry = _ENTRY_ADAPTER.validate_python(
        {
            "key": {name: row[column] for name, column in _KEY_COLUMNS.items()},
            "resolved_input": fact,
            "cached_at": row["cached_at"],
        }
    )
    if _encode(entry) != dict(row):
        raise ValueError("Malformed or inconsistent resolved-input cache encoding.")
    return entry


def _check_encoding(connection: Connection) -> None:
    """Require the migration-owned representation version."""
    version = connection.execute(
        select(schema_metadata.c.metadata_value).where(schema_metadata.c.metadata_key == "persistence_encoding_version")
    ).scalar_one_or_none()
    if version != 1:
        raise ValueError("Unsupported or missing cache persistence encoding version.")


class SQLiteResolvedInputCache:
    """Store original provider/derived inputs in a caller-owned SQLite database.

    The database must already be migrated. Every put replaces the entire row
    and refreshes cached_at. Reads preserve original provenance and never delete
    stale entries. Errors propagate explicitly to the caller.

    Args:
        database: Borrowed connection/transaction boundary.
        clock: Aware clock for writes and TTL checks; defaults to current UTC.
        ttl: Nonnegative lifetime, or None to disable age checking. Equality
            at the boundary and future cached times remain eligible.
    """

    def __init__(
        self,
        database: SQLiteDatabase,
        *,
        clock: Callable[[], datetime] | None = None,
        ttl: timedelta | None = None,
    ) -> None:
        """Configure the cache without opening connections or changing schema."""
        if ttl is not None and ttl < timedelta(0):
            raise ValueError("ttl must be non-negative.")
        self._database = database
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)
        self._ttl = ttl

    @property
    def ttl(self) -> timedelta | None:
        """Return the configured lifetime, or None when disabled."""
        return self._ttl

    def put(self, key: ResolvedInputCacheKey, resolved_input: ResolvedInput) -> None:
        """Validate and atomically replace the complete entry, refreshing its age."""
        entry = _ENTRY_ADAPTER.validate_python(
            {
                "key": asdict(key),
                "resolved_input": asdict(resolved_input),
                "cached_at": self._clock(),
            }
        )
        row = _encode(entry)
        statement = insert(resolved_input_cache).values(**row)
        with self._database.transaction() as connection:
            connection.execute(
                statement.on_conflict_do_update(
                    index_elements=["cache_key"],
                    set_={name: statement.excluded[name] for name in row if name != "cache_key"},
                )
            )
            # Write before reading so concurrent writers serialize; a version
            # mismatch rolls the write back with the rest of this transaction.
            _check_encoding(connection)

    def get(self, key: ResolvedInputCacheKey) -> ResolvedInputCacheEntry | None:
        """Return the original eligible entry, or None for an absent/stale key."""
        entry = self.inspect(key)
        return entry if entry is not None and self._is_eligible(entry) else None

    def list_keys(self, *, limit: int, offset: int = 0) -> tuple[ResolvedInputCacheKey, ...]:
        """Inspect a bounded page of stored keys in canonical identity order.

        Includes ineligible entries without consulting the clock or loading
        fact payloads. Each call uses one snapshot; pages across writes are not
        a frozen view. Invalid bounds, keys, or encodings raise explicit errors.

        Args:
            limit: Positive integer page size; booleans are rejected.
            offset: Nonnegative integer row offset; booleans are rejected.

        Returns:
            Stored fact keys, or an empty tuple for an empty page.
        """
        if type(limit) is not int or limit <= 0:
            raise ValueError("limit must be a positive integer.")
        if type(offset) is not int or offset < 0:
            raise ValueError("offset must be a nonnegative integer.")
        statement = (
            select(resolved_input_cache.c.cache_key, *(resolved_input_cache.c[name] for name in _KEY_COLUMNS.values()))
            .order_by(resolved_input_cache.c.cache_key)
            .limit(limit)
            .offset(offset)
        )
        with self._database.read() as connection:
            _check_encoding(connection)
            keys: list[ResolvedInputCacheKey] = []
            for row in connection.execute(statement).mappings():
                key = _KEY_ADAPTER.validate_python({name: row[column] for name, column in _KEY_COLUMNS.items()})
                if _key_row(key) != dict(row):
                    raise ValueError("Malformed or inconsistent resolved-input cache key encoding.")
                keys.append(key)
        return tuple(keys)

    def inspect(self, key: ResolvedInputCacheKey) -> ResolvedInputCacheEntry | None:
        """Return the validated stored entry, even if stale or ineligible.

        This administrative read preserves provenance and timestamps without
        consulting the clock, refreshing, deleting, or applying eligibility.
        Normal resolution must continue to use get/get_series.

        Args:
            key: Exact stored fact identity, validated before database access.

        Returns:
            The original entry, or None only for an absent key. Malformed input,
            corrupt storage, and unsupported encodings raise explicit errors.
        """
        key = _KEY_ADAPTER.validate_python(asdict(key))
        with self._database.read() as connection:
            _check_encoding(connection)
            row = (
                connection.execute(
                    select(resolved_input_cache).where(resolved_input_cache.c.cache_key == _key_row(key)["cache_key"])
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            return _decode(dict(row))

    def get_series(self, query: ResolvedInputSeriesCacheQuery) -> tuple[ResolvedInputCacheEntry, ...]:
        """Return eligible period-scoped facts ordered by end, start, and fact ID.

        All seven normalized query fields must match, with explicit SQL NULL
        equality for absent basis/as_of. Invalid stored entries raise errors;
        an empty or ineligible series returns an empty tuple.
        """
        query = _QUERY_ADAPTER.validate_python(asdict(query))
        statement = (
            select(resolved_input_cache)
            .where(
                *(resolved_input_cache.c[name] == _json_value(value) for name, value in asdict(query).items()),
                resolved_input_cache.c.key_period_start.is_not(None),
                resolved_input_cache.c.key_period_end.is_not(None),
            )
            .order_by(
                resolved_input_cache.c.key_period_end,
                resolved_input_cache.c.key_period_start,
                func.coalesce(resolved_input_cache.c.provider_fact_id, ""),
            )
        )
        with self._database.read() as connection:
            _check_encoding(connection)
            entries = [_decode(dict(row)) for row in connection.execute(statement).mappings()]
        return tuple(entry for entry in entries if self._is_eligible(entry))

    def _is_eligible(self, entry: ResolvedInputCacheEntry) -> bool:
        """Apply the same historical and TTL policy for scalar and series reads."""
        if entry.key.analysis_as_of is not None:
            available_at = entry.resolved_input.available_at
            if available_at is None or available_at > entry.key.analysis_as_of:
                return False
        if self._ttl is not None:
            now = self._clock()
            if now.utcoffset() is None:
                raise ValueError("Cache clock must be timezone-aware.")
            if now - entry.cached_at > self._ttl:
                return False
        return True
