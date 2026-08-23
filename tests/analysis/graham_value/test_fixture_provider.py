"""Step 2.3 Slice D: Fixture-backed provider, resolver, and assembly tests.

These tests exercise the ``ValuationFactsProvider`` protocol implementation
(``FixtureValuationProvider``), the ``InputResolver`` (single-fact and
three-year-average EPS paths), and the C2D method-level assembly
(``assemble_graham_number`` / ``assemble_growth_value``) using only
deterministic fixture data.

No network, filesystem, or wall-clock dependency.
"""

from __future__ import annotations

import math
import socket
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from src.analysis.graham_value.cache import InMemoryValuationCache
from src.analysis.graham_value.facts import (
    ProviderFact,
    ValuationFactRequest,
    ValuationFactsProvider,
    ValuationField,
    ValuationProviderError,
    ValuationUnit,
)
from src.analysis.graham_value.models import CalculationStatus
from src.analysis.graham_value.provenance import (
    ResolvedInput,
    SourceKind,
    ValuationSubjectKind,
)
from src.analysis.graham_value.resolver import InputResolver
from tests.analysis.graham_value.fixture_valuation_provider import (
    AAA_YIELD_VALUE,
    BVPS_VALUE,
    EPS_FY2022,
    EPS_FY2023,
    EPS_FY2024,
    EPS_TTM,
    MACRO_ID,
    NOW,
    PROVIDER_ID,
    QUOTE_VALUE,
    SECURITY_ID,
    SUBJECT_ERROR,
    SUBJECT_FUTURE,
    SUBJECT_INCOMPATIBLE,
    SUBJECT_MISSING,
    FixtureValuationProvider,
)

# ---------------------------------------------------------------------------
# Mutable clock for cache staleness tests
# ---------------------------------------------------------------------------


class MutableClock:
    """A controllable clock for deterministic time-based tests."""

    def __init__(self, initial: datetime) -> None:
        """Initialize with a fixed starting time."""
        self.current = initial

    def __call__(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta


# ---------------------------------------------------------------------------
# Error-raising provider stub for override/cache precedence tests
# ---------------------------------------------------------------------------


class ErrorProvider:
    """A provider that always raises ``ValuationProviderError``.

    Used to prove that override or cache short-circuits the provider call.
    If the provider is reached, the test will fail.
    """

    def fetch_facts(self, request: ValuationFactRequest) -> tuple[ProviderFact, ...]:  # noqa: ARG002
        """Always raises to prove the provider was reached.

        Args:
            request: Ignored; presence proves the provider was called.
        """
        raise ValuationProviderError("Provider was reached; override/cache should have short-circuited.")


# ===========================================================================
# Correction 2: Non-finite fixture-boundary tests
# ===========================================================================


class TestProviderFactBoundary:
    """Verify that non-finite values are rejected at the ProviderFact boundary."""

    def _make_fact_kwargs(self) -> dict[str, Any]:
        """Return base kwargs for a minimal valid ProviderFact."""
        return {
            "subject_kind": ValuationSubjectKind.SECURITY,
            "subject_id": SECURITY_ID,
            "field_name": ValuationField.BVPS,
            "units": ValuationUnit.CURRENCY_PER_SHARE,
            "provider_id": PROVIDER_ID,
            "provider_field": "fx_bvps",
            "retrieved_at": NOW,
            "currency": "USD",
        }

    @pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
    def test_provider_fact_rejects_non_finite_value(self, bad_value: float) -> None:
        """Constructing a ProviderFact with NaN or Inf must raise ValueError."""
        kwargs = self._make_fact_kwargs()
        kwargs["value"] = bad_value
        with pytest.raises(ValueError, match="must be finite"):
            ProviderFact(**kwargs)

    def test_non_finite_cannot_enter_resolution(self) -> None:
        """A non-finite value cannot enter the resolver as a valid fact.

        Since ProviderFact construction rejects non-finite values at the
        boundary, no valid ProviderFact carrying NaN/Inf can be returned
        from a provider and therefore cannot be processed by the resolver.
        """
        for bad in (float("nan"), float("inf"), float("-inf")):
            kwargs = self._make_fact_kwargs()
            kwargs["value"] = bad
            with pytest.raises(ValueError, match="must be finite"):
                ProviderFact(**kwargs)

        # A valid ProviderFact with a finite value CAN be constructed:
        kwargs = self._make_fact_kwargs()
        kwargs["value"] = 42.0
        fact = ProviderFact(**kwargs)
        assert math.isfinite(fact.value)


# ===========================================================================
# FixtureProvider contract tests
# ===========================================================================


class TestFixtureProviderContract:
    """Verify the fixture provider satisfies the protocol contract."""

    def test_satisfies_protocol(self) -> None:
        """FixtureValuationProvider is structurally compatible with ValuationFactsProvider."""
        provider = FixtureValuationProvider()
        assert isinstance(provider, ValuationFactsProvider)

    def test_happy_path_returns_non_empty_tuple(self) -> None:
        """SYNTH subject returns a non-empty tuple for BVPS."""
        provider = FixtureValuationProvider()
        request = ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=SECURITY_ID,
            field_name=ValuationField.BVPS,
            provider_id=PROVIDER_ID,
        )
        facts = provider.fetch_facts(request)
        assert len(facts) == 1
        assert facts[0].value == BVPS_VALUE

    def test_missing_subject_returns_empty_tuple(self) -> None:
        """MISSING subject returns an empty tuple (fact unavailable)."""
        provider = FixtureValuationProvider()
        request = ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=SUBJECT_MISSING,
            field_name=ValuationField.BVPS,
            provider_id=PROVIDER_ID,
        )
        facts = provider.fetch_facts(request)
        assert facts == ()

    def test_error_subject_raises(self) -> None:
        """ERROR subject raises ValuationProviderError."""
        provider = FixtureValuationProvider()
        request = ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=SUBJECT_ERROR,
            field_name=ValuationField.BVPS,
            provider_id=PROVIDER_ID,
        )
        with pytest.raises(ValuationProviderError):
            provider.fetch_facts(request)

    def test_unsupported_eps_basis_returns_empty(self) -> None:
        """Unsupported EPS basis (not ttm, not observation_count=3) returns empty."""
        provider = FixtureValuationProvider()
        request = ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=SECURITY_ID,
            field_name=ValuationField.EPS,
            provider_id=PROVIDER_ID,
            basis="unsupported_basis",
        )
        facts = provider.fetch_facts(request)
        assert facts == ()

    def test_ttm_eps_returns_single_fact(self) -> None:
        """EPS with basis='ttm' returns exactly one TTM fact."""
        provider = FixtureValuationProvider()
        request = ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=SECURITY_ID,
            field_name=ValuationField.EPS,
            provider_id=PROVIDER_ID,
            basis="ttm",
        )
        facts = provider.fetch_facts(request)
        assert len(facts) == 1
        assert facts[0].value == EPS_TTM
        assert facts[0].basis == "ttm"

    def test_three_year_eps_returns_three_facts(self) -> None:
        """EPS with observation_count=3 returns three fiscal-year facts."""
        provider = FixtureValuationProvider()
        request = ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=SECURITY_ID,
            field_name=ValuationField.EPS,
            provider_id=PROVIDER_ID,
            basis="fiscal_year",
            observation_count=3,
        )
        facts = provider.fetch_facts(request)
        assert len(facts) == 3
        values = sorted(f.value for f in facts)
        assert values == [EPS_FY2022, EPS_FY2023, EPS_FY2024]


# ===========================================================================
# Resolver single-fact tests
# ===========================================================================


class TestResolverSingleFact:
    """Exercise the single-fact resolve() path."""

    def test_resolve_happy_path(self) -> None:
        """BVPS resolves to a PROVIDER-sourced ResolvedInput."""
        provider = FixtureValuationProvider()
        resolver = InputResolver(provider=provider, clock=lambda: NOW)
        request = ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=SECURITY_ID,
            field_name=ValuationField.BVPS,
            provider_id=PROVIDER_ID,
        )
        result = resolver.resolve(request)
        assert result.status is CalculationStatus.OK
        assert result.resolved_input is not None
        assert result.resolved_input.value == pytest.approx(BVPS_VALUE)
        assert result.resolved_input.source_kind is SourceKind.PROVIDER

    def test_resolve_missing(self) -> None:
        """MISSING subject yields INPUT_UNAVAILABLE."""
        provider = FixtureValuationProvider()
        resolver = InputResolver(provider=provider, clock=lambda: NOW)
        request = ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=SUBJECT_MISSING,
            field_name=ValuationField.BVPS,
            provider_id=PROVIDER_ID,
        )
        result = resolver.resolve(request)
        assert result.status is CalculationStatus.INPUT_UNAVAILABLE

    def test_resolve_error(self) -> None:
        """ERROR subject yields PROVIDER_ERROR."""
        provider = FixtureValuationProvider()
        resolver = InputResolver(provider=provider, clock=lambda: NOW)
        request = ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=SUBJECT_ERROR,
            field_name=ValuationField.BVPS,
            provider_id=PROVIDER_ID,
        )
        result = resolver.resolve(request)
        assert result.status is CalculationStatus.PROVIDER_ERROR

    def test_resolve_incompatible_basis(self) -> None:
        """INCOMPATIBLE subject (mismatched basis) yields PROVIDER_ERROR."""
        provider = FixtureValuationProvider()
        resolver = InputResolver(provider=provider, clock=lambda: NOW)
        request = ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=SUBJECT_INCOMPATIBLE,
            field_name=ValuationField.EPS,
            provider_id=PROVIDER_ID,
            basis="ttm",
        )
        result = resolver.resolve(request)
        assert result.status is CalculationStatus.PROVIDER_ERROR


# ===========================================================================
# Correction 3: Fail-closed network guard tests
# ===========================================================================


class TestNetworkGuard:
    """Exercise a fixture-backed resolver flow while network is blocked."""

    def _block_network(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Monkeypatch socket to raise on any connection attempt."""

        def _blocked(*_args: object, **_kwargs: object) -> None:
            """Raise to block any network access."""
            msg = "Network access attempted during deterministic test."
            raise RuntimeError(msg)

        monkeypatch.setattr(socket, "create_connection", _blocked)
        monkeypatch.setattr(socket, "getaddrinfo", _blocked)

    def test_resolver_works_with_network_blocked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Full resolve flow succeeds while all socket operations are blocked."""
        self._block_network(monkeypatch)

        provider = FixtureValuationProvider()
        cache = InMemoryValuationCache(clock=lambda: NOW)
        resolver = InputResolver(provider=provider, cache=cache, clock=lambda: NOW)

        # Resolve a single fact (BVPS) — must succeed without network.
        request = ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=SECURITY_ID,
            field_name=ValuationField.BVPS,
            provider_id=PROVIDER_ID,
        )
        result = resolver.resolve(request)
        assert result.status is CalculationStatus.OK
        assert result.resolved_input is not None
        assert result.resolved_input.value == pytest.approx(BVPS_VALUE)

    def test_resolve_three_year_eps_with_network_blocked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Three-year-average EPS assembly succeeds while network is blocked."""
        self._block_network(monkeypatch)

        provider = FixtureValuationProvider()
        resolver = InputResolver(provider=provider, clock=lambda: NOW)

        request = ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=SECURITY_ID,
            field_name=ValuationField.EPS,
            provider_id=PROVIDER_ID,
            basis="fiscal_year",
            observation_count=3,
        )
        result = resolver.resolve_three_year_average_eps(request)
        assert result.status is CalculationStatus.OK
        assert result.resolved_input is not None
        expected = (EPS_FY2022 + EPS_FY2023 + EPS_FY2024) / 3.0
        assert result.resolved_input.value == pytest.approx(expected)


# ===========================================================================
# Correction 4: Stale/cache-ineligible integration test
# ===========================================================================


class TestCacheStaleness:
    """Verify that stale/cache-ineligible entries do not silently win."""

    def test_stale_cache_entry_is_rejected(self) -> None:
        """A cache entry older than TTL is treated as a miss; provider is used."""
        provider = FixtureValuationProvider()
        cache = InMemoryValuationCache(clock=lambda: NOW, ttl=timedelta(hours=1))
        resolver = InputResolver(provider=provider, cache=cache, clock=lambda: NOW)

        # First resolve populates the cache.
        request = ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=SECURITY_ID,
            field_name=ValuationField.BVPS,
            provider_id=PROVIDER_ID,
        )
        result1 = resolver.resolve(request)
        assert result1.status is CalculationStatus.OK

        # Advance the clock beyond TTL.
        # Use a mutable clock to advance time.
        mutable_clock = MutableClock(NOW)
        cache2 = InMemoryValuationCache(clock=mutable_clock, ttl=timedelta(hours=1))
        resolver2 = InputResolver(provider=provider, cache=cache2, clock=mutable_clock)

        # Populate cache with entry at NOW.
        result2a = resolver2.resolve(request)
        assert result2a.status is CalculationStatus.OK

        # Advance past TTL — entry is now stale.
        mutable_clock.advance(timedelta(hours=2))

        # Resolve again: cache entry is stale, so provider is called.
        result2b = resolver2.resolve(request)
        assert result2b.status is CalculationStatus.OK
        assert result2b.resolved_input is not None
        assert result2b.resolved_input.source_kind is SourceKind.PROVIDER

    def test_cache_hit_returns_cache_sourced_input(self) -> None:
        """A fresh cache entry is served as CACHE source."""
        provider = FixtureValuationProvider()
        mutable_clock = MutableClock(NOW)
        cache = InMemoryValuationCache(clock=mutable_clock, ttl=timedelta(hours=24))
        resolver = InputResolver(provider=provider, cache=cache, clock=mutable_clock)

        request = ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=SECURITY_ID,
            field_name=ValuationField.BVPS,
            provider_id=PROVIDER_ID,
        )

        # First call: populates cache, returns PROVIDER.
        result1 = resolver.resolve(request)
        assert result1.status is CalculationStatus.OK
        assert result1.resolved_input is not None
        assert result1.resolved_input.source_kind is SourceKind.PROVIDER

        # Second call: cache hit, returns CACHE source.
        result2 = resolver.resolve(request)
        assert result2.status is CalculationStatus.OK
        assert result2.resolved_input is not None
        assert result2.resolved_input.source_kind is SourceKind.CACHE
        assert result2.resolved_input.origin_source_kind is SourceKind.PROVIDER

    def test_future_published_facts_rejected_with_as_of(self) -> None:
        """A fact with available_at after as_of is rejected (future publication)."""
        provider = FixtureValuationProvider()
        resolver = InputResolver(provider=provider, clock=lambda: NOW)

        # Use a historical as_of boundary that is before FUTURE_AVAIL (2025-08-01).
        historical_as_of = datetime(2025, 7, 1, 12, 0, tzinfo=UTC)
        request = ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=SUBJECT_FUTURE,
            field_name=ValuationField.BVPS,
            provider_id=PROVIDER_ID,
            as_of=historical_as_of,
        )
        result = resolver.resolve(request)
        # The FUTURE subject returns a fact with available_at=2025-08-01 > as_of
        assert result.status is CalculationStatus.INPUT_UNAVAILABLE


# ===========================================================================
# Correction 5: Three-year-average EPS provenance tests
# ===========================================================================


class TestThreeYearEPSProvenance:
    """Strengthen three-year-average EPS provenance assertions."""

    def _resolve_3yr(self) -> ResolvedInput:
        """Helper: resolve 3-year average EPS and return the ResolvedInput."""
        provider = FixtureValuationProvider()
        resolver = InputResolver(provider=provider, clock=lambda: NOW)
        request = ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=SECURITY_ID,
            field_name=ValuationField.EPS,
            provider_id=PROVIDER_ID,
            basis="fiscal_year",
            observation_count=3,
        )
        result = resolver.resolve_three_year_average_eps(request)
        assert result.status is CalculationStatus.OK
        assert result.resolved_input is not None
        return result.resolved_input

    def test_source_kind_is_derived(self) -> None:
        """The three-year average result has SourceKind.DERIVED."""
        ri = self._resolve_3yr()
        assert ri.source_kind is SourceKind.DERIVED

    def test_lineage_has_exactly_three_components(self) -> None:
        """The lineage contains exactly three component ResolvedInputs."""
        ri = self._resolve_3yr()
        assert ri.lineage is not None
        assert len(ri.lineage.components) == 3

    def test_component_values_match_fixture_years(self) -> None:
        """Component EPS values match the three fixture fiscal-year observations."""
        ri = self._resolve_3yr()
        assert ri.lineage is not None
        component_values = sorted(c.value for c in ri.lineage.components)
        assert component_values == pytest.approx([EPS_FY2022, EPS_FY2023, EPS_FY2024])

    def test_component_provenance_preserved(self) -> None:
        """Component observations preserve fixture-provider provenance."""
        ri = self._resolve_3yr()
        assert ri.lineage is not None
        for comp in ri.lineage.components:
            assert comp.source_kind is SourceKind.PROVIDER
            assert comp.provider_id == PROVIDER_ID
            assert comp.provider_field is not None
            assert comp.basis == "fiscal_year"

    def test_result_value_is_arithmetic_mean(self) -> None:
        """The derived value equals the arithmetic mean of three observations."""
        ri = self._resolve_3yr()
        expected = (EPS_FY2022 + EPS_FY2023 + EPS_FY2024) / 3.0
        assert ri.value == pytest.approx(expected)


# ===========================================================================
# Correction 6: Override/cache precedence tests proving provider bypass
# ===========================================================================


class TestOverrideCachePrecedence:
    """Prove that override/cache actually short-circuits the provider."""

    def test_override_short_circuits_error_provider(self) -> None:
        """Override succeeds even when the provider would raise."""
        error_provider = ErrorProvider()
        resolver = InputResolver(provider=error_provider, clock=lambda: NOW)

        request = ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=SECURITY_ID,
            field_name=ValuationField.BVPS,
            provider_id=PROVIDER_ID,
        )
        override_value = 99.0
        result = resolver.resolve(request, override=override_value)
        assert result.status is CalculationStatus.OK
        assert result.resolved_input is not None
        assert result.resolved_input.source_kind is SourceKind.OVERRIDE
        assert result.resolved_input.value == override_value

    def test_cache_short_circuits_error_provider(self) -> None:
        """Cache hit succeeds even when the provider would raise."""
        # Build a cache entry using the fixture provider first.
        fixture_provider = FixtureValuationProvider()
        mutable_clock = MutableClock(NOW)
        cache = InMemoryValuationCache(clock=mutable_clock, ttl=timedelta(hours=24))
        fixture_resolver = InputResolver(provider=fixture_provider, cache=cache, clock=mutable_clock)

        request = ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=SECURITY_ID,
            field_name=ValuationField.BVPS,
            provider_id=PROVIDER_ID,
        )
        # Populate the cache.
        result_populate = fixture_resolver.resolve(request)
        assert result_populate.status is CalculationStatus.OK

        # Now use the error provider with the same cache — must hit cache.
        error_provider = ErrorProvider()
        error_resolver = InputResolver(provider=error_provider, cache=cache, clock=mutable_clock)
        result = error_resolver.resolve(request)
        assert result.status is CalculationStatus.OK
        assert result.resolved_input is not None
        assert result.resolved_input.source_kind is SourceKind.CACHE
        assert result.resolved_input.origin_source_kind is SourceKind.PROVIDER

    def test_provider_error_when_no_override_or_cache(self) -> None:
        """Without override or cache, the error provider causes PROVIDER_ERROR."""
        error_provider = ErrorProvider()
        resolver = InputResolver(provider=error_provider, clock=lambda: NOW)

        request = ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=SECURITY_ID,
            field_name=ValuationField.BVPS,
            provider_id=PROVIDER_ID,
        )
        result = resolver.resolve(request)
        assert result.status is CalculationStatus.PROVIDER_ERROR
        assert result.resolved_input is None


# ===========================================================================
# C2D method-assembly integration tests
# ===========================================================================


class TestC2DAssembly:
    """Prove the fixture works through both C2D method-level assembly paths."""

    def test_graham_number_assembly_three_year_avg(self) -> None:
        """assemble_graham_number() succeeds via fixture-backed three-year-average EPS."""
        provider = FixtureValuationProvider()
        resolver = InputResolver(provider=provider, clock=lambda: NOW)

        result = resolver.assemble_graham_number(
            security_subject_id=SECURITY_ID,
            security_provider_id=PROVIDER_ID,
            eps_basis="three_year_average",
        )

        assert result.status is CalculationStatus.OK

        # EPS: derived (three-year average)
        assert result.eps is not None
        assert result.eps.source_kind is SourceKind.DERIVED
        expected_eps = (EPS_FY2022 + EPS_FY2023 + EPS_FY2024) / 3.0
        assert result.eps.value == pytest.approx(expected_eps)

        # BVPS: from fixture provider
        assert result.bvps is not None
        assert result.bvps.source_kind is SourceKind.PROVIDER
        assert result.bvps.value == pytest.approx(BVPS_VALUE)
        assert result.bvps.provider_id == PROVIDER_ID

        # Optional quote: from fixture provider
        assert result.current_price is not None
        assert result.current_price.source_kind is SourceKind.PROVIDER
        assert result.current_price.value == pytest.approx(QUOTE_VALUE)
        assert result.current_price.provider_id == PROVIDER_ID

    def test_growth_value_assembly_ttm_eps(self) -> None:
        """assemble_growth_value() succeeds via fixture-backed TTM EPS and AAA yield."""
        provider = FixtureValuationProvider()
        resolver = InputResolver(provider=provider, clock=lambda: NOW)

        expected_growth = 12.0  # explicit override-only
        result = resolver.assemble_growth_value(
            security_subject_id=SECURITY_ID,
            security_provider_id=PROVIDER_ID,
            eps_basis="ttm",
            expected_growth=expected_growth,
            aaa_subject_id=MACRO_ID,
            aaa_provider_id=PROVIDER_ID,
        )

        assert result.status is CalculationStatus.OK

        # EPS: TTM from fixture provider
        assert result.eps is not None
        assert result.eps.source_kind is SourceKind.PROVIDER
        assert result.eps.value == pytest.approx(EPS_TTM)
        assert result.eps.basis == "ttm"

        # Expected growth: override
        assert result.expected_growth is not None
        assert result.expected_growth.source_kind is SourceKind.OVERRIDE
        assert result.expected_growth.value == expected_growth

        # AAA yield: from fixture provider
        assert result.current_aaa_yield is not None
        assert result.current_aaa_yield.source_kind is SourceKind.PROVIDER
        assert result.current_aaa_yield.value == pytest.approx(AAA_YIELD_VALUE)
        assert result.current_aaa_yield.provider_id == PROVIDER_ID

        # Optional quote: from fixture provider
        assert result.current_price is not None
        assert result.current_price.source_kind is SourceKind.PROVIDER
        assert result.current_price.value == pytest.approx(QUOTE_VALUE)
