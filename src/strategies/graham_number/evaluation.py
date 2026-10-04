"""Graham Number's fixture composition for the evaluation tier."""

from __future__ import annotations

from typing import Final

from src.evaluation.fixture_context import FixtureContext, FixtureRequirement
from src.strategies._graham.evaluation import REQUIREMENT as GRAHAM_REQUIREMENT
from src.strategies._graham.evaluation import graham_clock, graham_inputs
from src.strategies.graham_number.analyzer import GrahamNumberAnalyzer
from src.strategies.graham_number.calculation import GrahamNumberInputResolver
from src.strategies.graham_number.tool import GrahamNumberToolDependencies

REQUIREMENT: Final[FixtureRequirement] = GRAHAM_REQUIREMENT


def compose(context: FixtureContext) -> GrahamNumberToolDependencies:
    """Build Graham Number's dependencies from the selected Graham facts."""
    inputs = graham_inputs(context)
    resolver = GrahamNumberInputResolver(provider=inputs.provider, cache=inputs.cache, clock=graham_clock(context))
    provider_id = inputs.provider_id
    return GrahamNumberToolDependencies(
        analyzer=GrahamNumberAnalyzer(resolver),
        security_provider_id=provider_id,
        quote_provider_id=provider_id,
    )
