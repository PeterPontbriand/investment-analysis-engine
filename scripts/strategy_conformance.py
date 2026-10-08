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
import importlib
import inspect
import pkgutil
import re
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from types import MappingProxyType
from typing import cast, get_args, get_origin

import typer
from pydantic import BaseModel, ValidationError
from typer.core import TyperGroup

from scripts.generate_schemas import SCHEMA_DIRECTORY, schema_text, strategy_schema_file
from src.analysis.base_analyzer import AnalysisContext, BaseAnalyzer
from src.cli_strategy_wiring import (
    CLI_STRATEGIES,
    CliComposition,
    CliStrategy,
    build_selection_for,
    builders_by_alias,
    pair_cli,
    refresh_executor_for,
    refreshers_by_key,
)
from src.cli_watchlist_flags import WatchlistFlags
from src.core.strategy_errors import UndeclaredStrategyError, require
from src.data.instrument_profile import InstrumentProfile, InstrumentProfileCandidate
from src.evaluation.catalog import DETERMINISTIC_CASES, build_deterministic_requests
from src.evaluation.composition import compose_fixture_dependencies, compose_fixture_dispatcher, dispatch_fixture_case
from src.evaluation.fixture_context import CONTEXT_FIXTURE_IDS
from src.evaluation.strategy_fixtures import EVALUATION_STRATEGIES, EvalComposition, EvaluationStrategy
from src.orchestrator.analysis_tool_arguments import AnalysisToolArguments
from src.orchestrator.analysis_tools import register_analysis_tools
from src.orchestrator.dispatcher import AsyncToolDispatcher
from src.orchestrator.tool_names import ToolName
from src.orchestrator.tool_runtime import AnalysisToolHandler
from src.reporting.analysis_runs import project_run
from src.reporting.json_documents import JSON_DOCUMENTS, STRATEGY_REPLAY_COMMANDS
from src.reporting.presentation import PresentationMode
from src.reporting.replay_inputs import ReplayInputs, ReplayOptions, UnsupportedProjectionError
from src.strategy_wiring import (
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
from src.workspace.capture import ExecutionCapture
from src.workspace.codecs import UnsupportedRunVersionError, decode_evidence
from src.workspace.execution import execute
from src.workspace.models import RunOutcome
from src.workspace.requests import AnalysisRequest
from src.workspace.runs import AnalysisRun
from src.workspace.strategy_types import NativeEvidence, SelectionMember

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / "src"
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
    {"result_type", "encode_object", "decode_for", "native_status_of", "bind_handler", "project_for"}
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


def selection_union_gaps(descriptors: tuple[StrategyDescriptor, ...]) -> list[str]:
    """T1: compare the descriptors' identifiers with the selection classes' ``Literal`` identifiers."""
    declared = {(item.analysis_id, item.method_id): item for item in descriptors}
    selections = {
        (_literal_default(member, "analysis_id"), _literal_default(member, "method_id")): member
        for member in get_args(SelectionMember)
    }
    gaps: list[str] = []
    gaps.extend(
        f"selection class {selections[key].__name__} with ids {key} has no descriptor"
        for key in sorted(selections.keys() - declared.keys())
    )
    gaps.extend(
        f"descriptor {label(declared[key])} has no selection class in SelectionMember"
        for key in sorted(declared.keys() - selections.keys())
    )
    return gaps


def native_evidence_union_gaps(descriptors: tuple[StrategyDescriptor, ...]) -> list[str]:
    """T2: compare the descriptors' result types with the ``NativeEvidence`` union."""
    declared = {item.behavior.result_type: item for item in descriptors}
    union = set(get_args(NativeEvidence))
    gaps = [
        f"{member.__name__} is in NativeEvidence but no descriptor declares it" for member in union - declared.keys()
    ]
    gaps.extend(
        f"descriptor {label(declared[result_type])} result type {result_type.__name__} is not in NativeEvidence"
        for result_type in declared.keys() - union
    )
    return sorted(gaps)


def _import_strategy_modules() -> None:
    """Import every module of every strategy package so each analyzer class is defined."""
    package = importlib.import_module("src.strategies")
    for module in pkgutil.walk_packages(package.__path__, prefix="src.strategies."):
        if not any(part.startswith("_") for part in module.name.split(".")[2:]):
            importlib.import_module(module.name)


def _concrete_analyzers() -> list[type]:
    """Return every non-abstract analyzer class defined under ``src``, found through ``BaseAnalyzer``."""
    found: list[type] = []
    pending: list[type] = list(BaseAnalyzer.__subclasses__())
    while pending:
        analyzer = pending.pop()
        pending.extend(analyzer.__subclasses__())
        if analyzer.__module__.startswith("src.") and not inspect.isabstract(analyzer):
            found.append(analyzer)
    return sorted(found, key=lambda item: f"{item.__module__}.{item.__qualname__}")


def _analyzer_result_type(analyzer: type) -> type | None:
    """Read ``ResultT`` from the analyzer's own ``BaseAnalyzer[ConfigT, ResultT]`` specialization."""
    for base in getattr(analyzer, "__orig_bases__", ()):
        if get_origin(base) is BaseAnalyzer:
            result = get_args(base)[1]
            return result if isinstance(result, type) else None
    return None


def analyzer_generics_gaps(descriptors: tuple[StrategyDescriptor, ...]) -> list[str]:
    """T3: compare each descriptor's result type with the ``ResultT`` of the analyzers found by package walk."""
    _import_strategy_modules()
    gaps: list[str] = []
    claimed: dict[type, list[str]] = {}
    for analyzer in _concrete_analyzers():
        name = f"{analyzer.__module__}.{analyzer.__qualname__}"
        if not analyzer.__module__.startswith("src.strategies."):
            gaps.append(f"analyzer {name} is defined outside src/strategies")
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
    gaps.extend(
        f"descriptor {label(item)} result type {result_type.__name__} has no analyzer"
        for result_type, item in declared.items()
        if result_type not in claimed
    )
    return gaps


# ---------------------------------------------------------------------------
# T4, T5, T6: tool surfaces, case routing and evaluation coverage
# ---------------------------------------------------------------------------


def tool_surface_gaps(descriptors: tuple[StrategyDescriptor, ...]) -> list[str]:
    """T4: compare the tools and argument models with the ``ToolName`` enum and the argument subclasses.

    Only classes defined under ``src`` count as argument models, so a subclass defined by a test or a
    script cannot make this check depend on what else has been imported.
    """
    tools = {item.tool for item in descriptors}
    gaps = [f"tool {tool.name} is in ToolName but no descriptor binds it" for tool in ToolName if tool not in tools]
    models = {item.tool_arguments for item in descriptors}
    defined = {model for model in AnalysisToolArguments.__subclasses__() if model.__module__.startswith("src.")}
    gaps.extend(
        f"arguments model {model.__qualname__} subclasses AnalysisToolArguments but no descriptor declares it"
        for model in sorted(defined - models, key=lambda item: item.__qualname__)
    )
    gaps.extend(
        f"descriptor {label(item)} arguments model {item.tool_arguments.__qualname__} is not defined under src"
        for item in descriptors
        if item.tool_arguments not in defined
    )
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


def evaluation_coverage_gaps(descriptors: tuple[StrategyDescriptor, ...]) -> list[str]:
    """T6: every descriptor tool is required by a golden case, and the fixture composition serves every case."""
    required = {tool for case in DETERMINISTIC_CASES for tool in case.expectation.tool_constraints.required}
    gaps = [
        f"descriptor {label(item)} tool {item.tool.value} is required by no golden case"
        for item in descriptors
        if item.tool not in required
    ]
    indexes = build_indexes(descriptors)
    for request in build_deterministic_requests():
        case_id = request.case.case_id
        try:
            tool = tool_for_arguments(request.arguments, indexes.by_arguments)
        except UndeclaredStrategyError as error:
            gaps.append(f"case {case_id}: {error}")
            continue
        result = asyncio.run(dispatch_fixture_case(request.case, request.arguments, clock_at=_FIXTURE_CLOCK))
        expected = indexes.by_tool[tool].behavior.result_type
        if not result.success:
            gaps.append(f"case {case_id}: fixture dispatch failed: {result.error_message}")
        elif type(result.result) is not expected:
            gaps.append(
                f"case {case_id}: dispatch returned {type(result.result).__name__}, expected {expected.__name__}"
            )
    return gaps


# ---------------------------------------------------------------------------
# T10: the evaluation tier covers every descriptor
# ---------------------------------------------------------------------------


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
        entries = [entry for entry in tier if entry.behavior is item.behavior]
        if not entries:
            gaps.append(f"strategy {label(item)} is not wired in: evaluation tier")
        elif len(entries) > 1:
            gaps.append(f"strategy {label(item)} has {len(entries)} entries in the evaluation tier")
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
        entries = [entry for entry in tier if entry.behavior is item.behavior]
        if not entries:
            gaps.append(f"strategy {label(item)} is not wired in: CLI tier")
        elif len(entries) > 1:
            gaps.append(f"strategy {label(item)} has {len(entries)} entries in the CLI tier")
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
    """Return a capture callable that yields ``result`` as a completed, profile-less capture."""
    return lambda: ExecutionCapture(native_evidence=result, profile=None, outcome=RunOutcome.COMPLETED)


@dataclasses.dataclass(frozen=True)
class StoredRun:
    """One descriptor's real golden-fixture result and the run ``execute`` stored for it."""

    descriptor: StrategyDescriptor
    selection: SelectionMember
    result: NativeEvidence
    ticker: str
    run: AnalysisRun


def stored_runs(
    descriptors: tuple[StrategyDescriptor, ...],
    tier: tuple[EvaluationStrategy, ...] = EVALUATION_STRATEGIES,
) -> list[StoredRun]:
    """Execute and store one real fixture result per descriptor, as the terminal service would.

    The result is the first golden case routed to the descriptor's tool; the selection is the sample its
    evaluation-tier entry declares; the run goes through the real ``execute`` and ``AnalysisRun`` validation.
    A descriptor with no tier entry has no stored run, and the checks report it.
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
        run = execute(
            AnalysisRequest(ticker=request.arguments.ticker, selection=selection),
            spec=run_spec_for(selection, specs),
            capture=_capture_of(result),
            repository=sink,
            clock=lambda: _FIXTURE_CLOCK,
        )
        stored[item.alias] = StoredRun(item, selection, result, run.ticker, sink.inserted[0])
    return [stored[item.alias] for item in descriptors if item.alias in stored]


def versions_and_round_trip_gaps(
    descriptors: tuple[StrategyDescriptor, ...],
    tier: tuple[EvaluationStrategy, ...] = EVALUATION_STRATEGIES,
) -> list[str]:
    """T8: a stored run carries the descriptor's versions and decodes back to exactly the result stored."""
    codecs = evidence_by_key(descriptors)
    gaps: list[str] = []
    stored = stored_runs(descriptors, tier)
    gaps.extend(
        f"strategy {label(item)} has no golden fixture result or evaluation-tier sample selection to store"
        for item in descriptors
        if item.alias not in {entry.descriptor.alias for entry in stored}
    )
    for entry in stored:
        item, run = entry.descriptor, entry.run
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
        if decode_evidence(run, codecs) != entry.result:
            gaps.append(f"{item.label}: decode_evidence does not return the result execute stored")
    return gaps


# ---------------------------------------------------------------------------
# T8 (replay): the typed JSON document of each stored run
# ---------------------------------------------------------------------------


def replay_gaps(
    descriptors: tuple[StrategyDescriptor, ...],
    tier: tuple[EvaluationStrategy, ...] = EVALUATION_STRATEGIES,
) -> list[str]:
    """T8 (replay): each stored run replays in every mode and writes the document its descriptor declares.

    The JSON replay must validate against the descriptor's ``json_envelope``. A strategy with no stored run is
    reported by T8's round trip, not here.
    """
    gaps: list[str] = []
    codecs = evidence_by_key(descriptors)
    replays = replays_by_key(descriptors)
    for entry in stored_runs(descriptors, tier):
        item = entry.descriptor
        for mode in PresentationMode:
            try:
                text = project_run(entry.run, ReplayOptions(mode=mode), codecs=codecs, replays=replays)
            except Exception as error:
                gaps.append(
                    f"strategy {label(item)}: replay in {mode.value} mode raised {type(error).__name__}: {error}"
                )
                continue
            if not text.strip():
                gaps.append(f"strategy {label(item)}: replay in {mode.value} mode is empty")
            if mode is not PresentationMode.JSON:
                continue
            try:
                item.json_envelope.model_validate_json(text)
            except ValidationError as error:
                gaps.append(
                    f"strategy {label(item)}: the replayed JSON does not validate as "
                    f"{item.json_envelope.__name__}: {error}"
                )
                continue
    return gaps


# ---------------------------------------------------------------------------
# T10 (schemas), T21: every strategy document and every --json command has a model and a schema
# ---------------------------------------------------------------------------


def published_schema_gaps(descriptors: tuple[StrategyDescriptor, ...], directory: Path = SCHEMA_DIRECTORY) -> list[str]:
    """T10 (published schemas): each descriptor's ``json_envelope`` has a checked-in, current schema file."""
    gaps: list[str] = []
    for item in descriptors:
        path = directory / strategy_schema_file(item)
        if not path.is_file():
            gaps.append(f"strategy {label(item)} is not wired in: published schemas (schemas/{path.name} is missing)")
        elif path.read_bytes() != schema_text(item.json_envelope).encode("utf-8"):
            gaps.append(
                f"strategy {label(item)} is not wired in: published schemas (schemas/{path.name} is out of date)"
            )
    return gaps


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
                gaps.append(f"command '{command}' offers --json but schemas/{file_name} is not checked in")
            elif path.read_bytes() != schema_text(model).encode("utf-8"):
                gaps.append(f"command '{command}' offers --json but schemas/{file_name} is out of date")
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
    gaps: list[str], descriptors: tuple[StrategyDescriptor, ...], tier: tuple[EvaluationStrategy, ...]
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
    stored = stored_runs(descriptors, tier)
    for entry in stored:
        item, run = entry.descriptor, entry.run
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
                decode_evidence,
                run,
                {key: value for key, value in by_key.items() if key != (item.analysis_id, item.method_id)},
            ),
            UnsupportedRunVersionError,
        )
        inputs = ReplayInputs(ticker=run.ticker, instrument_profile=None, presentation_inputs=None)
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
            partial(project_run, run, codecs=by_key, replays=replays_without_own),
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
) -> None:
    """Record a gap unless a missing CLI-tier entry, key or another strategy's selection fails closed."""
    flags = WatchlistFlags(
        short_window=5,
        long_window=20,
        rsi_period=14,
        as_of=None,
        data_provider=None,
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
    stored = stored_runs(descriptors, tier)
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
) -> list[str]:
    """T11: every dispatcher rejects an input that matches no declared strategy, naming it."""
    gaps: list[str] = []
    indexes = build_indexes(descriptors)
    _evaluation_tier_probes(gaps, descriptors, tier)
    _cli_tier_probes(gaps, descriptors, tier, cli_tier)
    _workspace_probes(gaps, descriptors, tier)
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
    handlers = dict(bind_handlers(descriptors, dependencies, runtime))
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
        offered = {option for parameter in commands[alias].params for option in getattr(parameter, "opts", ())}
        gaps.extend(
            f"strategy command {alias!r} does not offer {flag}"
            for flag in ("--save-run", "--json")
            if flag not in offered
        )
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
            decode_evidence(run, codecs)
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


def wiring_files(root: Path = _SRC_ROOT) -> list[Path]:
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
    if module == "src.cli" and any(alias.name == "app" for alias in node.names):
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


def discovery_gaps(files: Iterable[Path], root: Path = _REPO_ROOT) -> list[str]:
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
    return [*sorted(_SRC_ROOT.rglob("*.py")), *sorted((_REPO_ROOT / "scripts").glob("*.py"))]
