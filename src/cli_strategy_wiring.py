"""The CLI tier: each strategy's watchlist selection builder and refresh executor paired with its core bundle.

``CLI_STRATEGIES`` is the closed, statically declared tuple of strategy CLI compositions. Each entry is built
by ``pair_cli``, which takes a strategy's typed ``StrategyBehavior`` and its ``CliComposition`` and ties them by
selection type, so pairing one strategy's functions with another strategy's bundle fails ``mypy --strict``.
Nothing here discovers or registers a composition: the lookups below are pure functions of the declared
tuples, and a strategy without an entry fails closed with ``UndeclaredStrategyError``. No strategy is a default.

The tier exists because these functions import ``cli_support``, ``typer`` and the production provider
composition, which neither the composition root nor the evaluation tier may import.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Protocol

from src.cli_watchlist_flags import WatchlistFlags
from src.core.strategy_errors import require, undeclared
from src.data.instrument_profile_cache import InstrumentProfileResolver
from src.strategies.fcf_growth.cli import build_selection as build_fcf_growth_selection
from src.strategies.fcf_growth.cli import refresh as refresh_fcf_growth
from src.strategies.graham_growth.cli import build_selection as build_graham_growth_selection
from src.strategies.graham_growth.cli import refresh as refresh_graham_growth
from src.strategies.graham_number.cli import build_selection as build_graham_number_selection
from src.strategies.graham_number.cli import refresh as refresh_graham_number
from src.strategies.momentum.cli import build_selection as build_momentum_selection
from src.strategies.momentum.cli import refresh as refresh_momentum
from src.strategy_wiring import (
    FCF_GROWTH_BEHAVIOR,
    GRAHAM_GROWTH_BEHAVIOR,
    GRAHAM_NUMBER_BEHAVIOR,
    MOMENTUM_BEHAVIOR,
    STRATEGIES,
    StrategyBehavior,
    StrategyDescriptor,
)
from src.workspace.capture import ExecutionCapture
from src.workspace.strategy_types import NativeEvidence, SelectionMember


class RefreshExecutor[SelT: SelectionMember](Protocol):
    """A refresh executor: one job for one ticker and one selection, with the job's shared profile cache."""

    def __call__(
        self, ticker: str, selection: SelT, /, *, profile_cache: InstrumentProfileResolver
    ) -> ExecutionCapture:
        """Execute the job and return its captured evidence."""
        ...


type SelectionBuilder = Callable[[WatchlistFlags], SelectionMember]
"""A selection builder with its selection type erased."""


@dataclass(frozen=True)
class CliComposition[SelT: SelectionMember]:
    """One strategy's watchlist selection builder and refresh executor, both over its own selection class.

    Attributes:
        build: Builds one validated selection from the watchlist command's flags.
        refresh: Executes one refresh job for a selection of exactly the strategy's own class.
    """

    build: Callable[[WatchlistFlags], SelT]
    refresh: RefreshExecutor[SelT]


@dataclass(frozen=True)
class CliStrategy:
    """A composition paired with the core bundle of the strategy it serves, with the selection type erased.

    ``behavior`` is the very bundle object a descriptor holds, so identity finds the descriptor it serves. Both
    functions check that the selection they receive or return is exactly the paired bundle's selection class.
    """

    behavior: object
    build: SelectionBuilder
    refresh: RefreshExecutor[SelectionMember]


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

    def refresh(
        ticker: str, selection: SelectionMember, /, *, profile_cache: InstrumentProfileResolver
    ) -> ExecutionCapture:
        if not isinstance(selection, behavior.selection_type) or type(selection) is not behavior.selection_type:
            raise undeclared("selection type", type(selection))
        return composition.refresh(ticker, selection, profile_cache=profile_cache)

    return CliStrategy(behavior=behavior, build=build, refresh=refresh)


CLI_STRATEGIES: Final = (
    pair_cli(
        MOMENTUM_BEHAVIOR,
        CliComposition(build=build_momentum_selection, refresh=refresh_momentum),
    ),
    pair_cli(
        GRAHAM_NUMBER_BEHAVIOR,
        CliComposition(build=build_graham_number_selection, refresh=refresh_graham_number),
    ),
    pair_cli(
        GRAHAM_GROWTH_BEHAVIOR,
        CliComposition(build=build_graham_growth_selection, refresh=refresh_graham_growth),
    ),
    pair_cli(
        FCF_GROWTH_BEHAVIOR,
        CliComposition(build=build_fcf_growth_selection, refresh=refresh_fcf_growth),
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
            raise undeclared("CLI tier entry for strategy", key, entries)
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


def refreshers_by_key(
    descriptors: tuple[StrategyDescriptor, ...],
    tier: tuple[CliStrategy, ...] = CLI_STRATEGIES,
) -> Mapping[tuple[str, str], RefreshExecutor[SelectionMember]]:
    """Return each descriptor's refresh executor keyed by ``(analysis_id, method_id)``, read-only.

    Raises:
        UndeclaredStrategyError: If a descriptor has no CLI-tier entry or an entry serves no descriptor.
    """
    return MappingProxyType(
        {
            (descriptor.analysis_id, descriptor.method_id): entry.refresh
            for descriptor, entry in cli_entries(descriptors, tier)
        }
    )


CLI_BUILDERS: Final = builders_by_alias(STRATEGIES)
CLI_REFRESHERS: Final = refreshers_by_key(STRATEGIES)


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


def refresh_executor_for(
    selection: SelectionMember,
    refreshers: Mapping[tuple[str, str], RefreshExecutor[SelectionMember]] = CLI_REFRESHERS,
) -> RefreshExecutor[SelectionMember]:
    """Return the refresh executor of the strategy that owns ``selection``.

    Raises:
        UndeclaredStrategyError: If no declared strategy has a refresh executor for the selection's identifiers.
    """
    return require(refreshers, (selection.analysis_id, selection.method_id), what="refresh executor")
