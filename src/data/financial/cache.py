"""Minimal in-memory cache primitives for resolved financial inputs.

Defines the cache key, entry, protocol, and the concrete
``InMemoryResolvedInputCache`` implementation.

The cache stores original valid ``ResolvedInput`` facts (PROVIDER or DERIVED
source) and returns ``ResolvedInputCacheEntry`` objects.  It never relabels a
stored input as a cache resolution; the C2 resolver constructs the final
cache-sourced ``ResolvedInput``.

All datetimes must be timezone-aware.  Naive datetimes raise ``ValueError``.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol, runtime_checkable

from src.data.financial.provenance import (
    FinancialSubjectKind,
    ResolvedInput,
    SourceKind,
)


def _validate_optional_period_bounds(start: datetime | None, end: datetime | None) -> None:
    """Validate optional, paired, timezone-aware observation-period bounds."""
    if (start is None) is not (end is None):
        msg = "observation period start and end must either both be present or both be None."
        raise ValueError(msg)
    if start is not None and (start.tzinfo is None or start.utcoffset() is None):
        msg = "observation_period_start must be timezone-aware."
        raise ValueError(msg)
    if end is not None and (end.tzinfo is None or end.utcoffset() is None):
        msg = "observation_period_end must be timezone-aware."
        raise ValueError(msg)
    if start is not None and end is not None and start > end:
        msg = "observation_period_start must not be later than observation_period_end."
        raise ValueError(msg)


# ---------------------------------------------------------------------------
# ResolvedInputCacheKey
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedInputCacheKey:
    """Identity of a cached financial fact.

    Normalization (applied in ``__post_init__``):
        - SECURITY ``subject_id``: ``.strip().upper()``
        - MACRO ``subject_id``: ``.strip()`` (case preserved)
        - ``field_name``: ``.strip()``
        - ``basis``: ``.strip()`` if present; empty/whitespace-only rejected
        - ``provider_id``: ``.strip().lower()``

    Attributes:
        subject_kind: SECURITY or MACRO.
        subject_id: Security symbol (normalized) or macro identifier.
        field_name: Non-empty semantic input name.
        basis: Basis/variant label, or None.
        provider_id: Non-empty provider identifier (normalized lowercase).
        analysis_as_of: None = current; timezone-aware = historical boundary.
        schema_version: Positive integer; bumped on structural changes.
        observation_period_start: Optional timezone-aware start of a reporting period;
            ``None`` when the entry is not period-scoped.
        observation_period_end: Optional timezone-aware end; must accompany
            and not precede ``observation_period_start``.
    """

    subject_kind: FinancialSubjectKind
    subject_id: str
    field_name: str
    basis: str | None
    provider_id: str
    analysis_as_of: datetime | None
    schema_version: int
    observation_period_start: datetime | None = None
    observation_period_end: datetime | None = None

    def __post_init__(self) -> None:
        """Normalize subject_id, field_name, basis, provider_id; validate as_of and schema_version."""
        # --- subject_id normalization ---
        if self.subject_kind is FinancialSubjectKind.SECURITY:
            normalized_subject = self.subject_id.strip().upper()
        else:
            normalized_subject = self.subject_id.strip()

        if not normalized_subject:
            msg = "subject_id must be non-empty after normalization."
            raise ValueError(msg)

        # --- field_name ---
        normalized_field = self.field_name.strip()
        if not normalized_field:
            msg = "field_name must be non-empty after stripping."
            raise ValueError(msg)

        # --- basis ---
        normalized_basis: str | None
        if self.basis is None:
            normalized_basis = None
        else:
            normalized_basis = self.basis.strip()
            if not normalized_basis:
                msg = "basis must be non-empty when provided."
                raise ValueError(msg)

        # --- provider_id ---
        normalized_provider = self.provider_id.strip().lower()
        if not normalized_provider:
            msg = "provider_id must be non-empty after stripping."
            raise ValueError(msg)

        # --- analysis_as_of ---
        if self.analysis_as_of is not None and (
            self.analysis_as_of.tzinfo is None or self.analysis_as_of.tzinfo.utcoffset(self.analysis_as_of) is None
        ):
            msg = "analysis_as_of must be timezone-aware."
            raise ValueError(msg)

        # --- schema_version ---
        if self.schema_version < 1:
            msg = f"schema_version must be >= 1 (received {self.schema_version})."
            raise ValueError(msg)

        _validate_optional_period_bounds(self.observation_period_start, self.observation_period_end)

        # Apply normalization via object.__setattr__ (frozen dataclass).
        object.__setattr__(self, "subject_id", normalized_subject)
        object.__setattr__(self, "field_name", normalized_field)
        object.__setattr__(self, "basis", normalized_basis)
        object.__setattr__(self, "provider_id", normalized_provider)


# ---------------------------------------------------------------------------
# ResolvedInputCacheEntry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedInputCacheEntry:
    """A cached financial fact with its identity and insertion time.

    Attributes:
        key: The identity under which this entry is stored.
        resolved_input: The original valid ``ResolvedInput`` as at ``put`` time.
        cached_at: Timezone-aware time when this entry was placed in the cache.
    """

    key: ResolvedInputCacheKey
    resolved_input: ResolvedInput
    cached_at: datetime

    def __post_init__(self) -> None:
        """Validate cached_at and coherence between key and resolved_input."""
        # --- cached_at must be timezone-aware ---
        if self.cached_at.tzinfo is None or self.cached_at.tzinfo.utcoffset(self.cached_at) is None:
            msg = "cached_at must be timezone-aware."
            raise ValueError(msg)

        # --- key/input coherence ---
        if self.key.field_name != self.resolved_input.field_name:
            msg = (
                f"key.field_name ({self.key.field_name!r}) does not match "
                f"resolved_input.field_name ({self.resolved_input.field_name!r})."
            )
            raise ValueError(msg)

        if self.key.basis != self.resolved_input.basis:
            msg = f"key.basis ({self.key.basis!r}) does not match resolved_input.basis ({self.resolved_input.basis!r})."
            raise ValueError(msg)

        if self.key.analysis_as_of != self.resolved_input.as_of:
            msg = (
                f"key.analysis_as_of ({self.key.analysis_as_of!r}) does not match "
                f"resolved_input.as_of ({self.resolved_input.as_of!r})."
            )
            raise ValueError(msg)

        if self.key.observation_period_start is not None and (
            self.key.observation_period_start != self.resolved_input.observation_period_start
            or self.key.observation_period_end != self.resolved_input.observation_period_end
        ):
            msg = "Period-scoped cache key must match the resolved input observation period."
            raise ValueError(msg)

        if (
            self.resolved_input.source_kind is SourceKind.PROVIDER
            and self.key.provider_id != self.resolved_input.provider_id
        ):
            msg = (
                f"key.provider_id ({self.key.provider_id!r}) does not match "
                f"resolved_input.provider_id ({self.resolved_input.provider_id!r})."
            )
            raise ValueError(msg)

        # --- source_kind restriction ---
        if self.resolved_input.source_kind not in (SourceKind.PROVIDER, SourceKind.DERIVED):
            msg = f"resolved_input.source_kind must be PROVIDER or DERIVED, got {self.resolved_input.source_kind!r}."
            raise ValueError(msg)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class ResolvedInputCacheProtocol(Protocol):
    """Structural protocol for resolved-input cache implementations."""

    def get(self, key: ResolvedInputCacheKey) -> ResolvedInputCacheEntry | None:
        """Return the cached entry for *key*, or ``None`` on miss."""
        ...

    def put(self, key: ResolvedInputCacheKey, resolved_input: ResolvedInput) -> None:
        """Store *resolved_input* under *key*.

        Raises:
            ValueError: If the input or key is invalid for caching.
        """
        ...


# ---------------------------------------------------------------------------
# ResolvedInputSeriesCacheQuery
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedInputSeriesCacheQuery:
    """Identity for discovering cached period-scoped financial facts.

    Normalization (applied in ``__post_init__``) mirrors ``ResolvedInputCacheKey``:
        - SECURITY ``subject_id``: ``.strip().upper()``
        - MACRO ``subject_id``: ``.strip()`` (case preserved)
        - ``field_name``: ``.strip()``
        - ``basis``: ``.strip()`` if present; empty/whitespace-only rejected
        - ``provider_id``: ``.strip().lower()`` when provided

    Attributes:
        subject_kind: SECURITY or MACRO.
        subject_id: Security symbol (normalized) or macro identifier.
        field_name: Non-empty semantic input name.
        basis: Basis/variant label, or None.
        analysis_as_of: None = current; timezone-aware = historical boundary.
        schema_version: Positive integer; matching entries share this version.
        provider_id: Non-empty provider identifier (normalized lowercase).
    """

    subject_kind: FinancialSubjectKind
    subject_id: str
    field_name: str
    basis: str | None
    analysis_as_of: datetime | None
    schema_version: int
    provider_id: str

    def __post_init__(self) -> None:
        """Normalize identifiers and validate the series identity."""
        if self.subject_kind is FinancialSubjectKind.SECURITY:
            normalized_subject = self.subject_id.strip().upper()
        else:
            normalized_subject = self.subject_id.strip()
        if not normalized_subject:
            msg = "subject_id must be non-empty after normalization."
            raise ValueError(msg)

        normalized_field = self.field_name.strip()
        if not normalized_field:
            msg = "field_name must be non-empty after stripping."
            raise ValueError(msg)

        normalized_basis: str | None
        if self.basis is None:
            normalized_basis = None
        else:
            normalized_basis = self.basis.strip()
            if not normalized_basis:
                msg = "basis must be non-empty when provided."
                raise ValueError(msg)

        normalized_provider = self.provider_id.strip().lower()
        if not normalized_provider:
            msg = "provider_id must be non-empty after stripping."
            raise ValueError(msg)

        if self.analysis_as_of is not None and (
            self.analysis_as_of.tzinfo is None or self.analysis_as_of.utcoffset() is None
        ):
            msg = "analysis_as_of must be timezone-aware."
            raise ValueError(msg)

        if self.schema_version < 1:
            msg = f"schema_version must be >= 1 (received {self.schema_version})."
            raise ValueError(msg)

        object.__setattr__(self, "subject_id", normalized_subject)
        object.__setattr__(self, "field_name", normalized_field)
        object.__setattr__(self, "basis", normalized_basis)
        object.__setattr__(self, "provider_id", normalized_provider)


@runtime_checkable
class ResolvedInputSeriesCacheProtocol(ResolvedInputCacheProtocol, Protocol):
    """Additive cache protocol for discovering period-scoped fact entries."""

    def get_series(self, query: ResolvedInputSeriesCacheQuery) -> tuple[ResolvedInputCacheEntry, ...]:
        """Return eligible period-scoped entries matching *query*."""
        ...


# ---------------------------------------------------------------------------
# InMemoryResolvedInputCache
# ---------------------------------------------------------------------------


class InMemoryResolvedInputCache:
    """Deterministic in-memory resolved-input cache.

    Stores original PROVIDER or DERIVED facts.  Returns
    ``ResolvedInputCacheEntry`` objects on hit.  Does not relabel or rewrite
    the stored ``ResolvedInput``.

    Args:
        clock: Zero-argument callable returning a timezone-aware datetime.
            Used for ``cached_at`` and TTL age calculation.
        ttl: Optional time-to-live.  ``None`` disables staleness checking.
            Must be non-negative.
    """

    _DEFAULT_CLOCK: Callable[[], datetime] = staticmethod(lambda: datetime.now(UTC))

    def __init__(
        self,
        clock: Callable[[], datetime] | None = None,
        ttl: timedelta | None = None,
    ) -> None:
        """Create an in-memory resolved-input cache.

        Args:
            clock: Clock callable returning timezone-aware datetime. Defaults to
                ``datetime.now(UTC)``.
            ttl: Optional time-to-live. If set, entries older than this are
                treated as stale on read. ``None`` disables staleness.
        """
        if ttl is not None and ttl < timedelta(0):
            msg = f"ttl must be non-negative (received {ttl!r})."
            raise ValueError(msg)

        self._clock: Callable[[], datetime] = clock if clock is not None else self._DEFAULT_CLOCK
        self._ttl = ttl
        self._store: dict[ResolvedInputCacheKey, ResolvedInputCacheEntry] = {}

    @property
    def ttl(self) -> timedelta | None:
        """The configured TTL, or ``None`` if disabled."""
        return self._ttl

    def get(self, key: ResolvedInputCacheKey) -> ResolvedInputCacheEntry | None:
        """Return the cached entry for *key*, or ``None`` on miss.

        Miss conditions:
            - Key not found in store.
            - Historical key: ``available_at`` is None or > ``analysis_as_of``.
            - TTL enabled and entry age > TTL.

        Hit:
            - All checks pass; entry returned unchanged.
        """
        entry = self._store.get(key)
        if entry is None:
            return None
        if not self._is_eligible(key, entry):
            return None

        return entry

    def get_series(self, query: ResolvedInputSeriesCacheQuery) -> tuple[ResolvedInputCacheEntry, ...]:
        """Return eligible cached entries matching *query*, ordered by period.

        An entry matches when its key shares the query's subject, field, basis,
        provider, analysis boundary, and schema version. The same ``as_of`` and
        TTL eligibility rules as :meth:`get` apply per entry.

        Returns:
            A tuple of matching ``ResolvedInputCacheEntry`` objects ordered by
            reporting period (ascending); empty when nothing matches.
        """
        matches: list[tuple[datetime, datetime, str, ResolvedInputCacheEntry]] = []
        for key, entry in self._store.items():
            if not self._key_matches_query(key, query):
                continue
            if not self._is_eligible(key, entry):
                continue
            if key.observation_period_start is None or key.observation_period_end is None:
                continue
            matches.append(
                (
                    key.observation_period_end,
                    key.observation_period_start,
                    entry.resolved_input.provider_fact_id or "",
                    entry,
                )
            )

        matches.sort(key=lambda item: (item[0], item[1], item[2]))
        return tuple(entry for _, _, _, entry in matches)

    def put(self, key: ResolvedInputCacheKey, resolved_input: ResolvedInput) -> None:
        """Store *resolved_input* under *key*.

        Only PROVIDER and DERIVED source kinds are accepted.  OVERRIDE and
        CACHE source kinds raise ``ValueError``.

        Raises:
            ValueError: If the source kind is not cacheable, if the clock
                returns a naive datetime, or if key/input coherence fails.
        """
        # --- Source kind restriction ---
        if resolved_input.source_kind not in (SourceKind.PROVIDER, SourceKind.DERIVED):
            msg = (
                f"cache.put rejects source_kind={resolved_input.source_kind!r}; "
                f"only PROVIDER and DERIVED may be cached."
            )
            raise ValueError(msg)

        # --- Defensive re-check of value finiteness ---
        if not math.isfinite(resolved_input.value):
            msg = f"resolved_input.value must be finite (received {resolved_input.value!r})."
            raise ValueError(msg)

        # --- Clock must be timezone-aware ---
        cached_at = self._clock()
        if cached_at.tzinfo is None or cached_at.tzinfo.utcoffset(cached_at) is None:
            msg = "Cache clock returned a naive datetime."
            raise ValueError(msg)

        # --- Construct entry (triggers coherence validation) ---
        entry = ResolvedInputCacheEntry(
            key=key,
            resolved_input=resolved_input,
            cached_at=cached_at,
        )

        self._store[key] = entry

    # --- series-aware query helpers ---------------------------------------

    def _is_eligible(self, key: ResolvedInputCacheKey, entry: ResolvedInputCacheEntry) -> bool:
        """Return whether *entry* is readable under *key* (as_of + TTL rules).

        Raises:
            ValueError: If the clock returns a naive datetime while TTL is set.
        """
        if key.analysis_as_of is not None:
            available_at = entry.resolved_input.available_at
            if available_at is None:
                return False
            if available_at > key.analysis_as_of:
                return False
        if self._ttl is not None:
            now = self._clock()
            if now.tzinfo is None or now.utcoffset() is None:
                msg = "Clock returned a naive datetime."
                raise ValueError(msg)
            age = now - entry.cached_at
            if age > self._ttl:
                return False
        return True

    @staticmethod
    def _key_matches_query(key: ResolvedInputCacheKey, query: ResolvedInputSeriesCacheQuery) -> bool:
        """Return whether *key* matches the identity portion of *query*."""
        return (
            key.subject_kind is query.subject_kind
            and key.subject_id == query.subject_id
            and key.field_name == query.field_name
            and key.basis == query.basis
            and key.analysis_as_of == query.analysis_as_of
            and key.schema_version == query.schema_version
            and key.provider_id == query.provider_id
        )
