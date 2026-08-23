"""Focused tests for the F1B immutable resolver execution trace."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.analysis.graham_value.cache import InMemoryValuationCache
from src.analysis.graham_value.facts import (
    ProviderFact,
    ValuationFactRequest,
    ValuationField,
    ValuationProviderError,
    ValuationUnit,
)
from src.analysis.graham_value.models import CalculationStatus
from src.analysis.graham_value.provenance import ValuationSubjectKind
from src.analysis.graham_value.resolution_trace import (
    ResolutionEvent,
    ResolutionOutcome,
    ResolutionStage,
    ResolutionTrace,
)
from src.analysis.graham_value.resolver import InputResolver

NOW = datetime(2026, 8, 22, 16, 0, tzinfo=UTC)
PERIOD_END = datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC)


class RecordingProvider:
    """Small provider fake that records requests and returns configured facts."""

    def __init__(self, facts_by_field: dict[ValuationField, tuple[ProviderFact, ...]]) -> None:
        """Initialize configured facts."""
        self.facts_by_field = facts_by_field
        self.calls: list[ValuationFactRequest] = []

    def fetch_facts(self, request: ValuationFactRequest) -> tuple[ProviderFact, ...]:
        """Record the request and return facts for its semantic field."""
        self.calls.append(request)
        return self.facts_by_field.get(request.field_name, ())


class ErrorProvider:
    """Provider fake that always raises an operational provider error."""

    def fetch_facts(self, request: ValuationFactRequest) -> tuple[ProviderFact, ...]:
        """Raise a deterministic provider error."""
        raise ValuationProviderError(f"boom for {request.field_name.value}")


def _request(field: ValuationField, *, basis: str | None = None) -> ValuationFactRequest:
    """Build a current security request."""
    return ValuationFactRequest(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="NDAQ",
        field_name=field,
        provider_id="fixture",
        basis=basis,
    )


def _fact(
    field: ValuationField,
    value: float,
    *,
    units: ValuationUnit,
    basis: str | None = None,
    currency: str | None = None,
) -> ProviderFact:
    """Build one deterministic provider fact."""
    return ProviderFact(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="NDAQ",
        field_name=field,
        value=value,
        units=units,
        provider_id="fixture",
        provider_field=f"fixture:{field.value}",
        retrieved_at=NOW,
        basis=basis,
        currency=currency,
        observation_period_end=PERIOD_END,
        available_at=NOW,
    )


def _event_signature(trace: ResolutionTrace) -> list[tuple[str, str, str]]:
    """Return compact field/stage/outcome triples for assertions."""
    return [(event.field_name, event.stage.value, event.outcome.value) for event in trace.events]


def test_resolution_event_rejects_blank_identifiers_and_messages() -> None:
    """Trace events never carry empty display/diagnostic fields."""
    with pytest.raises(ValueError, match="field_name"):
        ResolutionEvent(
            field_name=" ",
            stage=ResolutionStage.CACHE,
            outcome=ResolutionOutcome.MISS,
            message="miss",
        )

    with pytest.raises(ValueError, match="message"):
        ResolutionEvent(
            field_name="eps",
            stage=ResolutionStage.CACHE,
            outcome=ResolutionOutcome.MISS,
            message=" ",
        )


def test_override_trace_short_circuits_cache_and_provider() -> None:
    """An explicit override records only the path that was actually taken."""
    provider = RecordingProvider({})
    resolver = InputResolver(provider=provider, cache=InMemoryValuationCache(clock=lambda: NOW), clock=lambda: NOW)

    result = resolver.resolve(_request(ValuationField.EPS, basis="ttm"), override=5.0)

    assert result.status is CalculationStatus.OK
    assert _event_signature(result.resolution_trace) == [
        ("eps", "override", "success"),
    ]
    assert provider.calls == []


def test_cache_miss_then_provider_success_is_recorded_in_order() -> None:
    """A real cache miss and provider fallback produce an ordered trace."""
    fact = _fact(
        ValuationField.EPS,
        5.0,
        units=ValuationUnit.CURRENCY_PER_SHARE,
        basis="ttm",
        currency="USD",
    )
    provider = RecordingProvider({ValuationField.EPS: (fact,)})
    resolver = InputResolver(provider=provider, cache=InMemoryValuationCache(clock=lambda: NOW), clock=lambda: NOW)

    result = resolver.resolve(_request(ValuationField.EPS, basis="ttm"))

    assert result.status is CalculationStatus.OK
    assert _event_signature(result.resolution_trace) == [
        ("eps", "override", "not_used"),
        ("eps", "cache", "miss"),
        ("eps", "provider", "attempted"),
        ("eps", "provider", "success"),
    ]
    cache_event = result.resolution_trace.events[1]
    assert "does not distinguish absent, stale, or temporally ineligible" in cache_event.message


def test_cache_hit_records_hit_and_does_not_repeat_provider_attempt() -> None:
    """A second identical request resolves from cache without inventing a provider attempt."""
    fact = _fact(
        ValuationField.EPS,
        5.0,
        units=ValuationUnit.CURRENCY_PER_SHARE,
        basis="ttm",
        currency="USD",
    )
    provider = RecordingProvider({ValuationField.EPS: (fact,)})
    cache = InMemoryValuationCache(clock=lambda: NOW)
    resolver = InputResolver(provider=provider, cache=cache, clock=lambda: NOW)
    request = _request(ValuationField.EPS, basis="ttm")

    first = resolver.resolve(request)
    second = resolver.resolve(request)

    assert first.status is CalculationStatus.OK
    assert second.status is CalculationStatus.OK
    assert _event_signature(second.resolution_trace) == [
        ("eps", "override", "not_used"),
        ("eps", "cache", "hit"),
    ]
    assert len(provider.calls) == 1


def test_provider_error_is_classified_without_losing_attempt_event() -> None:
    """Operational provider failures are distinct from ordinary unavailability."""
    resolver = InputResolver(provider=ErrorProvider(), clock=lambda: NOW)

    result = resolver.resolve(_request(ValuationField.EPS, basis="ttm"))

    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert _event_signature(result.resolution_trace)[-2:] == [
        ("eps", "provider", "attempted"),
        ("eps", "provider", "error"),
    ]


def test_bvps_fallback_trace_preserves_direct_failure_component_paths_and_derivation() -> None:
    """A derived BVPS trace shows why fallback occurred and how derivation succeeded."""
    equity = _fact(
        ValuationField.STOCKHOLDERS_EQUITY,
        100.0,
        units=ValuationUnit.CURRENCY,
        basis="fiscal_year_end",
        currency="USD",
    )
    preferred = _fact(
        ValuationField.PREFERRED_SHARES_OUTSTANDING,
        0.0,
        units=ValuationUnit.SHARES,
        basis="fiscal_year_end",
    )
    common = _fact(
        ValuationField.COMMON_SHARES_OUTSTANDING,
        10.0,
        units=ValuationUnit.SHARES,
        basis="fiscal_year_end",
    )
    provider = RecordingProvider(
        {
            ValuationField.STOCKHOLDERS_EQUITY: (equity,),
            ValuationField.PREFERRED_SHARES_OUTSTANDING: (preferred,),
            ValuationField.COMMON_SHARES_OUTSTANDING: (common,),
        }
    )
    resolver = InputResolver(provider=provider, clock=lambda: NOW)

    result = resolver.resolve_bvps(_request(ValuationField.BVPS))

    assert result.status is CalculationStatus.OK
    assert result.resolved_input is not None
    assert result.resolved_input.value == pytest.approx(10.0)

    signatures = _event_signature(result.resolution_trace)
    assert ("bvps", "provider", "unavailable") in signatures
    assert ("bvps", "derivation", "attempted") in signatures
    assert ("stockholders_equity", "provider", "success") in signatures
    assert ("preferred_shares_outstanding", "provider", "success") in signatures
    assert ("common_shares_outstanding", "provider", "success") in signatures
    assert signatures[-1] == ("bvps", "derivation", "success")


def test_graham_number_assembly_aggregates_field_traces_in_resolution_order() -> None:
    """Method-level assembly exposes one ordered trace across all resolved fields."""
    provider = RecordingProvider({})
    resolver = InputResolver(provider=provider, clock=lambda: NOW)

    assembly = resolver.assemble_graham_number(
        security_subject_id="NDAQ",
        security_provider_id="fixture",
        eps_basis="ttm",
        eps_override=5.0,
        bvps_override=10.0,
        quote_override=20.0,
    )

    assert assembly.status is CalculationStatus.OK
    assert _event_signature(assembly.resolution_trace) == [
        ("eps", "override", "success"),
        ("bvps", "override", "success"),
        ("current_price", "override", "success"),
    ]
    assert provider.calls == []


def test_optional_quote_unavailability_is_retained_in_method_trace() -> None:
    """A valid valuation keeps its value while diagnostics retain quote degradation."""
    eps = _fact(
        ValuationField.EPS,
        5.0,
        units=ValuationUnit.CURRENCY_PER_SHARE,
        basis="ttm",
        currency="USD",
    )
    bvps = _fact(
        ValuationField.BVPS,
        10.0,
        units=ValuationUnit.CURRENCY_PER_SHARE,
        currency="USD",
    )
    provider = RecordingProvider(
        {
            ValuationField.EPS: (eps,),
            ValuationField.BVPS: (bvps,),
        }
    )
    resolver = InputResolver(provider=provider, clock=lambda: NOW)

    assembly = resolver.assemble_graham_number(
        security_subject_id="NDAQ",
        security_provider_id="fixture",
        eps_basis="ttm",
    )

    assert assembly.status is CalculationStatus.OK
    assert assembly.quote_status is CalculationStatus.INPUT_UNAVAILABLE
    assert assembly.current_price is None
    signatures = _event_signature(assembly.resolution_trace)
    assert signatures[-2:] == [
        ("current_price", "provider", "attempted"),
        ("current_price", "provider", "unavailable"),
    ]
