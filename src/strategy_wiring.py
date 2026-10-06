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
from functools import partial
from types import MappingProxyType
from typing import Final, Protocol

from src.core.strategy_errors import require, undeclared
from src.orchestrator.analysis_tool_arguments import AnalysisToolArguments
from src.orchestrator.tool_names import ToolName
from src.orchestrator.tool_runtime import AnalysisToolHandler, ToolHandlerBinder, ToolRuntime
from src.strategies.fcf_growth.codec import (
    decode_fcf_growth,
    encode_fcf_growth,
    fcf_growth_native_status,
    fcf_growth_ticker,
)
from src.strategies.fcf_growth.models import METHOD_ID as FCF_GROWTH_METHOD_ID
from src.strategies.fcf_growth.models import METHOD_VERSION as FCF_GROWTH_METHOD_VERSION
from src.strategies.fcf_growth.models import SCHEMA_VERSION as FCF_GROWTH_RESULT_SCHEMA_VERSION
from src.strategies.fcf_growth.models import STRATEGY_ID as FCF_GROWTH_ANALYSIS_ID
from src.strategies.fcf_growth.models import FCFEarningsGrowthResult
from src.strategies.fcf_growth.selection import FCFGrowthSelection, parse_fcf_growth_selection
from src.strategies.fcf_growth.tool import (
    FCFEarningsGrowthToolArguments,
    FCFEarningsGrowthToolDependencies,
    FCFEarningsGrowthToolHandler,
)
from src.strategies.graham_growth.codec import (
    decode_graham_growth,
    encode_graham_growth,
    graham_growth_native_status,
    graham_growth_ticker,
)
from src.strategies.graham_growth.selection import GrahamGrowthSelection, parse_graham_growth_selection
from src.strategies.graham_growth.service import GrahamGrowthAnalysis
from src.strategies.graham_growth.tool import (
    GrahamGrowthToolDependencies,
    GrahamGrowthToolHandler,
    GrahamGrowthValueToolArguments,
)
from src.strategies.graham_number.codec import (
    decode_graham_number,
    encode_graham_number,
    graham_number_native_status,
    graham_number_ticker,
)
from src.strategies.graham_number.selection import GrahamNumberSelection, parse_graham_number_selection
from src.strategies.graham_number.service import GrahamNumberAnalysis
from src.strategies.graham_number.tool import (
    GrahamNumberToolArguments,
    GrahamNumberToolDependencies,
    GrahamNumberToolHandler,
)
from src.strategies.momentum.analyzer import MomentumRun
from src.strategies.momentum.codec import decode_momentum, encode_momentum, momentum_native_status, momentum_ticker
from src.strategies.momentum.selection import MomentumSelection, parse_momentum_selection
from src.strategies.momentum.tool import MomentumToolArguments, MomentumToolDependencies, MomentumToolHandler
from src.workspace.codecs import EvidenceCodec, encode_with
from src.workspace.execution import RunSpec
from src.workspace.models import StrictJsonMapping
from src.workspace.requests import SelectionParser
from src.workspace.strategy_types import NativeEvidence, SelectionMember


class BehaviorView(Protocol):
    """The erased view of a ``StrategyBehavior`` that generic consumers use.

    Every method guards with an exact-type check, so a bundle given another strategy's object raises
    ``UndeclaredStrategyError`` instead of routing it.
    """

    @property
    def result_type(self) -> type[NativeEvidence]:
        """Return the strategy's native result type."""
        ...

    def parse_for(self, config: dict[str, object], /) -> SelectionMember:
        """Parse a decoded configuration object into this strategy's selection."""
        ...

    def encode_object(self, evidence: object, /) -> StrictJsonMapping:
        """Encode ``evidence``, which must be exactly this strategy's result type."""
        ...

    def decode_for(self, payload: StrictJsonMapping, ticker: str, /) -> NativeEvidence:
        """Decode a stored payload and require its evidence to be about ``ticker``."""
        ...

    def native_status_of(self, result: object, /) -> str | None:
        """Return the result-level status recorded as telemetry evidence, or ``None`` if the strategy has none."""
        ...

    def bind_handler(self, dependencies: object, runtime: ToolRuntime, /) -> AnalysisToolHandler[NativeEvidence]:
        """Bind the strategy's handler to its own dependency class and the shared runtime."""
        ...


@dataclass(frozen=True)
class StrategyBehavior[SelT: SelectionMember, ResultT: NativeEvidence, DepsT]:
    """Strategy-owned functions paired with the selection, result and dependency types they mention.

    Pairing one strategy's function with another strategy's type is a type error.
    """

    selection_type: type[SelT]
    result_type: type[ResultT]
    deps_type: type[DepsT]
    parse: Callable[[dict[str, object]], SelT]
    encode: Callable[[ResultT], StrictJsonMapping]
    decode: Callable[[StrictJsonMapping], ResultT]
    ticker_of: Callable[[ResultT], str]
    handler: ToolHandlerBinder[DepsT, ResultT]
    native_status: Callable[[ResultT], str | None]

    def parse_for(self, config: dict[str, object], /) -> SelT:
        """Parse ``config`` with this strategy's parser, which must yield exactly its selection type."""
        selection = self.parse(config)
        if type(selection) is not self.selection_type:
            raise undeclared("selection type", type(selection))
        return selection

    def encode_object(self, evidence: object, /) -> StrictJsonMapping:
        """Encode ``evidence``, which must be exactly this strategy's result type."""
        if not isinstance(evidence, self.result_type) or type(evidence) is not self.result_type:
            raise undeclared("result type", type(evidence))
        return self.encode(evidence)

    def decode_for(self, payload: StrictJsonMapping, ticker: str, /) -> ResultT:
        """Decode ``payload`` into this strategy's result and require it to be about ``ticker``."""
        result = self.decode(payload)
        if type(result) is not self.result_type:
            raise undeclared("result type", type(result))
        if self.ticker_of(result) != ticker:
            raise ValueError("Ticker mismatch.")
        return result

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
    alias: str
    label: str
    tool: ToolName
    tool_arguments: type[AnalysisToolArguments]
    tool_description: str
    behavior: BehaviorView
    config_schema_version: int
    method_version: int
    result_schema_version: int
    evidence_codec_version: int


MOMENTUM_BEHAVIOR: Final = StrategyBehavior[MomentumSelection, MomentumRun, MomentumToolDependencies](
    selection_type=MomentumSelection,
    result_type=MomentumRun,
    deps_type=MomentumToolDependencies,
    parse=parse_momentum_selection,
    encode=encode_momentum,
    decode=decode_momentum,
    ticker_of=momentum_ticker,
    handler=MomentumToolHandler,
    native_status=momentum_native_status,
)
GRAHAM_NUMBER_BEHAVIOR: Final = StrategyBehavior[
    GrahamNumberSelection, GrahamNumberAnalysis, GrahamNumberToolDependencies
](
    selection_type=GrahamNumberSelection,
    result_type=GrahamNumberAnalysis,
    deps_type=GrahamNumberToolDependencies,
    parse=parse_graham_number_selection,
    encode=encode_graham_number,
    decode=decode_graham_number,
    ticker_of=graham_number_ticker,
    handler=GrahamNumberToolHandler,
    native_status=graham_number_native_status,
)
GRAHAM_GROWTH_BEHAVIOR: Final = StrategyBehavior[
    GrahamGrowthSelection, GrahamGrowthAnalysis, GrahamGrowthToolDependencies
](
    selection_type=GrahamGrowthSelection,
    result_type=GrahamGrowthAnalysis,
    deps_type=GrahamGrowthToolDependencies,
    parse=parse_graham_growth_selection,
    encode=encode_graham_growth,
    decode=decode_graham_growth,
    ticker_of=graham_growth_ticker,
    handler=GrahamGrowthToolHandler,
    native_status=graham_growth_native_status,
)
FCF_GROWTH_BEHAVIOR: Final = StrategyBehavior[
    FCFGrowthSelection, FCFEarningsGrowthResult, FCFEarningsGrowthToolDependencies
](
    selection_type=FCFGrowthSelection,
    result_type=FCFEarningsGrowthResult,
    deps_type=FCFEarningsGrowthToolDependencies,
    parse=parse_fcf_growth_selection,
    encode=encode_fcf_growth,
    decode=decode_fcf_growth,
    ticker_of=fcf_growth_ticker,
    handler=FCFEarningsGrowthToolHandler,
    native_status=fcf_growth_native_status,
)

MOMENTUM: Final = StrategyDescriptor(
    analysis_id="momentum",
    method_id="sma_crossover",
    alias="momentum",
    label="Momentum",
    tool=ToolName.ANALYZE_MOMENTUM,
    tool_arguments=MomentumToolArguments,
    tool_description="Analyze historical price momentum with structured SMA and RSI metrics.",
    behavior=MOMENTUM_BEHAVIOR,
    config_schema_version=2,
    method_version=1,
    result_schema_version=2,
    evidence_codec_version=1,
)
GRAHAM_NUMBER: Final = StrategyDescriptor(
    analysis_id="graham_number",
    method_id="graham_number",
    alias="graham-number",
    label="Graham Number",
    tool=ToolName.ANALYZE_GRAHAM_NUMBER,
    tool_arguments=GrahamNumberToolArguments,
    tool_description="Calculate the Graham Number company-level valuation ceiling.",
    behavior=GRAHAM_NUMBER_BEHAVIOR,
    config_schema_version=1,
    method_version=1,
    result_schema_version=1,
    evidence_codec_version=1,
)
GRAHAM_GROWTH: Final = StrategyDescriptor(
    analysis_id="graham_growth_value",
    method_id="graham_growth_value",
    alias="graham-growth",
    label="Graham Growth",
    tool=ToolName.ANALYZE_GRAHAM_GROWTH_VALUE,
    tool_arguments=GrahamGrowthValueToolArguments,
    tool_description="Calculate the explicit Graham growth-value method.",
    behavior=GRAHAM_GROWTH_BEHAVIOR,
    config_schema_version=1,
    method_version=1,
    result_schema_version=1,
    evidence_codec_version=1,
)
FCF_GROWTH: Final = StrategyDescriptor(
    analysis_id=FCF_GROWTH_ANALYSIS_ID,
    method_id=FCF_GROWTH_METHOD_ID,
    alias="fcf-growth",
    label="FCF Growth",
    tool=ToolName.ANALYZE_FCF_EARNINGS_GROWTH,
    tool_arguments=FCFEarningsGrowthToolArguments,
    tool_description="Analyze company free-cash-flow and diluted-EPS growth.",
    behavior=FCF_GROWTH_BEHAVIOR,
    config_schema_version=1,
    method_version=FCF_GROWTH_METHOD_VERSION,
    result_schema_version=FCF_GROWTH_RESULT_SCHEMA_VERSION,
    evidence_codec_version=1,
)

STRATEGIES: Final = (MOMENTUM, GRAHAM_NUMBER, GRAHAM_GROWTH, FCF_GROWTH)


@dataclass(frozen=True)
class StrategyIndexes:
    """Read-only lookups over one tuple of descriptors, each unique by its key."""

    by_key: Mapping[tuple[str, str], StrategyDescriptor]
    by_method_id: Mapping[str, StrategyDescriptor]
    by_alias: Mapping[str, StrategyDescriptor]
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
        by_alias=_unique_index(descriptors, "alias", lambda item: item.alias),
        by_tool=_unique_index(descriptors, "tool", lambda item: item.tool),
        by_arguments=_unique_index(descriptors, "tool_arguments", lambda item: item.tool_arguments),
        by_result_type=_unique_index(descriptors, "result_type", lambda item: item.behavior.result_type),
    )


_INDEXES: Final = build_indexes(STRATEGIES)
BY_KEY: Final = _INDEXES.by_key
BY_METHOD_ID: Final = _INDEXES.by_method_id
BY_ALIAS: Final = _INDEXES.by_alias
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


def evidence_codecs(descriptors: tuple[StrategyDescriptor, ...]) -> tuple[EvidenceCodec, ...]:
    """Build each descriptor's evidence codec from its versions, label and behavior, in declaration order."""
    return tuple(
        EvidenceCodec(
            label=descriptor.label,
            config_schema_version=descriptor.config_schema_version,
            method_version=descriptor.method_version,
            result_schema_version=descriptor.result_schema_version,
            evidence_codec_version=descriptor.evidence_codec_version,
            encode=descriptor.behavior.encode_object,
            decode=descriptor.behavior.decode_for,
        )
        for descriptor in descriptors
    )


def evidence_by_type(descriptors: tuple[StrategyDescriptor, ...]) -> Mapping[type, EvidenceCodec]:
    """Return each descriptor's evidence codec keyed by its exact result type, read-only."""
    return MappingProxyType(
        {
            descriptor.behavior.result_type: codec
            for descriptor, codec in zip(descriptors, evidence_codecs(descriptors), strict=True)
        }
    )


def evidence_by_key(descriptors: tuple[StrategyDescriptor, ...]) -> Mapping[tuple[str, str], EvidenceCodec]:
    """Return each descriptor's evidence codec keyed by ``(analysis_id, method_id)``, read-only."""
    return MappingProxyType(
        {
            (descriptor.analysis_id, descriptor.method_id): codec
            for descriptor, codec in zip(descriptors, evidence_codecs(descriptors), strict=True)
        }
    )


def run_specs_by_key(descriptors: tuple[StrategyDescriptor, ...]) -> Mapping[tuple[str, str], RunSpec]:
    """Return each descriptor's run spec keyed by ``(analysis_id, method_id)``, read-only."""
    return MappingProxyType(
        {
            (descriptor.analysis_id, descriptor.method_id): RunSpec(
                method_version=descriptor.method_version,
                result_schema_version=descriptor.result_schema_version,
                evidence_codec_version=descriptor.evidence_codec_version,
                encode=partial(encode_with, codec),
            )
            for descriptor, codec in zip(descriptors, evidence_codecs(descriptors), strict=True)
        }
    )


def parsers_by_alias(descriptors: tuple[StrategyDescriptor, ...]) -> Mapping[str, SelectionParser]:
    """Return each descriptor's selection parser keyed by its CLI alias, read-only."""
    return MappingProxyType({descriptor.alias: descriptor.behavior.parse_for for descriptor in descriptors})


EVIDENCE_BY_TYPE: Final = evidence_by_type(STRATEGIES)
EVIDENCE_BY_KEY: Final = evidence_by_key(STRATEGIES)
RUN_SPECS_BY_KEY: Final = run_specs_by_key(STRATEGIES)
PARSERS_BY_ALIAS: Final = parsers_by_alias(STRATEGIES)


def run_spec_for(
    selection: SelectionMember, run_specs: Mapping[tuple[str, str], RunSpec] = RUN_SPECS_BY_KEY
) -> RunSpec:
    """Return the run spec of the strategy that owns ``selection``.

    Raises:
        UndeclaredStrategyError: If no declared strategy has the selection's identifiers.
    """
    return require(run_specs, (selection.analysis_id, selection.method_id), what="run spec")
