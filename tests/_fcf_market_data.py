"""The FCF yield's dependencies for tests, served by the evaluation fixtures so that no test reaches a live service."""

from dataclasses import replace
from datetime import UTC, datetime

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.data.financial.resolver import InputResolver
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from investment_analysis_engine.evaluation.fixtures.fcf_earnings_growth import (
    FixtureAnnualFinancialFactsProvider,
    FixtureMarketCapProvider,
    FixtureSplitHistoryProvider,
    annual_series,
)
from investment_analysis_engine.strategies.fcf_growth.analyzer import FCFEarningsGrowthAnalyzer, MarketCapDependencies
from investment_analysis_engine.strategies.fcf_growth.input_resolver import ProductionAnnualGrowthSeriesResolver
from investment_analysis_engine.strategies.fcf_growth.models import (
    FCFEarningsGrowthConfig,
    FCFEarningsGrowthPolicy,
    FCFEarningsGrowthResult,
)

CLOCK = datetime(2026, 10, 28, 12, tzinfo=UTC)
"""The day the fixture quote is retrieved and the fixture split history is adjusted."""


def fcf_market_data(*, with_data: bool = False, now: datetime = CLOCK) -> MarketCapDependencies:
    """Return the FCF yield's dependencies over the success fixture's market data, or over none.

    With no data the share count, the anchor year-end and the cover are all unavailable, so the yield is
    ``unavailable`` and nothing else in a run is affected.
    """
    provider = FixtureMarketCapProvider(now, with_data=with_data)
    return MarketCapDependencies(
        resolver=InputResolver(provider, clock=lambda: now),
        split_history=FixtureSplitHistoryProvider(now, with_data=with_data),
        listing=provider,
    )


def fcf_annual_resolver(years: range = range(2020, 2026)) -> ProductionAnnualGrowthSeriesResolver:
    """Return the annual-series resolver over the fixture's annual facts, labelled as SEC EDGAR's."""
    facts = tuple(
        replace(fact, provider_id=SEC_PROVIDER_ID, provider_fact_id=f"fy-{fact.fiscal_year}:{fact.field_name.value}")
        for fact in annual_series(years)
    )
    return ProductionAnnualGrowthSeriesResolver(FixtureAnnualFinancialFactsProvider(facts), clock=lambda: CLOCK)


def fcf_result(market_data: MarketCapDependencies | None = None) -> FCFEarningsGrowthResult:
    """Run the analyzer over the fixture's annual facts, with the success fixture's market data unless given."""
    return FCFEarningsGrowthAnalyzer(
        fcf_annual_resolver(), market_data or fcf_market_data(with_data=True)
    ).run_analysis(
        "ACME",
        FCFEarningsGrowthConfig(policy=FCFEarningsGrowthPolicy(), currency="USD"),
        AnalysisContext(as_of=None, executed_at=CLOCK, use_cache=True),
    )
