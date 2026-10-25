"""Conformance check bodies for the closed strategy wiring.

Each check takes the tuple of descriptors under test (or the source files it inspects) and returns a list
of gaps: an empty list means the wiring is complete. The conformance tests assert that the list is empty,
and a status command prints it, so the two cannot disagree. Every check compares the descriptors with a
surface that is declared independently of them, so a strategy added to one place only is reported.
"""

from __future__ import annotations

import ast
import asyncio
import dataclasses
import functools
import importlib
import inspect
import pkgutil
import re
import sys
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from types import MappingProxyType
from typing import Protocol, cast, get_args, get_origin

import typer
from pydantic import BaseModel, ValidationError
from typer.core import TyperGroup

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext, BaseAnalyzer
from investment_analysis_engine.cli import app
from investment_analysis_engine.cli_strategy_wiring import (
    CLI_STRATEGIES,
    CliComposition,
    CliStrategy,
    build_selection_for,
    builders_by_alias,
    pair_cli,
    refresh_executor_for,
    refreshers_by_key,
)
from investment_analysis_engine.cli_watchlist_flags import WatchlistFlags
from investment_analysis_engine.cli_workspace import watchlist_app
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.package_root import PACKAGE_ROOT
from investment_analysis_engine.core.strategy_errors import UndeclaredStrategyError, require
from investment_analysis_engine.core.strategy_stub import UnfilledStubError
from investment_analysis_engine.data.instrument_profile import InstrumentProfile, InstrumentProfileCandidate
from investment_analysis_engine.evaluation.catalog import DETERMINISTIC_CASES, build_deterministic_requests
from investment_analysis_engine.evaluation.composition import (
    compose_fixture_dependencies,
    compose_fixture_dispatcher,
    dispatch_fixture_case,
)
from investment_analysis_engine.evaluation.fixture_context import CONTEXT_FIXTURE_IDS
from investment_analysis_engine.evaluation.runner import DeterministicCaseRequest
from investment_analysis_engine.evaluation.strategy_fixtures import (
    EVALUATION_STRATEGIES,
    EvalComposition,
    EvaluationStrategy,
)
from investment_analysis_engine.orchestrator.analysis_tool_arguments import AnalysisToolArguments
from investment_analysis_engine.orchestrator.analysis_tools import register_analysis_tools
from investment_analysis_engine.orchestrator.dispatcher import AsyncToolDispatcher
from investment_analysis_engine.orchestrator.tool_names import ToolName
from investment_analysis_engine.orchestrator.tool_runtime import AnalysisToolHandler
from investment_analysis_engine.reporting.presentation import PresentationMode
from investment_analysis_engine.reporting.replay_inputs import (
    ReplayInputs,
    ReplayOptions,
    ReplayProjector,
    UnsupportedProjectionError,
)
from investment_analysis_engine.strategy_wiring import (
    STRATEGIES,
    BehaviorView,
    StrategyBehavior,
    StrategyDescriptor,
    bind_handlers,
    build_indexes,
    evidence_by_key,
    replays_by_key,
    run_spec_for,
    run_specs_by_key,
    tool_for_arguments,
)
from investment_analysis_engine.workspace.capture import ExecutionCapture
from investment_analysis_engine.workspace.codecs import EvidenceCodec, UnsupportedRunVersionError, decode_evidence
from investment_analysis_engine.workspace.execution import execute
from investment_analysis_engine.workspace.requests import AnalysisRequest
from investment_analysis_engine.workspace.runs import AnalysisRun
from investment_analysis_engine.workspace.strategy_types import NativeEvidence, SelectionMember
from investment_analysis_engine.workspace_documents.json_documents import JSON_DOCUMENTS, STRATEGY_REPLAY_COMMANDS
from investment_analysis_engine.workspace_documents.run_replay import project_run
from scripts.generate_schemas import SCHEMA_DIRECTORY, schema_text, strategy_schema_file
from scripts.generate_strategy_docs import GENERATOR, BlockError, block_problem, current_body, strategy_list_blocks
from scripts.repository_root import REPOSITORY_ROOT
from scripts.strategy_sites import Gap, Site, StrategyNames, load_sites
from tests.test_no_unfilled_stubs import unfilled_stub_calls

_FIXTURE_CLOCK = datetime(2026, 8, 31, 18, 30, tzinfo=UTC)

DESCRIPTOR_FIELDS: dict[str, object] = {
    "analysis_id": str,
    "method_id": str,
    "alias": str,
    "label": str,
    "tool": ToolName,
    "tool_arguments": type[AnalysisToolArguments],
    "tool_description": str,
    "behavior": BehaviorView,
    "config_schema_version": int,
    "method_version": int,
    "result_schema_version": int,
    "evidence_codec_version": int,
    "json_envelope": type[BaseModel],
    "settings_type": type[BaseModel] | None,
}
"""The documented descriptor fields and their types; a change here is a reviewed change to the contract."""

BEHAVIOR_MEMBERS: frozenset[str] = frozenset(
    {
        "selection_type",
        "result_type",
        "deps_type",
        "encode",
        "decode",
        "ticker_of",
        "handler",
        "native_status",
        "headline",
        "project",
    }
)
"""The documented members of a strategy's behavior bundle."""

EVAL_COMPOSITION_MEMBERS: frozenset[str] = frozenset({"requirement", "fixture_ids", "compose", "sample_selection"})
"""The documented members of a strategy's evaluation-tier composition."""

EVALUATION_ENTRY_FIELDS: frozenset[str] = frozenset(
    {"behavior", "requirement", "fixture_ids", "compose", "sample_selection"}
)
"""The documented fields of an evaluation-tier entry: the paired core bundle and the erased composition."""

CLI_COMPOSITION_MEMBERS: frozenset[str] = frozenset({"build", "refresh", "command"})
"""The documented members of a strategy's CLI-tier composition."""

NON_STRATEGY_COMMANDS: frozenset[str] = frozenset({"evaluate", "health", "refresh"})
"""The top-level commands that are not a strategy's direct command; command groups are recognized by type."""

CLI_ENTRY_FIELDS: frozenset[str] = frozenset({"behavior", "build", "refresh", "command"})
"""The documented fields of a CLI-tier entry: the paired core bundle and the erased composition."""

VIEW_ACCESSORS: frozenset[str] = frozenset(
    {"result_type", "encode_object", "decode_for", "native_status_of", "headline_for", "bind_handler", "project_for"}
)
"""The behavior members that generic consumers can reach, through the erased view."""

ANALYZER_ENVELOPE_PARAMETERS: tuple[str, ...] = ("self", "ticker", "config", "context")
ANALYZER_CONTEXT_FIELDS: tuple[str, ...] = ("as_of", "executed_at", "use_cache", "instrument_profile")

_FORBIDDEN_IMPORTS = frozenset({"importlib", "pkgutil", "inspect", "entry_points"})
_FORBIDDEN_CALLS = frozenset({"globals", "locals", "get_type_hints"})
_FORBIDDEN_ATTRIBUTES = frozenset({"__subclasses__", "__init_subclass__"})
_FORBIDDEN_NAME = re.compile(r"^(register|unregister|load_|discover)|(Registry|Factory|Plugin)$")
_COMMAND_ADDER = "add_strategy_commands"
_COMMAND_ADDER_FILE = "cli_strategy_wiring.py"
_COMMAND_REGISTRATION = "registers a command on the Typer app"


def label(descriptor: StrategyDescriptor) -> str:
    """Name a descriptor by its identity for diagnostics."""
    return f"({descriptor.analysis_id!r}, {descriptor.method_id!r})"


def _literal_default(model: type[BaseModel], field: str) -> str:
    """Return the string default of a selection class's ``Literal`` identifier field."""
    default = model.model_fields[field].default
    if not isinstance(default, str):
        raise TypeError(f"{model.__name__}.{field} must default to a string literal.")
    return default


def _is_frozen(instance: object, attribute: str) -> bool:
    """Return whether assigning an attribute of ``instance`` is rejected."""
    try:
        setattr(instance, attribute, getattr(instance, attribute))
    except dataclasses.FrozenInstanceError:
        return True
    return False


# ---------------------------------------------------------------------------
# T1, T2, T3: the descriptors against independently declared type surfaces
# ---------------------------------------------------------------------------


def _selections_by_ids(members: Iterable[type[BaseModel]] | None = None) -> dict[tuple[str, str], type[BaseModel]]:
    """Return the selection classes keyed by the identifiers their ``Literal`` fields default to.

    The classes are the ``SelectionMember`` union unless a caller supplies others.
    """
    return {
        (_literal_default(member, "analysis_id"), _literal_default(member, "method_id")): member
        for member in (get_args(SelectionMember) if members is None else members)
    }


def _selection_gaps_for(item: StrategyDescriptor, selections: Mapping[tuple[str, str], type[BaseModel]]) -> list[str]:
    """T1 for one descriptor: a selection class in ``SelectionMember`` carries its identifiers."""
    if (item.analysis_id, item.method_id) in selections:
        return []
    return [f"descriptor {label(item)} has no selection class in SelectionMember"]


def selection_union_gaps(descriptors: tuple[StrategyDescriptor, ...]) -> list[str]:
    """T1: compare the descriptors' identifiers with the selection classes' ``Literal`` identifiers."""
    declared = {(item.analysis_id, item.method_id): item for item in descriptors}
    selections = _selections_by_ids()
    gaps: list[str] = []
    gaps.extend(
        f"selection class {selections[key].__name__} with ids {key} has no descriptor"
        for key in sorted(selections.keys() - declared.keys())
    )
    for key in sorted(declared.keys() - selections.keys()):
        gaps.extend(_selection_gaps_for(declared[key], selections))
    return gaps


def _evidence_gaps_for(item: StrategyDescriptor, union: set[type]) -> list[str]:
    """T2 for one descriptor: its result type is in the ``NativeEvidence`` union."""
    result_type = item.behavior.result_type
    if result_type in union:
        return []
    return [f"descriptor {label(item)} result type {result_type.__name__} is not in NativeEvidence"]


def native_evidence_union_gaps(descriptors: tuple[StrategyDescriptor, ...]) -> list[str]:
    """T2: compare the descriptors' result types with the ``NativeEvidence`` union."""
    declared = {item.behavior.result_type: item for item in descriptors}
    union = set(get_args(NativeEvidence))
    gaps = [
        f"{member.__name__} is in NativeEvidence but no descriptor declares it" for member in union - declared.keys()
    ]
    for result_type in declared.keys() - union:
        gaps.extend(_evidence_gaps_for(declared[result_type], union))
    return sorted(gaps)


def _import_strategy_modules() -> None:
    """Import every module of every strategy package so each analyzer class is defined."""
    package = importlib.import_module("investment_analysis_engine.strategies")
    for module in pkgutil.walk_packages(package.__path__, prefix="investment_analysis_engine.strategies."):
        if not any(part.startswith("_") for part in module.name.split(".")[2:]):
            importlib.import_module(module.name)


def _concrete_analyzers(scope: str = "investment_analysis_engine.") -> list[type]:
    """Return every non-abstract analyzer class defined under ``scope``, found through ``BaseAnalyzer``."""
    found: list[type] = []
    pending: list[type] = list(BaseAnalyzer.__subclasses__())
    while pending:
        analyzer = pending.pop()
        pending.extend(analyzer.__subclasses__())
        if analyzer.__module__.startswith(scope) and not inspect.isabstract(analyzer):
            found.append(analyzer)
    return sorted(found, key=lambda item: f"{item.__module__}.{item.__qualname__}")


def _analyzer_result_type(analyzer: type) -> type | None:
    """Read ``ResultT`` from the analyzer's own ``BaseAnalyzer[ConfigT, ResultT]`` specialization."""
    for base in getattr(analyzer, "__orig_bases__", ()):
        if get_origin(base) is BaseAnalyzer:
            result = get_args(base)[1]
            return result if isinstance(result, type) else None
    return None


def _analyzer_gaps_for(item: StrategyDescriptor, claimed: Mapping[type, list[str]]) -> list[str]:
    """T3 for one descriptor: an analyzer returns its result type."""
    result_type = item.behavior.result_type
    if result_type in claimed:
        return []
    return [f"descriptor {label(item)} result type {result_type.__name__} has no analyzer"]


def analyzer_generics_gaps(descriptors: tuple[StrategyDescriptor, ...]) -> list[str]:
    """T3: compare each descriptor's result type with the ``ResultT`` of the analyzers found by package walk."""
    _import_strategy_modules()
    gaps: list[str] = []
    claimed: dict[type, list[str]] = {}
    for analyzer in _concrete_analyzers():
        name = f"{analyzer.__module__}.{analyzer.__qualname__}"
        if not analyzer.__module__.startswith("investment_analysis_engine.strategies."):
            gaps.append(f"analyzer {name} is defined outside investment_analysis_engine/strategies")
            continue
        result_type = _analyzer_result_type(analyzer)
        if result_type is None:
            gaps.append(f"analyzer {name} does not specialize BaseAnalyzer[ConfigT, ResultT]")
            continue
        claimed.setdefault(result_type, []).append(name)
    declared = {item.behavior.result_type: item for item in descriptors}
    for result_type, names in claimed.items():
        if result_type not in declared:
            gaps.append(f"analyzer {', '.join(names)} returns {result_type.__name__}, which no descriptor declares")
        elif len(names) > 1:
            gaps.append(f"analyzers {', '.join(names)} share the result type {result_type.__name__}")
    for item in declared.values():
        gaps.extend(_analyzer_gaps_for(item, claimed))
    return gaps


# ---------------------------------------------------------------------------
# T4, T5, T6: tool surfaces, case routing and evaluation coverage
# ---------------------------------------------------------------------------


def _defined_argument_models(scope: str = "investment_analysis_engine.") -> set[type[AnalysisToolArguments]]:
    """Return the argument models defined under ``scope``, the package by default."""
    return {model for model in AnalysisToolArguments.__subclasses__() if model.__module__.startswith(scope)}


def _argument_gaps_for(item: StrategyDescriptor, defined: set[type[AnalysisToolArguments]]) -> list[str]:
    """T4 for one descriptor: its arguments model is defined under ``investment_analysis_engine``."""
    if item.tool_arguments in defined:
        return []
    return [
        f"descriptor {label(item)} arguments model {item.tool_arguments.__qualname__} is not defined under "
        "investment_analysis_engine"
    ]


def tool_surface_gaps(descriptors: tuple[StrategyDescriptor, ...]) -> list[str]:
    """T4: compare the tools and argument models with the ``ToolName`` enum and the argument subclasses.

    Only classes defined under ``investment_analysis_engine`` count as argument models, so a subclass defined by a test
    or a script cannot make this check depend on what else has been imported.
    """
    tools = {item.tool for item in descriptors}
    gaps = [f"tool {tool.name} is in ToolName but no descriptor binds it" for tool in ToolName if tool not in tools]
    models = {item.tool_arguments for item in descriptors}
    defined = _defined_argument_models()
    gaps.extend(
        f"arguments model {model.__qualname__} subclasses AnalysisToolArguments but no descriptor declares it"
        for model in sorted(defined - models, key=lambda item: item.__qualname__)
    )
    for item in descriptors:
        gaps.extend(_argument_gaps_for(item, defined))
    return gaps


def case_routing_gaps(descriptors: tuple[StrategyDescriptor, ...]) -> list[str]:
    """T5: route each catalog request's arguments to a tool and compare with the case's reviewed constraints."""
    by_arguments = build_indexes(descriptors).by_arguments
    gaps: list[str] = []
    for request in build_deterministic_requests():
        constraints = request.case.expectation.tool_constraints
        try:
            tool = tool_for_arguments(request.arguments, by_arguments)
        except UndeclaredStrategyError as error:
            gaps.append(f"case {request.case.case_id}: {error}")
            continue
        if tool not in constraints.required or tool in constraints.forbidden:
            gaps.append(f"case {request.case.case_id}: arguments route to {tool.value}, which its constraints reject")
    return gaps


def _required_tools() -> set[ToolName]:
    """Return the tools that some golden case requires."""
    return {tool for case in DETERMINISTIC_CASES for tool in case.expectation.tool_constraints.required}


def _tool_required_gaps_for(item: StrategyDescriptor, required: set[ToolName]) -> list[str]:
    """T6 for one descriptor: a golden case requires its tool."""
    if item.tool in required:
        return []
    return [f"descriptor {label(item)} tool {item.tool.value} is required by no golden case"]


def _dispatch_gaps_for(request: DeterministicCaseRequest, expected: type) -> list[str]:
    """T6 for one case: the fixture composition serves it with the result type its descriptor declares."""
    case_id = request.case.case_id
    result = asyncio.run(dispatch_fixture_case(request.case, request.arguments, clock_at=_FIXTURE_CLOCK))
    if not result.success:
        return [f"case {case_id}: fixture dispatch failed: {result.error_message}"]
    if type(result.result) is not expected:
        return [f"case {case_id}: dispatch returned {type(result.result).__name__}, expected {expected.__name__}"]
    return []


def evaluation_coverage_gaps(descriptors: tuple[StrategyDescriptor, ...]) -> list[str]:
    """T6: every descriptor tool is required by a golden case, and the fixture composition serves every case."""
    required = _required_tools()
    gaps: list[str] = []
    for item in descriptors:
        gaps.extend(_tool_required_gaps_for(item, required))
    indexes = build_indexes(descriptors)
    for request in build_deterministic_requests():
        case_id = request.case.case_id
        try:
            tool = tool_for_arguments(request.arguments, indexes.by_arguments)
        except UndeclaredStrategyError as error:
            gaps.append(f"case {case_id}: {error}")
            continue
        gaps.extend(_dispatch_gaps_for(request, indexes.by_tool[tool].behavior.result_type))
    return gaps


# ---------------------------------------------------------------------------
# T10: the evaluation tier covers every descriptor
# ---------------------------------------------------------------------------


def _tier_gaps_for(
    item: StrategyDescriptor, tier: Sequence[CliStrategy] | Sequence[EvaluationStrategy], tier_name: str
) -> list[str]:
    """T10 for one descriptor: exactly one entry of the named tier is paired with its core bundle."""
    entries = sum(1 for entry in tier if entry.behavior is item.behavior)
    if entries == 1:
        return []
    if entries == 0:
        return [f"strategy {label(item)} is not wired in: {tier_name}"]
    return [f"strategy {label(item)} has {entries} entries in the {tier_name}"]


def evaluation_tier_gaps(
    descriptors: tuple[StrategyDescriptor, ...],
    tier: tuple[EvaluationStrategy, ...] = EVALUATION_STRATEGIES,
) -> list[str]:
    """T10 (evaluation tier): every descriptor has exactly one tier entry, and every entry serves a descriptor.

    An entry belongs to the descriptor whose core bundle it was paired with, so the tier and the descriptors are
    compared as separate declarations: a strategy added to one only is reported by its identity.
    """
    gaps: list[str] = []
    for item in descriptors:
        gaps.extend(_tier_gaps_for(item, tier, "evaluation tier"))
    declared = {id(item.behavior) for item in descriptors}
    gaps.extend(
        "an evaluation tier entry is paired with a bundle that no descriptor holds"
        for entry in tier
        if id(entry.behavior) not in declared
    )
    return gaps


def cli_tier_gaps(
    descriptors: tuple[StrategyDescriptor, ...],
    tier: tuple[CliStrategy, ...] = CLI_STRATEGIES,
) -> list[str]:
    """T10 (CLI tier): every descriptor has exactly one tier entry, and every entry serves a descriptor.

    An entry belongs to the descriptor whose core bundle it was paired with, so the tier and the descriptors are
    compared as separate declarations: a strategy added to one only is reported by its identity.
    """
    gaps: list[str] = []
    for item in descriptors:
        gaps.extend(_tier_gaps_for(item, tier, "CLI tier"))
    declared = {id(item.behavior) for item in descriptors}
    gaps.extend(
        "a CLI tier entry is paired with a bundle that no descriptor holds"
        for entry in tier
        if id(entry.behavior) not in declared
    )
    return gaps


def evaluation_fixture_id_gaps(
    descriptors: tuple[StrategyDescriptor, ...],
    tier: tuple[EvaluationStrategy, ...] = EVALUATION_STRATEGIES,
) -> list[str]:
    """T10 (evaluation tier ids): each requirement's identifiers are declared, and no entry redeclares the context's.

    A requirement may name only identifiers its entry declares or the context consumes itself, so a case that
    selects a required identifier is never rejected as unsupported, and an identifier has one declaring owner.
    """
    gaps: list[str] = []
    for item in descriptors:
        for entry in (entry for entry in tier if entry.behavior is item.behavior):
            undeclared_ids = entry.requirement.required_ids - entry.fixture_ids - CONTEXT_FIXTURE_IDS
            if undeclared_ids:
                gaps.append(
                    f"strategy {label(item)} requires fixture ids that its evaluation tier entry and the context "
                    f"do not declare: {', '.join(sorted(undeclared_ids))}"
                )
            redeclared = entry.fixture_ids & CONTEXT_FIXTURE_IDS
            if redeclared:
                gaps.append(
                    f"strategy {label(item)} declares fixture ids that the context consumes itself: "
                    f"{', '.join(sorted(redeclared))}"
                )
    return gaps


# ---------------------------------------------------------------------------
# T8: versions and the stored round trip
# ---------------------------------------------------------------------------


class _MemorySink:
    """An in-memory run sink: the terminal insertion ``execute`` needs, with no database."""

    def __init__(self) -> None:
        self.inserted: list[AnalysisRun] = []

    def insert(self, run: AnalysisRun) -> None:
        """Retain ``run`` as stored."""
        self.inserted.append(run)


def _capture_of(result: NativeEvidence) -> Callable[[], ExecutionCapture]:
    """Return a capture callable that yields ``result`` as a profile-less capture whose status is ``ok``."""
    return lambda: ExecutionCapture(native_evidence=result, profile=None, native_status=CalculationStatus.OK)


class RunRecord(Protocol):
    """What the stored-run checks read of a run: its ticker, identifiers and version tuple."""

    @property
    def ticker(self) -> str:
        """Return the run's ticker."""
        ...

    @property
    def analysis_id(self) -> str:
        """Return the run's analysis identifier."""
        ...

    @property
    def method_id(self) -> str:
        """Return the run's method identifier."""
        ...

    @property
    def config_schema_version(self) -> int:
        """Return the stored configuration version."""
        ...

    @property
    def method_version(self) -> int:
        """Return the stored method version."""
        ...

    @property
    def result_schema_version(self) -> int:
        """Return the stored result version."""
        ...

    @property
    def evidence_codec_version(self) -> int:
        """Return the stored codec version."""
        ...

    @property
    def requested_config(self) -> object:
        """Return the selection the run was requested with."""
        ...


type RunDecoder = Callable[[Mapping[tuple[str, str], EvidenceCodec]], NativeEvidence | None]
"""Decode one stored run with the supplied codecs, as its kind of run does."""

type RunProjector = Callable[
    [ReplayOptions, Mapping[tuple[str, str], EvidenceCodec], Mapping[tuple[str, str], ReplayProjector]], str
]
"""Replay one stored run with the supplied codecs and projectors, as its kind of run does."""


@dataclasses.dataclass(frozen=True)
class StoredRun:
    """One descriptor's result and the run stored for it, with how that kind of run is decoded and replayed.

    A production run is an ``AnalysisRun``, whose selection the closed production union validates; the specimen
    stores a run of its own, so each entry carries the two functions that decode and replay its run.
    """

    descriptor: StrategyDescriptor
    selection: SelectionMember
    result: NativeEvidence
    ticker: str
    run: RunRecord
    decode: RunDecoder
    project: RunProjector


def _production_stored(
    item: StrategyDescriptor, selection: SelectionMember, result: NativeEvidence, run: AnalysisRun
) -> StoredRun:
    """Return the entry of a production run, decoded and replayed by the workspace functions."""

    def decode(codecs: Mapping[tuple[str, str], EvidenceCodec]) -> NativeEvidence | None:
        return decode_evidence(run, codecs)

    def project(
        options: ReplayOptions,
        codecs: Mapping[tuple[str, str], EvidenceCodec],
        replays: Mapping[tuple[str, str], ReplayProjector],
    ) -> str:
        return project_run(run, options, codecs=codecs, replays=replays)

    return StoredRun(item, selection, result, run.ticker, run, decode, project)


def stored_runs(
    descriptors: tuple[StrategyDescriptor, ...],
    tier: tuple[EvaluationStrategy, ...] = EVALUATION_STRATEGIES,
    local_runs: Sequence[StoredRun] = (),
) -> list[StoredRun]:
    """Execute and store one real fixture result per descriptor, as the terminal service would.

    The result is the first golden case routed to the descriptor's tool; the selection is the sample its
    evaluation-tier entry declares; the run goes through the real ``execute`` and ``AnalysisRun`` validation.
    A descriptor with no tier entry has no stored run, and the checks report it. ``local_runs`` are the entries of
    strategies that have no golden case or production run, which the caller built; they join those descriptors.
    """
    indexes = build_indexes(descriptors)
    specs = run_specs_by_key(descriptors)
    stored: dict[str, StoredRun] = {}
    for request in build_deterministic_requests():
        item = indexes.by_tool[tool_for_arguments(request.arguments, indexes.by_arguments)]
        entry = next((entry for entry in tier if entry.behavior is item.behavior), None)
        if item.alias in stored or entry is None:
            continue
        dispatched = asyncio.run(dispatch_fixture_case(request.case, request.arguments, clock_at=_FIXTURE_CLOCK))
        result = cast("NativeEvidence", dispatched.result)
        selection = entry.sample_selection
        sink = _MemorySink()
        execute(
            AnalysisRequest(ticker=request.arguments.ticker, selection=selection),
            spec=run_spec_for(selection, specs),
            capture=_capture_of(result),
            repository=sink,
            clock=lambda: _FIXTURE_CLOCK,
        )
        stored[item.alias] = _production_stored(item, selection, result, sink.inserted[0])
    for local in local_runs:
        if any(local.descriptor is item for item in descriptors):
            stored.setdefault(local.descriptor.alias, local)
    return [stored[item.alias] for item in descriptors if item.alias in stored]


def versions_and_round_trip_gaps(
    descriptors: tuple[StrategyDescriptor, ...],
    tier: tuple[EvaluationStrategy, ...] = EVALUATION_STRATEGIES,
    local_runs: Sequence[StoredRun] = (),
) -> list[str]:
    """T8: a stored run carries the descriptor's versions and decodes back to exactly the result stored."""
    codecs = evidence_by_key(descriptors)
    gaps: list[str] = []
    stored = stored_runs(descriptors, tier, local_runs)
    gaps.extend(
        f"strategy {label(item)} has no golden fixture result or evaluation-tier sample selection to store"
        for item in descriptors
        if item.alias not in {entry.descriptor.alias for entry in stored}
    )
    for entry in stored:
        gaps.extend(_round_trip_entry_gaps(entry, codecs))
    return gaps


def _round_trip_entry_gaps(entry: StoredRun, codecs: Mapping[tuple[str, str], EvidenceCodec]) -> list[str]:
    """T8 for one stored run: it carries the descriptor's versions and decodes back to the result stored."""
    item, run = entry.descriptor, entry.run
    gaps: list[str] = []
    recorded = (
        run.config_schema_version,
        run.method_version,
        run.result_schema_version,
        run.evidence_codec_version,
    )
    declared = (
        item.config_schema_version,
        item.method_version,
        item.result_schema_version,
        item.evidence_codec_version,
    )
    if recorded != declared:
        gaps.append(f"{item.label}: the stored run records versions {recorded}, the descriptor declares {declared}")
    payload = item.behavior.encode_object(entry.result)
    if item.behavior.decode_for(payload, entry.ticker) != entry.result:
        gaps.append(f"{item.label}: the behavior's decode does not return the result its encode stored")
    if entry.decode(codecs) != entry.result:
        gaps.append(f"{item.label}: decode_evidence does not return the result execute stored")
    return gaps


# ---------------------------------------------------------------------------
# T8 (replay): the typed JSON document of each stored run
# ---------------------------------------------------------------------------


def replay_gaps(
    descriptors: tuple[StrategyDescriptor, ...],
    tier: tuple[EvaluationStrategy, ...] = EVALUATION_STRATEGIES,
    local_runs: Sequence[StoredRun] = (),
) -> list[str]:
    """T8 (replay): each stored run replays in every mode and writes the document its descriptor declares.

    The JSON replay must validate against the descriptor's ``json_envelope``. A strategy with no stored run is
    reported by T8's round trip, not here.
    """
    gaps: list[str] = []
    codecs = evidence_by_key(descriptors)
    replays = replays_by_key(descriptors)
    for entry in stored_runs(descriptors, tier, local_runs):
        gaps.extend(_replay_entry_gaps(entry, codecs, replays))
    return gaps


def _replay_entry_gaps(
    entry: StoredRun,
    codecs: Mapping[tuple[str, str], EvidenceCodec],
    replays: Mapping[tuple[str, str], ReplayProjector],
) -> list[str]:
    """T8 (replay) for one stored run: it replays in every mode and its JSON validates as the declared envelope."""
    item = entry.descriptor
    gaps: list[str] = []
    for mode in PresentationMode:
        try:
            text = entry.project(ReplayOptions(mode=mode), codecs, replays)
        except Exception as error:
            gaps.append(f"strategy {label(item)}: replay in {mode.value} mode raised {type(error).__name__}: {error}")
            continue
        if not text.strip():
            gaps.append(f"strategy {label(item)}: replay in {mode.value} mode is empty")
        if mode is not PresentationMode.JSON:
            continue
        try:
            item.json_envelope.model_validate_json(text)
        except ValidationError as error:
            gaps.append(
                f"strategy {label(item)}: the replayed JSON does not validate as {item.json_envelope.__name__}: {error}"
            )
    return gaps


# ---------------------------------------------------------------------------
# T10 (schemas), T21: every strategy document and every --json command has a model and a schema
# ---------------------------------------------------------------------------


SCHEMA_COMMAND = "uv run python -m scripts.generate_schemas"
"""The command that writes the published schemas, as a diagnostic names it."""


def published_schema_gaps(descriptors: tuple[StrategyDescriptor, ...], directory: Path = SCHEMA_DIRECTORY) -> list[str]:
    """T10 (published schemas): each descriptor's ``json_envelope`` has a checked-in schema file.

    Whether the file is current is a separate question: the schema drift test and :func:`stale_schema_gaps` answer it.
    """
    return [
        f"strategy {label(item)} is not wired in: published schemas "
        f"(schemas/{strategy_schema_file(item)} is missing); run {SCHEMA_COMMAND}"
        for item in descriptors
        if not (directory / strategy_schema_file(item)).is_file()
    ]


def stale_schema_gaps(descriptors: tuple[StrategyDescriptor, ...], directory: Path = SCHEMA_DIRECTORY) -> list[str]:
    """Return one message per descriptor whose checked-in schema exists but differs from the regenerated text."""
    return [
        f"strategy {label(item)}: schemas/{path.name} is out of date; run {SCHEMA_COMMAND}"
        for item in descriptors
        if (path := directory / strategy_schema_file(item)).is_file()
        and path.read_bytes() != schema_text(item.json_envelope).encode("utf-8")
    ]


def json_command_paths(app: typer.Typer) -> list[str]:
    """Return the space-separated path of every command offering ``--json``, recursing every group, hidden ones too."""
    paths: list[str] = []

    def walk(command: object, path: list[str]) -> None:
        children = getattr(command, "commands", None)
        if isinstance(children, dict):
            for name, child in children.items():
                walk(child, [*path, name])
        elif any("--json" in getattr(parameter, "opts", ()) for parameter in getattr(command, "params", ())):
            paths.append(" ".join(path))

    walk(typer.main.get_command(app), [])
    return paths


def json_command_gaps(
    descriptors: tuple[StrategyDescriptor, ...],
    app: typer.Typer,
    directory: Path = SCHEMA_DIRECTORY,
) -> list[str]:
    """T21: every command offering ``--json`` has a typed document model and a current checked-in schema.

    The commands come from the CLI's own parameter declarations; the models from ``JSON_DOCUMENTS`` (workspace,
    database) and the descriptors (a strategy's direct command writes its ``json_envelope``; a replay command
    writes any of them); the schemas from the files on disk. There is no exemption list.
    """
    gaps: list[str] = []
    by_alias = {item.alias: item for item in descriptors}
    for command in json_command_paths(app):
        models: list[tuple[str, type[BaseModel]]]
        if command in JSON_DOCUMENTS:
            document = JSON_DOCUMENTS[command]
            models = [(document.schema_file, document.model)]
        elif command in by_alias:
            models = [(strategy_schema_file(by_alias[command]), by_alias[command].json_envelope)]
        elif command in STRATEGY_REPLAY_COMMANDS:
            models = [(strategy_schema_file(item), item.json_envelope) for item in descriptors]
        else:
            gaps.append(f"command '{command}' offers --json but has no typed document model")
            continue
        for file_name, model in models:
            path = directory / file_name
            if not path.is_file():
                gaps.append(
                    f"command '{command}' offers --json but schemas/{file_name} is not checked in; run {SCHEMA_COMMAND}"
                )
            elif path.read_bytes() != schema_text(model).encode("utf-8"):
                gaps.append(
                    f"command '{command}' offers --json but schemas/{file_name} is out of date; run {SCHEMA_COMMAND}"
                )
    return gaps


# ---------------------------------------------------------------------------
# T11: undeclared inputs fail closed
# ---------------------------------------------------------------------------


class _UndeclaredArguments(AnalysisToolArguments):
    """Arguments of a strategy that no descriptor declares."""


def _expect_undeclared(gaps: list[str], probe: str, action: Callable[[], object], *, names: str = "") -> None:
    """Record a gap unless ``action`` raises ``UndeclaredStrategyError`` that mentions ``names``."""
    try:
        action()
    except UndeclaredStrategyError as error:
        if names not in str(error):
            gaps.append(f"{probe}: the error does not name {names!r}: {error}")
    except Exception as error:
        gaps.append(f"{probe}: raised {type(error).__name__} instead of UndeclaredStrategyError")
    else:
        gaps.append(f"{probe}: accepted an undeclared input")


def _expect_error(
    gaps: list[str], probe: str, action: Callable[[], object], error_type: type[Exception], *, names: str = ""
) -> None:
    """Record a gap unless ``action`` raises exactly ``error_type`` and the error mentions ``names``."""
    try:
        action()
    except Exception as error:
        if type(error) is not error_type:
            gaps.append(f"{probe}: raised {type(error).__name__} instead of {error_type.__name__}")
        elif names not in str(error):
            gaps.append(f"{probe}: the error does not name {names!r}: {error}")
    else:
        gaps.append(f"{probe}: accepted an undeclared input")


def _workspace_probes(
    gaps: list[str],
    descriptors: tuple[StrategyDescriptor, ...],
    tier: tuple[EvaluationStrategy, ...],
    local_runs: Sequence[StoredRun],
) -> None:
    """Record a gap for each workspace dispatcher that accepts an undeclared input or another strategy's object."""
    by_key = evidence_by_key(descriptors)
    specs = run_specs_by_key(descriptors)
    _expect_undeclared(
        gaps,
        "alias lookup (undeclared alias)",
        partial(require, build_indexes(descriptors).by_alias, "undeclared-alias", what="alias"),
        names="undeclared-alias",
    )
    stored = stored_runs(descriptors, tier, local_runs)
    for entry in stored:
        item = entry.descriptor
        spec = specs[(item.analysis_id, item.method_id)]
        subclass_instance = cast(
            "NativeEvidence", object.__new__(type("_Subclassed", (item.behavior.result_type,), {}))
        )
        _expect_undeclared(
            gaps,
            f"{label(item)} run spec encode(subclass of its result type)",
            partial(spec.encode, subclass_instance),
            names="_Subclassed",
        )
        _expect_undeclared(
            gaps, f"{label(item)} run spec encode(object)", partial(spec.encode, cast("NativeEvidence", object()))
        )
        other = next((candidate for candidate in stored if candidate.descriptor is not item), None)
        if other is not None:
            _expect_undeclared(
                gaps,
                f"{label(item)} run spec encode(another strategy's result)",
                partial(spec.encode, other.result),
                names=type(other.result).__name__,
            )
        _expect_error(
            gaps,
            f"{label(item)} decode_evidence without its codec",
            partial(
                entry.decode,
                {key: value for key, value in by_key.items() if key != (item.analysis_id, item.method_id)},
            ),
            UnsupportedRunVersionError,
        )
        inputs = ReplayInputs(ticker=entry.ticker, instrument_profile=None, presentation_inputs=None)
        replay_options = ReplayOptions()
        _expect_undeclared(
            gaps,
            f"{label(item)} project_for(object evidence)",
            partial(item.behavior.project_for, inputs, object(), entry.selection, replay_options),
        )
        _expect_undeclared(
            gaps,
            f"{label(item)} project_for(object selection)",
            partial(item.behavior.project_for, inputs, entry.result, object(), replay_options),
        )
        replays_without_own = {
            key: value
            for key, value in replays_by_key(descriptors).items()
            if key != (item.analysis_id, item.method_id)
        }
        _expect_error(
            gaps,
            f"{label(item)} project_run without its replay projector",
            partial(entry.project, replay_options, by_key, replays_without_own),
            UnsupportedProjectionError,
            names=item.method_id,
        )
        _expect_undeclared(
            gaps,
            f"{label(item)} run_spec_for without its run spec",
            partial(
                run_spec_for,
                entry.selection,
                {
                    key: value
                    for key, value in run_specs_by_key(descriptors).items()
                    if key != (item.analysis_id, item.method_id)
                },
            ),
            names=item.method_id,
        )
    if len(stored) > 1 and all(isinstance(entry.descriptor.behavior, StrategyBehavior) for entry in stored):
        first, second = stored[0], stored[1]
        paired = first.descriptor.behavior
        if isinstance(paired, StrategyBehavior):
            other_result = second.result
            _expect_undeclared(
                gaps,
                "decode_for with another strategy's result",
                partial(
                    dataclasses.replace(paired, decode=lambda _payload: other_result).decode_for,
                    {},
                    first.ticker,
                ),
            )


def _evaluation_tier_probes(
    gaps: list[str],
    descriptors: tuple[StrategyDescriptor, ...],
    tier: tuple[EvaluationStrategy, ...],
) -> None:
    """Record a gap unless a missing tier entry and another strategy's dependency object both fail closed."""
    case = DETERMINISTIC_CASES[0]
    for item in descriptors:
        without = tuple(entry for entry in tier if entry.behavior is not item.behavior)
        _expect_undeclared(
            gaps,
            f"compose_fixture_dependencies without the {item.tool.value} tier entry",
            partial(compose_fixture_dependencies, case, clock_at=_FIXTURE_CLOCK, descriptors=descriptors, tier=without),
            names=item.tool.value,
        )
    request = build_deterministic_requests()[0]
    first = next((item for item in descriptors if item.tool is tool_for_arguments(request.arguments)), None)
    if first is not None:
        without_first = tuple(entry for entry in tier if entry.behavior is not first.behavior)
        _expect_undeclared(
            gaps,
            f"dispatch_fixture_case without the {first.tool.value} tier entry",
            lambda: asyncio.run(
                dispatch_fixture_case(
                    request.case,
                    request.arguments,
                    clock_at=_FIXTURE_CLOCK,
                    descriptors=descriptors,
                    tier=without_first,
                )
            ),
            names=first.tool.value,
        )
    if len(tier) > 1:
        paired, other = tier[0], tier[1]
        mispaired = dataclasses.replace(paired, compose=other.compose)
        _expect_undeclared(
            gaps,
            "compose_fixture_dispatcher with another strategy's dependency object",
            partial(
                compose_fixture_dispatcher,
                case,
                clock_at=_FIXTURE_CLOCK,
                descriptors=descriptors,
                tier=(mispaired, *tier[1:]),
            ),
        )


class _NoProfileCache:
    """A profile resolver that no probe may reach: a refresh executor rejects the selection before using it."""

    def resolve(
        self,
        ticker: str,
        *,
        identity_candidates: tuple[InstrumentProfileCandidate, ...],
        kind_candidate: InstrumentProfileCandidate | None,
        force_refresh: bool = False,
    ) -> InstrumentProfile:
        """Fail if reached."""
        del identity_candidates, kind_candidate, force_refresh
        raise AssertionError(f"A refresh executor used its profile cache for {ticker!r}.")


def _cli_tier_probes(
    gaps: list[str],
    descriptors: tuple[StrategyDescriptor, ...],
    tier: tuple[EvaluationStrategy, ...],
    cli_tier: tuple[CliStrategy, ...],
    local_runs: Sequence[StoredRun],
) -> None:
    """Record a gap unless a missing CLI-tier entry, key or another strategy's selection fails closed."""
    flags = WatchlistFlags(
        short_window=5,
        long_window=20,
        rsi_period=14,
        as_of=None,
        no_cache=True,
        eps=None,
        eps_basis=None,
        bvps=None,
        current_price=None,
        expected_growth=None,
        aaa_yield=None,
        growth_years=None,
        forward_policy="display-only",
        classification_basis="total-fcf",
        currency="USD",
    )
    _expect_undeclared(
        gaps,
        "build_selection_for(undeclared alias)",
        partial(build_selection_for, "undeclared-alias", flags, builders_by_alias(descriptors, cli_tier)),
        names="undeclared-alias",
    )
    stored = stored_runs(descriptors, tier, local_runs)
    for item in descriptors:
        without = tuple(entry for entry in cli_tier if entry.behavior is not item.behavior)
        for probe, action in (
            ("builders_by_alias", partial(builders_by_alias, descriptors, without)),
            ("refreshers_by_key", partial(refreshers_by_key, descriptors, without)),
        ):
            _expect_undeclared(
                gaps,
                f"{probe} without the {label(item)} CLI tier entry",
                action,
                names=item.method_id,
            )
        builders = builders_by_alias(descriptors, cli_tier)
        _expect_undeclared(
            gaps,
            f"build_selection_for without the {item.alias} builder",
            partial(
                build_selection_for,
                item.alias,
                flags,
                {alias: builder for alias, builder in builders.items() if alias != item.alias},
            ),
            names=item.alias,
        )
    for entry in stored:
        item = entry.descriptor
        refreshers = refreshers_by_key(descriptors, cli_tier)
        _expect_undeclared(
            gaps,
            f"refresh_executor_for without the {label(item)} refresh executor",
            partial(
                refresh_executor_for,
                entry.selection,
                {key: value for key, value in refreshers.items() if key != (item.analysis_id, item.method_id)},
            ),
            names=item.method_id,
        )
    if len(stored) > 1:
        first, second = stored[0], stored[1]
        entry_of = {id(entry.behavior): entry for entry in cli_tier}
        paired, other = entry_of.get(id(first.descriptor.behavior)), entry_of.get(id(second.descriptor.behavior))
        if paired is not None and other is not None:
            _expect_undeclared(
                gaps,
                "refresh executor with another strategy's selection",
                partial(paired.refresh, "X", second.selection, profile_cache=_NoProfileCache()),
            )
            behavior = first.descriptor.behavior
            if isinstance(behavior, StrategyBehavior):
                wrong = pair_cli(
                    behavior,
                    CliComposition(
                        build=lambda _flags: second.selection, refresh=paired.refresh, command=paired.command
                    ),
                )
                _expect_undeclared(
                    gaps,
                    "selection builder that returns another strategy's selection",
                    partial(wrong.build, flags),
                )


def undeclared_input_gaps(
    descriptors: tuple[StrategyDescriptor, ...],
    tier: tuple[EvaluationStrategy, ...] = EVALUATION_STRATEGIES,
    cli_tier: tuple[CliStrategy, ...] = CLI_STRATEGIES,
    local_runs: Sequence[StoredRun] = (),
    outside_tool_names: Sequence[StrategyDescriptor] = (),
) -> list[str]:
    """T11: every dispatcher rejects an input that matches no declared strategy, naming it.

    ``local_runs`` are the stored runs of descriptors that have no golden case, so their run-level probes run too.
    ``outside_tool_names`` are the descriptors, matched by identity, whose tool is deliberately not a ``ToolName``
    member (the specimen's). They take part in every probe except the two that register handlers against the closed
    enumeration, which the generator's end-to-end test covers.
    """
    gaps: list[str] = []
    indexes = build_indexes(descriptors)
    _evaluation_tier_probes(gaps, descriptors, tier)
    _cli_tier_probes(gaps, descriptors, tier, cli_tier, local_runs)
    _workspace_probes(gaps, descriptors, tier, local_runs)
    fixtures = compose_fixture_dependencies(
        DETERMINISTIC_CASES[0], clock_at=_FIXTURE_CLOCK, descriptors=descriptors, tier=tier
    )
    dependencies = dict(fixtures.dependencies)
    runtime = fixtures.runtime
    _expect_undeclared(
        gaps,
        "tool_for_arguments(undeclared model)",
        partial(tool_for_arguments, _UndeclaredArguments(ticker="X"), indexes.by_arguments),
        names="_UndeclaredArguments",
    )
    for item in descriptors:
        behavior = item.behavior
        subclass_instance: object = object.__new__(type("_Subclassed", (behavior.result_type,), {}))
        _expect_undeclared(
            gaps, f"{label(item)} native_status_of(object)", partial(behavior.native_status_of, object())
        )
        _expect_undeclared(
            gaps, f"{label(item)} native_status_of(subclass)", partial(behavior.native_status_of, subclass_instance)
        )
        _expect_undeclared(gaps, f"{label(item)} headline_for(object)", partial(behavior.headline_for, object()))
        _expect_undeclared(
            gaps, f"{label(item)} headline_for(subclass)", partial(behavior.headline_for, subclass_instance)
        )
        _expect_undeclared(
            gaps, f"{label(item)} bind_handler(object)", partial(behavior.bind_handler, object(), runtime)
        )
        _expect_undeclared(
            gaps,
            f"bind_handlers without {item.tool.value}",
            partial(
                bind_handlers,
                descriptors,
                {tool: dep for tool, dep in dependencies.items() if tool is not item.tool},
                runtime,
            ),
            names=item.tool.value,
        )
    if len(descriptors) > 1:
        first, second = descriptors[0], descriptors[1]
        _expect_undeclared(
            gaps,
            "bind_handlers with a tool no descriptor declares",
            partial(bind_handlers, descriptors[1:], dependencies, runtime),
            names=first.tool.value,
        )
        _expect_undeclared(
            gaps,
            "bind_handlers with another strategy's dependencies",
            partial(bind_handlers, descriptors, {**dependencies, first.tool: dependencies[second.tool]}, runtime),
        )
    skipped = {id(item.tool) for item in outside_tool_names if any(item is declared for declared in descriptors)}
    handlers = {
        tool: handler
        for tool, handler in bind_handlers(descriptors, dependencies, runtime).items()
        if id(tool) not in skipped
    }
    for tool in ToolName:
        _expect_undeclared(
            gaps,
            f"register_analysis_tools without {tool.value}",
            partial(
                register_analysis_tools,
                AsyncToolDispatcher(),
                {key: value for key, value in handlers.items() if key is not tool},
            ),
            names=tool.value,
        )
    extra = cast(
        "Mapping[ToolName, AnalysisToolHandler[object]]", {**handlers, "analyze_unknown": next(iter(handlers.values()))}
    )
    _expect_undeclared(
        gaps,
        "register_analysis_tools with a handler for no tool",
        partial(register_analysis_tools, AsyncToolDispatcher(), extra),
        names="analyze_unknown",
    )
    return gaps


# ---------------------------------------------------------------------------
# T24: uniqueness rules
# ---------------------------------------------------------------------------


def uniqueness_gaps(descriptors: tuple[StrategyDescriptor, ...]) -> list[str]:
    """T24: duplicating each uniqueness key in a copy of the tuple raises, naming the rule and both descriptors."""
    if len(descriptors) < 2:
        return ["uniqueness rules cannot be challenged with fewer than two descriptors"]
    first, second = descriptors[0], descriptors[1]
    duplicates: dict[str, StrategyDescriptor] = {
        "analysis_id+method_id": dataclasses.replace(second, analysis_id=first.analysis_id, method_id=first.method_id),
        "method_id": dataclasses.replace(second, method_id=first.method_id),
        "alias": dataclasses.replace(second, alias=first.alias),
        "tool": dataclasses.replace(second, tool=first.tool),
        "tool_arguments": dataclasses.replace(second, tool_arguments=first.tool_arguments),
        "result_type": dataclasses.replace(second, behavior=first.behavior),
        "json_envelope": dataclasses.replace(second, json_envelope=first.json_envelope),
    }
    gaps: list[str] = []
    for rule, duplicate in duplicates.items():
        try:
            build_indexes((first, duplicate))
        except ValueError as error:
            message = str(error)
            if rule not in message or label(first) not in message or label(duplicate) not in message:
                gaps.append(f"duplicate {rule}: the error does not name the rule and both descriptors: {message}")
        else:
            gaps.append(f"duplicate {rule}: accepted by the index builder")
    return gaps


# ---------------------------------------------------------------------------
# T15, T17: the descriptor and the analyzer envelope are closed
# ---------------------------------------------------------------------------


def _type_parts(field_type: object) -> Iterator[object]:
    """Yield a type annotation and every type argument nested inside it."""
    yield field_type
    for argument in get_args(field_type):
        yield from _type_parts(argument)


def descriptor_is_closed_gaps() -> list[str]:
    """T15: the descriptor, its behavior bundle and the closed tuple have exactly the documented shape."""
    gaps: list[str] = []
    fields = {field.name: field.type for field in dataclasses.fields(StrategyDescriptor)}
    if fields != DESCRIPTOR_FIELDS:
        gaps.append(f"descriptor fields differ from the documented set: {fields} != {DESCRIPTOR_FIELDS}")
    if getattr(StrategyDescriptor, "__parameters__", ()):
        gaps.append("StrategyDescriptor is generic")
    if StrategyDescriptor.__subclasses__():
        gaps.append("StrategyDescriptor is subclassed")
    members = {field.name for field in dataclasses.fields(StrategyBehavior)}
    if members != BEHAVIOR_MEMBERS:
        gaps.append(f"behavior members differ from the documented set: {sorted(members)} != {sorted(BEHAVIOR_MEMBERS)}")
    for name, field_type in fields.items():
        for part in _type_parts(field_type):
            if isinstance(part, type) and issubclass(part, BaseAnalyzer):
                gaps.append(f"descriptor field {name} mentions an analyzer class")
            if get_origin(part) is Callable or part is Callable:
                gaps.append(f"descriptor field {name} is a callable")
    if not isinstance(STRATEGIES, tuple):
        gaps.append("STRATEGIES is not a tuple")
    elif STRATEGIES:
        if not _is_frozen(STRATEGIES[0], "analysis_id"):
            gaps.append("StrategyDescriptor is not frozen")
        behavior = STRATEGIES[0].behavior
        if not isinstance(behavior, StrategyBehavior) or not _is_frozen(behavior, "result_type"):
            gaps.append("StrategyBehavior is not frozen")
    return gaps


def evaluation_tier_is_closed_gaps(tier: Sequence[EvaluationStrategy] = EVALUATION_STRATEGIES) -> list[str]:
    """T15 (evaluation tier): the composition and the tier entry have exactly the documented members."""
    gaps: list[str] = []
    members = {field.name for field in dataclasses.fields(EvalComposition)}
    if members != EVAL_COMPOSITION_MEMBERS:
        gaps.append(
            f"evaluation composition members differ from the documented set: {sorted(members)} != "
            f"{sorted(EVAL_COMPOSITION_MEMBERS)}"
        )
    fields = {field.name for field in dataclasses.fields(EvaluationStrategy)}
    if fields != EVALUATION_ENTRY_FIELDS:
        gaps.append(
            f"evaluation tier entry fields differ from the documented set: {sorted(fields)} != "
            f"{sorted(EVALUATION_ENTRY_FIELDS)}"
        )
    if len(getattr(EvalComposition, "__parameters__", ())) != 2:
        gaps.append("EvalComposition does not take exactly two type parameters, the selection and dependency types")
    if getattr(EvaluationStrategy, "__parameters__", ()):
        gaps.append("EvaluationStrategy is generic")
    if EvaluationStrategy.__subclasses__() or EvalComposition.__subclasses__():
        gaps.append("an evaluation tier type is subclassed")
    if not isinstance(tier, tuple):
        gaps.append("EVALUATION_STRATEGIES is not a tuple")
    elif tier:
        entry = tier[0]
        if not _is_frozen(entry, "requirement"):
            gaps.append("EvaluationStrategy is not frozen")
        composition = EvalComposition(
            requirement=entry.requirement,
            fixture_ids=entry.fixture_ids,
            compose=entry.compose,
            sample_selection=entry.sample_selection,
        )
        if not _is_frozen(composition, "requirement"):
            gaps.append("EvalComposition is not frozen")
    return gaps


def _strategy_flag_gaps_for(alias: str, parameters: Iterable[object]) -> list[str]:
    """T7 for one strategy command: it offers ``--save-run`` and ``--json``."""
    offered = {option for parameter in parameters for option in getattr(parameter, "opts", ())}
    return [
        f"strategy command {alias!r} does not offer {flag}" for flag in ("--save-run", "--json") if flag not in offered
    ]


def command_table_gaps(descriptors: tuple[StrategyDescriptor, ...], app: typer.Typer) -> list[str]:
    """T7: the real Typer app's top-level commands against the descriptors' aliases.

    Every top-level command is a descriptor alias, a command group (hidden ones included) or listed in
    ``NON_STRATEGY_COMMANDS``; no alias equals a group or non-strategy name; and each strategy command offers
    ``--save-run`` and ``--json``. That every alias is a command is derived from the CLI tier and is checked by
    T10's CLI-tier surface.
    """
    gaps: list[str] = []
    root = typer.main.get_command(app)
    commands = root.commands if isinstance(root, TyperGroup) else {}
    groups = {name for name, command in commands.items() if isinstance(command, TyperGroup)}
    aliases = {item.alias for item in descriptors}
    gaps.extend(
        f"alias {alias!r} is also a command group or non-strategy command name"
        for alias in sorted(aliases & (groups | NON_STRATEGY_COMMANDS))
    )
    for name in sorted(set(commands) - aliases - groups - NON_STRATEGY_COMMANDS):
        gaps.append(
            f"top-level command {name!r} is neither a strategy alias, a command group nor a listed non-strategy command"
        )
    for alias in sorted((aliases & set(commands)) - groups):
        gaps.extend(_strategy_flag_gaps_for(alias, commands[alias].params))
    return gaps


def save_run_gaps(
    descriptors: tuple[StrategyDescriptor, ...],
    stored: Mapping[str, Callable[[], Sequence[AnalysisRun]]],
) -> list[str]:
    """T22: each alias's real command, run with ``--save-run``, stores exactly one run its codec accepts.

    ``stored`` maps an alias to a function that runs that alias's command against a temporary database and
    fixture providers, then returns the runs the database holds. The per-alias fixture setup is hand-written
    test data; a missing entry is a gap.
    """
    return run_record_gaps(descriptors, stored, decode_evidence)


def run_record_gaps[RunT: RunRecord](
    descriptors: tuple[StrategyDescriptor, ...],
    stored: Mapping[str, Callable[[], Sequence[RunT]]],
    decode: Callable[[RunT, Mapping[tuple[str, str], EvidenceCodec]], object],
) -> list[str]:
    """T22 for any kind of run: ``decode`` is the function that kind of run is decoded with."""
    gaps: list[str] = []
    codecs = evidence_by_key(descriptors)
    for item in descriptors:
        run_alias = stored.get(item.alias)
        if run_alias is None:
            gaps.append(f"no save-run fixture for alias {item.alias!r}")
            continue
        runs = tuple(run_alias())
        if not runs:
            gaps.append(f"alias {item.alias!r} stored no run")
            continue
        if len(runs) > 1:
            gaps.append(f"alias {item.alias!r} stored {len(runs)} runs, not one")
            continue
        run = runs[0]
        if (run.analysis_id, run.method_id) != (item.analysis_id, item.method_id):
            gaps.append(
                f"alias {item.alias!r} stored a run keyed {(run.analysis_id, run.method_id)!r}, "
                f"not {(item.analysis_id, item.method_id)!r}"
            )
            continue
        try:
            decode(run, codecs)
        except Exception as error:  # noqa: BLE001 - any rejection is the gap being reported
            gaps.append(f"alias {item.alias!r} stored a run its codec rejects: {error}")
    return gaps


def cli_tier_is_closed_gaps(tier: Sequence[CliStrategy] = CLI_STRATEGIES) -> list[str]:
    """T15 (CLI tier): the composition and the tier entry have exactly the documented members."""
    gaps: list[str] = []
    members = {field.name for field in dataclasses.fields(CliComposition)}
    if members != CLI_COMPOSITION_MEMBERS:
        gaps.append(
            f"CLI composition members differ from the documented set: {sorted(members)} != "
            f"{sorted(CLI_COMPOSITION_MEMBERS)}"
        )
    fields = {field.name for field in dataclasses.fields(CliStrategy)}
    if fields != CLI_ENTRY_FIELDS:
        gaps.append(
            f"CLI tier entry fields differ from the documented set: {sorted(fields)} != {sorted(CLI_ENTRY_FIELDS)}"
        )
    if len(getattr(CliComposition, "__parameters__", ())) != 1:
        gaps.append("CliComposition does not take exactly one type parameter, the selection type")
    if getattr(CliStrategy, "__parameters__", ()):
        gaps.append("CliStrategy is generic")
    if CliStrategy.__subclasses__() or CliComposition.__subclasses__():
        gaps.append("a CLI tier type is subclassed")
    if not isinstance(tier, tuple):
        gaps.append("CLI_STRATEGIES is not a tuple")
    elif tier:
        entry = tier[0]
        if not _is_frozen(entry, "behavior"):
            gaps.append("CliStrategy is not frozen")
        composition = CliComposition(build=entry.build, refresh=entry.refresh, command=entry.command)
        if not _is_frozen(composition, "build"):
            gaps.append("CliComposition is not frozen")
    return gaps


def analyzer_envelope_gaps() -> list[str]:
    """T17: ``run_analysis`` and ``AnalysisContext`` keep the documented invocation envelope."""
    gaps: list[str] = []
    parameters = tuple(inspect.signature(BaseAnalyzer.run_analysis).parameters)
    if parameters != ANALYZER_ENVELOPE_PARAMETERS:
        gaps.append(f"run_analysis parameters changed: {parameters} != {ANALYZER_ENVELOPE_PARAMETERS}")
    context_fields = tuple(field.name for field in dataclasses.fields(AnalysisContext))
    if context_fields != ANALYZER_CONTEXT_FIELDS:
        gaps.append(f"AnalysisContext fields changed: {context_fields} != {ANALYZER_CONTEXT_FIELDS}")
    return gaps


# ---------------------------------------------------------------------------
# T14, T16: source-level checks
# ---------------------------------------------------------------------------


def wiring_files(root: Path = PACKAGE_ROOT) -> list[Path]:
    """Return the root module, the tier modules that exist and every strategy-owned file."""
    candidates = [
        root / "strategy_wiring.py",
        root / "cli_strategy_wiring.py",
        root / "evaluation" / "strategy_fixtures.py",
    ]
    files = [path for path in candidates if path.exists()]
    files.extend(sorted((root / "strategies").rglob("*.py")))
    return files


def _defined_names(tree: ast.Module) -> Iterator[tuple[str, int]]:
    """Yield each module-level class, function and assigned name with its line."""
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node.name, node.lineno
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    yield target.id, node.lineno
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            yield node.target.id, node.lineno


def _import_problems(node: ast.Import | ast.ImportFrom) -> Iterator[str]:
    """Yield what is wrong, if anything, with one import."""
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name.split(".")[0] in _FORBIDDEN_IMPORTS:
                yield f"imports {alias.name}"
        return
    module = node.module or ""
    if module.split(".")[0] in _FORBIDDEN_IMPORTS or any(alias.name in _FORBIDDEN_IMPORTS for alias in node.names):
        yield f"imports from {module}"
    if module == "investment_analysis_engine.cli" and any(alias.name == "app" for alias in node.names):
        yield "imports the Typer app"


def _attribute_problems(node: ast.Attribute) -> Iterator[str]:
    """Yield what is wrong, if anything, with one attribute access."""
    owner = node.value.id if isinstance(node.value, ast.Name) else ""
    if node.attr in _FORBIDDEN_ATTRIBUTES:
        yield f"uses {node.attr}"
    if node.attr == "register_tool":
        yield "registers a tool"
    if node.attr == "command" and owner == "app":
        yield _COMMAND_REGISTRATION


def _call_problems(node: ast.Call) -> Iterator[str]:
    """Yield what is wrong, if anything, with one call."""
    if isinstance(node.func, ast.Attribute) and node.func.attr == "Typer":
        owner = node.func.value.id if isinstance(node.func.value, ast.Name) else ""
        if owner == "typer":
            yield "constructs a Typer app"
    if not isinstance(node.func, ast.Name):
        return
    if node.func.id == "Typer":
        yield "constructs a Typer app"
    if node.func.id in _FORBIDDEN_CALLS:
        yield f"calls {node.func.id}"
    if node.func.id == "getattr" and not (len(node.args) > 1 and isinstance(node.args[1], ast.Constant)):
        yield "calls getattr with a computed name"


def _node_problems(node: ast.AST) -> Iterator[str]:
    """Yield what is wrong, if anything, with one syntax node."""
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        yield from _import_problems(node)
    elif isinstance(node, ast.Attribute):
        yield from _attribute_problems(node)
    elif isinstance(node, ast.Call):
        yield from _call_problems(node)


def _command_adder_lines(path: Path, tree: ast.Module) -> range:
    """Return the lines of the one permitted command registration: ``add_strategy_commands`` in the CLI tier."""
    if path.name != _COMMAND_ADDER_FILE:
        return range(0)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == _COMMAND_ADDER:
            return range(node.lineno, (node.end_lineno or node.lineno) + 1)
    return range(0)


def discovery_gaps(files: Iterable[Path], root: Path = REPOSITORY_ROOT) -> list[str]:
    """T14: no discovery, registration side effect, self-registration or registry-like name in ``files``.

    The one permitted ``app.command`` call is the one in ``add_strategy_commands`` in the CLI tier, which adds
    each strategy's command by iterating the closed tuple.
    """
    gaps: list[str] = []
    for path in files:
        where = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        permitted = _command_adder_lines(path, tree)
        for node in ast.walk(tree):
            line = getattr(node, "lineno", 0)
            gaps.extend(
                f"{where}:{line}: {problem}"
                for problem in _node_problems(node)
                if not (problem == _COMMAND_REGISTRATION and line in permitted)
            )
        gaps.extend(
            f"{where}:{line}: defines {name}, a registration or discovery name"
            for name, line in _defined_names(tree)
            if _FORBIDDEN_NAME.search(name)
        )
    return gaps


def closed_tuple_gaps(path: Path, names: Iterable[str]) -> list[str]:
    """T14 (A3): each named module-level tuple holds only module-level constants or ``pair_*`` calls."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    constants = {name for name, _ in _defined_names(tree)}
    wanted = set(names)
    found: set[str] = set()
    gaps: list[str] = []
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if not isinstance(target, ast.Name) or target.id not in wanted:
                continue
            found.add(target.id)
            if not isinstance(node.value, ast.Tuple):
                gaps.append(f"{path.name}: {target.id} is not a tuple literal")
                continue
            for element in node.value.elts:
                is_constant = isinstance(element, ast.Name) and element.id in constants
                is_pair = (
                    isinstance(element, ast.Call)
                    and isinstance(element.func, ast.Name)
                    and element.func.id.startswith("pair_")
                )
                if not (is_constant or is_pair):
                    gaps.append(
                        f"{path.name}: {target.id} holds an element that is not a module constant or pair_* call"
                    )
    gaps.extend(f"{path.name}: {name} is not declared" for name in sorted(wanted - found))
    return gaps


def read_only_index_gaps(indexes: Mapping[str, object]) -> list[str]:
    """T14 (A3): each named index is a read-only mapping."""
    return [
        f"{name} is not a read-only mapping"
        for name, index in indexes.items()
        if not isinstance(index, MappingProxyType)
    ]


class _DescriptorReads(ast.NodeVisitor):
    """Collect attribute reads on descriptor-typed expressions in one module, conservatively."""

    def __init__(self, constants: frozenset[str]) -> None:
        self.descriptors = set(constants)
        self.behaviors: set[str] = set()
        self.collections: set[str] = set()
        self.reads: set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        """Treat parameters annotated as a descriptor, or a tuple of them, as descriptor-typed."""
        for argument in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
            annotation = ast.unparse(argument.annotation) if argument.annotation is not None else ""
            if annotation == "StrategyDescriptor":
                self.descriptors.add(argument.arg)
            elif annotation == "tuple[StrategyDescriptor, ...]":
                self.collections.add(argument.arg)
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:  # noqa: N802
        """Treat a loop variable over the declared descriptors as descriptor-typed."""
        self._bind_loop(node.target, node.iter)
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        """Treat a comprehension variable over the declared descriptors as descriptor-typed."""
        self._bind_loop(node.target, node.iter)
        self.generic_visit(node)

    def visit_ListComp(self, node: ast.ListComp) -> None:  # noqa: N802
        """Bind the comprehension variables before reading the element expression."""
        self._visit_comprehension_parts(node.generators, [node.elt])

    def visit_SetComp(self, node: ast.SetComp) -> None:  # noqa: N802
        """Bind the comprehension variables before reading the element expression."""
        self._visit_comprehension_parts(node.generators, [node.elt])

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:  # noqa: N802
        """Bind the comprehension variables before reading the element expression."""
        self._visit_comprehension_parts(node.generators, [node.elt])

    def visit_DictComp(self, node: ast.DictComp) -> None:  # noqa: N802
        """Bind the comprehension variables before reading the key and value expressions."""
        self._visit_comprehension_parts(node.generators, [node.key, node.value])

    def _visit_comprehension_parts(self, generators: list[ast.comprehension], parts: list[ast.expr]) -> None:
        for generator in generators:
            self.visit(generator)
        for part in parts:
            self.visit(part)

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        """Treat a name assigned from a descriptor lookup as descriptor-typed."""
        names = [target.id for target in node.targets if isinstance(target, ast.Name)]
        if self._is_descriptor(node.value):
            self.descriptors.update(names)
        elif self._is_behavior(node.value):
            self.behaviors.update(names)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802
        """Record an attribute read on a descriptor or on its behavior."""
        if self._is_descriptor(node.value) or self._is_behavior(node.value):
            self.reads.add(node.attr)
        self.generic_visit(node)

    def _bind_loop(self, target: ast.expr, iterable: ast.expr) -> None:
        if isinstance(target, ast.Name) and self._iterates_descriptors(iterable):
            self.descriptors.add(target.id)

    def _iterates_descriptors(self, node: ast.expr) -> bool:
        if isinstance(node, ast.Name):
            return node.id == "STRATEGIES" or node.id in self.collections
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "values":
            return isinstance(node.func.value, ast.Name) and node.func.value.id.startswith("BY_")
        return False

    def _is_descriptor(self, node: ast.expr) -> bool:
        if isinstance(node, ast.Name):
            return node.id in self.descriptors
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return node.func.id in {"require", "find"}
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            return node.value.id.startswith("BY_")
        return False

    def _is_behavior(self, node: ast.expr) -> bool:
        if isinstance(node, ast.Name):
            return node.id in self.behaviors
        return isinstance(node, ast.Attribute) and node.attr == "behavior" and self._is_descriptor(node.value)


def _descriptor_constants(tree: ast.Module) -> Iterator[str]:
    """Yield the module-level names bound directly to a ``StrategyDescriptor(...)`` call."""
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "StrategyDescriptor":
            yield from (target.id for target in targets if isinstance(target, ast.Name))


def descriptor_reads(source: str, constants: frozenset[str] = frozenset()) -> set[str]:
    """Return the attribute names read on descriptor-typed expressions in ``source``."""
    visitor = _DescriptorReads(constants)
    visitor.visit(ast.parse(source))
    return visitor.reads


def unused_field_gaps(files: Iterable[Path], defining_module: Path) -> list[str]:
    """T16: every descriptor field and every behavior accessor is read outside the module that defines it.

    Behavior members are reached only through the erased view's accessors, so the accessors are the
    consumer-visible surface that must be read.
    """
    constants = frozenset(_descriptor_constants(ast.parse(defining_module.read_text(encoding="utf-8"))))
    reads: set[str] = set()
    for path in files:
        if path.resolve() != defining_module.resolve():
            reads |= descriptor_reads(path.read_text(encoding="utf-8"), constants)
    wanted = {*DESCRIPTOR_FIELDS, *VIEW_ACCESSORS}
    return [f"{name} is never read outside {defining_module.name}" for name in sorted(wanted - reads)]


def source_files() -> list[Path]:
    """Return every source and script file that may read a descriptor."""
    return [*sorted(PACKAGE_ROOT.rglob("*.py")), *sorted((REPOSITORY_ROOT / "scripts").glob("*.py"))]


# ---------------------------------------------------------------------------
# T25: site checks
# ---------------------------------------------------------------------------
#
# A site check takes the names of one strategy and a ``SiteContext`` and returns ``Gap`` records; the site data
# file names it, and the status command prints what it returns. It works from the package name and the alias,
# and consults the descriptor only when the strategy has one. A check is a site check exactly when it returns
# ``list[Gap]``; every other check in this module is a suite-wide rule over the whole closed tuple and needs no
# site.
#
# The context says what the check looks at: the descriptors, both tiers, the command application, the stored
# runs, the cases and the paths of the strategy's files. The default is the production wiring. The specimen
# strategy of the conformance tests passes a context of its own, so the same checks run over a strategy that the
# production tuples, tiers and unions never name.

_STRATEGIES_PACKAGE = "investment_analysis_engine.strategies"
_CATALOG_TEST = REPOSITORY_ROOT / "tests" / "evaluation" / "test_catalog.py"
_WATCHLIST_COMMANDS = ("create", "add-selection")
_GUIDE_LINKS = ("FINANCE_MATH.md#", "GLOSSARY.md")
SETTINGS_FILE_NAME = "settings.toml"
SETTINGS_MODEL_FILE_NAME = "settings.py"


@functools.cache
def _production_stored_runs() -> tuple[StoredRun, ...]:
    """Return the stored run of every production descriptor, built once."""
    return tuple(stored_runs(STRATEGIES))


def _production_stored_run(item: StrategyDescriptor) -> StoredRun | None:
    return next((entry for entry in _production_stored_runs() if entry.descriptor is item), None)


def _production_case_ids(item: StrategyDescriptor) -> list[str]:
    """Return the ids of the golden cases whose arguments route to the descriptor's tool."""
    return [request.case.case_id for request in _requests_of(item)]


def _production_served(item: StrategyDescriptor) -> list[str]:
    """Return the gaps in how the golden cases cover and the fixtures serve the descriptor's tool."""
    found = _tool_required_gaps_for(item, _required_tools())
    for request in _requests_of(item):
        found.extend(_dispatch_gaps_for(request, item.behavior.result_type))
    return found


def _production_strategy_docs(
    names: StrategyNames, where: str, descriptors: tuple[StrategyDescriptor, ...]
) -> list[Gap]:
    """Return the gaps in the generated strategy lists of the production user documents for ``names``."""
    del descriptors
    site_id = "strategy-docs"
    gaps: list[Gap] = []
    for block in strategy_list_blocks():
        document = block.file.relative_to(REPOSITORY_ROOT).as_posix()
        problem = block_problem(block)
        if problem is not None:
            gaps.append(Gap(site_id, where, problem))
        try:
            listed = block.lists is not None and block.lists(current_body(block), names.alias)
        except BlockError:
            continue
        if not listed:
            gaps.append(
                Gap(
                    site_id,
                    where,
                    f"{document}: the generated block {block.block_id!r} has no entry for {names.alias!r}; "
                    f"run {GENERATOR}",
                )
            )
    return gaps


@dataclasses.dataclass(frozen=True)
class SiteContext:
    """What the site checks look at, so one set of checks serves the production wiring and the specimen.

    Attributes:
        name: Names the context in diagnostics.
        descriptors: The closed tuple of descriptors the strategy is declared in.
        cli_tier: The CLI tier its entry is in.
        evaluation_tier: The evaluation tier its entry is in.
        app: The command application its direct command is added to.
        stored_run: The result and run stored for a descriptor, or ``None`` when it has none.
        case_ids: The ids of the golden cases that exercise a descriptor's tool.
        served: The gaps in how the cases cover and the fixtures serve a descriptor's tool.
        strategy_docs: The gaps in the generated strategy lists, given the strategy's names, its site path and
            the descriptors the lists are generated from.
        paths: The path of a site's file by site id, with the path placeholders, where it differs from the site
            data file's.
        selections: The selection classes the strategy's selection is one of; the ``SelectionMember`` union when
            ``None``.
        schema_directory: The folder of the published schemas; the repository's when ``None``.
        catalog_test: The test that pins the case ids; the catalog test when ``None``.
        root: The folder the paths are relative to; the repository root when ``None``.
        covered: The sites a check here cannot establish, by site id, with where they are covered instead. The
            status command reports them by name and does not run their checks.
    """

    name: str
    descriptors: tuple[StrategyDescriptor, ...]
    cli_tier: tuple[CliStrategy, ...]
    evaluation_tier: tuple[EvaluationStrategy, ...]
    app: typer.Typer
    stored_run: Callable[[StrategyDescriptor], StoredRun | None]
    case_ids: Callable[[StrategyDescriptor], list[str]]
    served: Callable[[StrategyDescriptor], list[str]]
    strategy_docs: Callable[[StrategyNames, str, tuple[StrategyDescriptor, ...]], list[Gap]]
    paths: Mapping[str, str] = dataclasses.field(default_factory=dict)
    selections: tuple[type[BaseModel], ...] | None = None
    schema_directory: Path | None = None
    catalog_test: Path | None = None
    root: Path | None = None
    covered: Mapping[str, str] = dataclasses.field(default_factory=dict)


PRODUCTION = SiteContext(
    name="production",
    descriptors=STRATEGIES,
    cli_tier=CLI_STRATEGIES,
    evaluation_tier=EVALUATION_STRATEGIES,
    app=app,
    stored_run=_production_stored_run,
    case_ids=_production_case_ids,
    served=_production_served,
    strategy_docs=_production_strategy_docs,
)
"""The context of the four production strategies."""


def site_checks() -> dict[str, Callable[..., list[Gap]]]:
    """Return the site checks of this module by name, told apart by signature.

    A site check is a function of a ``StrategyNames`` and a ``SiteContext`` that returns ``list[Gap]``; no list of
    names is kept.
    """
    checks: dict[str, Callable[..., list[Gap]]] = {}
    for name, function in inspect.getmembers(sys.modules[__name__], inspect.isfunction):
        if function.__module__ != __name__:
            continue
        signature = inspect.signature(function)
        parameters = [parameter.annotation for parameter in signature.parameters.values()]
        if signature.return_annotation == "list[Gap]" and parameters == ["StrategyNames", "SiteContext"]:
            checks[name] = function
    return checks


@functools.cache
def _sites_by_id() -> dict[str, Site]:
    return {site.id: site for site in load_sites()}


def site_path(site_id: str, names: StrategyNames, context: SiteContext = PRODUCTION) -> str:
    """Return the site's file for ``names``: the context's path when it has one, else the site data file's."""
    template = context.paths.get(site_id)
    if template is None:
        return _sites_by_id()[site_id].resolved_path(names)
    return template.format(module=names.module, alias=names.alias, guide=names.guide)


def _root(context: SiteContext) -> Path:
    """Return the folder the context's paths are relative to; the repository root is read when it is used."""
    return REPOSITORY_ROOT if context.root is None else context.root


def _module_of(path: str) -> str:
    """Return the dotted module name of a Python file's repository-relative path."""
    return path.removesuffix(".py").replace("/", ".")


def _package_of(names: StrategyNames, context: SiteContext) -> str:
    """Return the dotted name of the package that holds the strategy's files, read from its vocabulary path."""
    return _module_of(site_path("vocabulary", names, context)).rpartition(".")[0]


def _owns(names: StrategyNames, descriptor: StrategyDescriptor, package: str | None = None) -> bool:
    """Return whether ``descriptor`` is the one declared for ``names``: by alias, or by the package of its result."""
    owned = f"{_STRATEGIES_PACKAGE}.{names.module}" if package is None else package
    return descriptor.alias == names.alias or descriptor.behavior.result_type.__module__.startswith(f"{owned}.")


def find_descriptor(
    names: StrategyNames, descriptors: tuple[StrategyDescriptor, ...] = STRATEGIES, package: str | None = None
) -> StrategyDescriptor | None:
    """Return the descriptor declared for ``names``, or ``None`` when the strategy is not declared yet."""
    return next((item for item in descriptors if _owns(names, item, package)), None)


def _declared(names: StrategyNames, context: SiteContext) -> StrategyDescriptor | None:
    return find_descriptor(names, context.descriptors, _package_of(names, context))


def _undeclared(site_id: str, names: StrategyNames, context: SiteContext) -> list[Gap]:
    declared_in = site_path("descriptor", names, context)
    return [
        Gap(
            site_id,
            site_path(site_id, names, context),
            f"strategy {names.alias!r} (package {names.module!r}) has no descriptor; declare it in {declared_in}",
        )
    ]


def _descriptor_site(
    site_id: str,
    names: StrategyNames,
    context: SiteContext,
    inspect_descriptor: Callable[[StrategyDescriptor], list[str]],
) -> list[Gap]:
    """Report an undeclared strategy, or what ``inspect_descriptor`` finds wrong with the declared one."""
    item = _declared(names, context)
    if item is None:
        return _undeclared(site_id, names, context)
    where = site_path(site_id, names, context)
    return [Gap(site_id, where, message) for message in inspect_descriptor(item)]


_STUB_SITE = re.compile(r"for the '(?P<site>[a-z-]+)' site")
"""The site that an ``UnfilledStubError`` message names."""


def _stub_messages(where: str, path: Path) -> list[str]:
    """Return one message per call to ``unfilled_stub`` in the file, naming the file and line."""
    return [
        f"{where}:{line}: calls unfilled_stub({site}), a generated body that has not been written"
        for line, site in unfilled_stub_calls(path, where)
    ]


def _unfilled_dependency(
    error: UnfilledStubError, site_id: str, names: StrategyNames, context: SiteContext
) -> str | None:
    """Return the message that says a check could not run because another site's body is unfilled.

    Returns ``""`` when the unfilled body is the checked site's own, which is reported already, and ``None`` when
    the error names no site of this strategy whose file still calls ``unfilled_stub``.
    """
    match = _STUB_SITE.search(str(error))
    if match is None or match["site"] not in _sites_by_id():
        return None
    stub_site = match["site"]
    if stub_site == site_id:
        return ""
    stub_where = site_path(stub_site, names, context)
    stub_path = _root(context) / stub_where
    calls = unfilled_stub_calls(stub_path, stub_where) if stub_path.is_file() else []
    if not calls:
        return None
    return f"not checked: depends on unfilled {stub_site} ({stub_where}:{calls[0][0]})"


def _file_site(
    site_id: str,
    names: StrategyNames,
    context: SiteContext,
    *,
    inspect_tree: Callable[[ast.Module], list[str]] | None = None,
    inspect_descriptor: Callable[[StrategyDescriptor], list[str]] | None = None,
) -> list[Gap]:
    """A new-file site is done when the file exists, defines each of the site's ``defines`` and calls no stub.

    ``inspect_tree`` adds source-level findings, and ``inspect_descriptor`` adds findings about the declared
    descriptor; the latter runs only when the strategy has one. A call to ``unfilled_stub`` in the file is a
    finding, with its line. A descriptor check that runs stored code and reaches another site's unfilled body
    reports ``not checked`` and names that site, its file and its line.
    """
    where = site_path(site_id, names, context)
    path = _root(context) / where
    if not path.is_file():
        return [Gap(site_id, where, f"{where} does not exist")]
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=where)
    defined = {name for name, _ in _defined_names(tree)}
    messages = [
        f"{where} defines no name matching {pattern}"
        for pattern in _sites_by_id()[site_id].required_patterns(names)
        if not any(re.fullmatch(pattern, name) for name in defined)
    ]
    messages.extend(_stub_messages(where, path))
    if inspect_tree is not None:
        messages.extend(inspect_tree(tree))
    item = _declared(names, context)
    if inspect_descriptor is not None and item is not None:
        try:
            messages.extend(inspect_descriptor(item))
        except UnfilledStubError as error:
            dependency = _unfilled_dependency(error, site_id, names, context)
            if dependency is None:
                raise
            messages.extend([dependency] if dependency else [])
    return [Gap(site_id, where, message) for message in messages]


def _no_stored_run(item: StrategyDescriptor) -> str:
    return f"strategy {label(item)} has no golden fixture result or evaluation-tier sample selection to store"


def _own_package_imports(package: str) -> Callable[[ast.Module], list[str]]:
    """Return a tree check that reports each import from the strategy's own package."""

    def check(tree: ast.Module) -> list[str]:
        found: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.level > 0 or (node.module or "").startswith(package)):
                found.append(f"line {node.lineno} imports from its own package, but the vocabulary is a leaf")
            elif isinstance(node, ast.Import):
                found.extend(
                    f"line {node.lineno} imports {alias.name}, from its own package, but the vocabulary is a leaf"
                    for alias in node.names
                    if alias.name.startswith(package)
                )
        return found

    return check


def site_vocabulary(names: StrategyNames, context: SiteContext = PRODUCTION) -> list[Gap]:
    """Row 1a: the vocabulary leaf defines the identity constants, imports nothing from its package, and agrees."""

    def agrees(item: StrategyDescriptor) -> list[str]:
        module = importlib.import_module(_module_of(site_path("vocabulary", names, context)))
        found = []
        if getattr(module, "ANALYSIS_ID", None) != item.analysis_id:
            found.append(f"ANALYSIS_ID is not the descriptor's {item.analysis_id!r}")
        if getattr(module, "METHOD_ID", None) != item.method_id:
            found.append(f"METHOD_ID is not the descriptor's {item.method_id!r}")
        return found

    return _file_site(
        "vocabulary",
        names,
        context,
        inspect_tree=_own_package_imports(_package_of(names, context)),
        inspect_descriptor=agrees,
    )


def site_analyzer(names: StrategyNames, context: SiteContext = PRODUCTION) -> list[Gap]:
    """Row 1: the analyzer file defines an analyzer, and one analyzer of the package returns the descriptor's result."""

    def returns_the_result(item: StrategyDescriptor) -> list[str]:
        _import_strategy_modules()
        importlib.import_module(_module_of(site_path("analyzer", names, context)))
        package = _package_of(names, context)
        claimed: dict[type, list[str]] = {}
        for analyzer in _concrete_analyzers(f"{package.partition('.')[0]}."):
            result_type = _analyzer_result_type(analyzer)
            if analyzer.__module__.startswith(f"{package}.") and result_type is not None:
                claimed.setdefault(result_type, []).append(f"{analyzer.__module__}.{analyzer.__qualname__}")
        return _analyzer_gaps_for(item, claimed)

    return _file_site("analyzer", names, context, inspect_descriptor=returns_the_result)


def site_settings(names: StrategyNames, context: SiteContext = PRODUCTION) -> list[Gap]:
    """The strategy's settings, only when its package has a ``settings.py``: the shipped file and the descriptor.

    A package with no ``settings.py`` has no settings and is done. A package with one is done when a
    ``settings.toml`` sits beside it and the descriptor's ``settings_type`` is the model that file defines; each
    missing part is reported.
    """
    site_id = "settings"
    where = site_path(site_id, names, context)
    model_where = where.removesuffix(SETTINGS_FILE_NAME) + SETTINGS_MODEL_FILE_NAME
    root = _root(context)
    if not (root / model_where).is_file():
        return []
    gaps = []
    if not (root / where).is_file():
        gaps.append(Gap(site_id, where, f"{model_where} defines a settings model but {where} does not exist"))
    item = _declared(names, context)
    if item is None:
        return [*gaps, *_undeclared(site_id, names, context)]
    model = item.settings_type
    if model is None:
        gaps.append(Gap(site_id, model_where, f"{model_where} exists but the descriptor's settings_type is None"))
    elif (
        model.__module__ != _module_of(model_where)
        or getattr(importlib.import_module(model.__module__), model.__name__, None) is not model
    ):
        gaps.append(
            Gap(
                site_id,
                model_where,
                f"the descriptor's settings_type {model.__qualname__} is not defined in {model_where}",
            )
        )
    return gaps


def site_descriptor(names: StrategyNames, context: SiteContext = PRODUCTION) -> list[Gap]:
    """Row 2: the closed tuple of descriptors declares the strategy."""
    return _descriptor_site("descriptor", names, context, lambda _item: [])


def site_tool_name(names: StrategyNames, context: SiteContext = PRODUCTION) -> list[Gap]:
    """Row 3: the descriptor's tool is a ``ToolName`` member."""
    return _descriptor_site(
        "tool-name",
        names,
        context,
        lambda item: [] if item.tool in tuple(ToolName) else [f"tool {item.tool!r} is not a ToolName member"],
    )


def site_tool(names: StrategyNames, context: SiteContext = PRODUCTION) -> list[Gap]:
    """Row 4: the tool file defines the arguments model, dependencies and handler the descriptor binds."""
    package = _package_of(names, context)

    def binds_the_arguments(item: StrategyDescriptor) -> list[str]:
        found = _argument_gaps_for(item, _defined_argument_models(f"{package.partition('.')[0]}."))
        if not item.tool_arguments.__module__.startswith(f"{package}."):
            found.append(f"{item.tool_arguments.__qualname__} is not defined in the strategy's package")
        return found

    return _file_site("tool", names, context, inspect_descriptor=binds_the_arguments)


def site_unions(names: StrategyNames, context: SiteContext = PRODUCTION) -> list[Gap]:
    """Row 5: the descriptor's selection class and result type are in the two type-level unions."""

    def in_the_unions(item: StrategyDescriptor) -> list[str]:
        found = _evidence_gaps_for(item, set(get_args(NativeEvidence)))
        behavior = item.behavior
        if isinstance(behavior, StrategyBehavior) and behavior.selection_type not in get_args(SelectionMember):
            found.append(f"selection class {behavior.selection_type.__name__} is not in SelectionMember")
        return found

    return _descriptor_site("unions", names, context, in_the_unions)


def site_selection(names: StrategyNames, context: SiteContext = PRODUCTION) -> list[Gap]:
    """Row 6: the selection file defines a selection class whose identifiers are the descriptor's."""

    def carries_the_ids(item: StrategyDescriptor) -> list[str]:
        return _selection_gaps_for(item, _selections_by_ids(context.selections))

    return _file_site("selection", names, context, inspect_descriptor=carries_the_ids)


def site_codec(names: StrategyNames, context: SiteContext = PRODUCTION) -> list[Gap]:
    """Row 7: the codec file defines the codec functions, and the strategy's stored run decodes to its result."""

    def round_trips(item: StrategyDescriptor) -> list[str]:
        entry = context.stored_run(item)
        if entry is None:
            return [_no_stored_run(item)]
        return _round_trip_entry_gaps(entry, evidence_by_key(context.descriptors))

    return _file_site("codec", names, context, inspect_descriptor=round_trips)


def site_execution(names: StrategyNames, context: SiteContext = PRODUCTION) -> list[Gap]:
    """Row 8: the execution file defines the capture type and the function that turns a capture into a run."""
    return _file_site("execution", names, context)


def site_cli(names: StrategyNames, context: SiteContext = PRODUCTION) -> list[Gap]:
    """Row 9: the CLI file defines the selection builder, the refresh executor and the direct command."""
    return _file_site("cli", names, context)


def site_cli_tier(names: StrategyNames, context: SiteContext = PRODUCTION) -> list[Gap]:
    """Row 10: one CLI-tier entry serves the descriptor, and its alias is a command offering both strategy flags."""

    def wired(item: StrategyDescriptor) -> list[str]:
        found = _tier_gaps_for(item, context.cli_tier, "CLI tier")
        root = typer.main.get_command(context.app)
        commands = root.commands if isinstance(root, TyperGroup) else {}
        command = commands.get(item.alias)
        if command is None:
            return [*found, f"alias {item.alias!r} is not a top-level command"]
        return [*found, *_strategy_flag_gaps_for(item.alias, command.params)]

    return _descriptor_site("cli-tier", names, context, wired)


def _replays(item: StrategyDescriptor, context: SiteContext) -> list[str]:
    entry = context.stored_run(item)
    if entry is None:
        return [_no_stored_run(item)]
    return _replay_entry_gaps(entry, evidence_by_key(context.descriptors), replays_by_key(context.descriptors))


def site_presenter(names: StrategyNames, context: SiteContext = PRODUCTION) -> list[Gap]:
    """Row 11: the presenter file defines a renderer, and the stored run replays in every mode."""
    return _file_site("presenter", names, context, inspect_descriptor=lambda item: _replays(item, context))


def site_envelope(names: StrategyNames, context: SiteContext = PRODUCTION) -> list[Gap]:
    """Row 12: the envelope file defines the document version, and the direct command's ``--json`` has this model."""
    package = _package_of(names, context)

    def documents(item: StrategyDescriptor) -> list[str]:
        found = []
        if not item.json_envelope.__module__.startswith(f"{package}."):
            found.append(f"{item.json_envelope.__qualname__} is not defined in the strategy's package")
        if item.alias not in json_command_paths(context.app):
            found.append(f"command '{item.alias}' offers no --json document")
        return found

    return _file_site("envelope", names, context, inspect_descriptor=documents)


def site_replay(names: StrategyNames, context: SiteContext = PRODUCTION) -> list[Gap]:
    """Row 13: the replay file defines a projector, and the stored run replays in every mode."""
    return _file_site("replay", names, context, inspect_descriptor=lambda item: _replays(item, context))


def site_evaluation(names: StrategyNames, context: SiteContext = PRODUCTION) -> list[Gap]:
    """Row 14: the evaluation file defines its fixture ids, requirement, sample selection and composition."""
    return _file_site(
        "evaluation",
        names,
        context,
        inspect_descriptor=lambda item: evaluation_fixture_id_gaps((item,), context.evaluation_tier),
    )


def site_evaluation_tier(names: StrategyNames, context: SiteContext = PRODUCTION) -> list[Gap]:
    """Row 15: one evaluation-tier entry serves the descriptor."""

    def wired(item: StrategyDescriptor) -> list[str]:
        return _tier_gaps_for(item, context.evaluation_tier, "evaluation tier")

    return _descriptor_site("evaluation-tier", names, context, wired)


def _requests_of(item: StrategyDescriptor) -> list[DeterministicCaseRequest]:
    """Return the golden cases whose arguments route to the descriptor's tool."""
    requests = []
    for request in build_deterministic_requests():
        try:
            routed = tool_for_arguments(request.arguments)
        except UndeclaredStrategyError:
            continue
        if routed is item.tool:
            requests.append(request)
    return requests


def site_cases(names: StrategyNames, context: SiteContext = PRODUCTION) -> list[Gap]:
    """Row 16: the cases file defines the arguments table and cases, and the fixtures serve each of the tool's cases."""
    return _file_site("cases", names, context, inspect_descriptor=context.served)


def site_catalog(names: StrategyNames, context: SiteContext = PRODUCTION) -> list[Gap]:
    """Row 17: the catalog imports the case module, and the catalog test pins the id of each of the tool's cases.

    Whether the suite version was bumped is reviewed truth that no check can establish for one strategy.
    """
    site_id = "catalog"
    where = site_path(site_id, names, context)
    path = _root(context) / where
    if not path.is_file():
        return [Gap(site_id, where, f"{where} does not exist")]
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=where)
    module = _module_of(site_path("cases", names, context))
    gaps = []
    if not any(isinstance(node, ast.ImportFrom) and node.module == module for node in ast.walk(tree)):
        gaps.append(Gap(site_id, where, f"{where} does not import {module}"))
    item = _declared(names, context)
    if item is not None:
        catalog_test = _CATALOG_TEST if context.catalog_test is None else context.catalog_test
        pinned = catalog_test.read_text(encoding="utf-8")
        test_where = catalog_test.relative_to(REPOSITORY_ROOT).as_posix()
        gaps.extend(
            Gap(site_id, test_where, f"case {case_id} is not in the catalog test's pinned ids")
            for case_id in context.case_ids(item)
            if f'"{case_id}"' not in pinned
        )
    return gaps


def _module_level_names(path: Path, name: str) -> list[ast.expr] | None:
    """Return the elements of the dict (its keys) or tuple the module assigns to ``name``; ``None`` when it has none."""
    for node in ast.parse(path.read_text(encoding="utf-8"), filename=str(path)).body:
        value = node.value if isinstance(node, ast.Assign | ast.AnnAssign) else None
        targets = (
            node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        )
        if value is not None and any(isinstance(target, ast.Name) and target.id == name for target in targets):
            if isinstance(value, ast.Dict):
                return [key for key in value.keys if key is not None]
            if isinstance(value, ast.Tuple | ast.List):
                return list(value.elts)
    return None


def _missing_files(site_id: str, where: str, context: SiteContext, names: list[str], regenerate: str) -> list[Gap]:
    """Report each stored file beside ``where`` that does not exist, with the command that writes it."""
    root = _root(context)
    folder = Path(where).parent
    return [
        Gap(
            site_id,
            where,
            f"{(folder / name).as_posix()} does not exist; write it with {regenerate}",
        )
        for name in names
        if not (root / folder / name).is_file()
    ]


def site_direct_output(names: StrategyNames, context: SiteContext = PRODUCTION) -> list[Gap]:
    """The direct command has fixed arguments in the output tests and stored text and JSON output."""
    site_id = "direct-output"
    where = site_path(site_id, names, context)
    gaps = _missing_files(
        site_id,
        where,
        context,
        [f"{names.alias}.txt", f"{names.alias}.json"],
        "uv run python -m tests._direct_command_output",
    )
    registry = "tests/_direct_command_output.py"
    path = _root(context) / registry
    keys = _module_level_names(path, "_COMMANDS") if path.is_file() else None
    if keys is None or not any(isinstance(key, ast.Constant) and key.value == names.alias for key in keys):
        gaps.append(Gap(site_id, where, f"{registry} has no entry for {names.alias!r} in _COMMANDS"))
    return gaps


def site_strategy_documents(names: StrategyNames, context: SiteContext = PRODUCTION) -> list[Gap]:
    """The strategy has a success case in the document tests and its stored direct and replayed documents."""
    site_id = "strategy-documents"
    where = site_path(site_id, names, context)
    gaps = _missing_files(
        site_id,
        where,
        context,
        [f"{names.alias}-success.direct.json", f"{names.alias}-success.replay.json"],
        "uv run python -m tests._strategy_document_output",
    )
    registry = "tests/_strategy_document_output.py"
    path = _root(context) / registry
    cases = _module_level_names(path, "CASES") if path.is_file() else None
    case_names = {
        case.args[0].value
        for case in cases or []
        if isinstance(case, ast.Call) and case.args and isinstance(case.args[0], ast.Constant)
    }
    if f"{names.alias}-success" not in case_names:
        gaps.append(Gap(site_id, where, f"{registry} has no case named {names.alias}-success in CASES"))
    return gaps


_HELP_COMMAND = "uv run python -m tests._cli_help_output"


def site_help_snapshot(names: StrategyNames, context: SiteContext = PRODUCTION) -> list[Gap]:
    """The stored application help has a command row that starts with the strategy's alias."""
    site_id = "help-snapshot"
    where = site_path(site_id, names, context)
    path = _root(context) / where
    if not path.is_file():
        return [Gap(site_id, where, f"{where} does not exist")]
    if not any(line.split(maxsplit=1)[:1] == [names.alias] for line in path.read_text(encoding="utf-8").splitlines()):
        return [
            Gap(
                site_id,
                where,
                f"{where} has no command row for {names.alias!r}; write it with {_HELP_COMMAND}",
            )
        ]
    return []


def site_guide(names: StrategyNames, context: SiteContext = PRODUCTION) -> list[Gap]:
    """Row 18: the user guide exists and links to the finance mathematics and the glossary."""
    site_id = "guide"
    where = site_path(site_id, names, context)
    path = _root(context) / where
    if not path.is_file():
        return [Gap(site_id, where, f"no guide for alias {names.alias!r}: {where} does not exist")]
    text = path.read_text(encoding="utf-8")
    return [Gap(site_id, where, f"{where} has no link to {link}") for link in _GUIDE_LINKS if link not in text]


def site_watchlist_options(names: StrategyNames, context: SiteContext = PRODUCTION) -> list[Gap]:
    """Row 19: every flag the strategy's selection builder reads is a ``WatchlistFlags`` field and a watchlist option.

    A strategy that reads only the shared flags is done by having nothing to add; one that reads a flag of its own
    needs the typed field and the option on both watchlist commands.
    """
    site_id = "watchlist-options"
    where = site_path(site_id, names, context)
    cli_where = site_path("cli", names, context)
    cli_path = _root(context) / cli_where
    if not cli_path.is_file():
        return [
            Gap(site_id, where, f"{cli_where} does not exist, so the flags its selection builder reads are unknown")
        ]
    tree = ast.parse(cli_path.read_text(encoding="utf-8"), filename=cli_where)
    builder = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "build_selection"), None)
    if builder is None or not builder.args.args:
        return [Gap(site_id, where, f"{cli_where} defines no build_selection(flags) function")]
    parameter = builder.args.args[0].arg
    read = sorted(
        {
            node.attr
            for node in ast.walk(builder)
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == parameter
        }
    )
    fields = {field.name for field in dataclasses.fields(WatchlistFlags)}
    root = typer.main.get_command(watchlist_app)
    commands = root.commands if isinstance(root, TyperGroup) else {}
    gaps = []
    for flag in read:
        if flag not in fields:
            gaps.append(
                Gap(site_id, where, f"the selection builder reads {flag}, which WatchlistFlags does not define")
            )
            continue
        for command_name in _WATCHLIST_COMMANDS:
            command = commands.get(command_name)
            if command is None or flag not in {option.name for option in command.params}:
                gaps.append(
                    Gap(site_id, where, f"the selection builder reads {flag}, which 'watchlist {command_name}' lacks")
                )
    return gaps


def site_schema(names: StrategyNames, context: SiteContext = PRODUCTION) -> list[Gap]:
    """The published schema of the strategy's document exists and is current."""
    site_id = "schema"
    where = site_path(site_id, names, context)
    item = _declared(names, context)
    if item is None:
        if (_root(context) / where).is_file():
            return []
        return [Gap(site_id, where, f"{where} does not exist; run {SCHEMA_COMMAND}")]
    directory = SCHEMA_DIRECTORY if context.schema_directory is None else context.schema_directory
    messages = [*published_schema_gaps((item,), directory), *stale_schema_gaps((item,), directory)]
    return [Gap(site_id, where, message) for message in messages]


def site_strategy_docs(names: StrategyNames, context: SiteContext = PRODUCTION) -> list[Gap]:
    """The generated strategy lists of the user documents hold the strategy and are current.

    Each gap carries the site's path and names the document in its message; the remedy is always
    ``uv run python -m scripts.generate_strategy_docs``.
    """
    return context.strategy_docs(names, site_path("strategy-docs", names, context), context.descriptors)
