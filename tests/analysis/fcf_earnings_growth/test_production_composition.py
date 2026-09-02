"""Focused D4 tests for production annual-series composition."""

from __future__ import annotations

from dataclasses import replace

from src.analysis.fcf_earnings_growth import (
    FCFEarningsGrowthPolicy,
    ProductionAnnualGrowthSeriesResolver,
)
from src.core.analysis_status import CalculationStatus
from src.data.financial.facts import FinancialField
from src.data.financial.production import ProductionFinancialFactsProvider
from src.data.financial.provenance import SourceKind
from src.data.sec_edgar import SEC_PROVIDER_ID
from src.evaluation.fixtures.fcf_earnings_growth import (
    FixtureAnnualFinancialFactsProvider,
    annual_series,
)
from tests.analysis.fcf_earnings_growth.test_fcf_earnings_growth_input_resolver import NOW


def _sec_annual_provider(
    *, error_field: FinancialField | None = None
) -> tuple[ProductionFinancialFactsProvider, FixtureAnnualFinancialFactsProvider]:
    """Build the production façade around deterministic SEC annual facts."""
    facts = tuple(replace(fact, provider_id=SEC_PROVIDER_ID) for fact in annual_series(range(2020, 2026)))
    sec_adapter = FixtureAnnualFinancialFactsProvider(facts, error_field=error_field)
    return ProductionFinancialFactsProvider(sec_edgar=sec_adapter), sec_adapter


def test_sec_composition_resolves_all_required_fields_with_provenance() -> None:
    provider, sec_adapter = _sec_annual_provider()
    resolver = ProductionAnnualGrowthSeriesResolver(provider, clock=lambda: NOW)

    result = resolver.resolve(
        policy=FCFEarningsGrowthPolicy(),
        subject_id="ACME",
        currency="USD",
        as_of=None,
    )

    assert result.status is CalculationStatus.OK
    assert [request.field_name for request in sec_adapter.requests] == [
        FinancialField.OPERATING_CASH_FLOW,
        FinancialField.CAPITAL_EXPENDITURES,
        FinancialField.EPS,
        FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES,
    ]
    for observation in result.observations:
        assert observation.operating_cash_flow.provider_id == SEC_PROVIDER_ID
        assert observation.normalized_capital_expenditures.provider_id == SEC_PROVIDER_ID
        assert observation.diluted_eps.provider_id == SEC_PROVIDER_ID
        assert observation.free_cash_flow.source_kind is SourceKind.DERIVED
        assert observation.free_cash_flow.lineage is not None
        assert len(observation.free_cash_flow.lineage.components) == 2


def test_unapproved_provider_is_typed_unavailable_without_provider_work() -> None:
    provider, sec_adapter = _sec_annual_provider()
    resolver = ProductionAnnualGrowthSeriesResolver(provider, clock=lambda: NOW)

    result = resolver.resolve(
        policy=FCFEarningsGrowthPolicy(),
        subject_id="ACME",
        currency="USD",
        as_of=None,
        provider_id="unsupported-provider",
    )

    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.reason is not None
    assert "does not have approved" in result.reason
    assert sec_adapter.requests == []
    assert len(result.resolution_trace.events) == 1


def test_sec_provider_failure_remains_a_typed_provider_error() -> None:
    provider, sec_adapter = _sec_annual_provider(error_field=FinancialField.EPS)
    resolver = ProductionAnnualGrowthSeriesResolver(provider, clock=lambda: NOW)

    result = resolver.resolve(
        policy=FCFEarningsGrowthPolicy(),
        subject_id="ACME",
        currency="USD",
        as_of=None,
    )

    assert result.status is CalculationStatus.PROVIDER_ERROR
    assert result.reason is not None
    assert "eps provider failed" in result.reason
    assert sec_adapter.requests[-1].field_name is FinancialField.EPS
