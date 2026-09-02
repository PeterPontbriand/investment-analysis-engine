"""Deterministic fixture providers used by the Golden Suite and tests."""

from src.evaluation.fixtures.fcf_earnings_growth import (
    FixtureAnnualFinancialFactsProvider,
    annual_fact,
    annual_series,
)
from src.evaluation.fixtures.graham import FixtureFinancialFactsProvider
from src.evaluation.fixtures.instrument_profiles import fixture_instrument_profile
from src.evaluation.fixtures.market_data import FixtureDataClient, FixtureMarketDataProvider

__all__ = [
    "FixtureAnnualFinancialFactsProvider",
    "FixtureDataClient",
    "FixtureFinancialFactsProvider",
    "FixtureMarketDataProvider",
    "annual_fact",
    "annual_series",
    "fixture_instrument_profile",
]
