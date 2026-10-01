"""Frozen-clock skew tolerance in the shared input resolver (ESC-21).

A live run's clock is frozen at ``executed_at``, but provider timestamps are stamped when each fetch
completes, so a timestamp slightly after ``executed_at`` is normal. The resolver accepts up to
``FROZEN_CLOCK_SKEW_TOLERANCE`` of it on a live run, from the provider and from a cache hit, and
rejects anything beyond. An ``--as-of`` run accepts none: a fact available after the boundary is
look-ahead.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from src.analysis.strategy.graham_number.calculation import GrahamNumberInputResolver
from src.core.analysis_status import CalculationStatus
from src.core.clock import FROZEN_CLOCK_SKEW_TOLERANCE
from src.data.financial.cache import ResolvedInputCacheEntry, ResolvedInputCacheKey
from src.data.financial.facts import (
    FinancialFactRequest,
    FinancialField,
    FinancialUnit,
    ProviderFact,
)
from src.data.financial.provenance import FinancialSubjectKind, ResolvedInput, SourceKind

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
AS_OF = datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC)
TOLERANCE = FROZEN_CLOCK_SKEW_TOLERANCE
ONE_SECOND = timedelta(seconds=1)
PROVIDER_ID = "provider-a"
SUBJECT_ID = "SYNTH"
EARLIER = NOW - timedelta(days=2)


class _Provider:
    """Returns the supplied facts and counts calls."""

    def __init__(self, *facts: ProviderFact) -> None:
        self._facts = facts
        self.call_count = 0

    def fetch_facts(self, request: FinancialFactRequest, *, effective_as_of: datetime) -> tuple[ProviderFact, ...]:
        del request, effective_as_of
        self.call_count += 1
        return self._facts


class _Cache:
    """Holds one stored entry and ignores writes."""

    def __init__(self, entry: ResolvedInputCacheEntry | None = None) -> None:
        self._entry = entry

    def get(self, key: ResolvedInputCacheKey) -> ResolvedInputCacheEntry | None:
        del key
        return self._entry

    def put(self, key: ResolvedInputCacheKey, resolved_input: ResolvedInput) -> None:
        del key, resolved_input


def _request(field: FinancialField, *, as_of: datetime | None = None) -> FinancialFactRequest:
    return FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id=SUBJECT_ID,
        field_name=field,
        provider_id=PROVIDER_ID,
        basis=None,
        as_of=as_of,
        observation_count=1,
    )


def _fact(field: FinancialField, **overrides: Any) -> ProviderFact:
    values: dict[str, Any] = {
        "subject_kind": FinancialSubjectKind.SECURITY,
        "subject_id": SUBJECT_ID,
        "field_name": field,
        "value": 4.5,
        "units": FinancialUnit.CURRENCY_PER_SHARE,
        "provider_id": PROVIDER_ID,
        "provider_field": "synthetic_field",
        "retrieved_at": EARLIER,
        "basis": "latest_provider_quote" if field is FinancialField.CURRENT_PRICE else None,
        "currency": "USD",
        "available_at": EARLIER,
    }
    values.update(overrides)
    return ProviderFact(**values)


def _stored(field: FinancialField, **overrides: Any) -> ResolvedInput:
    values: dict[str, Any] = {
        "field_name": field.value,
        "value": 5.5,
        "source_kind": SourceKind.PROVIDER,
        "resolved_at": EARLIER,
        "basis": "latest_provider_quote" if field is FinancialField.CURRENT_PRICE else None,
        "units": "currency_per_share",
        "currency": "USD",
        "provider_id": PROVIDER_ID,
        "provider_field": "synthetic_field",
        "available_at": EARLIER,
        "retrieved_at": EARLIER,
    }
    values.update(overrides)
    return ResolvedInput(**values)


def _entry(field: FinancialField, stored: ResolvedInput, *, as_of: datetime | None = None) -> ResolvedInputCacheEntry:
    key = ResolvedInputCacheKey(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id=SUBJECT_ID,
        field_name=field.value,
        basis=stored.basis,
        provider_id=PROVIDER_ID,
        analysis_as_of=as_of,
        schema_version=1,
    )
    return ResolvedInputCacheEntry(key=key, resolved_input=stored, cached_at=NOW)


def _resolver(provider: _Provider, cache: _Cache | None = None) -> GrahamNumberInputResolver:
    return GrahamNumberInputResolver(provider=provider, cache=cache, clock=lambda: NOW, cache_schema_version=1)


def test_the_tolerance_is_ten_minutes() -> None:
    assert timedelta(minutes=10) == TOLERANCE


@pytest.mark.parametrize(
    ("offset", "accepted"),
    [
        (timedelta(0), True),
        (timedelta(minutes=9, seconds=59), True),
        (TOLERANCE, True),
        (TOLERANCE + ONE_SECOND, False),
        (timedelta(hours=1), False),
    ],
)
def test_live_provider_fact_available_after_executed_at(offset: timedelta, accepted: bool) -> None:
    provider = _Provider(_fact(FinancialField.EPS, available_at=NOW + offset))

    result = _resolver(provider).resolve(_request(FinancialField.EPS), use_cache=False)

    assert (result.status is CalculationStatus.OK) is accepted
    if not accepted:
        assert result.status is CalculationStatus.INPUT_UNAVAILABLE
        assert result.resolved_input is None


@pytest.mark.parametrize(
    ("offset", "accepted"),
    [(timedelta(minutes=5), True), (TOLERANCE, True), (TOLERANCE + ONE_SECOND, False)],
)
def test_live_cache_hit_available_after_executed_at(offset: timedelta, accepted: bool) -> None:
    stored = _stored(FinancialField.EPS, available_at=NOW + offset)
    cache = _Cache(_entry(FinancialField.EPS, stored))
    provider = _Provider(_fact(FinancialField.EPS, value=9.0))

    result = _resolver(provider, cache).resolve(_request(FinancialField.EPS), use_cache=True)

    assert result.status is CalculationStatus.OK
    assert result.resolved_input is not None
    if accepted:
        assert result.resolved_input.source_kind is SourceKind.CACHE
        assert result.resolved_input.value == 5.5
        assert provider.call_count == 0
    else:
        assert result.resolved_input.source_kind is SourceKind.PROVIDER
        assert result.resolved_input.value == 9.0
        assert provider.call_count == 1


@pytest.mark.parametrize("stamp", ["retrieved_at", "observed_at"])
@pytest.mark.parametrize(
    ("offset", "accepted"),
    [(timedelta(minutes=5), True), (TOLERANCE, True), (TOLERANCE + ONE_SECOND, False)],
)
def test_live_quote_stamped_after_executed_at_from_the_provider(stamp: str, offset: timedelta, accepted: bool) -> None:
    stamps = {"retrieved_at": NOW, "observed_at": NOW} | {stamp: NOW + offset}
    provider = _Provider(_fact(FinancialField.CURRENT_PRICE, **stamps))

    result = _resolver(provider).resolve(_request(FinancialField.CURRENT_PRICE), use_cache=False)

    if accepted:
        assert result.status is CalculationStatus.OK
        assert result.quote_freshness is not None
        assert result.quote_freshness.status == "recent_retrieval"
    else:
        assert result.status is CalculationStatus.INPUT_UNAVAILABLE
        assert result.reason is not None
        assert "later than the analysis boundary" in result.reason or "future_timestamp" in result.reason


@pytest.mark.parametrize(
    ("offset", "accepted"),
    [(timedelta(minutes=5), True), (TOLERANCE, True), (TOLERANCE + ONE_SECOND, False)],
)
def test_live_quote_stamped_after_executed_at_from_a_cache_hit(offset: timedelta, accepted: bool) -> None:
    stored = _stored(FinancialField.CURRENT_PRICE, retrieved_at=NOW + offset)
    cache = _Cache(_entry(FinancialField.CURRENT_PRICE, stored))
    provider = _Provider(_fact(FinancialField.CURRENT_PRICE, value=9.0, retrieved_at=NOW))

    result = _resolver(provider, cache).resolve(_request(FinancialField.CURRENT_PRICE), use_cache=True)

    assert result.status is CalculationStatus.OK
    assert result.resolved_input is not None
    if accepted:
        assert result.resolved_input.source_kind is SourceKind.CACHE
        assert provider.call_count == 0
    else:
        assert result.resolved_input.source_kind is SourceKind.PROVIDER
        assert provider.call_count == 1


def test_as_of_provider_fact_available_exactly_at_the_boundary_is_accepted() -> None:
    provider = _Provider(_fact(FinancialField.EPS, available_at=AS_OF))

    result = _resolver(provider).resolve(_request(FinancialField.EPS, as_of=AS_OF), use_cache=False)

    assert result.status is CalculationStatus.OK


def test_as_of_provider_fact_available_one_second_after_the_boundary_is_rejected() -> None:
    provider = _Provider(_fact(FinancialField.EPS, available_at=AS_OF + ONE_SECOND))

    result = _resolver(provider).resolve(_request(FinancialField.EPS, as_of=AS_OF), use_cache=False)

    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.resolved_input is None


@pytest.mark.parametrize(
    ("offset", "accepted"),
    [(timedelta(0), True), (-ONE_SECOND, True), (ONE_SECOND, False), (timedelta(minutes=5), False)],
)
def test_as_of_cache_hit_tolerates_no_skew(offset: timedelta, accepted: bool) -> None:
    stored = _stored(FinancialField.EPS, available_at=AS_OF + offset, as_of=AS_OF)
    cache = _Cache(_entry(FinancialField.EPS, stored, as_of=AS_OF))
    provider = _Provider(_fact(FinancialField.EPS, value=9.0, available_at=AS_OF - timedelta(days=30)))

    result = _resolver(provider, cache).resolve(_request(FinancialField.EPS, as_of=AS_OF), use_cache=True)

    assert result.status is CalculationStatus.OK
    assert result.resolved_input is not None
    expected_source = SourceKind.CACHE if accepted else SourceKind.PROVIDER
    assert result.resolved_input.source_kind is expected_source
    assert provider.call_count == (0 if accepted else 1)
