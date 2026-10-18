"""The specimen's fixture composition for the evaluation tier."""

from typing import Final

from investment_analysis_engine.evaluation.fixture_context import FixtureContext, FixtureRequirement
from tests.specimen.analyzer import SpecimenAnalyzer
from tests.specimen.selection import SpecimenSelection
from tests.specimen.tool import SpecimenToolDependencies

FIXTURE_IDS: Final = frozenset({"specimen-value"})
REQUIREMENT: Final = FixtureRequirement(FIXTURE_IDS, "Specimen value", etf_profile_exempt=False)
"""The specimen needs its value fixture; an ETF profile does not stand in for it."""

GOLDEN_MULTIPLIER: Final = 2.0
"""The multiplier the evaluation tier composes with, fixed so a fixture result does not follow the user's settings."""

SAMPLE_SELECTION: Final = SpecimenSelection(value=3.0)
"""A valid persisted selection of the specimen's reviewed case."""


def compose(context: FixtureContext) -> SpecimenToolDependencies:
    """Build the specimen's dependencies; the calculation needs no provider, so the context is not read."""
    del context
    return SpecimenToolDependencies(analyzer=SpecimenAnalyzer(multiplier=GOLDEN_MULTIPLIER))
