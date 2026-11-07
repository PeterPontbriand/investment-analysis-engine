"""The application tier: each strategy's run function paired with its core bundle.

``APPLICATION_STRATEGIES`` is the closed, statically declared tuple of strategy application compositions. Each entry
is built by ``pair_application``, which takes a strategy's typed ``StrategyBehavior`` and its
``ApplicationComposition`` and ties them by selection type, so pairing one strategy's functions with another strategy's
bundle fails ``mypy --strict``. Nothing here discovers or registers a composition: the lookups below are pure functions
of the declared tuples, and a strategy without an entry fails closed with ``UndeclaredStrategyError``. No strategy is
a default.

This module is the one declaration in ``investment_analysis_engine/application/`` that names the strategies, as the
CLI tier does for the commands. The functions it pairs are each strategy's ``application`` module.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Final, Protocol

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.strategy_run import StrategyRun
from investment_analysis_engine.core.strategy_errors import UndeclaredStrategyError, describe, require, undeclared
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.strategies.fcf_growth.application import run as run_fcf_growth
from investment_analysis_engine.strategies.graham_growth.application import run as run_graham_growth
from investment_analysis_engine.strategies.graham_number.application import run as run_graham_number
from investment_analysis_engine.strategies.momentum.application import run as run_momentum
from investment_analysis_engine.strategies.piotroski.application import run as run_piotroski
from investment_analysis_engine.strategy_wiring import (
    FCF_GROWTH_BEHAVIOR,
    GRAHAM_GROWTH_BEHAVIOR,
    GRAHAM_NUMBER_BEHAVIOR,
    MOMENTUM_BEHAVIOR,
    PIOTROSKI_BEHAVIOR,
    STRATEGIES,
    StrategyBehavior,
    StrategyDescriptor,
)
from investment_analysis_engine.workspace.strategy_types import NativeEvidence, SelectionMember


class AnalysisRunner[SelT: SelectionMember](Protocol):
    """A strategy's run function: one ticker and one selection, with the run's own clock and profile cache."""

    def __call__(
        self,
        context: ApplicationContext,
        ticker: str,
        selection: SelT,
        /,
        *,
        executed_at: datetime,
        profile_cache: InstrumentProfileResolver | None,
    ) -> StrategyRun:
        """Run the strategy and return the run with the means to present it."""
        ...


@dataclass(frozen=True)
class ApplicationComposition[SelT: SelectionMember]:
    """One strategy's run function, over its own selection class.

    Attributes:
        run: Runs the strategy for a direct analysis or a refresh job and returns the run with the means to present it.
    """

    run: AnalysisRunner[SelT]


@dataclass(frozen=True)
class ApplicationStrategy:
    """A composition paired with the core bundle of the strategy it serves, with the selection type erased.

    ``behavior`` is the very bundle object a descriptor holds, so identity finds the descriptor it serves. Both
    functions check that the selection they receive is exactly the paired bundle's selection class.
    """

    behavior: object
    run: AnalysisRunner[SelectionMember]


def pair_application[SelT: SelectionMember, ResultT: NativeEvidence, DepsT](
    behavior: StrategyBehavior[SelT, ResultT, DepsT],
    composition: ApplicationComposition[SelT],
) -> ApplicationStrategy:
    """Pair a strategy's core bundle with a composition for exactly its selection class."""

    def run(
        context: ApplicationContext,
        ticker: str,
        selection: SelectionMember,
        /,
        *,
        executed_at: datetime,
        profile_cache: InstrumentProfileResolver | None,
    ) -> StrategyRun:
        if not isinstance(selection, behavior.selection_type) or type(selection) is not behavior.selection_type:
            raise undeclared("selection type", type(selection))
        return composition.run(context, ticker, selection, executed_at=executed_at, profile_cache=profile_cache)

    return ApplicationStrategy(behavior=behavior, run=run)


APPLICATION_STRATEGIES: Final = (
    pair_application(MOMENTUM_BEHAVIOR, ApplicationComposition(run=run_momentum)),
    pair_application(GRAHAM_NUMBER_BEHAVIOR, ApplicationComposition(run=run_graham_number)),
    pair_application(GRAHAM_GROWTH_BEHAVIOR, ApplicationComposition(run=run_graham_growth)),
    pair_application(FCF_GROWTH_BEHAVIOR, ApplicationComposition(run=run_fcf_growth)),
    pair_application(PIOTROSKI_BEHAVIOR, ApplicationComposition(run=run_piotroski)),
)


def application_entries(
    descriptors: tuple[StrategyDescriptor, ...],
    tier: tuple[ApplicationStrategy, ...] = APPLICATION_STRATEGIES,
) -> tuple[tuple[StrategyDescriptor, ApplicationStrategy], ...]:
    """Pair each descriptor with its application-tier entry, in declaration order.

    An entry belongs to the descriptor whose core bundle it was paired with.

    Args:
        descriptors: The declared strategies; each must have exactly one entry.
        tier: The application tier; the declared one unless a caller supplies another.

    Returns:
        Each descriptor with its entry.

    Raises:
        UndeclaredStrategyError: If a descriptor has no entry, naming its identifiers, or an entry was paired
            with a bundle that belongs to no descriptor.
        ValueError: If two entries serve one descriptor.
    """
    descriptor_of_behavior = {id(descriptor.behavior): descriptor for descriptor in descriptors}
    entries: dict[tuple[str, str], ApplicationStrategy] = {}
    for entry in tier:
        descriptor = descriptor_of_behavior.get(id(entry.behavior))
        if descriptor is None:
            raise undeclared("application tier entry for bundle", entry.behavior)
        key = (descriptor.analysis_id, descriptor.method_id)
        if key in entries:
            raise ValueError(f"Duplicate application tier entry for strategy {key!r}.")
        entries[key] = entry
    for descriptor in descriptors:
        key = (descriptor.analysis_id, descriptor.method_id)
        if key not in entries:
            listed = ", ".join(sorted(describe(entry_key) for entry_key in entries))
            raise UndeclaredStrategyError(
                f"The application tier has no entry for strategy {describe(key)}; it has entries for: {listed}."
            )
    return tuple((descriptor, entries[(descriptor.analysis_id, descriptor.method_id)]) for descriptor in descriptors)


def runners_by_key(
    descriptors: tuple[StrategyDescriptor, ...],
    tier: tuple[ApplicationStrategy, ...] = APPLICATION_STRATEGIES,
) -> Mapping[tuple[str, str], AnalysisRunner[SelectionMember]]:
    """Return each descriptor's run function keyed by ``(analysis_id, method_id)``, read-only.

    Raises:
        UndeclaredStrategyError: If a descriptor has no application-tier entry or an entry serves no descriptor.
    """
    return MappingProxyType(
        {
            (descriptor.analysis_id, descriptor.method_id): entry.run
            for descriptor, entry in application_entries(descriptors, tier)
        }
    )


APPLICATION_RUNNERS: Final = runners_by_key(STRATEGIES)


def analysis_runner_for(
    selection: SelectionMember,
    runners: Mapping[tuple[str, str], AnalysisRunner[SelectionMember]] = APPLICATION_RUNNERS,
) -> AnalysisRunner[SelectionMember]:
    """Return the run function of the strategy that owns ``selection``.

    Raises:
        UndeclaredStrategyError: If no declared strategy has a run function for the selection's identifiers.
    """
    return require(runners, (selection.analysis_id, selection.method_id), what="analysis runner")


__all__ = [
    "APPLICATION_RUNNERS",
    "APPLICATION_STRATEGIES",
    "AnalysisRunner",
    "ApplicationComposition",
    "ApplicationStrategy",
    "analysis_runner_for",
    "application_entries",
    "pair_application",
    "runners_by_key",
]
