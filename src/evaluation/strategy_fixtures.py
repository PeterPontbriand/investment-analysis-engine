"""The evaluation tier: each strategy's fixture composition paired with its core bundle.

``EVALUATION_STRATEGIES`` is the closed, statically declared tuple of strategy fixture compositions. Each
entry is built by ``pair_evaluation``, which takes a strategy's typed ``StrategyBehavior`` and its
``EvalComposition`` and ties them by dependency type, so pairing one strategy's composition with another
strategy's bundle fails ``mypy --strict``. Nothing here discovers or registers a composition: the lookup
below is a pure function of the declared tuples, and a descriptor without an entry fails closed.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Final

from src.core.strategy_errors import undeclared
from src.evaluation.fixture_context import (
    CONTEXT_FIXTURE_IDS,
    FixtureCompositionError,
    FixtureContext,
    FixtureRequirement,
    build_fixture_context,
    validate_clock,
)
from src.evaluation.models import Case
from src.orchestrator.tool_names import ToolName
from src.strategies.fcf_growth.evaluation import FIXTURE_IDS as FCF_GROWTH_FIXTURE_IDS
from src.strategies.fcf_growth.evaluation import REQUIREMENT as FCF_GROWTH_REQUIREMENT
from src.strategies.fcf_growth.evaluation import compose as compose_fcf_growth
from src.strategies.graham_growth.evaluation import FIXTURE_IDS as GRAHAM_GROWTH_FIXTURE_IDS
from src.strategies.graham_growth.evaluation import REQUIREMENT as GRAHAM_GROWTH_REQUIREMENT
from src.strategies.graham_growth.evaluation import compose as compose_graham_growth
from src.strategies.graham_number.evaluation import FIXTURE_IDS as GRAHAM_NUMBER_FIXTURE_IDS
from src.strategies.graham_number.evaluation import REQUIREMENT as GRAHAM_NUMBER_REQUIREMENT
from src.strategies.graham_number.evaluation import compose as compose_graham_number
from src.strategies.momentum.evaluation import FIXTURE_IDS as MOMENTUM_FIXTURE_IDS
from src.strategies.momentum.evaluation import REQUIREMENT as MOMENTUM_REQUIREMENT
from src.strategies.momentum.evaluation import compose as compose_momentum
from src.strategy_wiring import (
    FCF_GROWTH_BEHAVIOR,
    GRAHAM_GROWTH_BEHAVIOR,
    GRAHAM_NUMBER_BEHAVIOR,
    MOMENTUM_BEHAVIOR,
    StrategyBehavior,
    StrategyDescriptor,
)
from src.workspace.strategy_types import NativeEvidence


@dataclass(frozen=True)
class EvalComposition[DepsT]:
    """One strategy's fixture requirement and the function that builds its dependency class.

    Attributes:
        requirement: The fixture capability the strategy's tool needs before it can be dispatched.
        fixture_ids: Every identifier the strategy's composition understands, apart from the ones the context
            consumes itself.
        compose: Builds the strategy's own dependency class from the case-level fixture context.
    """

    requirement: FixtureRequirement
    fixture_ids: frozenset[str]
    compose: Callable[[FixtureContext], DepsT]


@dataclass(frozen=True)
class EvaluationStrategy:
    """A composition paired with the core bundle of the strategy it serves, with the dependency type erased.

    ``behavior`` is the very bundle object a descriptor holds, so identity finds the descriptor it serves.
    """

    behavior: object
    requirement: FixtureRequirement
    fixture_ids: frozenset[str]
    compose: Callable[[FixtureContext], object]


def pair_evaluation[ResultT: NativeEvidence, DepsT](
    behavior: StrategyBehavior[ResultT, DepsT],
    composition: EvalComposition[DepsT],
) -> EvaluationStrategy:
    """Pair a strategy's core bundle with a composition that builds exactly its dependency class."""
    return EvaluationStrategy(
        behavior=behavior,
        requirement=composition.requirement,
        fixture_ids=composition.fixture_ids,
        compose=composition.compose,
    )


EVALUATION_STRATEGIES: Final = (
    pair_evaluation(
        MOMENTUM_BEHAVIOR,
        EvalComposition(requirement=MOMENTUM_REQUIREMENT, fixture_ids=MOMENTUM_FIXTURE_IDS, compose=compose_momentum),
    ),
    pair_evaluation(
        GRAHAM_NUMBER_BEHAVIOR,
        EvalComposition(
            requirement=GRAHAM_NUMBER_REQUIREMENT, fixture_ids=GRAHAM_NUMBER_FIXTURE_IDS, compose=compose_graham_number
        ),
    ),
    pair_evaluation(
        GRAHAM_GROWTH_BEHAVIOR,
        EvalComposition(
            requirement=GRAHAM_GROWTH_REQUIREMENT, fixture_ids=GRAHAM_GROWTH_FIXTURE_IDS, compose=compose_graham_growth
        ),
    ),
    pair_evaluation(
        FCF_GROWTH_BEHAVIOR,
        EvalComposition(
            requirement=FCF_GROWTH_REQUIREMENT, fixture_ids=FCF_GROWTH_FIXTURE_IDS, compose=compose_fcf_growth
        ),
    ),
)


def evaluation_by_tool(
    descriptors: tuple[StrategyDescriptor, ...],
    tier: tuple[EvaluationStrategy, ...] = EVALUATION_STRATEGIES,
) -> Mapping[ToolName, EvaluationStrategy]:
    """Map each descriptor's tool to its evaluation-tier entry, in declaration order.

    An entry belongs to the descriptor whose core bundle it was paired with.

    Args:
        descriptors: The declared strategies; each must have exactly one entry.
        tier: The evaluation tier; the declared one unless a caller supplies another.

    Returns:
        A read-only mapping from tool to entry.

    Raises:
        UndeclaredStrategyError: If a descriptor has no entry, naming its tool, or an entry was paired with
            a bundle that belongs to no descriptor.
        ValueError: If two entries serve one descriptor.
    """
    tool_of_behavior = {id(descriptor.behavior): descriptor.tool for descriptor in descriptors}
    entries: dict[ToolName, EvaluationStrategy] = {}
    for entry in tier:
        tool = tool_of_behavior.get(id(entry.behavior))
        if tool is None:
            raise undeclared("evaluation tier entry for bundle", entry.behavior)
        if tool in entries:
            raise ValueError(f"Duplicate evaluation tier entry for tool {tool.value!r}.")
        entries[tool] = entry
    for descriptor in descriptors:
        if descriptor.tool not in entries:
            raise undeclared("evaluation tier entry for tool", descriptor.tool, entries)
    return MappingProxyType({descriptor.tool: entries[descriptor.tool] for descriptor in descriptors})


def supported_fixture_ids(
    descriptors: tuple[StrategyDescriptor, ...],
    tier: tuple[EvaluationStrategy, ...] = EVALUATION_STRATEGIES,
) -> frozenset[str]:
    """Return every fixture identifier a case may select: the context's own and those the tier declares.

    Only entries that serve a descriptor count, so removing a strategy from the descriptors or its entry from
    the tier removes the identifiers only that strategy declared.
    """
    declared = [entry.fixture_ids for entry in evaluation_by_tool(descriptors, tier).values()]
    return CONTEXT_FIXTURE_IDS.union(*declared)


def build_case_context(
    case: Case,
    *,
    clock_at: datetime,
    descriptors: tuple[StrategyDescriptor, ...],
    tier: tuple[EvaluationStrategy, ...] = EVALUATION_STRATEGIES,
) -> FixtureContext:
    """Check the clock and the case's identifiers against the tier, then build the cross-strategy context.

    The checks run in a fixed order: the clock, the identifiers no entry declares, then conflicting shared
    evidence.

    Raises:
        FixtureCompositionError: If the clock is naive, an identifier is declared by no entry or by the
            context, or the case selects conflicting foreign-private-issuer evidence.
        UndeclaredStrategyError: If a descriptor has no entry or an entry serves no descriptor.
    """
    validate_clock(clock_at)
    unknown_ids = frozenset(case.fixture_ids) - supported_fixture_ids(descriptors, tier)
    if unknown_ids:
        joined = ", ".join(sorted(unknown_ids))
        raise FixtureCompositionError(f"Unsupported fixture IDs: {joined}.")
    return build_fixture_context(case, clock_at=clock_at)
