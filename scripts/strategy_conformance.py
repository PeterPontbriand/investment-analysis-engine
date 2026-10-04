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

from pydantic import BaseModel

from src.analysis.base_analyzer import AnalysisContext, BaseAnalyzer
from src.core.strategy_errors import UndeclaredStrategyError
from src.evaluation.catalog import DETERMINISTIC_CASES, build_deterministic_requests
from src.evaluation.composition import compose_fixture_dependencies, compose_fixture_dispatcher, dispatch_fixture_case
from src.evaluation.strategy_fixtures import EVALUATION_STRATEGIES, EvalComposition, EvaluationStrategy
from src.orchestrator.analysis_tool_arguments import AnalysisToolArguments
from src.orchestrator.analysis_tools import register_analysis_tools
from src.orchestrator.dispatcher import AsyncToolDispatcher
from src.orchestrator.tool_names import ToolName
from src.orchestrator.tool_runtime import AnalysisToolHandler
from src.strategy_wiring import (
    STRATEGIES,
    BehaviorView,
    StrategyBehavior,
    StrategyDescriptor,
    bind_handlers,
    build_indexes,
    tool_for_arguments,
)
from src.workspace.strategy_types import NativeEvidence, SelectionMember

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / "src"
_FIXTURE_CLOCK = datetime(2026, 8, 31, 18, 30, tzinfo=UTC)

DESCRIPTOR_FIELDS: dict[str, object] = {
    "analysis_id": str,
    "method_id": str,
    "tool": ToolName,
    "tool_arguments": type[AnalysisToolArguments],
    "tool_description": str,
    "behavior": BehaviorView,
}
"""The documented descriptor fields and their types; a change here is a reviewed change to the contract."""

BEHAVIOR_MEMBERS: frozenset[str] = frozenset({"result_type", "deps_type", "handler", "native_status"})
"""The documented members of a strategy's behavior bundle."""

EVAL_COMPOSITION_MEMBERS: frozenset[str] = frozenset({"requirement", "compose"})
"""The documented members of a strategy's evaluation-tier composition."""

EVALUATION_ENTRY_FIELDS: frozenset[str] = frozenset({"behavior", "requirement", "compose"})
"""The documented fields of an evaluation-tier entry: the paired core bundle and the erased composition."""

VIEW_ACCESSORS: frozenset[str] = frozenset({"result_type", "native_status_of", "bind_handler"})
"""The behavior members that generic consumers can reach, through the erased view."""

ANALYZER_ENVELOPE_PARAMETERS: tuple[str, ...] = ("self", "ticker", "config", "context")
ANALYZER_CONTEXT_FIELDS: tuple[str, ...] = ("as_of", "executed_at", "use_cache", "instrument_profile")

_FORBIDDEN_IMPORTS = frozenset({"importlib", "pkgutil", "inspect", "entry_points"})
_FORBIDDEN_CALLS = frozenset({"globals", "locals", "get_type_hints"})
_FORBIDDEN_ATTRIBUTES = frozenset({"__subclasses__", "__init_subclass__"})
_FORBIDDEN_NAME = re.compile(r"^(register|unregister|load_|discover)|(Registry|Factory|Plugin)$")


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
    gaps = [
        f"selection class {selections[key].__name__} with ids {key} has no descriptor"
        for key in sorted(selections.keys() - declared.keys())
    ]
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


def undeclared_input_gaps(
    descriptors: tuple[StrategyDescriptor, ...],
    tier: tuple[EvaluationStrategy, ...] = EVALUATION_STRATEGIES,
) -> list[str]:
    """T11: every dispatcher rejects an input that matches no declared strategy, naming it."""
    gaps: list[str] = []
    indexes = build_indexes(descriptors)
    _evaluation_tier_probes(gaps, descriptors, tier)
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
        "tool": dataclasses.replace(second, tool=first.tool),
        "tool_arguments": dataclasses.replace(second, tool_arguments=first.tool_arguments),
        "result_type": dataclasses.replace(second, behavior=first.behavior),
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
    if len(getattr(EvalComposition, "__parameters__", ())) != 1:
        gaps.append("EvalComposition does not take exactly one type parameter, the dependency type")
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
        if not _is_frozen(EvalComposition(requirement=entry.requirement, compose=entry.compose), "requirement"):
            gaps.append("EvalComposition is not frozen")
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
        yield "registers a command on the Typer app"
    if node.attr == "Typer" and owner == "typer":
        yield "constructs a Typer app"


def _call_problems(node: ast.Call) -> Iterator[str]:
    """Yield what is wrong, if anything, with one call."""
    if not isinstance(node.func, ast.Name):
        return
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


def discovery_gaps(files: Iterable[Path], root: Path = _REPO_ROOT) -> list[str]:
    """T14: no discovery, registration side effect, self-registration or registry-like name in ``files``."""
    gaps: list[str] = []
    for path in files:
        where = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            line = getattr(node, "lineno", 0)
            gaps.extend(f"{where}:{line}: {problem}" for problem in _node_problems(node))
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
