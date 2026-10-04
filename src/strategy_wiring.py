"""Composition root: the closed declaration of the supported analysis strategies.

``STRATEGIES`` is the one authoritative, statically declared tuple of strategy descriptors. Each
descriptor holds a strategy's identity, its analysis-tool binding and one typed ``StrategyBehavior``
bundle that pairs every strategy-owned function mentioning the strategy's result type with that type.
Nothing here discovers, registers or constructs a strategy: the indexes below are pure functions of the
tuple, and the layers that need them receive them as parameters or import this module only where the
layering rule permits.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Protocol

from src.core.strategy_errors import require, undeclared
from src.orchestrator.analysis_tool_arguments import AnalysisToolArguments
from src.orchestrator.tool_names import ToolName
from src.orchestrator.tool_runtime import AnalysisToolHandler, ToolHandlerBinder, ToolRuntime
from src.strategies.fcf_growth.codec import fcf_growth_native_status
from src.strategies.fcf_growth.models import METHOD_ID as FCF_GROWTH_METHOD_ID
from src.strategies.fcf_growth.models import STRATEGY_ID as FCF_GROWTH_ANALYSIS_ID
from src.strategies.fcf_growth.models import FCFEarningsGrowthResult
from src.strategies.fcf_growth.tool import (
    FCFEarningsGrowthToolArguments,
    FCFEarningsGrowthToolDependencies,
    FCFEarningsGrowthToolHandler,
)
from src.strategies.graham_growth.codec import graham_growth_native_status
from src.strategies.graham_growth.service import GrahamGrowthAnalysis
from src.strategies.graham_growth.tool import (
    GrahamGrowthToolDependencies,
    GrahamGrowthToolHandler,
    GrahamGrowthValueToolArguments,
)
from src.strategies.graham_number.codec import graham_number_native_status
from src.strategies.graham_number.service import GrahamNumberAnalysis
from src.strategies.graham_number.tool import (
    GrahamNumberToolArguments,
    GrahamNumberToolDependencies,
    GrahamNumberToolHandler,
)
from src.strategies.momentum.analyzer import MomentumRun
from src.strategies.momentum.codec import momentum_native_status
from src.strategies.momentum.tool import MomentumToolArguments, MomentumToolDependencies, MomentumToolHandler
from src.workspace.strategy_types import NativeEvidence


class BehaviorView(Protocol):
    """The erased view of a ``StrategyBehavior`` that generic consumers use.

    Every method guards with an exact-type check, so a bundle given another strategy's object raises
    ``UndeclaredStrategyError`` instead of routing it.
    """

    @property
    def result_type(self) -> type[NativeEvidence]:
        """Return the strategy's native result type."""
        ...

    def native_status_of(self, result: object, /) -> str | None:
        """Return the result-level status recorded as telemetry evidence, or ``None`` if the strategy has none."""
        ...

    def bind_handler(self, dependencies: object, runtime: ToolRuntime, /) -> AnalysisToolHandler[NativeEvidence]:
        """Bind the strategy's handler to its own dependency class and the shared runtime."""
        ...


@dataclass(frozen=True)
class StrategyBehavior[ResultT: NativeEvidence, DepsT]:
    """Strategy-owned functions paired with the result and dependency types they mention.

    Pairing one strategy's function with another strategy's type is a type error. The selection type is
    not a parameter yet: no member here mentions it, and the slice that adds the first member that does
    adds the parameter with it.
    """

    result_type: type[ResultT]
    deps_type: type[DepsT]
    handler: ToolHandlerBinder[DepsT, ResultT]
    native_status: Callable[[ResultT], str | None]

    def native_status_of(self, result: object, /) -> str | None:
        """Return the result-level status of ``result``, which must be exactly this strategy's result type."""
        if not isinstance(result, self.result_type) or type(result) is not self.result_type:
            raise undeclared("result type", type(result))
        return self.native_status(result)

    def bind_handler(self, dependencies: object, runtime: ToolRuntime, /) -> AnalysisToolHandler[ResultT]:
        """Bind the handler to ``dependencies``, which must be exactly this strategy's dependency class."""
        if not isinstance(dependencies, self.deps_type) or type(dependencies) is not self.deps_type:
            raise undeclared("handler dependencies", type(dependencies))
        return self.handler(dependencies, runtime)


@dataclass(frozen=True)
class StrategyDescriptor:
    """One strategy's identity, analysis-tool binding and typed behavior."""

    analysis_id: str
    method_id: str
    tool: ToolName
    tool_arguments: type[AnalysisToolArguments]
    tool_description: str
    behavior: BehaviorView


MOMENTUM_BEHAVIOR: Final = StrategyBehavior[MomentumRun, MomentumToolDependencies](
    result_type=MomentumRun,
    deps_type=MomentumToolDependencies,
    handler=MomentumToolHandler,
    native_status=momentum_native_status,
)
GRAHAM_NUMBER_BEHAVIOR: Final = StrategyBehavior[GrahamNumberAnalysis, GrahamNumberToolDependencies](
    result_type=GrahamNumberAnalysis,
    deps_type=GrahamNumberToolDependencies,
    handler=GrahamNumberToolHandler,
    native_status=graham_number_native_status,
)
GRAHAM_GROWTH_BEHAVIOR: Final = StrategyBehavior[GrahamGrowthAnalysis, GrahamGrowthToolDependencies](
    result_type=GrahamGrowthAnalysis,
    deps_type=GrahamGrowthToolDependencies,
    handler=GrahamGrowthToolHandler,
    native_status=graham_growth_native_status,
)
FCF_GROWTH_BEHAVIOR: Final = StrategyBehavior[FCFEarningsGrowthResult, FCFEarningsGrowthToolDependencies](
    result_type=FCFEarningsGrowthResult,
    deps_type=FCFEarningsGrowthToolDependencies,
    handler=FCFEarningsGrowthToolHandler,
    native_status=fcf_growth_native_status,
)

MOMENTUM: Final = StrategyDescriptor(
    analysis_id="momentum",
    method_id="sma_crossover",
    tool=ToolName.ANALYZE_MOMENTUM,
    tool_arguments=MomentumToolArguments,
    tool_description="Analyze historical price momentum with structured SMA and RSI metrics.",
    behavior=MOMENTUM_BEHAVIOR,
)
GRAHAM_NUMBER: Final = StrategyDescriptor(
    analysis_id="graham_number",
    method_id="graham_number",
    tool=ToolName.ANALYZE_GRAHAM_NUMBER,
    tool_arguments=GrahamNumberToolArguments,
    tool_description="Calculate the Graham Number company-level valuation ceiling.",
    behavior=GRAHAM_NUMBER_BEHAVIOR,
)
GRAHAM_GROWTH: Final = StrategyDescriptor(
    analysis_id="graham_growth_value",
    method_id="graham_growth_value",
    tool=ToolName.ANALYZE_GRAHAM_GROWTH_VALUE,
    tool_arguments=GrahamGrowthValueToolArguments,
    tool_description="Calculate the explicit Graham growth-value method.",
    behavior=GRAHAM_GROWTH_BEHAVIOR,
)
FCF_GROWTH: Final = StrategyDescriptor(
    analysis_id=FCF_GROWTH_ANALYSIS_ID,
    method_id=FCF_GROWTH_METHOD_ID,
    tool=ToolName.ANALYZE_FCF_EARNINGS_GROWTH,
    tool_arguments=FCFEarningsGrowthToolArguments,
    tool_description="Analyze company free-cash-flow and diluted-EPS growth.",
    behavior=FCF_GROWTH_BEHAVIOR,
)

STRATEGIES: Final = (MOMENTUM, GRAHAM_NUMBER, GRAHAM_GROWTH, FCF_GROWTH)


@dataclass(frozen=True)
class StrategyIndexes:
    """Read-only lookups over one tuple of descriptors, each unique by its key."""

    by_key: Mapping[tuple[str, str], StrategyDescriptor]
    by_method_id: Mapping[str, StrategyDescriptor]
    by_tool: Mapping[ToolName, StrategyDescriptor]
    by_arguments: Mapping[type[AnalysisToolArguments], StrategyDescriptor]
    by_result_type: Mapping[type, StrategyDescriptor]


def _label(descriptor: StrategyDescriptor) -> str:
    """Name a descriptor by its identity for diagnostics."""
    return f"({descriptor.analysis_id!r}, {descriptor.method_id!r})"


def _unique_index[K](
    descriptors: tuple[StrategyDescriptor, ...],
    rule: str,
    key_of: Callable[[StrategyDescriptor], K],
) -> Mapping[K, StrategyDescriptor]:
    """Index ``descriptors`` by ``key_of``, raising on a repeated key and naming both descriptors."""
    index: dict[K, StrategyDescriptor] = {}
    for descriptor in descriptors:
        key = key_of(descriptor)
        if key in index:
            raise ValueError(f"Duplicate {rule} {key!r}: declared by {_label(index[key])} and {_label(descriptor)}.")
        index[key] = descriptor
    return MappingProxyType(index)


def build_indexes(descriptors: tuple[StrategyDescriptor, ...]) -> StrategyIndexes:
    """Build every lookup from ``descriptors``, in declaration order.

    This is a pure function of its argument, so tests call it on a modified copy; it raises ``ValueError``
    naming the rule and both descriptors when a key repeats.
    """
    return StrategyIndexes(
        by_key=_unique_index(descriptors, "analysis_id+method_id", lambda item: (item.analysis_id, item.method_id)),
        by_method_id=_unique_index(descriptors, "method_id", lambda item: item.method_id),
        by_tool=_unique_index(descriptors, "tool", lambda item: item.tool),
        by_arguments=_unique_index(descriptors, "tool_arguments", lambda item: item.tool_arguments),
        by_result_type=_unique_index(descriptors, "result_type", lambda item: item.behavior.result_type),
    )


_INDEXES: Final = build_indexes(STRATEGIES)
BY_KEY: Final = _INDEXES.by_key
BY_METHOD_ID: Final = _INDEXES.by_method_id
BY_TOOL: Final = _INDEXES.by_tool
BY_ARGUMENTS: Final = _INDEXES.by_arguments
BY_RESULT_TYPE: Final = _INDEXES.by_result_type


def tool_for_arguments(
    arguments: AnalysisToolArguments,
    by_arguments: Mapping[type[AnalysisToolArguments], StrategyDescriptor] = BY_ARGUMENTS,
) -> ToolName:
    """Return the tool whose arguments model is exactly the type of ``arguments``.

    Args:
        arguments: A validated analysis-tool arguments model.
        by_arguments: Lookup by arguments model; the declared strategies unless a caller supplies another.

    Raises:
        UndeclaredStrategyError: If the arguments belong to no declared strategy.
    """
    return require(by_arguments, type(arguments), what="tool-arguments model").tool


def bind_handlers(
    descriptors: tuple[StrategyDescriptor, ...],
    dependencies: Mapping[ToolName, object],
    runtime: ToolRuntime,
) -> Mapping[ToolName, AnalysisToolHandler[NativeEvidence]]:
    """Bind each descriptor's handler to the dependencies supplied for its tool.

    Args:
        descriptors: The declared strategies; a descriptor tool with no dependencies entry is an error.
        dependencies: Each strategy's own dependency instance, keyed by its tool.
        runtime: The shared clock and profile resolver.

    Returns:
        A read-only mapping from tool to bound handler, in declaration order.

    Raises:
        UndeclaredStrategyError: If a descriptor tool has no dependencies entry, or an entry belongs to no
            descriptor, or a dependency instance is not exactly its strategy's dependency class.
    """
    declared = {descriptor.tool for descriptor in descriptors}
    for tool in dependencies:
        if tool not in declared:
            raise undeclared("tool", tool, {descriptor.tool: descriptor for descriptor in descriptors})
    return MappingProxyType(
        {
            descriptor.tool: descriptor.behavior.bind_handler(
                require(dependencies, descriptor.tool, what="tool dependencies"), runtime
            )
            for descriptor in descriptors
        }
    )
