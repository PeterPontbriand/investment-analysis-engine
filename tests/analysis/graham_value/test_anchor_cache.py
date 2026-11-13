"""A cached input of another fiscal year is never served at the anchor (decision record A.19, M6).

A live run's cache key has no boundary and the cache has no time limit by default, so before this decision an input
cached for an older fiscal year was served for as long as the entry lived. Each test runs once at an older anchor to
fill the cache and then at the newer anchor, and fails without the helper that sets the older entry aside.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.data.financial.cache import InMemoryResolvedInputCache
from investment_analysis_engine.data.financial.facts import (
    FinancialFactRequest,
    FinancialField,
    FinancialUnit,
    ProviderFact,
)
from investment_analysis_engine.data.financial.provenance import FinancialSubjectKind, SourceKind
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from investment_analysis_engine.evaluation.fixtures.graham import FY2024_AVAIL, NOW, RETRIEVED_AT, SECURITY_ID
from tests.analysis.graham_value._anchored import (
    ScriptedProvider,
    anchor_for,
    requested_fields,
    run_growth,
    run_number,
)

OLDER = date(2023, 6, 30)
NEWER = date(2024, 6, 30)


def _older_provider() -> ScriptedProvider:
    """The issuer as it was when its newest annual report was the one for the year ended 2023-06-30."""
    provider = ScriptedProvider()
    provider.anchor = anchor_for(OLDER)
    provider.eps_years_back = 1
    provider.bvps_years_back = 1
    return provider


class ComponentProvider(ScriptedProvider):
    """A provider with no direct BVPS, whose equity and share counts are dated ``component_year_end``."""

    def __init__(self, component_year_end: date) -> None:
        """Serve the three components of a derived BVPS at ``component_year_end``."""
        super().__init__()
        self.component_year_end = component_year_end

    def fetch_facts(self, request: FinancialFactRequest, *, effective_as_of: datetime) -> tuple[ProviderFact, ...]:
        """Serve no direct BVPS, and the components of a derived one."""
        if request.field_name is FinancialField.BVPS:
            self.fact_requests.append(request)
            return ()
        components = {
            FinancialField.STOCKHOLDERS_EQUITY: (100.0, FinancialUnit.CURRENCY, "USD"),
            FinancialField.COMMON_SHARES_OUTSTANDING: (10.0, FinancialUnit.SHARES, None),
            FinancialField.PREFERRED_SHARES_OUTSTANDING: (0.0, FinancialUnit.SHARES, None),
        }
        if request.field_name in components:
            self.fact_requests.append(request)
            value, units, currency = components[request.field_name]
            end = datetime(
                self.component_year_end.year, self.component_year_end.month, self.component_year_end.day, tzinfo=UTC
            )
            return (
                ProviderFact(
                    subject_kind=FinancialSubjectKind.SECURITY,
                    subject_id=SECURITY_ID,
                    field_name=request.field_name,
                    value=value,
                    units=units,
                    provider_id=SEC_PROVIDER_ID,
                    provider_field=f"test:{request.field_name.value}",
                    retrieved_at=RETRIEVED_AT,
                    basis="fiscal_year_end",
                    currency=currency,
                    observation_period_end=end,
                    available_at=FY2024_AVAIL,
                ),
            )
        return super().fetch_facts(request, effective_as_of=effective_as_of)


def test_m6_a_cached_three_year_eps_of_an_older_year_is_set_aside_and_replaced_by_the_providers() -> None:
    cache = InMemoryResolvedInputCache(clock=lambda: NOW)
    first = run_growth(_older_provider(), cache=cache, quote_override=40.0)
    assert first.assembly.status is CalculationStatus.OK
    assert first.assembly.eps is not None
    assert first.assembly.eps.observation_period_end == datetime(2023, 6, 30, tzinfo=UTC)

    provider = ScriptedProvider()
    second = run_growth(provider, cache=cache, quote_override=40.0)
    assert second.assembly.status is CalculationStatus.OK
    eps = second.assembly.eps
    assert eps is not None
    assert eps.observation_period_end == datetime(2024, 6, 30, tzinfo=UTC)
    assert eps.source_kind is not SourceKind.CACHE
    assert eps.value == pytest.approx((2.10 + 3.40 + 4.20) / 3)
    assert requested_fields(provider).count(FinancialField.EPS) == 1, "the provider is asked once, not repeatedly"

    third = ScriptedProvider()
    again = run_growth(third, cache=cache, quote_override=40.0)
    assert again.assembly.status is CalculationStatus.OK
    assert again.assembly.eps is not None
    assert again.assembly.eps.source_kind is SourceKind.CACHE, "the provider's answer replaced the entry"
    assert FinancialField.EPS not in requested_fields(third)


def test_m6_a_cached_direct_bvps_of_an_older_year_is_set_aside_and_replaced_by_the_providers() -> None:
    cache = InMemoryResolvedInputCache(clock=lambda: NOW)
    first = run_number(_older_provider(), cache=cache, quote_override=40.0)
    assert first.assembly.status is CalculationStatus.OK

    provider = ScriptedProvider()
    second = run_number(provider, cache=cache, quote_override=40.0)
    assert second.assembly.status is CalculationStatus.OK
    assert second.assembly.eps is not None
    assert second.assembly.eps.observation_period_end == datetime(2024, 6, 30, tzinfo=UTC)
    bvps = second.assembly.bvps
    assert bvps is not None
    assert bvps.observation_period_end == datetime(2024, 6, 30, tzinfo=UTC)
    assert bvps.source_kind is not SourceKind.CACHE
    assert requested_fields(provider).count(FinancialField.BVPS) == 1

    third = ScriptedProvider()
    again = run_number(third, cache=cache, quote_override=40.0)
    assert again.assembly.bvps is not None
    assert again.assembly.bvps.source_kind is SourceKind.CACHE
    assert FinancialField.BVPS not in requested_fields(third)


def test_m6_a_cached_derived_bvps_and_its_components_of_an_older_year_are_set_aside() -> None:
    cache = InMemoryResolvedInputCache(clock=lambda: NOW)
    older = ComponentProvider(OLDER)
    older.anchor = anchor_for(OLDER)
    older.eps_years_back = 1
    first = run_number(older, cache=cache, quote_override=40.0)
    assert first.assembly.status is CalculationStatus.OK
    assert first.assembly.bvps is not None
    assert first.assembly.bvps.source_kind is SourceKind.DERIVED

    provider = ComponentProvider(NEWER)
    second = run_number(provider, cache=cache, quote_override=40.0)
    assert second.assembly.status is CalculationStatus.OK
    bvps = second.assembly.bvps
    assert bvps is not None
    assert bvps.observation_period_end == datetime(2024, 6, 30, tzinfo=UTC)
    assert bvps.source_kind is not SourceKind.CACHE
    assert bvps.lineage is not None
    assert {component.observation_period_end for component in bvps.lineage.components} == {
        datetime(2024, 6, 30, tzinfo=UTC)
    }


def test_m6_when_the_providers_year_still_differs_the_year_rule_applies_to_its_answer() -> None:
    cache = InMemoryResolvedInputCache(clock=lambda: NOW)
    run_number(_older_provider(), cache=cache, quote_override=40.0)

    provider = _older_provider()
    provider.anchor = anchor_for(NEWER)  # the anchor moved on, and the provider still holds the older year
    second = run_number(provider, cache=cache, quote_override=40.0)
    assert second.assembly.status is CalculationStatus.INPUT_UNAVAILABLE
    assert second.assembly.reason is not None
    assert second.assembly.reason.startswith(
        "Earnings per share is unavailable: The newest fiscal year of diluted EPS ends 2023-06-30, not"
    )
    assert requested_fields(provider).count(FinancialField.EPS) == 1


def test_m6_an_entry_of_the_anchors_year_is_served_from_the_cache() -> None:
    cache = InMemoryResolvedInputCache(clock=lambda: NOW)
    run_number(ScriptedProvider(), cache=cache, quote_override=40.0)
    provider = ScriptedProvider()
    second = run_number(provider, cache=cache, quote_override=40.0)
    assert second.assembly.status is CalculationStatus.OK
    assert FinancialField.EPS not in requested_fields(provider)
    assert FinancialField.BVPS not in requested_fields(provider)
