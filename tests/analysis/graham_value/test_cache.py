"""Tests for src.analysis.graham_value.cache models and InMemoryValuationCache."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest

from src.analysis.graham_value.cache import (
    InMemoryValuationCache,
    ValuationCacheEntry,
    ValuationCacheKey,
    ValuationCacheProtocol,
)
from src.analysis.graham_value.provenance import (
    ComponentLineage,
    ResolvedInput,
    SourceKind,
    ValuationSubjectKind,
)

AW = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
NAIVE = datetime(2025, 6, 1, 12, 0)
AS_OF = datetime(2025, 12, 31, tzinfo=UTC)
FIXED_TIME = datetime(2025, 6, 1, 10, 0, tzinfo=UTC)


def _fixed_clock() -> Callable[[], datetime]:
    return lambda: FIXED_TIME  # noqa: E731


def _make_provider_input(
    field_name: str = "eps",
    basis: str | None = None,
    provider_id: str = "fixture",
    available_at: datetime | None = None,
    as_of: datetime | None = None,
    **kwargs: object,
) -> ResolvedInput:
    defaults: dict[str, object] = {
        "field_name": field_name,
        "value": 5.0,
        "source_kind": SourceKind.PROVIDER,
        "resolved_at": AW,
        "provider_id": provider_id,
        "basis": basis,
        "available_at": available_at,
        "as_of": as_of,
    }
    defaults.update(kwargs)
    return ResolvedInput(**defaults)  # type: ignore[arg-type]


def _make_key(  # noqa: PLR0913, PLR0917
    subject_kind: ValuationSubjectKind = ValuationSubjectKind.SECURITY,
    subject_id: str = "AAPL",
    field_name: str = "eps",
    basis: str | None = None,
    provider_id: str = "fixture",
    analysis_as_of: datetime | None = None,
    schema_version: int = 1,
) -> ValuationCacheKey:
    return ValuationCacheKey(
        subject_kind=subject_kind,
        subject_id=subject_id,
        field_name=field_name,
        basis=basis,
        provider_id=provider_id,
        analysis_as_of=analysis_as_of,
        schema_version=schema_version,
    )


def _make_derived_input(
    field_name: str = "avg_eps",
    basis: str | None = None,
    as_of: datetime | None = None,
    **kwargs: object,
) -> ResolvedInput:
    comp = _make_provider_input(field_name="eps")
    lineage = ComponentLineage(transformation="mean", components=(comp,))
    defaults: dict[str, object] = {
        "field_name": field_name,
        "value": 3.0,
        "source_kind": SourceKind.DERIVED,
        "resolved_at": AW,
        "lineage": lineage,
        "basis": basis,
        "as_of": as_of,
    }
    defaults.update(kwargs)
    return ResolvedInput(**defaults)  # type: ignore[arg-type]


# ===========================================================================
# ValuationCacheKey — constructor validation
# ===========================================================================


def test_key_security_normalization() -> None:
    key = _make_key(subject_id="  aapl  ")
    assert key.subject_id == "AAPL"


def test_key_macro_case_preserved() -> None:
    key = _make_key(
        subject_kind=ValuationSubjectKind.MACRO,
        subject_id="  aaa  ",
        field_name="current_aaa_yield",
    )
    assert key.subject_id == "aaa"


def test_key_macro_upper_preserved() -> None:
    key = _make_key(
        subject_kind=ValuationSubjectKind.MACRO,
        subject_id="AAA",
        field_name="current_aaa_yield",
    )
    assert key.subject_id == "AAA"


def test_key_empty_subject_id_rejected() -> None:
    with pytest.raises(ValueError, match="subject_id"):
        _make_key(subject_id="   ")


def test_key_empty_field_name_rejected() -> None:
    with pytest.raises(ValueError, match="field_name"):
        _make_key(field_name="  ")


def test_key_empty_provider_id_rejected() -> None:
    with pytest.raises(ValueError, match="provider_id"):
        _make_key(provider_id="  ")


def test_key_empty_basis_rejected() -> None:
    with pytest.raises(ValueError, match="basis"):
        _make_key(basis="  ")


def test_key_basis_normalization() -> None:
    key = _make_key(basis="  ttm  ")
    assert key.basis == "ttm"


def test_key_provider_normalization() -> None:
    key = _make_key(provider_id="  YFinance  ")
    assert key.provider_id == "yfinance"


def test_key_naive_as_of_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _make_key(analysis_as_of=NAIVE)


def test_key_zero_schema_version_rejected() -> None:
    with pytest.raises(ValueError, match="schema_version"):
        _make_key(schema_version=0)


def test_key_negative_schema_version_rejected() -> None:
    with pytest.raises(ValueError, match="schema_version"):
        _make_key(schema_version=-1)


def test_key_frozen() -> None:
    key = _make_key()
    with pytest.raises(AttributeError):
        key.subject_id = "MSFT"  # type: ignore[misc]


# ===========================================================================
# ValuationCacheEntry — constructor validation
# ===========================================================================


def test_entry_naive_cached_at_rejected() -> None:
    key = _make_key()
    ri = _make_provider_input()
    with pytest.raises(ValueError, match="timezone-aware"):
        ValuationCacheEntry(key=key, resolved_input=ri, cached_at=NAIVE)


def test_entry_field_mismatch_rejected() -> None:
    key = _make_key(field_name="bvps")
    ri = _make_provider_input(field_name="eps")
    with pytest.raises(ValueError, match="field_name"):
        ValuationCacheEntry(key=key, resolved_input=ri, cached_at=AW)


def test_entry_basis_mismatch_rejected() -> None:
    key = _make_key(basis="ttm")
    ri = _make_provider_input(basis="three_year_average")
    with pytest.raises(ValueError, match="basis"):
        ValuationCacheEntry(key=key, resolved_input=ri, cached_at=AW)


def test_entry_asof_mismatch_rejected() -> None:
    key = _make_key(analysis_as_of=AS_OF)
    ri = _make_provider_input(as_of=None)
    with pytest.raises(ValueError, match="analysis_as_of"):
        ValuationCacheEntry(key=key, resolved_input=ri, cached_at=AW)


def test_entry_provider_mismatch_rejected() -> None:
    key = _make_key(provider_id="yfinance")
    ri = _make_provider_input(provider_id="fixture")
    with pytest.raises(ValueError, match="provider_id"):
        ValuationCacheEntry(key=key, resolved_input=ri, cached_at=AW)


def test_entry_equivalent_provider_ids_pass_coherence() -> None:
    """Differently formatted but canonically equivalent provider IDs pass entry coherence."""
    key = _make_key(provider_id="YFinance")
    ri = _make_provider_input(provider_id=" yfinance ")
    entry = ValuationCacheEntry(key=key, resolved_input=ri, cached_at=AW)
    assert entry.key.provider_id == "yfinance"
    assert entry.resolved_input.provider_id == "yfinance"


def test_entry_override_source_rejected() -> None:
    key = _make_key()
    ri = ResolvedInput(
        field_name="eps",
        value=1.0,
        source_kind=SourceKind.OVERRIDE,
        resolved_at=AW,
    )
    with pytest.raises(ValueError, match="PROVIDER or DERIVED"):
        ValuationCacheEntry(key=key, resolved_input=ri, cached_at=AW)


def test_entry_cache_source_rejected() -> None:
    key = _make_key()
    ri = ResolvedInput(
        field_name="eps",
        value=1.0,
        source_kind=SourceKind.CACHE,
        resolved_at=AW,
        origin_source_kind=SourceKind.PROVIDER,
        provider_id="fixture",
        cache_schema_version=1,
    )
    with pytest.raises(ValueError, match="PROVIDER or DERIVED"):
        ValuationCacheEntry(key=key, resolved_input=ri, cached_at=AW)


def test_entry_frozen() -> None:
    key = _make_key()
    ri = _make_provider_input()
    entry = ValuationCacheEntry(key=key, resolved_input=ri, cached_at=AW)
    with pytest.raises(AttributeError):
        entry.cached_at = datetime(2026, 1, 1, tzinfo=UTC)  # type: ignore[misc]


# ===========================================================================
# InMemoryValuationCache — put/get basic
# ===========================================================================


def test_put_get_current_hit() -> None:
    cache = InMemoryValuationCache(clock=_fixed_clock())
    key = _make_key()
    ri = _make_provider_input()
    cache.put(key, ri)
    entry = cache.get(key)
    assert entry is not None
    assert entry.resolved_input is ri
    assert entry.cached_at == FIXED_TIME


def test_get_without_put_returns_none() -> None:
    cache = InMemoryValuationCache(clock=_fixed_clock())
    assert cache.get(_make_key()) is None


def test_put_get_derived_input() -> None:
    cache = InMemoryValuationCache(clock=_fixed_clock())
    key = _make_key(field_name="avg_eps")
    ri = _make_derived_input(field_name="avg_eps")
    cache.put(key, ri)
    entry = cache.get(key)
    assert entry is not None
    assert entry.resolved_input.source_kind is SourceKind.DERIVED


def test_last_write_wins() -> None:
    cache = InMemoryValuationCache(clock=_fixed_clock())
    key = _make_key()
    ri1 = ResolvedInput(
        field_name="eps",
        value=1.0,
        source_kind=SourceKind.PROVIDER,
        resolved_at=AW,
        provider_id="fixture",
    )
    ri2 = ResolvedInput(
        field_name="eps",
        value=2.0,
        source_kind=SourceKind.PROVIDER,
        resolved_at=AW,
        provider_id="fixture",
    )
    cache.put(key, ri1)
    cache.put(key, ri2)
    entry = cache.get(key)
    assert entry is not None
    assert entry.resolved_input.value == 2.0


def test_get_returns_entry_type() -> None:
    cache = InMemoryValuationCache(clock=_fixed_clock())
    key = _make_key()
    ri = _make_provider_input()
    cache.put(key, ri)
    entry = cache.get(key)
    assert isinstance(entry, ValuationCacheEntry)


def test_stored_input_not_relabelled() -> None:
    cache = InMemoryValuationCache(clock=_fixed_clock())
    key = _make_key()
    ri = _make_provider_input()
    cache.put(key, ri)
    entry = cache.get(key)
    assert entry is not None
    assert entry.resolved_input.source_kind is SourceKind.PROVIDER
    assert entry.resolved_input.origin_source_kind is None


# ===========================================================================
# InMemoryValuationCache — source restrictions
# ===========================================================================


def test_override_input_cannot_be_cached() -> None:
    cache = InMemoryValuationCache(clock=_fixed_clock())
    key = _make_key()
    ri = ResolvedInput(
        field_name="eps",
        value=1.0,
        source_kind=SourceKind.OVERRIDE,
        resolved_at=AW,
    )
    with pytest.raises(ValueError, match="PROVIDER and DERIVED"):
        cache.put(key, ri)


def test_cache_input_cannot_be_cached() -> None:
    cache = InMemoryValuationCache(clock=_fixed_clock())
    key = _make_key()
    ri = ResolvedInput(
        field_name="eps",
        value=1.0,
        source_kind=SourceKind.CACHE,
        resolved_at=AW,
        origin_source_kind=SourceKind.PROVIDER,
        provider_id="fixture",
        cache_schema_version=1,
    )
    with pytest.raises(ValueError, match="PROVIDER and DERIVED"):
        cache.put(key, ri)


# ===========================================================================
# InMemoryValuationCache — naive clock rejection
# ===========================================================================


def test_put_naive_clock_rejected() -> None:
    naive_clock: Callable[[], datetime] = lambda: NAIVE  # noqa: E731
    cache = InMemoryValuationCache(clock=naive_clock)
    key = _make_key()
    ri = _make_provider_input()
    with pytest.raises(ValueError, match="naive"):
        cache.put(key, ri)


# ===========================================================================
# InMemoryValuationCache — TTL
# ===========================================================================


def test_ttl_exact_boundary_hit() -> None:
    """Age == TTL is a hit."""
    t0 = datetime(2025, 6, 1, 10, 0, tzinfo=UTC)
    t1 = datetime(2025, 6, 1, 11, 0, tzinfo=UTC)
    ttl = timedelta(hours=1)

    state = {"time": t0}

    def mutable_clock() -> datetime:
        return state["time"]

    cache = InMemoryValuationCache(clock=mutable_clock, ttl=ttl)
    key = _make_key()
    ri = _make_provider_input()
    cache.put(key, ri)

    state["time"] = t1
    entry = cache.get(key)
    assert entry is not None


def test_ttl_beyond_boundary_miss() -> None:
    """Age > TTL is stale."""
    t0 = datetime(2025, 6, 1, 10, 0, tzinfo=UTC)
    t1 = datetime(2025, 6, 1, 11, 0, 1, tzinfo=UTC)
    ttl = timedelta(hours=1)

    state = {"time": t0}

    def mutable_clock() -> datetime:
        return state["time"]

    cache = InMemoryValuationCache(clock=mutable_clock, ttl=ttl)
    key = _make_key()
    ri = _make_provider_input()
    cache.put(key, ri)

    state["time"] = t1
    entry = cache.get(key)
    assert entry is None


def test_ttl_within_boundary_hit() -> None:
    """Age < TTL is a hit."""
    t0 = datetime(2025, 6, 1, 10, 0, tzinfo=UTC)
    t1 = datetime(2025, 6, 1, 10, 30, tzinfo=UTC)
    ttl = timedelta(hours=1)

    state = {"time": t0}

    def mutable_clock() -> datetime:
        return state["time"]

    cache = InMemoryValuationCache(clock=mutable_clock, ttl=ttl)
    key = _make_key()
    ri = _make_provider_input()
    cache.put(key, ri)

    state["time"] = t1
    entry = cache.get(key)
    assert entry is not None


def test_ttl_none_no_staleness() -> None:
    """ttl=None means no staleness check."""
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    t1 = datetime(2025, 6, 1, tzinfo=UTC)

    state = {"time": t0}

    def mutable_clock() -> datetime:
        return state["time"]

    cache = InMemoryValuationCache(clock=mutable_clock)
    key = _make_key()
    ri = _make_provider_input()
    cache.put(key, ri)

    state["time"] = t1
    entry = cache.get(key)
    assert entry is not None


def test_negative_ttl_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        InMemoryValuationCache(ttl=timedelta(seconds=-1))


def test_cached_at_from_injected_clock() -> None:
    cache = InMemoryValuationCache(clock=_fixed_clock())
    key = _make_key()
    ri = _make_provider_input()
    cache.put(key, ri)
    entry = cache.get(key)
    assert entry is not None
    assert entry.cached_at == FIXED_TIME


def test_original_retrieved_at_preserved() -> None:
    retrieved = datetime(2025, 5, 1, 8, 0, tzinfo=UTC)
    cache = InMemoryValuationCache(clock=_fixed_clock())
    key = _make_key()
    ri = _make_provider_input(retrieved_at=retrieved)
    cache.put(key, ri)
    entry = cache.get(key)
    assert entry is not None
    assert entry.resolved_input.retrieved_at == retrieved


# ===========================================================================
# InMemoryValuationCache — historical eligibility
# ===========================================================================


def test_historical_available_after_as_of_miss() -> None:
    avail = datetime(2026, 1, 1, tzinfo=UTC)
    cache = InMemoryValuationCache(clock=_fixed_clock())
    key = _make_key(analysis_as_of=AS_OF)
    ri = _make_provider_input(available_at=avail, as_of=AS_OF)
    cache.put(key, ri)
    assert cache.get(key) is None


def test_historical_available_before_as_of_hit() -> None:
    avail = datetime(2025, 6, 1, tzinfo=UTC)
    cache = InMemoryValuationCache(clock=_fixed_clock())
    key = _make_key(analysis_as_of=AS_OF)
    ri = _make_provider_input(available_at=avail, as_of=AS_OF)
    cache.put(key, ri)
    assert cache.get(key) is not None


def test_historical_available_equal_as_of_hit() -> None:
    """available_at == analysis_as_of is eligible."""
    cache = InMemoryValuationCache(clock=_fixed_clock())
    key = _make_key(analysis_as_of=AS_OF)
    ri = _make_provider_input(available_at=AS_OF, as_of=AS_OF)
    cache.put(key, ri)
    assert cache.get(key) is not None


def test_historical_available_none_miss() -> None:
    cache = InMemoryValuationCache(clock=_fixed_clock())
    key = _make_key(analysis_as_of=AS_OF)
    ri = _make_provider_input(available_at=None, as_of=AS_OF)
    cache.put(key, ri)
    assert cache.get(key) is None


def test_current_available_none_hit() -> None:
    """Current key: missing available_at does not cause a miss."""
    cache = InMemoryValuationCache(clock=_fixed_clock())
    key = _make_key(analysis_as_of=None)
    ri = _make_provider_input(available_at=None, as_of=None)
    cache.put(key, ri)
    assert cache.get(key) is not None


# ===========================================================================
# Key collision tests
# ===========================================================================


def test_security_macro_no_collision() -> None:
    cache = InMemoryValuationCache(clock=_fixed_clock())
    key_sec = _make_key(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="AAA",
        field_name="current_aaa_yield",
    )
    key_macro = _make_key(
        subject_kind=ValuationSubjectKind.MACRO,
        subject_id="AAA",
        field_name="current_aaa_yield",
    )
    ri_sec = _make_provider_input(field_name="current_aaa_yield")
    ri_macro = _make_provider_input(field_name="current_aaa_yield")
    cache.put(key_sec, ri_sec)
    cache.put(key_macro, ri_macro)
    assert cache.get(key_sec) is not None
    assert cache.get(key_macro) is not None
    assert cache.get(key_sec) is not cache.get(key_macro)  # type: ignore[comparison-overlap]


def test_different_subject_id_no_collision() -> None:
    cache = InMemoryValuationCache(clock=_fixed_clock())
    key1 = _make_key(subject_id="AAPL")
    key2 = _make_key(subject_id="MSFT")
    ri = _make_provider_input()
    cache.put(key1, ri)
    cache.put(key2, ri)
    assert cache.get(key1) is not None
    assert cache.get(key2) is not None


def test_different_field_no_collision() -> None:
    cache = InMemoryValuationCache(clock=_fixed_clock())
    key_eps = _make_key(field_name="eps")
    key_bvps = _make_key(field_name="bvps")
    ri_eps = _make_provider_input(field_name="eps")
    ri_bvps = _make_provider_input(field_name="bvps")
    cache.put(key_eps, ri_eps)
    cache.put(key_bvps, ri_bvps)
    assert cache.get(key_eps) is not None
    assert cache.get(key_bvps) is not None


def test_different_basis_no_collision() -> None:
    cache = InMemoryValuationCache(clock=_fixed_clock())
    key_ttm = _make_key(basis="ttm")
    key_3yr = _make_key(basis="three_year_average")
    ri_ttm = _make_provider_input(basis="ttm")
    ri_3yr = _make_provider_input(basis="three_year_average")
    cache.put(key_ttm, ri_ttm)
    cache.put(key_3yr, ri_3yr)
    assert cache.get(key_ttm) is not None
    assert cache.get(key_3yr) is not None


def test_different_provider_no_collision() -> None:
    cache = InMemoryValuationCache(clock=_fixed_clock())
    key_fix = _make_key(provider_id="fixture")
    key_yf = _make_key(provider_id="yfinance")
    ri_fix = _make_provider_input(provider_id="fixture")
    ri_yf = _make_provider_input(provider_id="yfinance")
    cache.put(key_fix, ri_fix)
    cache.put(key_yf, ri_yf)
    assert cache.get(key_fix) is not None
    assert cache.get(key_yf) is not None


def test_current_vs_historical_no_collision() -> None:
    cache = InMemoryValuationCache(clock=_fixed_clock())
    key_cur = _make_key(analysis_as_of=None)
    key_hist = _make_key(analysis_as_of=AS_OF)
    ri_cur = _make_provider_input(as_of=None)
    ri_hist = _make_provider_input(as_of=AS_OF, available_at=AW)
    cache.put(key_cur, ri_cur)
    cache.put(key_hist, ri_hist)
    assert cache.get(key_cur) is not None
    assert cache.get(key_hist) is not None
    assert cache.get(key_cur) is not cache.get(key_hist)  # type: ignore[comparison-overlap]


def test_two_historical_boundaries_no_collision() -> None:
    as_of_1 = datetime(2025, 12, 31, tzinfo=UTC)
    as_of_2 = datetime(2026, 6, 30, tzinfo=UTC)
    cache = InMemoryValuationCache(clock=_fixed_clock())
    key1 = _make_key(analysis_as_of=as_of_1)
    key2 = _make_key(analysis_as_of=as_of_2)
    ri1 = _make_provider_input(as_of=as_of_1, available_at=AW)
    ri2 = _make_provider_input(as_of=as_of_2, available_at=AW)
    cache.put(key1, ri1)
    cache.put(key2, ri2)
    assert cache.get(key1) is not None
    assert cache.get(key2) is not None
    assert cache.get(key1) is not cache.get(key2)  # type: ignore[comparison-overlap]


def test_schema_version_isolation() -> None:
    cache = InMemoryValuationCache(clock=_fixed_clock())
    key_v1 = _make_key(schema_version=1)
    key_v2 = _make_key(schema_version=2)
    ri = _make_provider_input()
    cache.put(key_v1, ri)
    assert cache.get(key_v1) is not None
    assert cache.get(key_v2) is None


# ===========================================================================
# Macro entry independence
# ===========================================================================


def test_macro_entry_no_ticker_required() -> None:
    cache = InMemoryValuationCache(clock=_fixed_clock())
    key = _make_key(
        subject_kind=ValuationSubjectKind.MACRO,
        subject_id="AAA",
        field_name="current_aaa_yield",
        basis="percentage_points",
        provider_id="fred",
        analysis_as_of=AS_OF,
    )
    ri = _make_provider_input(
        field_name="current_aaa_yield",
        basis="percentage_points",
        provider_id="fred",
        available_at=AW,
        as_of=AS_OF,
    )
    cache.put(key, ri)
    entry = cache.get(key)
    assert entry is not None
    assert entry.key.subject_kind is ValuationSubjectKind.MACRO
    assert entry.key.subject_id == "AAA"


# ===========================================================================
# Provider ID normalization in key
# ===========================================================================


def test_provider_id_normalization_hit() -> None:
    cache = InMemoryValuationCache(clock=_fixed_clock())
    key = _make_key(provider_id="YFinance")
    ri = _make_provider_input(provider_id="yfinance")
    cache.put(key, ri)
    assert cache.get(key) is not None


# ===========================================================================
# Protocol conformance
# ===========================================================================


def test_runtime_protocol_conformance() -> None:
    cache = InMemoryValuationCache(clock=_fixed_clock())
    assert isinstance(cache, ValuationCacheProtocol)
