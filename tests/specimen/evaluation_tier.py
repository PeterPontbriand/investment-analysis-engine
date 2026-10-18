"""The specimen's evaluation-tier entry and the closed evaluation tier the conformance tests build with it.

``EvaluationStrategy`` types its sample selection with the closed production selection union; the specimen's
selection is not in it, so the one cast below is the specimen's departure from that field's type.
"""

from typing import Final, cast

from investment_analysis_engine.evaluation.strategy_fixtures import EVALUATION_STRATEGIES, EvaluationStrategy
from investment_analysis_engine.workspace.strategy_types import SelectionMember
from tests.specimen.evaluation import FIXTURE_IDS, REQUIREMENT, SAMPLE_SELECTION, compose
from tests.specimen.wiring import SPECIMEN_BEHAVIOR

SPECIMEN_EVALUATION: Final = EvaluationStrategy(
    behavior=SPECIMEN_BEHAVIOR,
    requirement=REQUIREMENT,
    fixture_ids=FIXTURE_IDS,
    compose=compose,
    sample_selection=cast("SelectionMember", SAMPLE_SELECTION),
)

SPECIMEN_EVALUATION_STRATEGIES: Final = (*EVALUATION_STRATEGIES, SPECIMEN_EVALUATION)
