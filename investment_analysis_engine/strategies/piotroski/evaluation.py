"""The Piotroski F-Score strategy's fixture composition for the evaluation tier."""

from typing import Final

from investment_analysis_engine.data.financial.production import ProductionFinancialFactsProvider
from investment_analysis_engine.data.financial.resolver import InputResolver
from investment_analysis_engine.evaluation.fixture_context import FixtureContext, FixtureRequirement, selected_variant
from investment_analysis_engine.evaluation.fixtures.sec_edgar_statements import (
    STATEMENTS_FIXTURE_IDS,
    fixture_statements_adapter,
)
from investment_analysis_engine.strategies.piotroski.analyzer import PiotroskiAnalyzer
from investment_analysis_engine.strategies.piotroski.selection import PiotroskiSelection
from investment_analysis_engine.strategies.piotroski.tool import PiotroskiToolDependencies

FIXTURE_IDS: Final = STATEMENTS_FIXTURE_IDS
REQUIREMENT: Final = FixtureRequirement(FIXTURE_IDS, "Piotroski F-Score statements", etf_profile_exempt=True)
"""The strategy reads captured statements; affirmative ETF profile evidence for the ticker stands in for them."""

SAMPLE_SELECTION: Final = PiotroskiSelection()
"""A valid persisted selection of the strategy's reviewed case: it has no required field."""


def compose(context: FixtureContext) -> PiotroskiToolDependencies:
    """Build the strategy's dependencies: the real SEC adapter over the captured statements of the selected issuer.

    The adapter is the analyzer's resolver provider (through the production provider) and its as-filed SIC source. A
    case that selected no statements, such as an ETF case, gets the first captured issuer, which its profile makes
    unreachable.
    """
    fixture_id = selected_variant(context.fixture_ids, FIXTURE_IDS, label="Piotroski F-Score statements")
    adapter = fixture_statements_adapter(fixture_id or min(FIXTURE_IDS), clock_at=context.clock_at)
    resolver = InputResolver(ProductionFinancialFactsProvider(sec_edgar=adapter), clock=lambda: context.clock_at)
    return PiotroskiToolDependencies(analyzer=PiotroskiAnalyzer(resolver, adapter))
