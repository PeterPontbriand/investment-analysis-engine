"""Tests for src.analysis.graham_value.resolver deterministic single-fact resolution.

Uses tiny in-test fakes/spies only.  All datetimes are fixed timezone-aware
values.  No live network access.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import inf, nan
from typing import Any

import pytest

from src.analysis.graham_value.cache import (
    InMemoryValuationCache,
    ValuationCacheEntry,
    ValuationCacheKey,
)
from src.analysis.graham_value.facts import (
    ProviderFact,
    ValuationFactRequest,
    ValuationField,
    ValuationProviderError,
    ValuationUnit,
)
from src.analysis.graham_value.models import CalculationStatus, GrahamMethod
from src.analysis.graham_value.provenance import (
    ComponentLineage,
    ResolvedInput,
    SourceKind,
    ValuationSubjectKind,
)
from src.analysis.graham_value.resolver import (
    InputResolutionResult,
    InputResolver,
)

# ---------------------------------------------------------------------------
# Fixed datetimes
# ---------------------------------------------------------------------------

NOW = datetime(2025, 7, 1, 12, 0, tzinfo=UTC)
RETRIEVED_AT = datetime(2025, 6, 30, 8, 0, tzinfo=UTC)
AVAILABLE_AT = datetime(2025, 6, 29, 16, 0, tzinfo=UTC)
AS_OF = datetime(2025, 12, 31, tzinfo=UTC)
FUTURE_AVAILABLE = datetime(2026, 1, 1, tzinfo=UTC)
PERIOD_START = datetime(2024, 7, 1, tzinfo=UTC)
PERIOD_END = datetime(2025, 6, 30, tzinfo=UTC)
OBSERVED_AT = datetime(2025, 6, 30, 10, 0, tzinfo=UTC)

PROVIDER_ID = "provider-a"
SUBJECT_ID = "SYNTH"
PROVIDER_FIELD = "synthetic_eps_field"


# ---------------------------------------------------------------------------
# Fakes / spies
# ---------------------------------------------------------------------------


class FakeProvider:
    """Configurable provider fake."""

    def __init__(self, facts: tuple[ProviderFact, ...] | ValuationProviderError | None = None) -> None:
        """Initialize the fake with facts to return or an error to raise."""
        if facts is None:
            self._facts: tuple[ProviderFact, ...] = ()
        elif isinstance(facts, ValuationProviderError):
            self._error = facts
        else:
            self._facts = facts
        self.call_count = 0
        self.last_request: ValuationFactRequest | None = None

    def fetch_facts(self, request: ValuationFactRequest) -> tuple[ProviderFact, ...]:
        self.call_count += 1
        self.last_request = request
        if hasattr(self, "_error"):
            raise self._error
        return self._facts


class SpyCache:
    """Cache spy that records get/put calls."""

    def __init__(self, entry: ValuationCacheEntry | None = None) -> None:
        """Initialize the spy with an optional cached entry."""
        self._entry = entry
        self.get_count = 0
        self.put_count = 0
        self.last_get_key: ValuationCacheKey | None = None
        self.last_put_key: ValuationCacheKey | None = None
        self.last_put_input: ResolvedInput | None = None

    def get(self, key: ValuationCacheKey) -> ValuationCacheEntry | None:
        self.get_count += 1
        self.last_get_key = key
        return self._entry

    def put(self, key: ValuationCacheKey, resolved_input: ResolvedInput) -> None:
        self.put_count += 1
        self.last_put_key = key
        self.last_put_input = resolved_input


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fixed_clock() -> Any:
    return lambda: NOW  # noqa: E731


def _make_request(  # noqa: PLR0913, PLR0917
    field: ValuationField = ValuationField.EPS,
    subject_kind: ValuationSubjectKind = ValuationSubjectKind.SECURITY,
    subject_id: str = SUBJECT_ID,
    provider_id: str = PROVIDER_ID,
    basis: str | None = None,
    as_of: datetime | None = None,
    observation_count: int = 1,
) -> ValuationFactRequest:
    return ValuationFactRequest(
        subject_kind=subject_kind,
        subject_id=subject_id,
        field_name=field,
        provider_id=provider_id,
        basis=basis,
        as_of=as_of,
        observation_count=observation_count,
    )


def _make_fact(  # noqa: PLR0913, PLR0917
    field: ValuationField = ValuationField.EPS,
    value: float = 4.5,
    subject_kind: ValuationSubjectKind = ValuationSubjectKind.SECURITY,
    subject_id: str = SUBJECT_ID,
    provider_id: str = PROVIDER_ID,
    provider_field: str = PROVIDER_FIELD,
    basis: str | None = None,
    currency: str | None = "USD",
    available_at: datetime | None = AVAILABLE_AT,
    **kwargs: Any,
) -> ProviderFact:
    # For percentage-point fields, currency must be None.
    if field is ValuationField.CURRENT_AAA_YIELD:
        currency = None
    defaults: dict[str, Any] = {
        "subject_kind": subject_kind,
        "subject_id": subject_id,
        "field_name": field,
        "value": value,
        "units": ValuationUnit.CURRENCY_PER_SHARE if currency else ValuationUnit.PERCENTAGE_POINTS,
        "provider_id": provider_id,
        "provider_field": provider_field,
        "retrieved_at": RETRIEVED_AT,
        "basis": basis,
        "currency": currency,
        "available_at": available_at,
    }
    defaults.update(kwargs)
    return ProviderFact(**defaults)


def _make_provider_input(  # noqa: PLR0913, PLR0917
    field_name: str = "eps",
    value: float = 4.5,
    basis: str | None = None,
    provider_id: str = PROVIDER_ID,
    provider_field: str | None = PROVIDER_FIELD,
    currency: str | None = "USD",
    available_at: datetime | None = AVAILABLE_AT,
    as_of: datetime | None = None,
    retrieved_at: datetime | None = RETRIEVED_AT,
    notes: tuple[str, ...] = (),
    **kwargs: Any,
) -> ResolvedInput:
    defaults: dict[str, Any] = {
        "field_name": field_name,
        "value": value,
        "source_kind": SourceKind.PROVIDER,
        "resolved_at": NOW,
        "basis": basis,
        "units": "currency_per_share" if currency else "percentage_points",
        "currency": currency,
        "provider_id": provider_id,
        "provider_field": provider_field,
        "available_at": available_at,
        "as_of": as_of,
        "retrieved_at": retrieved_at,
        "notes": notes,
    }
    defaults.update(kwargs)
    return ResolvedInput(**defaults)


def _make_derived_input(
    field_name: str = "avg_eps",
    value: float = 4.0,
    basis: str | None = "three_year_average",
    as_of: datetime | None = None,
) -> ResolvedInput:
    comp = _make_provider_input(field_name="eps", value=5.0)
    lineage = ComponentLineage(transformation="arithmetic_mean", components=(comp,))
    return ResolvedInput(
        field_name=field_name,
        value=value,
        source_kind=SourceKind.DERIVED,
        resolved_at=NOW,
        basis=basis,
        lineage=lineage,
        as_of=as_of,
    )


def _make_resolver(
    provider: FakeProvider | None = None,
    cache: Any = None,
    clock: Any = None,
    schema_version: int = 1,
) -> InputResolver:
    return InputResolver(
        provider=provider or FakeProvider(),
        cache=cache,
        clock=clock or _fixed_clock(),
        cache_schema_version=schema_version,
    )


# ===========================================================================
# 1. Valid override returns OK and SourceKind.OVERRIDE
# ===========================================================================


def test_valid_override_returns_ok_and_override_source() -> None:
    resolver = _make_resolver()
    result = resolver.resolve(_make_request(), override=42.0)
    assert result.status is CalculationStatus.OK
    assert result.resolved_input is not None
    assert result.resolved_input.source_kind is SourceKind.OVERRIDE
    assert result.resolved_input.value == 42.0
    assert result.reason is None


# ===========================================================================
# 2. Override prevents both cache access and provider access
# ===========================================================================


def test_override_prevents_cache_and_provider_access() -> None:
    provider = FakeProvider()
    cache = SpyCache()
    resolver = _make_resolver(provider=provider, cache=cache)
    resolver.resolve(_make_request(), override=99.0)
    assert provider.call_count == 0
    assert cache.get_count == 0
    assert cache.put_count == 0


# ===========================================================================
# 3. NaN/infinite override -> INVALID_INPUT
# ===========================================================================


@pytest.mark.parametrize("bad_value", [nan, inf, -inf])
def test_nan_infinite_override_rejected(bad_value: float) -> None:
    resolver = _make_resolver()
    result = resolver.resolve(_make_request(), override=bad_value)
    assert result.status is CalculationStatus.INVALID_INPUT
    assert result.resolved_input is None
    assert result.reason is not None


# ===========================================================================
# 4. Zero/non-positive current-price override -> INVALID_INPUT
# ===========================================================================


@pytest.mark.parametrize("val", [0.0, -1.0])
def test_zero_negative_current_price_override_rejected(val: float) -> None:
    resolver = _make_resolver()
    req = _make_request(field=ValuationField.CURRENT_PRICE)
    result = resolver.resolve(req, override=val)
    assert result.status is CalculationStatus.INVALID_INPUT
    assert result.resolved_input is None


# ===========================================================================
# 5. Zero/non-positive AAA-yield override -> INVALID_INPUT
# ===========================================================================


@pytest.mark.parametrize("val", [0.0, -5.0])
def test_zero_negative_aaa_yield_override_rejected(val: float) -> None:
    resolver = _make_resolver()
    req = _make_request(
        field=ValuationField.CURRENT_AAA_YIELD,
        subject_kind=ValuationSubjectKind.MACRO,
        subject_id="macro-a",
    )
    result = resolver.resolve(req, override=val)
    assert result.status is CalculationStatus.INVALID_INPUT
    assert result.resolved_input is None


# ===========================================================================
# 6. Zero/negative EPS override remains valid
# ===========================================================================


@pytest.mark.parametrize("val", [0.0, -3.5])
def test_zero_negative_eps_override_valid(val: float) -> None:
    resolver = _make_resolver()
    result = resolver.resolve(_make_request(field=ValuationField.EPS), override=val)
    assert result.status is CalculationStatus.OK
    assert result.resolved_input is not None
    assert result.resolved_input.value == val


# ===========================================================================
# 7. Zero/negative BVPS override remains valid
# ===========================================================================


@pytest.mark.parametrize("val", [0.0, -10.0])
def test_zero_negative_bvps_override_valid(val: float) -> None:
    resolver = _make_resolver()
    result = resolver.resolve(_make_request(field=ValuationField.BVPS), override=val)
    assert result.status is CalculationStatus.OK
    assert result.resolved_input is not None
    assert result.resolved_input.value == val


# ===========================================================================
# 8. Override preserves as_of, basis, semantic field, and deterministic resolved_at
# ===========================================================================


def test_override_preserves_fields() -> None:
    resolver = _make_resolver()
    req = _make_request(field=ValuationField.EPS, basis="ttm", as_of=AS_OF)
    result = resolver.resolve(req, override=7.5)
    ri = result.resolved_input
    assert ri is not None
    assert ri.field_name == "eps"
    assert ri.basis == "ttm"
    assert ri.as_of == AS_OF
    assert ri.resolved_at == NOW
    assert ri.source_kind is SourceKind.OVERRIDE
    assert ri.units == "currency_per_share"


def test_override_current_as_of_none() -> None:
    resolver = _make_resolver()
    req = _make_request(field=ValuationField.EPS)
    result = resolver.resolve(req, override=7.5)
    ri = result.resolved_input
    assert ri is not None
    assert ri.as_of is None


# ===========================================================================
# 9. Valid provider-origin cache hit wins over provider
# ===========================================================================


def test_valid_cache_hit_wins_over_provider() -> None:
    stored = _make_provider_input(field_name="eps", value=3.3)
    key = ValuationCacheKey(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id=SUBJECT_ID,
        field_name="eps",
        basis=None,
        provider_id=PROVIDER_ID,
        analysis_as_of=None,
        schema_version=1,
    )
    entry = ValuationCacheEntry(key=key, resolved_input=stored, cached_at=NOW)
    provider = FakeProvider(facts=(_make_fact(),))
    cache = SpyCache(entry=entry)
    resolver = _make_resolver(provider=provider, cache=cache)

    result = resolver.resolve(_make_request())
    assert result.status is CalculationStatus.OK
    assert result.resolved_input is not None
    assert result.resolved_input.source_kind is SourceKind.CACHE
    assert provider.call_count == 0


# ===========================================================================
# 10. Cache hit is returned as new SourceKind.CACHE value
# ===========================================================================


def test_cache_hit_returns_new_cache_sourced_value() -> None:
    stored = _make_provider_input(field_name="eps", value=2.0)
    key = ValuationCacheKey(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id=SUBJECT_ID,
        field_name="eps",
        basis=None,
        provider_id=PROVIDER_ID,
        analysis_as_of=None,
        schema_version=1,
    )
    entry = ValuationCacheEntry(key=key, resolved_input=stored, cached_at=NOW)
    cache = SpyCache(entry=entry)
    resolver = _make_resolver(cache=cache)

    result = resolver.resolve(_make_request())
    ri = result.resolved_input
    assert ri is not None
    assert ri.source_kind is SourceKind.CACHE
    assert ri is not stored  # New object, not the stored one


# ===========================================================================
# 11. Cache hit preserves origin_source_kind=PROVIDER
# ===========================================================================


def test_cache_hit_preserves_origin_provider() -> None:
    stored = _make_provider_input(field_name="eps")
    key = ValuationCacheKey(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id=SUBJECT_ID,
        field_name="eps",
        basis=None,
        provider_id=PROVIDER_ID,
        analysis_as_of=None,
        schema_version=1,
    )
    entry = ValuationCacheEntry(key=key, resolved_input=stored, cached_at=NOW)
    cache = SpyCache(entry=entry)
    resolver = _make_resolver(cache=cache)

    result = resolver.resolve(_make_request())
    ri = result.resolved_input
    assert ri is not None
    assert ri.origin_source_kind is SourceKind.PROVIDER


# ===========================================================================
# 12. Cache hit preserves provenance fields
# ===========================================================================


def test_cache_hit_preserves_provenance() -> None:
    stored = _make_provider_input(
        field_name="eps",
        value=6.6,
        basis="ttm",
        provider_id=PROVIDER_ID,
        provider_field=PROVIDER_FIELD,
        currency="USD",
        available_at=AVAILABLE_AT,
        as_of=None,
        retrieved_at=RETRIEVED_AT,
        notes=("synthetic note",),
        observation_period_start=PERIOD_START,
        observation_period_end=PERIOD_END,
        observed_at=OBSERVED_AT,
    )
    key = ValuationCacheKey(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id=SUBJECT_ID,
        field_name="eps",
        basis="ttm",
        provider_id=PROVIDER_ID,
        analysis_as_of=None,
        schema_version=1,
    )
    entry = ValuationCacheEntry(key=key, resolved_input=stored, cached_at=NOW)
    cache = SpyCache(entry=entry)
    resolver = _make_resolver(cache=cache)

    result = resolver.resolve(_make_request(basis="ttm"))
    ri = result.resolved_input
    assert ri is not None
    assert ri.value == 6.6
    assert ri.basis == "ttm"
    assert ri.provider_id == PROVIDER_ID
    assert ri.provider_field == PROVIDER_FIELD
    assert ri.currency == "USD"
    assert ri.available_at == AVAILABLE_AT
    assert ri.retrieved_at == RETRIEVED_AT
    assert ri.notes == ("synthetic note",)
    assert ri.observation_period_start == PERIOD_START
    assert ri.observation_period_end == PERIOD_END
    assert ri.observed_at == OBSERVED_AT
    assert ri.units == "currency_per_share"


# ===========================================================================
# 13. Cached DERIVED input retains origin_source_kind=DERIVED and full lineage
# ===========================================================================


def test_cache_hit_derived_retains_lineage() -> None:
    derived = _make_derived_input(field_name="eps", basis="three_year_average")
    key = ValuationCacheKey(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id=SUBJECT_ID,
        field_name="eps",
        basis="three_year_average",
        provider_id=PROVIDER_ID,
        analysis_as_of=None,
        schema_version=1,
    )
    cache = InMemoryValuationCache(clock=_fixed_clock())
    cache.put(key, derived)
    provider = FakeProvider(facts=(_make_fact(),))
    resolver = _make_resolver(provider=provider, cache=cache)

    req = _make_request(field=ValuationField.EPS, basis="three_year_average")
    result = resolver.resolve(req)
    ri = result.resolved_input
    assert ri is not None
    assert ri.source_kind is SourceKind.CACHE
    assert ri.origin_source_kind is SourceKind.DERIVED
    assert ri.lineage is not None
    assert ri.lineage.transformation == "arithmetic_mean"
    assert len(ri.lineage.components) == 1
    assert provider.call_count == 0


# ===========================================================================
# 14. Cached original object is not mutated
# ===========================================================================


def test_cache_hit_does_not_mutate_stored_input() -> None:
    stored = _make_provider_input(field_name="eps", value=1.0)
    key = ValuationCacheKey(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id=SUBJECT_ID,
        field_name="eps",
        basis=None,
        provider_id=PROVIDER_ID,
        analysis_as_of=None,
        schema_version=1,
    )
    entry = ValuationCacheEntry(key=key, resolved_input=stored, cached_at=NOW)
    cache = SpyCache(entry=entry)
    resolver = _make_resolver(cache=cache)

    resolver.resolve(_make_request())
    # Stored object remains unchanged.
    assert stored.source_kind is SourceKind.PROVIDER
    assert stored.value == 1.0
    assert stored.origin_source_kind is None
    assert stored.cache_schema_version is None


# ===========================================================================
# 15. Cache miss falls through to provider
# ===========================================================================


def test_cache_miss_falls_through_to_provider() -> None:
    fact = _make_fact()
    provider = FakeProvider(facts=(fact,))
    cache = SpyCache(entry=None)
    resolver = _make_resolver(provider=provider, cache=cache)

    result = resolver.resolve(_make_request())
    assert result.status is CalculationStatus.OK
    assert provider.call_count == 1
    assert cache.get_count == 1


# ===========================================================================
# 16. Stale TTL entry falls through to provider
# ===========================================================================


def test_stale_ttl_entry_falls_through() -> None:
    # Cache with TTL shorter than the age of the entry.
    old_time = NOW - timedelta(hours=2)
    cache = InMemoryValuationCache(clock=_fixed_clock(), ttl=timedelta(hours=1))
    stored = _make_provider_input(field_name="eps", value=9.9)
    key = ValuationCacheKey(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id=SUBJECT_ID,
        field_name="eps",
        basis=None,
        provider_id=PROVIDER_ID,
        analysis_as_of=None,
        schema_version=1,
    )
    # Manually insert with a cached_at that is old relative to NOW.
    old_entry = ValuationCacheEntry(key=key, resolved_input=stored, cached_at=old_time)
    cache._store[key] = old_entry

    fact = _make_fact()
    provider = FakeProvider(facts=(fact,))
    resolver = _make_resolver(provider=provider, cache=cache)

    result = resolver.resolve(_make_request())
    assert result.status is CalculationStatus.OK
    assert provider.call_count == 1


# ===========================================================================
# 17. Historical cache entry with future available_at falls through
# ===========================================================================


def test_historical_cache_future_available_at_falls_through() -> None:
    # InMemoryValuationCache already treats this as a miss for historical keys.
    stored = _make_provider_input(
        field_name="eps",
        value=5.0,
        available_at=FUTURE_AVAILABLE,
        as_of=AS_OF,
    )
    key = ValuationCacheKey(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id=SUBJECT_ID,
        field_name="eps",
        basis=None,
        provider_id=PROVIDER_ID,
        analysis_as_of=AS_OF,
        schema_version=1,
    )
    cache = InMemoryValuationCache(clock=_fixed_clock())
    entry = ValuationCacheEntry(key=key, resolved_input=stored, cached_at=NOW)
    cache._store[key] = entry

    fact = _make_fact(available_at=AVAILABLE_AT)
    provider = FakeProvider(facts=(fact,))
    resolver = _make_resolver(provider=provider, cache=cache)

    result = resolver.resolve(_make_request(as_of=AS_OF))
    assert result.status is CalculationStatus.OK
    assert provider.call_count == 1


# ===========================================================================
# 18. Cache schema-version mismatch falls through to provider
# ===========================================================================


def test_schema_version_mismatch_falls_through() -> None:
    # Store under schema version 1, resolve with schema version 2.
    stored = _make_provider_input(field_name="eps", value=2.0)
    key_v1 = ValuationCacheKey(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id=SUBJECT_ID,
        field_name="eps",
        basis=None,
        provider_id=PROVIDER_ID,
        analysis_as_of=None,
        schema_version=1,
    )
    cache = InMemoryValuationCache(clock=_fixed_clock())
    entry = ValuationCacheEntry(key=key_v1, resolved_input=stored, cached_at=NOW)
    cache._store[key_v1] = entry

    fact = _make_fact()
    provider = FakeProvider(facts=(fact,))
    resolver = _make_resolver(provider=provider, cache=cache, schema_version=2)

    result = resolver.resolve(_make_request())
    assert result.status is CalculationStatus.OK
    assert provider.call_count == 1


# ===========================================================================
# 19. use_cache=False performs neither cache read nor cache write
# ===========================================================================


def test_use_cache_false_skips_cache() -> None:
    fact = _make_fact()
    provider = FakeProvider(facts=(fact,))
    cache = SpyCache()
    resolver = _make_resolver(provider=provider, cache=cache)

    result = resolver.resolve(_make_request(), use_cache=False)
    assert result.status is CalculationStatus.OK
    assert cache.get_count == 0
    assert cache.put_count == 0


# ===========================================================================
# 20. Provider success returns SourceKind.PROVIDER
# ===========================================================================


def test_provider_success_returns_provider_source() -> None:
    fact = _make_fact()
    provider = FakeProvider(facts=(fact,))
    resolver = _make_resolver(provider=provider)

    result = resolver.resolve(_make_request())
    assert result.status is CalculationStatus.OK
    ri = result.resolved_input
    assert ri is not None
    assert ri.source_kind is SourceKind.PROVIDER


# ===========================================================================
# 21. Provider success is cached only after validation
# ===========================================================================


def test_provider_success_cached_after_validation() -> None:
    fact = _make_fact()
    provider = FakeProvider(facts=(fact,))
    cache = SpyCache()
    resolver = _make_resolver(provider=provider, cache=cache)

    result = resolver.resolve(_make_request())
    assert result.status is CalculationStatus.OK
    assert cache.put_count == 1
    assert cache.last_put_input is not None
    assert cache.last_put_input.source_kind is SourceKind.PROVIDER


# ===========================================================================
# 22. Empty provider tuple -> INPUT_UNAVAILABLE
# ===========================================================================


def test_empty_provider_tuple_input_unavailable() -> None:
    provider = FakeProvider(facts=())
    resolver = _make_resolver(provider=provider)

    result = resolver.resolve(_make_request())
    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.resolved_input is None
    assert result.reason is not None


# ===========================================================================
# 23. ValuationProviderError -> PROVIDER_ERROR
# ===========================================================================


def test_provider_error_raises() -> None:
    provider = FakeProvider(facts=ValuationProviderError("synthetic failure"))
    resolver = _make_resolver(provider=provider)

    result = resolver.resolve(_make_request())
    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert result.resolved_input is None
    assert "synthetic failure" in (result.reason or "")


# ===========================================================================
# 24. Multiple provider facts -> PROVIDER_ERROR
# ===========================================================================


def test_multiple_facts_provider_error() -> None:
    f1 = _make_fact(value=1.0)
    f2 = _make_fact(value=2.0)
    provider = FakeProvider(facts=(f1, f2))
    resolver = _make_resolver(provider=provider)

    result = resolver.resolve(_make_request())
    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert result.resolved_input is None


# ===========================================================================
# 25. Mismatched provider subject -> PROVIDER_ERROR and no cache write
# ===========================================================================


def test_mismatched_subject_kind() -> None:
    # Request is EPS/SECURITY; fact is AAA_YIELD/MACRO (structurally valid but wrong subject).
    fact = _make_fact(
        field=ValuationField.CURRENT_AAA_YIELD,
        subject_kind=ValuationSubjectKind.MACRO,
        subject_id="macro-a",
        provider_field="synthetic_yield_field",
    )
    provider = FakeProvider(facts=(fact,))
    cache = SpyCache()
    resolver = _make_resolver(provider=provider, cache=cache)

    result = resolver.resolve(_make_request())
    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert cache.put_count == 0


def test_mismatched_subject_id() -> None:
    fact = _make_fact(subject_id="OTHER")
    provider = FakeProvider(facts=(fact,))
    cache = SpyCache()
    resolver = _make_resolver(provider=provider, cache=cache)

    result = resolver.resolve(_make_request())
    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert cache.put_count == 0


# ===========================================================================
# 26. Mismatched provider field -> PROVIDER_ERROR and no cache write
# ===========================================================================


def test_mismatched_field_name() -> None:
    fact = _make_fact(field=ValuationField.BVPS)
    provider = FakeProvider(facts=(fact,))
    cache = SpyCache()
    resolver = _make_resolver(provider=provider, cache=cache)

    result = resolver.resolve(_make_request(field=ValuationField.EPS))
    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert cache.put_count == 0


# ===========================================================================
# 27. Mismatched provider ID -> PROVIDER_ERROR and no cache write
# ===========================================================================


def test_mismatched_provider_id() -> None:
    fact = _make_fact(provider_id="provider-b")
    provider = FakeProvider(facts=(fact,))
    cache = SpyCache()
    resolver = _make_resolver(provider=provider, cache=cache)

    result = resolver.resolve(_make_request(provider_id=PROVIDER_ID))
    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert cache.put_count == 0


# ===========================================================================
# 28. Mismatched provider basis -> PROVIDER_ERROR and no cache write
# ===========================================================================


def test_mismatched_basis() -> None:
    fact = _make_fact(basis="wrong_basis")
    provider = FakeProvider(facts=(fact,))
    cache = SpyCache()
    resolver = _make_resolver(provider=provider, cache=cache)

    result = resolver.resolve(_make_request(basis="ttm"))
    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert cache.put_count == 0


# ===========================================================================
# 29. Historical provider fact with available_at=None -> INPUT_UNAVAILABLE, not cached
# ===========================================================================


def test_historical_fact_no_available_at() -> None:
    fact = _make_fact(available_at=None)
    provider = FakeProvider(facts=(fact,))
    cache = SpyCache()
    resolver = _make_resolver(provider=provider, cache=cache)

    result = resolver.resolve(_make_request(as_of=AS_OF))
    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert cache.put_count == 0


# ===========================================================================
# 30. Historical provider fact with available_at > as_of -> INPUT_UNAVAILABLE
# ===========================================================================


def test_historical_fact_future_available_at() -> None:
    fact = _make_fact(available_at=FUTURE_AVAILABLE)
    provider = FakeProvider(facts=(fact,))
    cache = SpyCache()
    resolver = _make_resolver(provider=provider, cache=cache)

    result = resolver.resolve(_make_request(as_of=AS_OF))
    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert cache.put_count == 0


# ===========================================================================
# 31. Historical provider fact with available_at <= as_of succeeds
# ===========================================================================


def test_historical_fact_available_at_before_as_of() -> None:
    fact = _make_fact(available_at=AVAILABLE_AT)
    provider = FakeProvider(facts=(fact,))
    cache = SpyCache()
    resolver = _make_resolver(provider=provider, cache=cache)

    result = resolver.resolve(_make_request(as_of=AS_OF))
    assert result.status is CalculationStatus.OK
    assert result.resolved_input is not None
    assert result.resolved_input.as_of == AS_OF
    assert cache.put_count == 1


# ===========================================================================
# 32. Current provider fact may have available_at=None
# ===========================================================================


def test_current_fact_no_available_at_ok() -> None:
    fact = _make_fact(available_at=None)
    provider = FakeProvider(facts=(fact,))
    resolver = _make_resolver(provider=provider)

    result = resolver.resolve(_make_request())
    assert result.status is CalculationStatus.OK
    assert result.resolved_input is not None
    assert result.resolved_input.available_at is None


# ===========================================================================
# 33. Current provider fact with future available_at -> INPUT_UNAVAILABLE
# ===========================================================================


def test_current_fact_future_available_at_rejected() -> None:
    fact = _make_fact(available_at=FUTURE_AVAILABLE)
    provider = FakeProvider(facts=(fact,))
    cache = SpyCache()
    resolver = _make_resolver(provider=provider, cache=cache)

    result = resolver.resolve(_make_request())
    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert cache.put_count == 0


# ===========================================================================
# 34. Current resolution preserves as_of=None
# ===========================================================================


def test_current_resolution_preserves_as_of_none() -> None:
    fact = _make_fact()
    provider = FakeProvider(facts=(fact,))
    resolver = _make_resolver(provider=provider)

    result = resolver.resolve(_make_request())
    ri = result.resolved_input
    assert ri is not None
    assert ri.as_of is None


# ===========================================================================
# 35. Provider success preserves all fact provenance fields in ResolvedInput
# ===========================================================================


def test_provider_success_preserves_provenance() -> None:
    fact = _make_fact(
        value=8.8,
        basis="ttm",
        provider_field=PROVIDER_FIELD,
        currency="USD",
        available_at=AVAILABLE_AT,
        retrieved_at=RETRIEVED_AT,
        observation_period_start=PERIOD_START,
        observation_period_end=PERIOD_END,
        observed_at=OBSERVED_AT,
        notes=("note-a", "note-b"),
    )
    provider = FakeProvider(facts=(fact,))
    resolver = _make_resolver(provider=provider)

    result = resolver.resolve(_make_request(basis="ttm"))
    ri = result.resolved_input
    assert ri is not None
    assert ri.value == 8.8
    assert ri.source_kind is SourceKind.PROVIDER
    assert ri.basis == "ttm"
    assert ri.units == "currency_per_share"
    assert ri.currency == "USD"
    assert ri.provider_id == PROVIDER_ID
    assert ri.provider_field == PROVIDER_FIELD
    assert ri.observation_period_start == PERIOD_START
    assert ri.observation_period_end == PERIOD_END
    assert ri.observed_at == OBSERVED_AT
    assert ri.available_at == AVAILABLE_AT
    assert ri.retrieved_at == RETRIEVED_AT
    assert ri.notes == ("note-a", "note-b")
    assert ri.resolved_at == NOW
    assert ri.as_of is None
    assert ri.lineage is None
    assert ri.origin_source_kind is None
    assert ri.cache_schema_version is None


# ===========================================================================
# 36. Missing/unavailable provider data never becomes numeric zero
# ===========================================================================


def test_unavailable_does_not_become_zero() -> None:
    provider = FakeProvider(facts=())
    resolver = _make_resolver(provider=provider)

    result = resolver.resolve(_make_request())
    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.resolved_input is None


# ===========================================================================
# 37. observation_count > 1 rejected before any override/cache/provider work
# ===========================================================================


def test_multi_observation_rejected_bare() -> None:
    provider = FakeProvider(facts=(_make_fact(),))
    resolver = _make_resolver(provider=provider)
    req = _make_request(field=ValuationField.EPS, observation_count=3)

    result = resolver.resolve(req)
    assert result.status is CalculationStatus.INVALID_INPUT
    assert result.resolved_input is None
    assert result.reason is not None
    assert provider.call_count == 0


def test_multi_observation_rejected_with_override() -> None:
    provider = FakeProvider(facts=(_make_fact(),))
    cache = SpyCache()
    resolver = _make_resolver(provider=provider, cache=cache)
    req = _make_request(field=ValuationField.EPS, observation_count=3)

    result = resolver.resolve(req, override=99.0)
    assert result.status is CalculationStatus.INVALID_INPUT
    assert result.resolved_input is None
    assert provider.call_count == 0
    assert cache.get_count == 0
    assert cache.put_count == 0


def test_multi_observation_rejected_with_cache() -> None:
    provider = FakeProvider(facts=(_make_fact(),))
    cache = SpyCache()
    resolver = _make_resolver(provider=provider, cache=cache)
    req = _make_request(field=ValuationField.EPS, observation_count=3)

    result = resolver.resolve(req)
    assert result.status is CalculationStatus.INVALID_INPUT
    assert result.resolved_input is None
    assert provider.call_count == 0
    assert cache.get_count == 0
    assert cache.put_count == 0


# ===========================================================================
# 38. Temporal cache: current request with future available_at falls through
# ===========================================================================


def test_current_cache_future_available_at_falls_through() -> None:
    """A cache entry whose available_at is later than the resolver clock is unusable."""
    stored = _make_provider_input(
        field_name="eps",
        value=5.5,
        available_at=FUTURE_AVAILABLE,  # 2026-01-01, after NOW (2025-07-01)
    )
    key = ValuationCacheKey(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id=SUBJECT_ID,
        field_name="eps",
        basis=None,
        provider_id=PROVIDER_ID,
        analysis_as_of=None,
        schema_version=1,
    )
    entry = ValuationCacheEntry(key=key, resolved_input=stored, cached_at=NOW)
    cache = SpyCache(entry=entry)
    # Provider returns an eligible fact (available_at is in the past).
    provider = FakeProvider(facts=(_make_fact(available_at=AVAILABLE_AT),))
    resolver = _make_resolver(provider=provider, cache=cache)

    result = resolver.resolve(_make_request())
    assert result.status is CalculationStatus.OK
    assert result.resolved_input is not None
    assert result.resolved_input.source_kind is SourceKind.PROVIDER
    assert provider.call_count == 1


# ===========================================================================
# 39. Temporal cache: historical request with available_at=None falls through
# ===========================================================================


def test_historical_cache_missing_available_at_falls_through() -> None:
    """A historical cache entry with available_at=None is unusable."""
    stored = _make_provider_input(
        field_name="eps",
        value=5.0,
        available_at=None,
        as_of=AS_OF,
    )
    key = ValuationCacheKey(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id=SUBJECT_ID,
        field_name="eps",
        basis=None,
        provider_id=PROVIDER_ID,
        analysis_as_of=AS_OF,
        schema_version=1,
    )
    cache = InMemoryValuationCache(clock=_fixed_clock())
    cache.put(key, stored)
    provider = FakeProvider(facts=(_make_fact(available_at=AVAILABLE_AT),))
    resolver = _make_resolver(provider=provider, cache=cache)

    result = resolver.resolve(_make_request(as_of=AS_OF))
    assert result.status is CalculationStatus.OK
    assert result.resolved_input is not None
    assert result.resolved_input.source_kind is SourceKind.PROVIDER
    assert provider.call_count == 1


# ===========================================================================
# 40. InputResolutionResult enforces status/value invariants
# ===========================================================================


def test_result_ok_requires_resolved_input() -> None:
    with pytest.raises(ValueError, match="resolved_input"):
        InputResolutionResult(status=CalculationStatus.OK)


def test_result_ok_rejects_reason() -> None:
    ri = ResolvedInput(
        field_name="eps",
        value=1.0,
        source_kind=SourceKind.OVERRIDE,
        resolved_at=NOW,
    )
    with pytest.raises(ValueError, match="reason"):
        InputResolutionResult(status=CalculationStatus.OK, resolved_input=ri, reason="bad")


def test_result_not_applicable_rejected() -> None:
    with pytest.raises(ValueError, match="NOT_APPLICABLE"):
        InputResolutionResult(status=CalculationStatus.NOT_APPLICABLE, reason="x")


def test_result_invalid_requires_none_input_and_reason() -> None:
    ri = ResolvedInput(
        field_name="eps",
        value=1.0,
        source_kind=SourceKind.OVERRIDE,
        resolved_at=NOW,
    )
    with pytest.raises(ValueError, match="resolved_input to be None"):
        InputResolutionResult(status=CalculationStatus.INVALID_INPUT, resolved_input=ri, reason="x")

    with pytest.raises(ValueError, match="non-empty reason"):
        InputResolutionResult(status=CalculationStatus.INVALID_INPUT, resolved_input=None, reason=None)


def test_result_input_unavailable_valid() -> None:
    r = InputResolutionResult(status=CalculationStatus.INPUT_UNAVAILABLE, resolved_input=None, reason="no data")
    assert r.status is CalculationStatus.INPUT_UNAVAILABLE


def test_result_provider_error_valid() -> None:
    r = InputResolutionResult(status=CalculationStatus.PROVIDER_ERROR, resolved_input=None, reason="failed")
    assert r.status is CalculationStatus.PROVIDER_ERROR


# ===========================================================================
# C2C: Three-year average EPS resolution
# ===========================================================================

FISCAL_YEAR = "fiscal_year"
THREE_YR_AVG = "three_year_average"

# Fixed fiscal-year period ends (newest to oldest)
FY2024_END = datetime(2024, 12, 31, tzinfo=UTC)
FY2023_END = datetime(2023, 12, 31, tzinfo=UTC)
FY2022_END = datetime(2022, 12, 31, tzinfo=UTC)
FY2021_END = datetime(2021, 12, 31, tzinfo=UTC)
FY2020_END = datetime(2020, 12, 31, tzinfo=UTC)

# Period starts (one year before end)
FY2024_START = datetime(2024, 1, 1, tzinfo=UTC)
FY2023_START = datetime(2023, 1, 1, tzinfo=UTC)
FY2022_START = datetime(2022, 1, 1, tzinfo=UTC)
FY2021_START = datetime(2021, 1, 1, tzinfo=UTC)
FY2020_START = datetime(2020, 1, 1, tzinfo=UTC)


def _fy_fact(  # noqa: PLR0913
    value: float,
    period_start: datetime,
    period_end: datetime,
    *,
    available_at: datetime | None = AVAILABLE_AT,
    retrieved_at: datetime = RETRIEVED_AT,
    provider_field: str = PROVIDER_FIELD,
    provider_id: str = PROVIDER_ID,
    currency: str = "USD",
    basis: str = FISCAL_YEAR,
) -> ProviderFact:
    """Build a fiscal-year EPS ProviderFact for C2C tests."""
    return ProviderFact(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id=SUBJECT_ID,
        field_name=ValuationField.EPS,
        value=value,
        units=ValuationUnit.CURRENCY_PER_SHARE,
        provider_id=provider_id,
        provider_field=provider_field,
        retrieved_at=retrieved_at,
        basis=basis,
        currency=currency,
        observation_period_start=period_start,
        observation_period_end=period_end,
        observed_at=None,
        available_at=available_at,
    )


def _c2c_request(
    as_of: datetime | None = None,
) -> ValuationFactRequest:
    """Build a valid C2C request: EPS, observation_count=3, basis=fiscal_year."""
    return ValuationFactRequest(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id=SUBJECT_ID,
        field_name=ValuationField.EPS,
        provider_id=PROVIDER_ID,
        basis=FISCAL_YEAR,
        as_of=as_of,
        observation_count=3,
    )


def _three_fy_facts() -> tuple[ProviderFact, ...]:
    """Three eligible fiscal-year facts (FY2022, FY2023, FY2024)."""
    return (
        _fy_fact(2.0, FY2022_START, FY2022_END),
        _fy_fact(3.0, FY2023_START, FY2023_END),
        _fy_fact(4.0, FY2024_START, FY2024_END),
    )


# ---------------------------------------------------------------------------
# Request validation
# ---------------------------------------------------------------------------


def test_c2c_wrong_field_rejected_before_cache_provider() -> None:
    """Wrong field_name => INVALID_INPUT before touching cache/provider."""
    provider = FakeProvider(facts=_three_fy_facts())
    cache = SpyCache()
    resolver = _make_resolver(provider=provider, cache=cache)
    req = ValuationFactRequest(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id=SUBJECT_ID,
        field_name=ValuationField.BVPS,
        provider_id=PROVIDER_ID,
        basis=FISCAL_YEAR,
        observation_count=1,
    )
    result = resolver.resolve_three_year_average_eps(req)
    assert result.status is CalculationStatus.INVALID_INPUT
    assert provider.call_count == 0
    assert cache.get_count == 0
    assert cache.put_count == 0


def test_c2c_wrong_observation_count_rejected() -> None:
    """observation_count != 3 => INVALID_INPUT."""
    provider = FakeProvider(facts=_three_fy_facts())
    cache = SpyCache()
    resolver = _make_resolver(provider=provider, cache=cache)
    req = ValuationFactRequest(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id=SUBJECT_ID,
        field_name=ValuationField.EPS,
        provider_id=PROVIDER_ID,
        basis=FISCAL_YEAR,
        observation_count=2,
    )
    result = resolver.resolve_three_year_average_eps(req)
    assert result.status is CalculationStatus.INVALID_INPUT
    assert provider.call_count == 0
    assert cache.get_count == 0
    assert cache.put_count == 0


def test_c2c_wrong_basis_rejected() -> None:
    """Basis != 'fiscal_year' => INVALID_INPUT."""
    provider = FakeProvider(facts=_three_fy_facts())
    cache = SpyCache()
    resolver = _make_resolver(provider=provider, cache=cache)
    req = ValuationFactRequest(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id=SUBJECT_ID,
        field_name=ValuationField.EPS,
        provider_id=PROVIDER_ID,
        basis="ttm",
        observation_count=3,
    )
    result = resolver.resolve_three_year_average_eps(req)
    assert result.status is CalculationStatus.INVALID_INPUT
    assert provider.call_count == 0
    assert cache.get_count == 0
    assert cache.put_count == 0


# ---------------------------------------------------------------------------
# Empty / insufficient eligible periods
# ---------------------------------------------------------------------------


def test_c2c_empty_provider_input_unavailable() -> None:
    """Empty provider tuple => INPUT_UNAVAILABLE."""
    provider = FakeProvider(facts=())
    resolver = _make_resolver(provider=provider)
    result = resolver.resolve_three_year_average_eps(_c2c_request())
    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.resolved_input is None


def test_c2c_two_eligible_periods_input_unavailable() -> None:
    """Only 2 distinct eligible periods => INPUT_UNAVAILABLE."""
    facts = (
        _fy_fact(2.0, FY2023_START, FY2023_END),
        _fy_fact(3.0, FY2024_START, FY2024_END),
    )
    provider = FakeProvider(facts=facts)
    resolver = _make_resolver(provider=provider)
    result = resolver.resolve_three_year_average_eps(_c2c_request())
    assert result.status is CalculationStatus.INPUT_UNAVAILABLE


def test_c2c_one_eligible_period_input_unavailable() -> None:
    """Only 1 distinct eligible period => INPUT_UNAVAILABLE."""
    facts = (_fy_fact(2.0, FY2024_START, FY2024_END),)
    provider = FakeProvider(facts=facts)
    resolver = _make_resolver(provider=provider)
    result = resolver.resolve_three_year_average_eps(_c2c_request())
    assert result.status is CalculationStatus.INPUT_UNAVAILABLE


# ---------------------------------------------------------------------------
# Selection: >3 observations selects latest 3
# ---------------------------------------------------------------------------


def test_c2c_five_observations_selects_latest_three() -> None:
    """5 observations => selects FY2022, FY2023, FY2024 (not FY2020, FY2021)."""
    facts = (
        _fy_fact(1.0, FY2020_START, FY2020_END),
        _fy_fact(1.5, FY2021_START, FY2021_END),
        _fy_fact(2.0, FY2022_START, FY2022_END),
        _fy_fact(3.0, FY2023_START, FY2023_END),
        _fy_fact(4.0, FY2024_START, FY2024_END),
    )
    provider = FakeProvider(facts=facts)
    resolver = _make_resolver(provider=provider)
    result = resolver.resolve_three_year_average_eps(_c2c_request())
    assert result.status is CalculationStatus.OK
    ri = result.resolved_input
    assert ri is not None
    # Mean of 2.0, 3.0, 4.0 = 3.0
    assert ri.value == pytest.approx(3.0)
    assert ri.observation_period_start == FY2022_START
    assert ri.observation_period_end == FY2024_END


# ---------------------------------------------------------------------------
# Scrambled tuple order does not affect result
# ---------------------------------------------------------------------------


def test_c2c_scrambled_order_same_result() -> None:
    """Provider returns facts in arbitrary order; result is deterministic."""
    facts = (
        _fy_fact(4.0, FY2024_START, FY2024_END),
        _fy_fact(2.0, FY2022_START, FY2022_END),
        _fy_fact(3.0, FY2023_START, FY2023_END),
    )
    provider = FakeProvider(facts=facts)
    resolver = _make_resolver(provider=provider)
    result = resolver.resolve_three_year_average_eps(_c2c_request())
    assert result.status is CalculationStatus.OK
    ri = result.resolved_input
    assert ri is not None
    assert ri.value == pytest.approx(3.0)
    # Components ordered oldest -> newest
    assert ri.lineage is not None
    comps = ri.lineage.components
    assert len(comps) == 3
    assert comps[0].value == 2.0  # oldest (FY2022)
    assert comps[1].value == 3.0  # middle (FY2023)
    assert comps[2].value == 4.0  # newest (FY2024)


# ---------------------------------------------------------------------------
# Temporal eligibility
# ---------------------------------------------------------------------------


def test_c2c_historical_look_ahead_fact_excluded() -> None:
    """For historical request (as_of=2024-06-30), FY2024 (end=2024-12-31) is excluded."""
    as_of = datetime(2024, 6, 30, tzinfo=UTC)
    hist_avail = datetime(2024, 3, 1, tzinfo=UTC)  # available before as_of
    facts = (
        _fy_fact(2.0, FY2022_START, FY2022_END, available_at=hist_avail),
        _fy_fact(3.0, FY2023_START, FY2023_END, available_at=hist_avail),
        _fy_fact(4.0, FY2024_START, FY2024_END, available_at=hist_avail),  # period_end > as_of: ineligible
        _fy_fact(1.0, FY2021_START, FY2021_END, available_at=hist_avail),  # needed as 3rd eligible
    )
    provider = FakeProvider(facts=facts)
    resolver = _make_resolver(provider=provider)
    req = _c2c_request(as_of=as_of)
    result = resolver.resolve_three_year_average_eps(req)
    assert result.status is CalculationStatus.OK
    ri = result.resolved_input
    assert ri is not None
    # Should use FY2021, FY2022, FY2023 (not FY2024)
    assert ri.value == pytest.approx((1.0 + 2.0 + 3.0) / 3.0)
    assert ri.observation_period_end == FY2023_END


def test_c2c_current_future_dated_fact_excluded() -> None:
    """Current request: fact with available_at > resolver_now is excluded."""
    future_avail = NOW + timedelta(days=1)
    facts = (
        _fy_fact(2.0, FY2022_START, FY2022_END),
        _fy_fact(3.0, FY2023_START, FY2023_END),
        _fy_fact(4.0, FY2024_START, FY2024_END, available_at=future_avail),  # excluded
        _fy_fact(1.0, FY2021_START, FY2021_END),  # 3rd eligible
    )
    provider = FakeProvider(facts=facts)
    resolver = _make_resolver(provider=provider)
    result = resolver.resolve_three_year_average_eps(_c2c_request())
    assert result.status is CalculationStatus.OK
    ri = result.resolved_input
    assert ri is not None
    # Should use FY2021, FY2022, FY2023
    assert ri.value == pytest.approx((1.0 + 2.0 + 3.0) / 3.0)


# ---------------------------------------------------------------------------
# Duplicates
# ---------------------------------------------------------------------------


def test_c2c_duplicate_in_selected_period_provider_error() -> None:
    """Two candidates with same period_end in a selected period => PROVIDER_ERROR."""
    facts = (
        _fy_fact(2.0, FY2022_START, FY2022_END),
        _fy_fact(3.0, FY2023_START, FY2023_END),
        _fy_fact(4.0, FY2024_START, FY2024_END),
        _fy_fact(9.9, FY2024_START, FY2024_END),  # duplicate in selected period
    )
    provider = FakeProvider(facts=facts)
    resolver = _make_resolver(provider=provider)
    result = resolver.resolve_three_year_average_eps(_c2c_request())
    assert result.status is CalculationStatus.PROVIDER_ERROR


def test_c2c_duplicate_in_unselected_period_harmless() -> None:
    """Duplicate in an older, unselected period does not invalidate the result."""
    facts = (
        _fy_fact(2.0, FY2022_START, FY2022_END),
        _fy_fact(3.0, FY2023_START, FY2023_END),
        _fy_fact(4.0, FY2024_START, FY2024_END),
        _fy_fact(1.0, FY2021_START, FY2021_END),
        _fy_fact(0.5, FY2021_START, FY2021_END),  # duplicate in unselected period
    )
    provider = FakeProvider(facts=facts)
    resolver = _make_resolver(provider=provider)
    result = resolver.resolve_three_year_average_eps(_c2c_request())
    assert result.status is CalculationStatus.OK
    ri = result.resolved_input
    assert ri is not None
    # Uses FY2022, FY2023, FY2024
    assert ri.value == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# Selected-series compatibility
# ---------------------------------------------------------------------------


def test_c2c_incompatible_provider_field_provider_error() -> None:
    """Incompatible provider_field in selected facts => PROVIDER_ERROR."""
    facts = (
        _fy_fact(2.0, FY2022_START, FY2022_END),
        _fy_fact(3.0, FY2023_START, FY2023_END),
        _fy_fact(4.0, FY2024_START, FY2024_END, provider_field="other_field"),
    )
    provider = FakeProvider(facts=facts)
    resolver = _make_resolver(provider=provider)
    result = resolver.resolve_three_year_average_eps(_c2c_request())
    assert result.status is CalculationStatus.PROVIDER_ERROR


def test_c2c_incompatible_currency_provider_error() -> None:
    """Incompatible currency in selected facts => PROVIDER_ERROR."""
    facts = (
        _fy_fact(2.0, FY2022_START, FY2022_END),
        _fy_fact(3.0, FY2023_START, FY2023_END),
        _fy_fact(4.0, FY2024_START, FY2024_END, currency="EUR"),
    )
    provider = FakeProvider(facts=facts)
    resolver = _make_resolver(provider=provider)
    result = resolver.resolve_three_year_average_eps(_c2c_request())
    assert result.status is CalculationStatus.PROVIDER_ERROR


# ---------------------------------------------------------------------------
# Arithmetic mean and lineage
# ---------------------------------------------------------------------------


def test_c2c_mean_and_lineage_correct() -> None:
    """Mean of 2.0, 3.0, 4.0 = 3.0; lineage has 3 components oldest->newest."""
    facts = _three_fy_facts()
    provider = FakeProvider(facts=facts)
    resolver = _make_resolver(provider=provider)
    result = resolver.resolve_three_year_average_eps(_c2c_request())
    assert result.status is CalculationStatus.OK
    ri = result.resolved_input
    assert ri is not None
    assert ri.value == pytest.approx(3.0)
    assert ri.source_kind is SourceKind.DERIVED
    assert ri.lineage is not None
    assert ri.lineage.transformation == "arithmetic_mean"
    comps = ri.lineage.components
    assert len(comps) == 3
    assert comps[0].observation_period_end == FY2022_END
    assert comps[1].observation_period_end == FY2023_END
    assert comps[2].observation_period_end == FY2024_END
    assert comps[0].source_kind is SourceKind.PROVIDER


# ---------------------------------------------------------------------------
# Derived temporal/retrieval metadata
# ---------------------------------------------------------------------------


def test_c2c_derived_metadata_correct() -> None:
    """Derived result has correct temporal metadata."""
    # Use distinct retrieved_at and available_at per fact
    ret_a = datetime(2025, 1, 1, tzinfo=UTC)
    ret_b = datetime(2025, 2, 1, tzinfo=UTC)
    ret_c = datetime(2025, 3, 1, tzinfo=UTC)
    avail_a = datetime(2024, 1, 1, tzinfo=UTC)
    avail_b = datetime(2024, 6, 1, tzinfo=UTC)
    avail_c = datetime(2025, 1, 1, tzinfo=UTC)

    facts = (
        _fy_fact(2.0, FY2022_START, FY2022_END, retrieved_at=ret_a, available_at=avail_a),
        _fy_fact(3.0, FY2023_START, FY2023_END, retrieved_at=ret_b, available_at=avail_b),
        _fy_fact(4.0, FY2024_START, FY2024_END, retrieved_at=ret_c, available_at=avail_c),
    )
    provider = FakeProvider(facts=facts)
    resolver = _make_resolver(provider=provider)
    result = resolver.resolve_three_year_average_eps(_c2c_request())
    assert result.status is CalculationStatus.OK
    ri = result.resolved_input
    assert ri is not None
    # observation_period_start = oldest component start (FY2022_START)
    assert ri.observation_period_start == FY2022_START
    # observation_period_end = newest component end (FY2024_END)
    assert ri.observation_period_end == FY2024_END
    # available_at = max(all available_at) since all are present
    assert ri.available_at == avail_c
    # retrieved_at = max(all retrieved_at)
    assert ri.retrieved_at == ret_c
    # observed_at = None
    assert ri.observed_at is None
    # as_of = request.as_of (None for current)
    assert ri.as_of is None
    # basis
    assert ri.basis == THREE_YR_AVG
    # field_name
    assert ri.field_name == "eps"
    # source_kind
    assert ri.source_kind is SourceKind.DERIVED


def test_c2c_derived_available_at_none_when_any_missing() -> None:
    """If any component lacks available_at, derived available_at is None."""
    facts = (
        _fy_fact(2.0, FY2022_START, FY2022_END, available_at=AVAILABLE_AT),
        _fy_fact(3.0, FY2023_START, FY2023_END, available_at=None),  # missing
        _fy_fact(4.0, FY2024_START, FY2024_END, available_at=AVAILABLE_AT),
    )
    provider = FakeProvider(facts=facts)
    resolver = _make_resolver(provider=provider)
    result = resolver.resolve_three_year_average_eps(_c2c_request())
    assert result.status is CalculationStatus.OK
    ri = result.resolved_input
    assert ri is not None
    assert ri.available_at is None


# ---------------------------------------------------------------------------
# Zero/negative EPS
# ---------------------------------------------------------------------------


def test_c2c_zero_eps_valid() -> None:
    """Zero EPS values are valid resolver inputs."""
    facts = (
        _fy_fact(0.0, FY2022_START, FY2022_END),
        _fy_fact(2.0, FY2023_START, FY2023_END),
        _fy_fact(3.0, FY2024_START, FY2024_END),
    )
    provider = FakeProvider(facts=facts)
    resolver = _make_resolver(provider=provider)
    result = resolver.resolve_three_year_average_eps(_c2c_request())
    assert result.status is CalculationStatus.OK
    ri = result.resolved_input
    assert ri is not None
    assert ri.value == pytest.approx(5.0 / 3.0)


def test_c2c_negative_eps_valid() -> None:
    """Negative EPS values are valid resolver inputs."""
    facts = (
        _fy_fact(-2.0, FY2022_START, FY2022_END),
        _fy_fact(1.0, FY2023_START, FY2023_END),
        _fy_fact(0.0, FY2024_START, FY2024_END),
    )
    provider = FakeProvider(facts=facts)
    resolver = _make_resolver(provider=provider)
    result = resolver.resolve_three_year_average_eps(_c2c_request())
    assert result.status is CalculationStatus.OK
    ri = result.resolved_input
    assert ri is not None
    assert ri.value == pytest.approx(-1.0 / 3.0)


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------


def test_c2c_derived_cache_hit() -> None:
    """A later call hits the derived cache and returns CACHE source."""
    facts = _three_fy_facts()
    provider = FakeProvider(facts=facts)
    cache = InMemoryValuationCache(clock=_fixed_clock())
    resolver = _make_resolver(provider=provider, cache=cache)

    # First call: miss -> provider -> cache write
    result1 = resolver.resolve_three_year_average_eps(_c2c_request())
    assert result1.status is CalculationStatus.OK
    ri1 = result1.resolved_input
    assert ri1 is not None
    assert ri1.source_kind is SourceKind.DERIVED
    assert provider.call_count == 1

    # Second call: hit -> CACHE source
    result2 = resolver.resolve_three_year_average_eps(_c2c_request())
    assert result2.status is CalculationStatus.OK
    ri2 = result2.resolved_input
    assert ri2 is not None
    assert ri2.source_kind is SourceKind.CACHE
    assert ri2.origin_source_kind is SourceKind.DERIVED
    assert ri2.value == pytest.approx(3.0)
    assert provider.call_count == 1  # no second provider call
    # Cache hit preserves lineage
    assert ri2.lineage is not None
    assert ri2.lineage.transformation == "arithmetic_mean"


def test_c2c_use_cache_false_skips_both() -> None:
    """use_cache=False skips both cache get and put."""
    facts = _three_fy_facts()
    provider = FakeProvider(facts=facts)
    cache = SpyCache()
    resolver = _make_resolver(provider=provider, cache=cache)
    result = resolver.resolve_three_year_average_eps(_c2c_request(), use_cache=False)
    assert result.status is CalculationStatus.OK
    assert cache.get_count == 0
    assert cache.put_count == 0


def test_c2c_provider_error_never_caches() -> None:
    """Provider error => no cache write."""
    provider = FakeProvider(facts=ValuationProviderError("synthetic failure"))
    cache = SpyCache()
    resolver = _make_resolver(provider=provider, cache=cache)
    result = resolver.resolve_three_year_average_eps(_c2c_request())
    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert cache.put_count == 0


# ===========================================================================
# C2D: Method-level input assembly
# ===========================================================================


class MultiFieldProvider:
    """Provider fake that dispatches facts by semantic field name.

    Records every request so tests can assert which fields were requested.
    """

    def __init__(self, *, handlers: dict[ValuationField, tuple[ProviderFact, ...]] | None = None) -> None:
        """Initialize the fake with optional per-field fact handlers."""
        self._handlers: dict[ValuationField, tuple[ProviderFact, ...]] = handlers or {}
        self.requests: list[ValuationFactRequest] = []
        self.call_count = 0

    def fetch_facts(self, request: ValuationFactRequest) -> tuple[ProviderFact, ...]:
        self.call_count += 1
        self.requests.append(request)
        return self._handlers.get(request.field_name, ())

    def requested_fields(self) -> list[ValuationField]:
        """Return the list of ValuationField values requested in order."""
        return [r.field_name for r in self.requests]


def _bvps_fact(value: float = 50.0) -> ProviderFact:
    return ProviderFact(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id=SUBJECT_ID,
        field_name=ValuationField.BVPS,
        value=value,
        units=ValuationUnit.CURRENCY_PER_SHARE,
        provider_id=PROVIDER_ID,
        provider_field="bvps_synthetic",
        retrieved_at=RETRIEVED_AT,
        basis=None,
        currency="USD",
    )


def _price_fact(value: float = 100.0) -> ProviderFact:
    return ProviderFact(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id=SUBJECT_ID,
        field_name=ValuationField.CURRENT_PRICE,
        value=value,
        units=ValuationUnit.CURRENCY_PER_SHARE,
        provider_id=PROVIDER_ID,
        provider_field="price_synthetic",
        retrieved_at=RETRIEVED_AT,
        basis=None,
        currency="USD",
        observed_at=OBSERVED_AT,
    )


def _aaa_fact(value: float = 5.0) -> ProviderFact:
    return ProviderFact(
        subject_kind=ValuationSubjectKind.MACRO,
        subject_id="AAA",
        field_name=ValuationField.CURRENT_AAA_YIELD,
        value=value,
        units=ValuationUnit.PERCENTAGE_POINTS,
        provider_id="provider-aaa",
        provider_field="aaa_synthetic",
        retrieved_at=RETRIEVED_AT,
        basis=None,
    )


def _ttm_eps_fact(value: float = 8.0) -> ProviderFact:
    return ProviderFact(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id=SUBJECT_ID,
        field_name=ValuationField.EPS,
        value=value,
        units=ValuationUnit.CURRENCY_PER_SHARE,
        provider_id=PROVIDER_ID,
        provider_field="ttm_eps_synthetic",
        retrieved_at=RETRIEVED_AT,
        basis="ttm",
        currency="USD",
    )


# ---------------------------------------------------------------------------
# Test 1: Graham Number succeeds with three-year-average EPS + BVPS + quote
# ---------------------------------------------------------------------------


def test_c2d_graham_number_three_year_avg_success() -> None:
    """Graham Number: three-year-avg EPS (provider) + BVPS (provider) + quote (provider) → OK."""
    provider = MultiFieldProvider(
        handlers={
            ValuationField.EPS: _three_fy_facts(),
            ValuationField.BVPS: (_bvps_fact(),),
            ValuationField.CURRENT_PRICE: (_price_fact(),),
        }
    )
    resolver = InputResolver(provider=provider, clock=lambda: NOW)
    result = resolver.assemble_graham_number(
        security_subject_id=SUBJECT_ID,
        security_provider_id=PROVIDER_ID,
    )
    assert result.status is CalculationStatus.OK
    assert result.method is GrahamMethod.NUMBER
    assert result.eps is not None
    assert result.eps.value == pytest.approx(3.0)  # mean of 2.0, 3.0, 4.0
    assert result.eps.basis == "three_year_average"
    assert result.bvps is not None
    assert result.bvps.value == 50.0
    assert result.current_price is not None
    assert result.current_price.value == 100.0
    assert result.quote_status is None
    assert result.quote_reason is None
    assert result.reason is None


# ---------------------------------------------------------------------------
# Test 2: TTM EPS override bypasses EPS provider access
# ---------------------------------------------------------------------------


def test_c2d_graham_number_ttm_override_bypasses_eps_provider() -> None:
    """TTM EPS override short-circuits provider; basis retained in provenance."""
    # No EPS handler registered — provider would return empty if called.
    provider = MultiFieldProvider(
        handlers={
            ValuationField.BVPS: (_bvps_fact(),),
            ValuationField.CURRENT_PRICE: (_price_fact(),),
        }
    )
    resolver = InputResolver(provider=provider, clock=lambda: NOW)
    result = resolver.assemble_graham_number(
        security_subject_id=SUBJECT_ID,
        security_provider_id=PROVIDER_ID,
        eps_basis="ttm",
        eps_override=10.0,
    )
    assert result.status is CalculationStatus.OK
    assert result.eps is not None
    assert result.eps.value == 10.0
    assert result.eps.source_kind is SourceKind.OVERRIDE
    assert result.eps.basis == "ttm"
    # EPS field must never have reached the provider.
    assert ValuationField.EPS not in provider.requested_fields()


# ---------------------------------------------------------------------------
# Test 3: Required Graham Number failure prevents quote resolution
# ---------------------------------------------------------------------------


def test_c2d_graham_number_bvps_failure_prevents_quote() -> None:
    """BVPS unavailable → assembly INPUT_UNAVAILABLE; quote never requested."""
    provider = MultiFieldProvider(
        handlers={
            ValuationField.EPS: _three_fy_facts(),
            ValuationField.BVPS: (),  # empty → INPUT_UNAVAILABLE
            # No CURRENT_PRICE handler: would return empty if called.
        }
    )
    resolver = InputResolver(provider=provider, clock=lambda: NOW)
    result = resolver.assemble_graham_number(
        security_subject_id=SUBJECT_ID,
        security_provider_id=PROVIDER_ID,
    )
    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.eps is not None  # EPS resolved before BVPS failed
    assert result.bvps is None
    assert result.current_price is None
    assert "bvps" in (result.reason or "")
    assert ValuationField.CURRENT_PRICE not in provider.requested_fields()


# ---------------------------------------------------------------------------
# Test 4: Growth method succeeds with explicit basis + growth + AAA + quote
# ---------------------------------------------------------------------------


def test_c2d_growth_value_success() -> None:
    """Growth Value: TTM EPS (provider) + growth 12 + AAA 5 + quote 100 → OK."""
    provider = MultiFieldProvider(
        handlers={
            ValuationField.EPS: (_ttm_eps_fact(),),
            ValuationField.CURRENT_AAA_YIELD: (_aaa_fact(),),
            ValuationField.CURRENT_PRICE: (_price_fact(),),
        }
    )
    resolver = InputResolver(provider=provider, clock=lambda: NOW)
    result = resolver.assemble_growth_value(
        security_subject_id=SUBJECT_ID,
        security_provider_id=PROVIDER_ID,
        eps_basis="ttm",
        expected_growth=12.0,
        aaa_subject_id="AAA",
        aaa_provider_id="provider-aaa",
    )
    assert result.status is CalculationStatus.OK
    assert result.method is GrahamMethod.GROWTH_VALUE
    # EPS
    assert result.eps is not None
    assert result.eps.value == 8.0
    assert result.eps.basis == "ttm"
    # Expected growth
    assert result.expected_growth is not None
    assert result.expected_growth.value == 12.0
    assert result.expected_growth.source_kind is SourceKind.OVERRIDE
    assert result.expected_growth.units == "percentage_points"
    # AAA yield
    assert result.current_aaa_yield is not None
    assert result.current_aaa_yield.value == 5.0
    # Quote
    assert result.current_price is not None
    assert result.current_price.value == 100.0
    assert result.quote_status is None
    assert result.quote_reason is None
    assert result.reason is None


# ---------------------------------------------------------------------------
# Test 5: Missing expected growth → INPUT_UNAVAILABLE
# ---------------------------------------------------------------------------


def test_c2d_growth_value_missing_growth() -> None:
    """expected_growth not provided → INPUT_UNAVAILABLE; AAA and quote never reached."""
    provider = MultiFieldProvider(
        handlers={
            ValuationField.EPS: (_ttm_eps_fact(),),
            # No AAA or quote handlers
        }
    )
    resolver = InputResolver(provider=provider, clock=lambda: NOW)
    result = resolver.assemble_growth_value(
        security_subject_id=SUBJECT_ID,
        security_provider_id=PROVIDER_ID,
        eps_basis="ttm",
        # expected_growth intentionally omitted (defaults to None)
        aaa_subject_id="AAA",
        aaa_provider_id="provider-aaa",
    )
    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert "expected_growth" in (result.reason or "")
    assert result.current_aaa_yield is None
    assert result.current_price is None
    # AAA and quote must never have been requested.
    assert ValuationField.CURRENT_AAA_YIELD not in provider.requested_fields()
    assert ValuationField.CURRENT_PRICE not in provider.requested_fields()


# ---------------------------------------------------------------------------
# Test 6: Non-finite expected growth → INVALID_INPUT
# ---------------------------------------------------------------------------


def test_c2d_growth_value_non_finite_growth() -> None:
    """expected_growth=inf → INVALID_INPUT; AAA and quote never reached."""
    provider = MultiFieldProvider(
        handlers={
            ValuationField.EPS: (_ttm_eps_fact(),),
        }
    )
    resolver = InputResolver(provider=provider, clock=lambda: NOW)
    result = resolver.assemble_growth_value(
        security_subject_id=SUBJECT_ID,
        security_provider_id=PROVIDER_ID,
        eps_basis="ttm",
        expected_growth=inf,
        aaa_subject_id="AAA",
        aaa_provider_id="provider-aaa",
    )
    assert result.status is CalculationStatus.INVALID_INPUT
    assert "expected_growth" in (result.reason or "")
    assert ValuationField.CURRENT_AAA_YIELD not in provider.requested_fields()
    assert ValuationField.CURRENT_PRICE not in provider.requested_fields()


# ---------------------------------------------------------------------------
# Test 7: Quote unavailable → assembly still OK, no current_price
# ---------------------------------------------------------------------------


def test_c2d_graham_number_quote_unavailable_still_ok() -> None:
    """Quote unavailable → assembly OK, current_price=None, quote_status preserved."""
    provider = MultiFieldProvider(
        handlers={
            ValuationField.EPS: _three_fy_facts(),
            ValuationField.BVPS: (_bvps_fact(),),
            ValuationField.CURRENT_PRICE: (),  # empty → INPUT_UNAVAILABLE
        }
    )
    resolver = InputResolver(provider=provider, clock=lambda: NOW)
    result = resolver.assemble_graham_number(
        security_subject_id=SUBJECT_ID,
        security_provider_id=PROVIDER_ID,
    )
    assert result.status is CalculationStatus.OK
    assert result.eps is not None
    assert result.bvps is not None
    assert result.current_price is None
    assert result.quote_status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.quote_reason is not None
    assert result.reason is None


# ---------------------------------------------------------------------------
# C2C corrective-pass regression tests
# ---------------------------------------------------------------------------


def test_c2c_provider_origin_cache_entry_falls_through() -> None:
    """A PROVIDER-origin entry at the derived cache key is rejected; resolver calls provider."""
    # Seed the derived key with a legal PROVIDER-origin EPS input having basis="three_year_average".
    poisoned_entry = _make_provider_input(
        field_name="eps",
        value=9.99,
        basis="three_year_average",
        provider_field=None,
    )
    derived_key = ValuationCacheKey(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id=SUBJECT_ID,
        field_name="eps",
        basis="three_year_average",
        provider_id=PROVIDER_ID,
        analysis_as_of=None,
        schema_version=1,
    )
    entry = ValuationCacheEntry(key=derived_key, resolved_input=poisoned_entry, cached_at=NOW)
    cache = SpyCache(entry=entry)

    # Provider returns valid 3-year facts.
    facts = (
        _fy_fact(2.0, FY2022_START, FY2022_END),
        _fy_fact(3.0, FY2023_START, FY2023_END),
        _fy_fact(4.0, FY2024_START, FY2024_END),
    )
    provider = FakeProvider(facts=facts)
    resolver = _make_resolver(provider=provider, cache=cache)

    result = resolver.resolve_three_year_average_eps(_c2c_request())
    assert result.status is CalculationStatus.OK
    assert provider.call_count == 1
    ri = result.resolved_input
    assert ri is not None
    assert ri.source_kind is SourceKind.DERIVED
    assert ri.value == pytest.approx(3.0)
    assert ri.provider_id == PROVIDER_ID


def test_c2c_derived_result_preserves_provider_id() -> None:
    """Fresh derived result has provider_id == request.provider_id."""
    facts = (
        _fy_fact(2.0, FY2022_START, FY2022_END),
        _fy_fact(3.0, FY2023_START, FY2023_END),
        _fy_fact(4.0, FY2024_START, FY2024_END),
    )
    provider = FakeProvider(facts=facts)
    cache = SpyCache()
    resolver = _make_resolver(provider=provider, cache=cache)
    result = resolver.resolve_three_year_average_eps(_c2c_request())
    assert result.status is CalculationStatus.OK
    ri = result.resolved_input
    assert ri is not None
    assert ri.provider_id == PROVIDER_ID
    assert ri.provider_field is None


def test_c2c_cache_hit_preserves_provider_id() -> None:
    """A cache hit on the derived key preserves provider_id from the stored entry."""
    # First resolve to populate cache (use real in-memory cache).
    facts = (
        _fy_fact(2.0, FY2022_START, FY2022_END),
        _fy_fact(3.0, FY2023_START, FY2023_END),
        _fy_fact(4.0, FY2024_START, FY2024_END),
    )
    provider = FakeProvider(facts=facts)
    cache = InMemoryValuationCache(clock=_fixed_clock())
    resolver = _make_resolver(provider=provider, cache=cache)
    resolver.resolve_three_year_average_eps(_c2c_request())

    # Second resolve should hit cache.
    result2 = resolver.resolve_three_year_average_eps(_c2c_request())
    assert result2.status is CalculationStatus.OK
    ri2 = result2.resolved_input
    assert ri2 is not None
    assert ri2.source_kind is SourceKind.CACHE
    assert ri2.origin_source_kind is SourceKind.DERIVED
    assert ri2.provider_id == PROVIDER_ID


def test_c2c_historical_publication_date_lookahead_excluded() -> None:
    """Historical request: candidate with available_at > as_of is excluded before selection."""
    as_of = datetime(2024, 6, 30, tzinfo=UTC)
    # Look-ahead candidate: period_end=2024-03-31 (<= as_of) but available_at=2024-08-01 (> as_of)
    # => excluded by publication date, NOT by period-end eligibility
    # FY2021, FY2022, FY2023 are the three eligible facts
    look_start = datetime(2023, 4, 1, tzinfo=UTC)
    look_end = datetime(2024, 3, 31, tzinfo=UTC)
    facts = (
        _fy_fact(1.0, FY2021_START, FY2021_END, available_at=datetime(2022, 5, 1, tzinfo=UTC)),
        _fy_fact(2.0, FY2022_START, FY2022_END, available_at=datetime(2023, 5, 1, tzinfo=UTC)),
        _fy_fact(3.0, FY2023_START, FY2023_END, available_at=datetime(2024, 5, 1, tzinfo=UTC)),
        _fy_fact(99.0, look_start, look_end, available_at=datetime(2024, 8, 1, tzinfo=UTC)),  # lookahead
    )
    provider = FakeProvider(facts=facts)
    resolver = _make_resolver(provider=provider)
    req = _c2c_request(as_of=as_of)
    result = resolver.resolve_three_year_average_eps(req)
    assert result.status is CalculationStatus.OK
    ri = result.resolved_input
    assert ri is not None
    # Should be mean of 1.0, 2.0, 3.0 = 2.0 (the 99.0 candidate excluded)
    assert ri.value == pytest.approx(2.0)
    # Oldest -> newest lineage
    assert ri.lineage is not None
    assert len(ri.lineage.components) == 3
    assert ri.lineage.components[0].value == pytest.approx(1.0)
    assert ri.lineage.components[1].value == pytest.approx(2.0)
    assert ri.lineage.components[2].value == pytest.approx(3.0)


def test_c2c_current_incomplete_fiscal_period_excluded() -> None:
    """Current request: candidate with observation_period_end > resolver_now is excluded."""
    # resolver_now = NOW (2025-07-01)
    # FY2024 ends 2024-12-31 (<= NOW) => eligible
    # FY2025 ends 2025-09-30 (> NOW) => excluded by period-end
    # FY2023, FY2022 are eligible
    future_end = datetime(2025, 9, 30, tzinfo=UTC)
    future_start = datetime(2024, 10, 1, tzinfo=UTC)
    facts = (
        _fy_fact(1.0, FY2022_START, FY2022_END),
        _fy_fact(2.0, FY2023_START, FY2023_END),
        _fy_fact(3.0, FY2024_START, FY2024_END),
        _fy_fact(99.0, future_start, future_end),  # incomplete period
    )
    provider = FakeProvider(facts=facts)
    resolver = _make_resolver(provider=provider)
    result = resolver.resolve_three_year_average_eps(_c2c_request())
    assert result.status is CalculationStatus.OK
    ri = result.resolved_input
    assert ri is not None
    # Mean of 1.0, 2.0, 3.0 = 2.0 (the 99.0 candidate excluded)
    assert ri.value == pytest.approx(2.0)


def test_c2c_input_unavailable_never_caches() -> None:
    """INPUT_UNAVAILABLE => no cache write."""
    facts = (_fy_fact(1.0, FY2024_START, FY2024_END),)  # only 1 period
    provider = FakeProvider(facts=facts)
    cache = SpyCache()
    resolver = _make_resolver(provider=provider, cache=cache)
    result = resolver.resolve_three_year_average_eps(_c2c_request())
    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert cache.put_count == 0


def test_c2c_provider_error_candidate_never_caches() -> None:
    """Coherence failure => PROVIDER_ERROR, no cache write."""
    facts = (
        _fy_fact(2.0, FY2022_START, FY2022_END),
        _fy_fact(3.0, FY2023_START, FY2023_END, provider_id="other-provider"),  # mismatch
        _fy_fact(4.0, FY2024_START, FY2024_END),
    )
    provider = FakeProvider(facts=facts)
    cache = SpyCache()
    resolver = _make_resolver(provider=provider, cache=cache)
    result = resolver.resolve_three_year_average_eps(_c2c_request())
    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert cache.put_count == 0


# ===========================================================================
# C2D-2: Optional-quote edge cases, AAA-yield override, and propagation
# ===========================================================================


class MultiFieldProviderWithError:
    """Provider fake that can raise ValuationProviderError for specific fields.

    Extends MultiFieldProvider by adding per-field error injection.
    """

    def __init__(
        self,
        *,
        handlers: dict[ValuationField, tuple[ProviderFact, ...]] | None = None,
        error_fields: set[ValuationField] | None = None,
    ) -> None:
        """Initialize with optional per-field handlers and error fields."""
        self._handlers: dict[ValuationField, tuple[ProviderFact, ...]] = handlers or {}
        self._error_fields: set[ValuationField] = error_fields or set()
        self.requests: list[ValuationFactRequest] = []
        self.call_count = 0

    def fetch_facts(self, request: ValuationFactRequest) -> tuple[ProviderFact, ...]:
        self.call_count += 1
        self.requests.append(request)
        if request.field_name in self._error_fields:
            raise ValuationProviderError("synthetic provider failure")
        return self._handlers.get(request.field_name, ())

    def requested_fields(self) -> list[ValuationField]:
        return [r.field_name for r in self.requests]


# ---------------------------------------------------------------------------
# Quote provider error → assembly OK, current_price=None, quote_status preserved
# ---------------------------------------------------------------------------


def test_c2d_graham_number_quote_provider_error_non_fatal() -> None:
    """Quote provider error → assembly OK, current_price=None, quote_status=PROVIDER_ERROR."""
    provider = MultiFieldProviderWithError(
        handlers={
            ValuationField.EPS: _three_fy_facts(),
            ValuationField.BVPS: (_bvps_fact(),),
        },
        error_fields={ValuationField.CURRENT_PRICE},
    )
    resolver = InputResolver(provider=provider, clock=lambda: NOW)
    result = resolver.assemble_graham_number(
        security_subject_id=SUBJECT_ID,
        security_provider_id=PROVIDER_ID,
    )
    assert result.status is CalculationStatus.OK
    assert result.eps is not None
    assert result.bvps is not None
    assert result.current_price is None
    assert result.quote_status is CalculationStatus.PROVIDER_ERROR
    assert result.quote_reason is not None
    assert result.reason is None


# ---------------------------------------------------------------------------
# Invalid explicit quote override (<= 0) → INVALID_INPUT
# ---------------------------------------------------------------------------


def test_c2d_graham_number_quote_override_invalid() -> None:
    """Explicit quote override <= 0 → assembly INVALID_INPUT."""
    provider = MultiFieldProvider(
        handlers={
            ValuationField.EPS: _three_fy_facts(),
            ValuationField.BVPS: (_bvps_fact(),),
        }
    )
    resolver = InputResolver(provider=provider, clock=lambda: NOW)
    result = resolver.assemble_graham_number(
        security_subject_id=SUBJECT_ID,
        security_provider_id=PROVIDER_ID,
        quote_override=-5.0,
    )
    assert result.status is CalculationStatus.INVALID_INPUT
    assert result.eps is not None
    assert result.bvps is not None
    assert result.current_price is None
    assert result.reason is not None
    assert "current_price" in result.reason


# ---------------------------------------------------------------------------
# AAA-yield override: Growth Value succeeds, AAA not requested from provider
# ---------------------------------------------------------------------------


def test_c2d_growth_value_aaa_yield_override() -> None:
    """Growth Value with explicit AAA-yield override: provider not called for AAA."""
    provider = MultiFieldProvider(
        handlers={
            ValuationField.EPS: (_ttm_eps_fact(),),
            ValuationField.CURRENT_PRICE: (_price_fact(),),
            # No AAA handler — would return empty if called.
        }
    )
    resolver = InputResolver(provider=provider, clock=lambda: NOW)
    result = resolver.assemble_growth_value(
        security_subject_id=SUBJECT_ID,
        security_provider_id=PROVIDER_ID,
        eps_basis="ttm",
        expected_growth=12.0,
        aaa_subject_id="AAA",
        aaa_provider_id="provider-aaa",
        aaa_yield_override=4.5,
    )
    assert result.status is CalculationStatus.OK
    # AAA yield: value and provenance correct
    assert result.current_aaa_yield is not None
    assert result.current_aaa_yield.value == 4.5
    assert result.current_aaa_yield.source_kind is SourceKind.OVERRIDE
    assert result.current_aaa_yield.units == "percentage_points"
    assert result.current_aaa_yield.resolved_at == NOW
    # Expected growth remains OVERRIDE
    assert result.expected_growth is not None
    assert result.expected_growth.value == 12.0
    assert result.expected_growth.source_kind is SourceKind.OVERRIDE
    # AAA field must never have reached the provider
    assert ValuationField.CURRENT_AAA_YIELD not in provider.requested_fields()


# ---------------------------------------------------------------------------
# Propagation: use_cache=False + historical as_of
# ---------------------------------------------------------------------------


def test_c2d_growth_value_no_cache_historical_as_of_propagation() -> None:
    """use_cache=False + historical as_of: no cache I/O, all fields get as_of, expected_growth carries as_of."""
    hist_as_of = datetime(2024, 6, 30, tzinfo=UTC)
    # available_at must be <= as_of for historical eligibility.
    hist_available = datetime(2024, 6, 29, tzinfo=UTC)

    eps_fact = ProviderFact(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id=SUBJECT_ID,
        field_name=ValuationField.EPS,
        value=8.0,
        units=ValuationUnit.CURRENCY_PER_SHARE,
        provider_id=PROVIDER_ID,
        provider_field="ttm_eps_synthetic",
        retrieved_at=RETRIEVED_AT,
        basis="ttm",
        currency="USD",
        available_at=hist_available,
    )
    aaa_fact = ProviderFact(
        subject_kind=ValuationSubjectKind.MACRO,
        subject_id="AAA",
        field_name=ValuationField.CURRENT_AAA_YIELD,
        value=5.0,
        units=ValuationUnit.PERCENTAGE_POINTS,
        provider_id="provider-aaa",
        provider_field="aaa_synthetic",
        retrieved_at=RETRIEVED_AT,
        basis=None,
        available_at=hist_available,
    )
    price_fact = ProviderFact(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id=SUBJECT_ID,
        field_name=ValuationField.CURRENT_PRICE,
        value=100.0,
        units=ValuationUnit.CURRENCY_PER_SHARE,
        provider_id=PROVIDER_ID,
        provider_field="price_synthetic",
        retrieved_at=RETRIEVED_AT,
        basis=None,
        currency="USD",
        available_at=hist_available,
    )

    provider = MultiFieldProvider(
        handlers={
            ValuationField.EPS: (eps_fact,),
            ValuationField.CURRENT_AAA_YIELD: (aaa_fact,),
            ValuationField.CURRENT_PRICE: (price_fact,),
        }
    )
    cache = SpyCache()
    resolver = InputResolver(provider=provider, cache=cache, clock=lambda: NOW)

    result = resolver.assemble_growth_value(
        security_subject_id=SUBJECT_ID,
        security_provider_id=PROVIDER_ID,
        eps_basis="ttm",
        expected_growth=12.0,
        aaa_subject_id="AAA",
        aaa_provider_id="provider-aaa",
        as_of=hist_as_of,
        use_cache=False,
    )
    assert result.status is CalculationStatus.OK

    # No cache reads or writes
    assert cache.get_count == 0
    assert cache.put_count == 0

    # All provider-backed fields received the historical as_of
    for req in provider.requests:
        assert req.as_of == hist_as_of

    # EPS provenance carries as_of
    assert result.eps is not None
    assert result.eps.as_of == hist_as_of

    # AAA-yield provenance carries as_of
    assert result.current_aaa_yield is not None
    assert result.current_aaa_yield.as_of == hist_as_of

    # Quote provenance carries as_of
    assert result.current_price is not None
    assert result.current_price.as_of == hist_as_of

    # Expected growth provenance also carries as_of
    assert result.expected_growth is not None
    assert result.expected_growth.as_of == hist_as_of
    assert result.expected_growth.source_kind is SourceKind.OVERRIDE
    assert result.expected_growth.value == 12.0
    assert result.expected_growth.units == "percentage_points"
    assert result.expected_growth.resolved_at == NOW
