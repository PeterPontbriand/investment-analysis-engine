"""Graham growth-value's fixture composition for the evaluation tier."""

from __future__ import annotations

from typing import Final

from src.evaluation.fixture_context import FixtureContext, FixtureRequirement
from src.evaluation.fixtures.graham import (
    GOLDEN_BASELINE_AAA_YIELD,
    GOLDEN_GROWTH_BASE_PE,
    GOLDEN_GROWTH_MULTIPLIER,
)
from src.strategies._graham.evaluation import REQUIREMENT as GRAHAM_REQUIREMENT
from src.strategies._graham.evaluation import graham_cache, graham_clock, graham_provider, graham_provider_id
from src.strategies.graham_growth.analyzer import GrahamGrowthAnalyzer
from src.strategies.graham_growth.calculation import GrahamGrowthCalculationPolicy, GrahamGrowthInputResolver
from src.strategies.graham_growth.tool import GrahamGrowthToolDependencies

REQUIREMENT: Final[FixtureRequirement] = GRAHAM_REQUIREMENT


def compose(context: FixtureContext) -> GrahamGrowthToolDependencies:
    """Build Graham growth-value's dependencies from the selected Graham facts."""
    resolver = GrahamGrowthInputResolver(
        provider=graham_provider(context), cache=graham_cache(context), clock=graham_clock(context)
    )
    provider_id = graham_provider_id(context)
    return GrahamGrowthToolDependencies(
        analyzer=GrahamGrowthAnalyzer(
            resolver,
            policy=GrahamGrowthCalculationPolicy(
                base_pe=GOLDEN_GROWTH_BASE_PE,
                growth_multiplier=GOLDEN_GROWTH_MULTIPLIER,
                baseline_aaa_yield=GOLDEN_BASELINE_AAA_YIELD,
            ),
        ),
        security_provider_id=provider_id,
        quote_provider_id=provider_id,
    )
