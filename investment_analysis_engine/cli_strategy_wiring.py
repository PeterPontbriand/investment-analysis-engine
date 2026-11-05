"""The CLI tier: each strategy's direct command and selection builder paired with its core bundle.

``CLI_STRATEGIES`` is the closed, statically declared tuple of strategy CLI compositions. Each entry is built
by ``pair_cli``, which takes a strategy's typed ``StrategyBehavior`` and its ``CliComposition`` and ties them by
selection type, so pairing one strategy's functions with another strategy's bundle fails ``mypy --strict``.
Nothing here discovers or registers a composition: the lookups below are pure functions of the declared
tuples, and a strategy without an entry fails closed with ``UndeclaredStrategyError``. No strategy is a default.
``add_strategy_commands`` is the one place a command is added to the Typer application, by iterating the tuple.

The tier exists because these functions import ``cli_support`` and ``typer``, which neither the composition root nor
the evaluation tier may import. Each strategy's run function and refresh executor are paired in the application tier.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

import typer

from investment_analysis_engine.cli_watchlist_flags import WatchlistFlags
from investment_analysis_engine.core.strategy_errors import UndeclaredStrategyError, describe, require, undeclared
from investment_analysis_engine.strategies.fcf_growth.cli import build_selection as build_fcf_growth_selection
from investment_analysis_engine.strategies.fcf_growth.cli import command as fcf_growth_command
from investment_analysis_engine.strategies.graham_growth.cli import build_selection as build_graham_growth_selection
from investment_analysis_engine.strategies.graham_growth.cli import command as graham_growth_command
from investment_analysis_engine.strategies.graham_number.cli import build_selection as build_graham_number_selection
from investment_analysis_engine.strategies.graham_number.cli import command as graham_number_command
from investment_analysis_engine.strategies.momentum.cli import build_selection as build_momentum_selection
from investment_analysis_engine.strategies.momentum.cli import command as momentum_command
from investment_analysis_engine.strategies.piotroski.cli import build_selection as build_piotroski_selection
from investment_analysis_engine.strategies.piotroski.cli import command as piotroski_command
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

type SelectionBuilder = Callable[[WatchlistFlags], SelectionMember]
"""A selection builder with its selection type erased."""


@dataclass(frozen=True)
class CliComposition[SelT: SelectionMember]:
    """One strategy's selection builder and direct command, over its own selection class.

    Attributes:
        build: Builds one validated selection from the watchlist command's flags.
        command: The strategy's direct command, a plain function whose options are its own. The tier supplies
            the command's name, the descriptor's alias.
    """

    build: Callable[[WatchlistFlags], SelT]
    command: Callable[..., None]


@dataclass(frozen=True)
class CliStrategy:
    """A composition paired with the core bundle of the strategy it serves, with the selection type erased.

    ``behavior`` is the very bundle object a descriptor holds, so identity finds the descriptor it serves. The
    builder checks that the selection it returns is exactly the paired bundle's selection class.
    """

    behavior: object
    build: SelectionBuilder
    command: Callable[..., None]


def pair_cli[SelT: SelectionMember, ResultT: NativeEvidence, DepsT](
    behavior: StrategyBehavior[SelT, ResultT, DepsT],
    composition: CliComposition[SelT],
) -> CliStrategy:
    """Pair a strategy's core bundle with a composition for exactly its selection class."""

    def build(flags: WatchlistFlags, /) -> SelectionMember:
        selection = composition.build(flags)
        if type(selection) is not behavior.selection_type:
            raise undeclared("selection type", type(selection))
        return selection

    return CliStrategy(behavior=behavior, build=build, command=composition.command)


CLI_STRATEGIES: Final = (
    pair_cli(
        MOMENTUM_BEHAVIOR,
        CliComposition(build=build_momentum_selection, command=momentum_command),
    ),
    pair_cli(
        GRAHAM_NUMBER_BEHAVIOR,
        CliComposition(build=build_graham_number_selection, command=graham_number_command),
    ),
    pair_cli(
        GRAHAM_GROWTH_BEHAVIOR,
        CliComposition(build=build_graham_growth_selection, command=graham_growth_command),
    ),
    pair_cli(
        FCF_GROWTH_BEHAVIOR,
        CliComposition(build=build_fcf_growth_selection, command=fcf_growth_command),
    ),
    pair_cli(
        PIOTROSKI_BEHAVIOR,
        CliComposition(build=build_piotroski_selection, command=piotroski_command),
    ),
)


def cli_entries(
    descriptors: tuple[StrategyDescriptor, ...],
    tier: tuple[CliStrategy, ...] = CLI_STRATEGIES,
) -> tuple[tuple[StrategyDescriptor, CliStrategy], ...]:
    """Pair each descriptor with its CLI-tier entry, in declaration order.

    An entry belongs to the descriptor whose core bundle it was paired with.

    Args:
        descriptors: The declared strategies; each must have exactly one entry.
        tier: The CLI tier; the declared one unless a caller supplies another.

    Returns:
        Each descriptor with its entry.

    Raises:
        UndeclaredStrategyError: If a descriptor has no entry, naming its identifiers, or an entry was paired
            with a bundle that belongs to no descriptor.
        ValueError: If two entries serve one descriptor.
    """
    descriptor_of_behavior = {id(descriptor.behavior): descriptor for descriptor in descriptors}
    entries: dict[tuple[str, str], CliStrategy] = {}
    for entry in tier:
        descriptor = descriptor_of_behavior.get(id(entry.behavior))
        if descriptor is None:
            raise undeclared("CLI tier entry for bundle", entry.behavior)
        key = (descriptor.analysis_id, descriptor.method_id)
        if key in entries:
            raise ValueError(f"Duplicate CLI tier entry for strategy {key!r}.")
        entries[key] = entry
    for descriptor in descriptors:
        key = (descriptor.analysis_id, descriptor.method_id)
        if key not in entries:
            listed = ", ".join(sorted(describe(entry_key) for entry_key in entries))
            raise UndeclaredStrategyError(
                f"The CLI tier has no entry for strategy {describe(key)}; it has entries for: {listed}."
            )
    return tuple((descriptor, entries[(descriptor.analysis_id, descriptor.method_id)]) for descriptor in descriptors)


def builders_by_alias(
    descriptors: tuple[StrategyDescriptor, ...],
    tier: tuple[CliStrategy, ...] = CLI_STRATEGIES,
) -> Mapping[str, SelectionBuilder]:
    """Return each descriptor's selection builder keyed by its CLI alias, read-only.

    Raises:
        UndeclaredStrategyError: If a descriptor has no CLI-tier entry or an entry serves no descriptor.
    """
    return MappingProxyType({descriptor.alias: entry.build for descriptor, entry in cli_entries(descriptors, tier)})


def add_strategy_commands(
    app: typer.Typer,
    descriptors: tuple[StrategyDescriptor, ...] = STRATEGIES,
    tier: tuple[CliStrategy, ...] = CLI_STRATEGIES,
) -> None:
    """Add each strategy's direct command to ``app`` under its CLI alias, in declaration order.

    A strategy file never registers itself; this is the one place a strategy command is added.

    Raises:
        UndeclaredStrategyError: If a descriptor has no CLI-tier entry or an entry serves no descriptor.
    """
    for descriptor, entry in cli_entries(descriptors, tier):
        app.command(name=descriptor.alias)(entry.command)


CLI_BUILDERS: Final = builders_by_alias(STRATEGIES)


def build_selection_for(
    alias: str,
    flags: WatchlistFlags,
    builders: Mapping[str, SelectionBuilder] = CLI_BUILDERS,
) -> SelectionMember:
    """Build the selection of the strategy with CLI alias ``alias`` from the watchlist command's flags.

    Raises:
        UndeclaredStrategyError: If no declared strategy has a selection builder for ``alias``.
    """
    return require(builders, alias, what="selection builder alias")(flags)
