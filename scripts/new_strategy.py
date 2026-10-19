"""Generate the typed wiring of a new analysis strategy.

Usage, from the repository root::

    uv run python -m scripts.new_strategy <module_name> --label "<Label>" [--alias <alias>]

The generator writes the typed stubs from ``scripts/strategy_templates/`` into
``investment_analysis_engine/strategies/<module_name>/`` and makes the insertions a strategy needs in the five
existing files that name every strategy: the closed descriptor tuple, the ``ToolName`` enumeration, the two
type-level unions, the CLI tier and the evaluation tier. Each insertion is located by the target file's syntax
tree, and the generator asserts that the file parses before and after and that every tuple, union and enumeration it
extends grew by exactly one entry.

It writes no formula, classification or presentation text, copies nothing from another strategy, and writes no
settings files. The module name gives the analysis identifier, the method identifier and the tool name; every
version field is 1; the generated descriptor has no settings model. Unfilled bodies call ``unfilled_stub``, so a
generated file type-checks as written and fails the test suite until its author has filled it.

The generator refuses to overwrite. It builds every change in memory, including the formatting that Ruff gives the
files it writes or edits (and only those). If a target file exists, or the module name, alias, tool or method
identifier already appears where it would be added, it exits with code 2, lists the conflicts and writes nothing.
Otherwise it writes through temporary files and ``os.replace``, and restores the originals if any step fails.

Exit code 0 on success, 1 when a change could not be built or written, 2 for a usage error or a conflict. This is a
developer script, not an ``ian`` command.
"""

import argparse
import ast
import contextlib
import functools
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Final

if __package__ in {None, ""}:
    # Run as a file, only this folder is on the import path; the documented working directory is the repository root.
    sys.path.insert(0, str(Path.cwd()))

from scripts.repository_root import REPOSITORY_ROOT
from scripts.strategy_sites import (  # noqa: E402 - after the path adjustment
    SiteDataError,
    StrategyNames,
    strategy_names,
)

TEMPLATE_DIRECTORY: Final = Path(__file__).resolve().parent / "strategy_templates"
PACKAGE: Final = "investment_analysis_engine"
STUB_ROLES: Final = (
    "vocabulary",
    "analyzer",
    "tool",
    "selection",
    "codec",
    "execution",
    "cli",
    "presenter",
    "envelope",
    "replay",
    "evaluation",
)
"""The role files written from a template, one per stub site."""

STRATEGY_WIRING: Final = "strategy_wiring.py"
TOOL_NAMES: Final = "orchestrator/tool_names.py"
STRATEGY_TYPES: Final = "workspace/strategy_types.py"
CLI_TIER: Final = "cli_strategy_wiring.py"
EVALUATION_TIER: Final = "evaluation/strategy_fixtures.py"
EDITED_FILES: Final = (STRATEGY_WIRING, TOOL_NAMES, STRATEGY_TYPES, CLI_TIER, EVALUATION_TIER)
"""The five existing files the generator edits, relative to the package folder."""

_LABEL: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9 .&-]*")
_FIRST_PARTY: Final = ("--config", f'lint.isort.known-first-party = ["{PACKAGE}"]')
"""Ruff cannot tell that the package of a file in a folder that does not exist yet is first-party, so it is said."""
_NEXT_STEPS: Final = (
    "Fill every unfilled_stub body, then run: uv run python -m scripts.strategy_status {module} --alias {alias}"
)


class GenerationError(RuntimeError):
    """A change could not be built, or the files it builds do not meet the generator's assertions."""


class ConflictError(GenerationError):
    """The strategy collides with something that exists; ``conflicts`` lists each collision."""

    def __init__(self, conflicts: Sequence[str]) -> None:
        """Retain the conflicts and name the first in the message."""
        super().__init__(f"{len(conflicts)} conflict(s): {conflicts[0]}")
        self.conflicts = tuple(conflicts)


@dataclass(frozen=True)
class Spec:
    """Everything the templates and insertions are written from."""

    names: StrategyNames
    label: str

    @property
    def module(self) -> str:
        """Return the snake_case package name, which is also the analysis and method identifier."""
        return self.names.module

    @property
    def class_name(self) -> str:
        """Return the PascalCase prefix of the strategy's classes."""
        return "".join(part.capitalize() for part in self.module.split("_"))

    @property
    def upper(self) -> str:
        """Return the upper-case prefix of the strategy's constants."""
        return self.module.upper()

    @property
    def tool_member(self) -> str:
        """Return the ``ToolName`` member name."""
        return f"ANALYZE_{self.upper}"

    @property
    def tool_value(self) -> str:
        """Return the tool name the model calls."""
        return f"analyze_{self.module}"

    def substitutions(self) -> dict[str, str]:
        """Return the template placeholders."""
        return {
            "module": self.module,
            "alias": self.names.alias,
            "label": self.label,
            "Class": self.class_name,
            "UPPER": self.upper,
        }


@dataclass(frozen=True)
class Plan:
    """Every change, built in memory: the new files, and the new content of each edited file with its original."""

    package_directory: Path
    new_files: dict[Path, str]
    edited: dict[Path, str]
    originals: dict[Path, bytes]
    entries: dict[Path, tuple[str, ...]]


# ---------------------------------------------------------------------------
# Locating and changing code by its syntax tree
# ---------------------------------------------------------------------------


def _line_starts(data: bytes) -> list[int]:
    starts = [0]
    starts.extend(index + 1 for index, byte in enumerate(data) if byte == 10)
    return starts


def _offset(starts: list[int], lineno: int, column: int) -> int:
    """Return the byte offset of a node position, whose columns count bytes."""
    return starts[lineno - 1] + column


def _splice(source: str, start: int, end: int, text: str) -> str:
    data = source.encode()
    return (data[:start] + text.encode() + data[end:]).decode()


def _parse(source: str, where: str) -> ast.Module:
    try:
        return ast.parse(source, filename=where)
    except SyntaxError as error:
        raise GenerationError(f"{where} does not parse: {error}") from error


def _assignment(tree: ast.Module, target: str, where: str) -> ast.Assign | ast.AnnAssign:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(item, ast.Name) and item.id == target for item in node.targets
        ):
            return node
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == target:
            return node
    raise GenerationError(f"{where} has no module-level assignment to {target}")


def _tuple_of(tree: ast.Module, target: str, where: str) -> ast.Tuple:
    value = _assignment(tree, target, where).value
    if not isinstance(value, ast.Tuple):
        raise GenerationError(f"{where}: {target} is not a tuple")
    return value


def _union_members(node: ast.expr) -> list[ast.expr]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return [*_union_members(node.left), *_union_members(node.right)]
    return [node]


def _enum_members(tree: ast.Module, name: str, where: str) -> list[ast.Assign]:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return [item for item in node.body if isinstance(item, ast.Assign)]
    raise GenerationError(f"{where} defines no class {name}")


def tuple_length(source: str, target: str, where: str) -> int:
    """Return the number of entries of the module-level tuple ``target``."""
    return len(_tuple_of(_parse(source, where), target, where).elts)


def union_length(source: str, target: str, where: str) -> int:
    """Return the number of members of the module-level union ``target``."""
    value = _assignment(_parse(source, where), target, where).value
    if value is None:
        raise GenerationError(f"{where}: {target} has no value")
    return len(_union_members(value))


def enum_length(source: str, name: str, where: str) -> int:
    """Return the number of members of the enumeration ``name``."""
    return len(_enum_members(_parse(source, where), name, where))


def append_imports(source: str, statements: Sequence[str], where: str) -> str:
    """Insert ``statements`` after the last top-level import."""
    tree = _parse(source, where)
    imports = [node for node in tree.body if isinstance(node, ast.Import | ast.ImportFrom)]
    if not imports:
        raise GenerationError(f"{where} has no import to insert after")
    data = source.encode()
    starts = _line_starts(data)
    after = max(node.end_lineno or node.lineno for node in imports)
    position = starts[after] if after < len(starts) else len(data)
    prefix = "" if position == 0 or data[position - 1 : position] == b"\n" else "\n"
    return _splice(source, position, position, prefix + "\n".join(statements) + "\n")


def add_import_name(source: str, module: str, name: str, where: str) -> str:
    """Add ``name`` to the existing ``from <module> import ...`` statement."""
    tree = _parse(source, where)
    node = next(
        (item for item in tree.body if isinstance(item, ast.ImportFrom) and item.module == module and item.level == 0),
        None,
    )
    if node is None:
        raise GenerationError(f"{where} has no 'from {module} import' statement")
    existing = [alias.name + (f" as {alias.asname}" if alias.asname else "") for alias in node.names]
    body = "".join(f"    {item},\n" for item in [*existing, name])
    starts = _line_starts(source.encode())
    start = _offset(starts, node.lineno, node.col_offset)
    end = _offset(starts, node.end_lineno or node.lineno, node.end_col_offset or 0)
    return _splice(source, start, end, f"from {module} import (\n{body})")


def append_tuple_entry(source: str, target: str, entry: str, where: str) -> str:
    """Append ``entry`` as the last element of the module-level tuple ``target``."""
    elements = _tuple_of(_parse(source, where), target, where).elts
    data = source.encode()
    starts = _line_starts(data)
    last = elements[-1]
    end = _offset(starts, last.end_lineno or last.lineno, last.end_col_offset or 0)
    cursor = end
    while cursor < len(data) and data[cursor : cursor + 1] in {b" ", b"\t", b"\r", b"\n"}:
        cursor += 1
    if data[cursor : cursor + 1] == b",":
        return _splice(source, cursor + 1, cursor + 1, f"\n    {entry},")
    return _splice(source, end, end, f", {entry}")


def append_union_member(source: str, target: str, member: str, where: str) -> str:
    """Append ``member`` to the module-level union ``target``."""
    value = _assignment(_parse(source, where), target, where).value
    if value is None:
        raise GenerationError(f"{where}: {target} has no value")
    starts = _line_starts(source.encode())
    end = _offset(starts, value.end_lineno or value.lineno, value.end_col_offset or 0)
    return _splice(source, end, end, f" | {member}")


def insert_before(source: str, target: str, text: str, where: str) -> str:
    """Insert ``text`` as whole lines immediately before the module-level assignment to ``target``."""
    node = _assignment(_parse(source, where), target, where)
    start = _offset(_line_starts(source.encode()), node.lineno, 0)
    return _splice(source, start, start, text.rstrip("\n") + "\n\n")


def append_enum_member(source: str, name: str, line: str, where: str) -> str:
    """Append ``line`` as the last member of the enumeration ``name``."""
    members = _enum_members(_parse(source, where), name, where)
    last = members[-1]
    starts = _line_starts(source.encode())
    position = starts[last.end_lineno or last.lineno]
    return _splice(source, position, position, " " * last.col_offset + line + "\n")


def bound_names(source: str, where: str) -> set[str]:
    """Return the names a module binds at its top level."""
    names: set[str] = set()
    for node in _parse(source, where).body:
        if isinstance(node, ast.Import | ast.ImportFrom):
            names.update((alias.asname or alias.name).split(".")[0] for alias in node.names)
        elif isinstance(node, ast.Assign):
            names.update(item.id for item in node.targets if isinstance(item, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
    return names


# ---------------------------------------------------------------------------
# What each existing file receives
# ---------------------------------------------------------------------------


def _strategy_import(spec: Spec, role: str, names: Sequence[str]) -> str:
    return f"from {PACKAGE}.strategies.{spec.module}.{role} import {', '.join(names)}"


def _wiring_edit(spec: Spec, source: str, where: str) -> tuple[str, tuple[str, ...]]:
    """Edit the composition root: imports, the behavior and descriptor constants and the ``STRATEGIES`` entry."""
    module, cls, upper = spec.module, spec.class_name, spec.upper
    imports = [
        _strategy_import(spec, "analyzer", [f"{cls}Result"]),
        _strategy_import(
            spec, "codec", [f"decode_{module}", f"encode_{module}", f"{module}_native_status", f"{module}_ticker"]
        ),
        _strategy_import(spec, "envelope", [f"{cls}Document"]),
        _strategy_import(spec, "replay", [f"project_{module}"]),
        _strategy_import(spec, "selection", [f"{cls}Selection"]),
        _strategy_import(spec, "tool", [f"{cls}ToolArguments", f"{cls}ToolDependencies", f"{cls}ToolHandler"]),
        _strategy_import(spec, "vocabulary", [f"ANALYSIS_ID as {upper}_ANALYSIS_ID"]),
        _strategy_import(spec, "vocabulary", [f"CONFIG_SCHEMA_VERSION as {upper}_CONFIG_SCHEMA_VERSION"]),
        _strategy_import(spec, "vocabulary", [f"METHOD_ID as {upper}_METHOD_ID"]),
    ]
    behavior = (
        f"{upper}_BEHAVIOR: Final = StrategyBehavior[{cls}Selection, {cls}Result, {cls}ToolDependencies](\n"
        f"    selection_type={cls}Selection,\n"
        f"    result_type={cls}Result,\n"
        f"    deps_type={cls}ToolDependencies,\n"
        f"    encode=encode_{module},\n"
        f"    decode=decode_{module},\n"
        f"    ticker_of={module}_ticker,\n"
        f"    handler={cls}ToolHandler,\n"
        f"    native_status={module}_native_status,\n"
        f"    project=project_{module},\n"
        ")\n"
    )
    descriptor = (
        f"{upper}: Final = StrategyDescriptor(\n"
        f"    analysis_id={upper}_ANALYSIS_ID,\n"
        f"    method_id={upper}_METHOD_ID,\n"
        f'    alias="{spec.names.alias}",\n'
        f'    label="{spec.label}",\n'
        f"    tool=ToolName.{spec.tool_member},\n"
        f"    tool_arguments={cls}ToolArguments,\n"
        f'    tool_description="Run the {spec.label} analysis.",\n'
        f"    behavior={upper}_BEHAVIOR,\n"
        f"    config_schema_version={upper}_CONFIG_SCHEMA_VERSION,\n"
        "    method_version=1,\n"
        "    result_schema_version=1,\n"
        "    evidence_codec_version=1,\n"
        f"    json_envelope={cls}Document,\n"
        "    settings_type=None,\n"
        ")"
    )
    introduced = (
        f"{upper}_BEHAVIOR",
        upper,
        f"{upper}_ANALYSIS_ID",
        f"{upper}_METHOD_ID",
        f"{upper}_CONFIG_SCHEMA_VERSION",
    )
    edited = append_imports(source, imports, where)
    edited = insert_before(edited, "STRATEGIES", behavior + descriptor, where)
    return append_tuple_entry(edited, "STRATEGIES", upper, where), introduced


def _tool_name_edit(spec: Spec, source: str, where: str) -> tuple[str, tuple[str, ...]]:
    edited = append_enum_member(source, "ToolName", f'{spec.tool_member} = "{spec.tool_value}"', where)
    return edited, ()


def _types_edit(spec: Spec, source: str, where: str) -> tuple[str, tuple[str, ...]]:
    cls = spec.class_name
    imports = [
        _strategy_import(spec, "analyzer", [f"{cls}Result"]),
        _strategy_import(spec, "selection", [f"{cls}Selection"]),
    ]
    edited = append_imports(source, imports, where)
    edited = append_union_member(edited, "NativeEvidence", f"{cls}Result", where)
    return append_union_member(edited, "SelectionMember", f"{cls}Selection", where), (f"{cls}Result", f"{cls}Selection")


def _cli_tier_edit(spec: Spec, source: str, where: str) -> tuple[str, tuple[str, ...]]:
    module, upper = spec.module, spec.upper
    imports = [
        _strategy_import(spec, "cli", [f"build_selection as build_{module}_selection"]),
        _strategy_import(spec, "cli", [f"command as {module}_command"]),
        _strategy_import(spec, "cli", [f"refresh as refresh_{module}"]),
    ]
    entry = (
        f"pair_cli(\n    {upper}_BEHAVIOR,\n"
        f"    CliComposition(build=build_{module}_selection, refresh=refresh_{module}, command={module}_command),\n)"
    )
    edited = append_imports(source, imports, where)
    edited = add_import_name(edited, f"{PACKAGE}.strategy_wiring", f"{upper}_BEHAVIOR", where)
    introduced = (f"build_{module}_selection", f"{module}_command", f"refresh_{module}")
    return append_tuple_entry(edited, "CLI_STRATEGIES", entry, where), introduced


def _evaluation_tier_edit(spec: Spec, source: str, where: str) -> tuple[str, tuple[str, ...]]:
    module, upper = spec.module, spec.upper
    imports = [
        _strategy_import(spec, "evaluation", [f"FIXTURE_IDS as {upper}_FIXTURE_IDS"]),
        _strategy_import(spec, "evaluation", [f"REQUIREMENT as {upper}_REQUIREMENT"]),
        _strategy_import(spec, "evaluation", [f"SAMPLE_SELECTION as {upper}_SAMPLE_SELECTION"]),
        _strategy_import(spec, "evaluation", [f"compose as compose_{module}"]),
    ]
    entry = (
        f"pair_evaluation(\n    {upper}_BEHAVIOR,\n    EvalComposition(\n"
        f"        requirement={upper}_REQUIREMENT,\n"
        f"        fixture_ids={upper}_FIXTURE_IDS,\n"
        f"        compose=compose_{module},\n"
        f"        sample_selection={upper}_SAMPLE_SELECTION,\n    ),\n)"
    )
    edited = append_imports(source, imports, where)
    edited = add_import_name(edited, f"{PACKAGE}.strategy_wiring", f"{upper}_BEHAVIOR", where)
    introduced = (f"{upper}_FIXTURE_IDS", f"{upper}_REQUIREMENT", f"{upper}_SAMPLE_SELECTION", f"compose_{module}")
    return append_tuple_entry(edited, "EVALUATION_STRATEGIES", entry, where), introduced


@dataclass(frozen=True)
class EditedFile:
    """One existing file: where it is, how it is edited and which counted entries must each grow by one."""

    relative: str
    edit: Callable[[Spec, str, str], tuple[str, tuple[str, ...]]]
    tuples: tuple[str, ...] = ()
    unions: tuple[str, ...] = ()
    enums: tuple[str, ...] = ()


EDITS: Final = (
    EditedFile(STRATEGY_WIRING, _wiring_edit, tuples=("STRATEGIES",)),
    EditedFile(TOOL_NAMES, _tool_name_edit, enums=("ToolName",)),
    EditedFile(STRATEGY_TYPES, _types_edit, unions=("NativeEvidence", "SelectionMember")),
    EditedFile(CLI_TIER, _cli_tier_edit, tuples=("CLI_STRATEGIES",)),
    EditedFile(EVALUATION_TIER, _evaluation_tier_edit, tuples=("EVALUATION_STRATEGIES",)),
)


def _counts(entry: EditedFile, source: str, where: str) -> list[int]:
    return [
        *(tuple_length(source, name, where) for name in entry.tuples),
        *(union_length(source, name, where) for name in entry.unions),
        *(enum_length(source, name, where) for name in entry.enums),
    ]


def _assert_grew_by_one(entry: EditedFile, before: str, after: str, where: str) -> None:
    """Assert that ``after`` parses and every tuple, union and enumeration of ``entry`` grew by exactly one."""
    _parse(after, where)
    old, new = _counts(entry, before, where), _counts(entry, after, where)
    if [b + 1 for b in old] != new:
        raise GenerationError(f"{where}: entry counts went from {old} to {new}, not up by one each")


# ---------------------------------------------------------------------------
# Conflicts
# ---------------------------------------------------------------------------


def _string_assignments(source: str, wanted: set[str], where: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for node in _parse(source, where).body:
        target = (
            node.target
            if isinstance(node, ast.AnnAssign)
            else node.targets[0]
            if isinstance(node, ast.Assign) and len(node.targets) == 1
            else None
        )
        value = node.value if isinstance(node, ast.AnnAssign | ast.Assign) else None
        if isinstance(target, ast.Name) and target.id in wanted and isinstance(value, ast.Constant):
            found[target.id] = str(value.value)
    return found


def _descriptor_aliases(source: str, where: str) -> set[str]:
    return {
        str(keyword.value.value)
        for node in ast.walk(_parse(source, where))
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "alias" and isinstance(keyword.value, ast.Constant)
    }


def _identity_conflicts(spec: Spec, root: Path) -> Iterator[str]:
    """Yield each existing strategy that already uses the analysis id, the method id, the alias or the tool."""
    package = root / PACKAGE
    for vocabulary in sorted((package / "strategies").glob("*/vocabulary.py")):
        where = vocabulary.relative_to(root).as_posix()
        ids = _string_assignments(vocabulary.read_text(encoding="utf-8"), {"ANALYSIS_ID", "METHOD_ID"}, where)
        for key, label in (("ANALYSIS_ID", "analysis id"), ("METHOD_ID", "method id")):
            if ids.get(key) == spec.module:
                yield f"{where}: the {label} {spec.module!r} is already used"
    wiring = package / STRATEGY_WIRING
    if spec.names.alias in _descriptor_aliases(wiring.read_text(encoding="utf-8"), STRATEGY_WIRING):
        yield f"{wiring.relative_to(root).as_posix()}: the alias {spec.names.alias!r} is already declared"
    tool_names = package / TOOL_NAMES
    tool_source = tool_names.read_text(encoding="utf-8")
    for member in _enum_members(_parse(tool_source, TOOL_NAMES), "ToolName", TOOL_NAMES):
        value = member.value
        named = isinstance(member.targets[0], ast.Name) and member.targets[0].id == spec.tool_member
        valued = isinstance(value, ast.Constant) and value.value == spec.tool_value
        if named or valued:
            yield f"{tool_names.relative_to(root).as_posix()}: the tool {spec.tool_value!r} is already declared"


# ---------------------------------------------------------------------------
# Ruff
# ---------------------------------------------------------------------------


def _ruff(root: Path, arguments: Sequence[str], path: Path, source: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - the interpreter running this script, with fixed Ruff arguments
        [sys.executable, "-m", "ruff", *arguments, "--stdin-filename", str(path), "-"],
        input=source,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        cwd=root,
    )


def ruff_clean(root: Path, path: Path, source: str) -> str:
    """Return ``source`` as Ruff fixes and formats it for ``path``, read from standard input so nothing else is touched.

    Ruff takes its settings from the repository root it is run in.

    Raises:
        GenerationError: If Ruff cannot run, or still reports a violation after fixing and formatting.
    """
    fixed = _ruff(root, ["check", "--fix", "--exit-zero", "--quiet", *_FIRST_PARTY], path, source)
    if fixed.returncode != 0:
        raise GenerationError(f"ruff check --fix failed for {path.name}: {fixed.stderr.strip()}")
    formatted = _ruff(root, ["format", "--quiet"], path, fixed.stdout)
    if formatted.returncode != 0:
        raise GenerationError(f"ruff format failed for {path.name}: {formatted.stderr.strip()}")
    verified = _ruff(root, ["check", "--quiet", "--output-format", "concise", *_FIRST_PARTY], path, formatted.stdout)
    if verified.returncode != 0:
        report = (verified.stdout + verified.stderr).strip()
        raise GenerationError(f"ruff reports violations in the generated {path.name}:\n{report}")
    return formatted.stdout


# ---------------------------------------------------------------------------
# Plan and apply
# ---------------------------------------------------------------------------


def build_plan(
    root: Path, names: StrategyNames, label: str, *, clean: Callable[[Path, str], str] | None = None
) -> Plan:
    """Build every change in memory and return it; nothing is written.

    Args:
        root: The repository root.
        names: The strategy's package name, alias and guide name.
        label: The strategy's display label.
        clean: Fixes and formats the source of one file; Ruff, run in ``root``, by default.

    Raises:
        ConflictError: If a target file exists or an identifier already appears where it would be added.
        GenerationError: If a template or insertion cannot be applied or fails its assertions.
    """
    spec = Spec(names, label)
    if clean is None:
        clean = functools.partial(ruff_clean, root)
    package = root / PACKAGE
    directory = package / "strategies" / spec.module
    targets = {directory / "__init__.py": "", **{directory / f"{role}.py": "" for role in STUB_ROLES}}
    conflicts = [f"{path.relative_to(root).as_posix()} already exists" for path in targets if path.exists()]
    if directory.exists() and not any(path.exists() for path in targets):
        conflicts.append(f"{directory.relative_to(root).as_posix()} already exists")
    conflicts.extend(_identity_conflicts(spec, root))
    sources = {entry.relative: (package / entry.relative).read_bytes() for entry in EDITS}
    for entry in EDITS:
        where = entry.relative
        _, introduced = entry.edit(spec, sources[where].decode(), where)
        taken = bound_names(sources[where].decode(), where)
        conflicts.extend(f"{PACKAGE}/{where}: {name} is already defined" for name in introduced if name in taken)
    if conflicts:
        raise ConflictError(sorted(dict.fromkeys(conflicts)))
    new_files: dict[Path, str] = {directory / "__init__.py": ""}
    for role in STUB_ROLES:
        template = Template((TEMPLATE_DIRECTORY / f"{role}.py.tmpl").read_text(encoding="utf-8"))
        path = directory / f"{role}.py"
        new_files[path] = clean(path, template.substitute(spec.substitutions()))
    edited: dict[Path, str] = {}
    entries: dict[Path, tuple[str, ...]] = {}
    for entry in EDITS:
        path = package / entry.relative
        before = sources[entry.relative].decode()
        after, _ = entry.edit(spec, before, entry.relative)
        _assert_grew_by_one(entry, before, after, entry.relative)
        final = clean(path, after)
        _assert_grew_by_one(entry, before, final, entry.relative)
        edited[path] = final
        entries[path] = (*entry.tuples, *entry.unions, *entry.enums)
    return Plan(directory, new_files, edited, {package / e.relative: sources[e.relative] for e in EDITS}, entries)


def _write_temporary(path: Path, data: bytes) -> Path:
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
    return Path(name)


def apply_plan(plan: Plan, replace: Callable[[Path, Path], None] = os.replace) -> None:
    """Write ``plan`` through temporary files and ``replace``, restoring the originals if any step fails.

    Args:
        plan: The changes from :func:`build_plan`.
        replace: Moves a temporary file onto its target; ``os.replace`` unless a test supplies another.
    """
    created_directory = not plan.package_directory.exists()
    written: list[Path] = []
    replaced: list[Path] = []
    temporaries: list[Path] = []
    try:
        plan.package_directory.mkdir(parents=True, exist_ok=True)
        for path, text in plan.new_files.items():
            temporaries.append(_write_temporary(path, text.encode()))
            replace(temporaries[-1], path)
            written.append(path)
        for path, text in plan.edited.items():
            temporaries.append(_write_temporary(path, text.encode()))
            replace(temporaries[-1], path)
            replaced.append(path)
    except BaseException:
        for path in replaced:
            restore = _write_temporary(path, plan.originals[path])
            os.replace(restore, path)
        for path in written:
            path.unlink(missing_ok=True)
        for temporary in temporaries:
            temporary.unlink(missing_ok=True)
        if created_directory:
            for leftover in plan.package_directory.glob("*"):
                leftover.unlink(missing_ok=True)
            with contextlib.suppress(OSError):
                plan.package_directory.rmdir()
        raise


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


def main(
    argv: Sequence[str] | None = None,
    root: Path = REPOSITORY_ROOT,
    clean: Callable[[Path, str], str] | None = None,
) -> int:
    """Generate a strategy's wiring under ``root`` and return the exit code.

    ``clean`` fixes and formats one file's source; Ruff, run in ``root``, when ``None``.
    """
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0] if __doc__ else None)
    parser.add_argument("module_name", help="The strategy's package name under investment_analysis_engine/strategies.")
    parser.add_argument("--label", required=True, help="The strategy's display label, for example 'Piotroski F-Score'.")
    parser.add_argument("--alias", help="The strategy's command alias; defaults to the module name with hyphens.")
    arguments = parser.parse_args(argv)
    if not _LABEL.fullmatch(arguments.label):
        parser.error("the label must be letters, digits, spaces, periods, ampersands or hyphens, starting with one.")
    try:
        names = strategy_names(arguments.module_name, arguments.alias)
    except SiteDataError as error:
        parser.error(str(error))
    try:
        plan = build_plan(root, names, arguments.label, clean=clean)
    except ConflictError as error:
        sys.stderr.write("Nothing was written; the strategy conflicts with what exists:\n")
        sys.stderr.write("".join(f"  conflict: {conflict}\n" for conflict in error.conflicts))
        return 2
    except GenerationError as error:
        sys.stderr.write(f"Nothing was written: {error}\n")
        return 1
    try:
        apply_plan(plan)
    except OSError as error:
        sys.stderr.write(f"Writing failed and the originals were restored: {error}\n")
        return 1
    for path in plan.new_files:
        sys.stdout.write(f"created  {path.relative_to(root).as_posix()}\n")
    for path in plan.edited:
        sys.stdout.write(
            f"edited   {path.relative_to(root).as_posix()} (+1 entry in {', '.join(plan.entries[path])})\n"
        )
    sys.stdout.write(_NEXT_STEPS.format(module=names.module, alias=names.alias) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
