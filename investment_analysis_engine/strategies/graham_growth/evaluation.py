"""Graham growth-value's fixture composition for the evaluation tier."""

from __future__ import annotations

from typing import Final

from investment_analysis_engine.evaluation.fixture_context import FixtureContext, FixtureRequirement
from investment_analysis_engine.evaluation.fixtures.graham import (
    GOLDEN_BASELINE_AAA_YIELD,
    GOLDEN_GROWTH_BASE_PE,
    GOLDEN_GROWTH_MULTIPLIER,
)
from investment_analysis_engine.strategies._graham.evaluation import FIXTURE_IDS as GRAHAM_FIXTURE_IDS
from investment_analysis_engine.strategies._graham.evaluation import REQUIREMENT as GRAHAM_REQUIREMENT
from investment_analysis_engine.strategies._graham.evaluation import graham_clock, graham_inputs
from investment_analysis_engine.strategies.graham_growth.analyzer import GrahamGrowthAnalyzer
from investment_analysis_engine.strategies.graham_growth.calculation import (
    GrahamGrowthCalculationPolicy,
    GrahamGrowthInputResolver,
)
from investment_analysis_engine.strategies.graham_growth.selection import GrahamGrowthSelection
from investment_analysis_engine.strategies.graham_growth.tool import GrahamGrowthToolDependencies

FIXTURE_IDS: Final[frozenset[str]] = GRAHAM_FIXTURE_IDS
REQUIREMENT: Final[FixtureRequirement] = GRAHAM_REQUIREMENT

SAMPLE_SELECTION: Final = GrahamGrowthSelection(expected_growth=6.5, aaa_yield_override=4.15)
"""A valid persisted selection with the explicit assumptions of reviewed case GRG-01."""


def compose(context: FixtureContext) -> GrahamGrowthToolDependencies:
    """Build Graham growth-value's dependencies from the selected Graham facts."""
    inputs = graham_inputs(context)
    resolver = GrahamGrowthInputResolver(provider=inputs.provider, cache=inputs.cache, clock=graham_clock(context))
    return GrahamGrowthToolDependencies(
        analyzer=GrahamGrowthAnalyzer(
            resolver,
            policy=GrahamGrowthCalculationPolicy(
                base_pe=GOLDEN_GROWTH_BASE_PE,
                growth_multiplier=GOLDEN_GROWTH_MULTIPLIER,
                baseline_aaa_yield=GOLDEN_BASELINE_AAA_YIELD,
            ),
        ),
    )
