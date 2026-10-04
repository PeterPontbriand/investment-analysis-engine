"""FCF & Earnings Growth's fixture composition and fixture-capability requirement for the evaluation tier."""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from src.data.financial.facts import ProviderFact
from src.data.sec_edgar import SEC_PROVIDER_ID
from src.evaluation.fixture_context import FixtureContext, FixtureRequirement, selected_variant
from src.evaluation.fixture_ids import (
    FCF_GROWTH_NONMEANINGFUL_FIXTURE_ID,
    FCF_GROWTH_PERIOD_AS_OF_FIXTURE_ID,
    FCF_GROWTH_SUCCESS_FIXTURE_ID,
)
from src.evaluation.fixtures.fcf_earnings_growth import (
    FixtureAnnualFinancialFactsProvider,
    fcf_growth_nonmeaningful_facts,
    fcf_growth_period_as_of_facts,
    fcf_growth_success_facts,
)
from src.evaluation.fixtures.sec_edgar_fpi import SEC_FPI_FIXTURE_IDS
from src.strategies.fcf_growth.analyzer import FCFEarningsGrowthAnalyzer
from src.strategies.fcf_growth.input_resolver import ProductionAnnualGrowthSeriesResolver
from src.strategies.fcf_growth.tool import FCFEarningsGrowthToolDependencies

FCF_FIXTURE_IDS: Final = frozenset(
    {
        FCF_GROWTH_SUCCESS_FIXTURE_ID,
        FCF_GROWTH_NONMEANINGFUL_FIXTURE_ID,
        FCF_GROWTH_PERIOD_AS_OF_FIXTURE_ID,
    }
)

REQUIREMENT: Final = FixtureRequirement(
    FCF_FIXTURE_IDS | SEC_FPI_FIXTURE_IDS,
    "FCF/Earnings Growth fact",
    etf_profile_exempt=True,
)
"""FCF needs selected annual facts; affirmative ETF profile evidence for the ticker stands in for them."""


def _annual_facts(fixture_id: str | None) -> tuple[ProviderFact, ...]:
    """Return the selected annual fixture evidence or an explicitly empty set."""
    if fixture_id == FCF_GROWTH_SUCCESS_FIXTURE_ID:
        return fcf_growth_success_facts()
    if fixture_id == FCF_GROWTH_NONMEANINGFUL_FIXTURE_ID:
        return fcf_growth_nonmeaningful_facts()
    if fixture_id == FCF_GROWTH_PERIOD_AS_OF_FIXTURE_ID:
        return fcf_growth_period_as_of_facts()
    return ()


def compose(context: FixtureContext) -> FCFEarningsGrowthToolDependencies:
    """Build FCF & Earnings Growth's dependencies from the selected annual facts."""
    clock_at = context.clock_at
    fixture_id = selected_variant(context.fixture_ids, FCF_FIXTURE_IDS, label="FCF/Earnings Growth facts")
    annual_facts = _annual_facts(fixture_id)
    annual_provider = context.sec_fpi_provider or FixtureAnnualFinancialFactsProvider(
        tuple(replace(fact, provider_id=SEC_PROVIDER_ID) for fact in annual_facts)
    )
    return FCFEarningsGrowthToolDependencies(
        analyzer=FCFEarningsGrowthAnalyzer(
            ProductionAnnualGrowthSeriesResolver(annual_provider, clock=lambda: clock_at)
        ),
        provider_id=SEC_PROVIDER_ID,
    )
