"""The CLI tier: each strategy's direct command and ``add-selection`` command paired with its core bundle.

``CLI_STRATEGIES`` is the closed, statically declared tuple of strategy CLI compositions. Each entry is built
by ``pair_cli``, which takes a strategy's typed ``StrategyBehavior`` and its ``CliComposition`` and ties them by
selection type, so pairing one strategy's functions with another strategy's bundle fails ``mypy --strict``.
Nothing here discovers or registers a composition: the lookups below are pure functions of the declared
tuples, and a strategy without an entry fails closed with ``UndeclaredStrategyError``. No strategy is a default.
``add_strategy_commands`` and ``add_selection_commands`` are the places a command is added to the Typer application,
by iterating the tuple.

The tier exists because these functions import ``cli_support`` and ``typer``, which neither the composition root nor
the evaluation tier may import. Each strategy's run function and refresh executor are paired in the application tier.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

import typer

from investment_analysis_engine.cli_support import SelectionOption
from investment_analysis_engine.core.strategy_errors import UndeclaredStrategyError, describe, undeclared
from investment_analysis_engine.strategies.fcf_growth.cli import SELECTION_OPTIONS as FCF_GROWTH_OPTIONS
from investment_analysis_engine.strategies.fcf_growth.cli import add_selection as fcf_growth_add_selection
from investment_analysis_engine.strategies.fcf_growth.cli import command as fcf_growth_command
from investment_analysis_engine.strategies.graham_growth.cli import SELECTION_OPTIONS as GRAHAM_GROWTH_OPTIONS
from investment_analysis_engine.strategies.graham_growth.cli import add_selection as graham_growth_add_selection
from investment_analysis_engine.strategies.graham_growth.cli import command as graham_growth_command
from investment_analysis_engine.strategies.graham_number.cli import SELECTION_OPTIONS as GRAHAM_NUMBER_OPTIONS
from investment_analysis_engine.strategies.graham_number.cli import add_selection as graham_number_add_selection
from investment_analysis_engine.strategies.graham_number.cli import command as graham_number_command
from investment_analysis_engine.strategies.momentum.cli import SELECTION_OPTIONS as MOMENTUM_OPTIONS
from investment_analysis_engine.strategies.momentum.cli import add_selection as momentum_add_selection
from investment_analysis_engine.strategies.momentum.cli import command as momentum_command
from investment_analysis_engine.strategies.piotroski.cli import SELECTION_OPTIONS as PIOTROSKI_OPTIONS
from investment_analysis_engine.strategies.piotroski.cli import add_selection as piotroski_add_selection
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


@dataclass(frozen=True)
class CliComposition[SelT: SelectionMember]:
    """One strategy's direct command, ``add-selection`` command and option table, over its own selection class.

    Attributes:
        command: The strategy's direct command, a plain function whose options are its own. The tier supplies
            the command's name, the descriptor's alias.
        add_selection: The strategy's ``add-selection`` command, whose selection options are the direct command's.
            The tier supplies its name, the descriptor's alias, and its summary, from the descriptor's label.
        selection_options: The table that maps each selection field to the option that sets it.
    """

    command: Callable[..., None]
    add_selection: Callable[..., None]
    selection_options: tuple[SelectionOption, ...]


@dataclass(frozen=True)
class CliStrategy:
    """A composition paired with the core bundle of the strategy it serves.

    ``behavior`` is the very bundle object a descriptor holds, so identity finds the descriptor it serves.
    """

    behavior: object
    command: Callable[..., None]
    add_selection: Callable[..., None]
    selection_options: tuple[SelectionOption, ...]


def pair_cli[SelT: SelectionMember, ResultT: NativeEvidence, DepsT](
    behavior: StrategyBehavior[SelT, ResultT, DepsT],
    composition: CliComposition[SelT],
) -> CliStrategy:
    """Pair a strategy's core bundle with a composition for exactly its selection class."""
    return CliStrategy(
        behavior=behavior,
        command=composition.command,
        add_selection=composition.add_selection,
        selection_options=composition.selection_options,
    )


CLI_STRATEGIES: Final = (
    pair_cli(
        MOMENTUM_BEHAVIOR,
        CliComposition(
            command=momentum_command,
            add_selection=momentum_add_selection,
            selection_options=MOMENTUM_OPTIONS,
        ),
    ),
    pair_cli(
        GRAHAM_NUMBER_BEHAVIOR,
        CliComposition(
            command=graham_number_command,
            add_selection=graham_number_add_selection,
            selection_options=GRAHAM_NUMBER_OPTIONS,
        ),
    ),
    pair_cli(
        GRAHAM_GROWTH_BEHAVIOR,
        CliComposition(
            command=graham_growth_command,
            add_selection=graham_growth_add_selection,
            selection_options=GRAHAM_GROWTH_OPTIONS,
        ),
    ),
    pair_cli(
        FCF_GROWTH_BEHAVIOR,
        CliComposition(
            command=fcf_growth_command,
            add_selection=fcf_growth_add_selection,
            selection_options=FCF_GROWTH_OPTIONS,
        ),
    ),
    pair_cli(
        PIOTROSKI_BEHAVIOR,
        CliComposition(
            command=piotroski_command,
            add_selection=piotroski_add_selection,
            selection_options=PIOTROSKI_OPTIONS,
        ),
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


def add_selection_commands(
    group: typer.Typer,
    descriptors: tuple[StrategyDescriptor, ...] = STRATEGIES,
    tier: tuple[CliStrategy, ...] = CLI_STRATEGIES,
) -> None:
    """Add each strategy's ``add-selection`` command to ``group`` under its CLI alias, in declaration order.

    The command's summary is generated from the descriptor's label.

    Raises:
        UndeclaredStrategyError: If a descriptor has no CLI-tier entry or an entry serves no descriptor.
    """
    for descriptor, entry in cli_entries(descriptors, tier):
        group.command(
            name=descriptor.alias, help=f"Add one {descriptor.label} entry per ticker to an existing watchlist."
        )(entry.add_selection)
