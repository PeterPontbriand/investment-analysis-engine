"""Simulate a set of file and name moves and report the package graph before and after.

Reads a committed move list (TOML) naming files and single names that change unit. For the code
as it is ("today") and for the code with every listed move applied ("target") it reports the units, the
dependencies between them, the two-way pairs, every loop with its members and, when there is no loop,
the layered order. It also reports loops between modules at import time and the function-level imports
that close one. Standard library only; it never modifies a file.

A *unit* is as ``scripts/package_graph.py`` defines it, role rule included. A move changes the unit of one file
(``[[file]]``) or of one top-level name of a file (``[[name]]``). The simulation models the code after
each move slice: an import of a moved file or name is retargeted to its new home, an index file
(``__init__.py``) that only re-exports a moved file or name loses that re-export, and the file a name
leaves keeps a dependency on the name if it still uses it. The re-exports that must be removed are listed
as index edits.

Imports are resolved through index files (a name imported from a package is followed to the module that
defines it), relative imports, imports inside functions and ``TYPE_CHECKING`` blocks, and single-name
moves. Importing a module also depends on the ``__init__.py`` files of its packages, as the import system
executes them.

Usage, from the repository root::

    py -3 -m scripts.simulate_package_layers [--moves PATH] [--root PATH] [--relabel A=B] [--override KEY=UNIT]
        [--only today|target] [--importers] [--table] [--cycle-through UNIT]
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
import tomllib
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from scripts.package_graph import ROLE_RULES, Graph, layers, shortest_cycle, strongly_connected, two_way, unit_of_path

SOURCE_ROOT = "src"
TESTS_ROOT = "tests"
DEFAULT_MOVES = Path("docs/project/milestones/v0.2/layering/LAY_MOVE_LIST.toml")
VIRTUAL_SEPARATOR = "::"
IMPORTER_COLUMNS = (
    "move",
    "source files staying",
    "source files moving",
    "test files",
    "other files",
    "test files naming it in a string",
)


@dataclass(frozen=True)
class Move:
    """One file or one top-level name that changes unit."""

    path: str
    name: str | None
    unit: str
    serves: str
    destination: str

    @property
    def key(self) -> str:
        """Return ``path`` or ``path::name``: the handle ``--override`` matches against."""
        return self.path if self.name is None else f"{self.path}{VIRTUAL_SEPARATOR}{self.name}"


@dataclass(frozen=True)
class MoveList:
    """The committed moves and the owner text of each target unit."""

    moves: tuple[Move, ...]
    owns: Mapping[str, str]


@dataclass
class Module:
    """One parsed Python file."""

    name: str
    path: str
    is_init: bool
    tree: ast.Module
    definitions: set[str] = field(default_factory=set)
    bindings: dict[str, tuple[str, str | None]] = field(default_factory=dict)

    @property
    def package(self) -> str:
        """Return the dotted package a relative import in this file is resolved against."""
        return self.name if self.is_init else self.name.rpartition(".")[0]


@dataclass(frozen=True)
class ImportStatement:
    """One import statement with the scope it executes in."""

    node: ast.Import | ast.ImportFrom
    in_function: bool
    type_checking: bool


@dataclass(frozen=True)
class ResolvedImport:
    """One imported name, resolved to the module that executes and the one that defines it."""

    base: str
    origin: str
    symbol: str | None
    lineno: int
    in_function: bool
    type_checking: bool
    local: str | None


@dataclass(frozen=True)
class Edge:
    """A dependency of one node on another, with the statement that causes it."""

    source: str
    target: str
    path: str
    lineno: int
    import_time: bool


@dataclass
class Simulation:
    """The graph of the code with a set of moves applied (none for "today")."""

    unit_of: dict[str, str]
    edges: list[Edge]
    implicit: list[tuple[str, str]]
    findings: list[str]
    index_edits: list[str]
    paths: dict[str, str]
    names: dict[str, str]


def _is_type_checking(test: ast.expr) -> bool:
    """Return whether an ``if`` test is ``TYPE_CHECKING`` or ``typing.TYPE_CHECKING``."""
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def collect_statements(
    node: ast.AST, in_function: bool = False, type_checking: bool = False
) -> Iterator[ImportStatement]:
    """Yield every import statement below ``node`` with its scope."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.Import, ast.ImportFrom)):
            yield ImportStatement(child, in_function, type_checking)
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            yield from collect_statements(child, True, type_checking)
        elif isinstance(child, ast.If) and _is_type_checking(child.test):
            for statement in child.body:
                yield from collect_statements(ast.Module(body=[statement], type_ignores=[]), in_function, True)
            for statement in child.orelse:
                yield from collect_statements(ast.Module(body=[statement], type_ignores=[]), in_function, type_checking)
        else:
            yield from collect_statements(child, in_function, type_checking)


def _target_names(statement: ast.stmt) -> list[str]:
    """Return the names a top-level non-import statement defines."""
    if isinstance(statement, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        return [statement.name]
    if isinstance(statement, ast.Assign):
        return [target.id for target in statement.targets if isinstance(target, ast.Name)]
    if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
        return [statement.target.id]
    return []


def _flatten_top_level(body: Sequence[ast.stmt]) -> Iterator[ast.stmt]:
    """Yield the statements of a module body, entering ``if``, ``try`` and ``with`` blocks."""
    for statement in body:
        if isinstance(statement, ast.If):
            yield from _flatten_top_level(statement.body)
            yield from _flatten_top_level(statement.orelse)
        elif isinstance(statement, ast.Try):
            yield from _flatten_top_level(statement.body)
            for handler in statement.handlers:
                yield from _flatten_top_level(handler.body)
            yield from _flatten_top_level(statement.orelse)
            yield from _flatten_top_level(statement.finalbody)
        elif isinstance(statement, ast.With):
            yield from _flatten_top_level(statement.body)
        else:
            yield statement


def module_name_of(relative: Path) -> str:
    """Return the dotted module name of a path relative to the repository root."""
    parts = relative.with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _absolute_base(module: Module, node: ast.ImportFrom) -> str:
    """Return the dotted module a ``from`` import names, resolving relative levels."""
    if not node.level:
        return node.module or ""
    package = module.package.split(".")
    if node.level > 1:
        package = package[: len(package) - (node.level - 1)]
    return ".".join((*package, *(node.module.split(".") if node.module else ())))


def parse_module(root: Path, path: Path) -> Module:
    """Parse one file and index its top-level definitions and import bindings."""
    relative = path.relative_to(root)
    module = Module(
        name=module_name_of(relative),
        path=relative.as_posix(),
        is_init=path.name == "__init__.py",
        tree=ast.parse(path.read_text(encoding="utf-8"), filename=str(path)),
    )
    for statement in _flatten_top_level(module.tree.body):
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                if alias.asname:
                    module.bindings[alias.asname] = (alias.name, None)
        elif isinstance(statement, ast.ImportFrom):
            base = _absolute_base(module, statement)
            for alias in statement.names:
                if alias.name != "*":
                    module.bindings[alias.asname or alias.name] = (base, alias.name)
        else:
            module.definitions.update(_target_names(statement))
    return module


def load_modules(root: Path, top: str) -> dict[str, Module]:
    """Parse every Python file below ``root / top`` into modules keyed by dotted name."""
    modules: dict[str, Module] = {}
    for path in sorted((root / top).rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        module = parse_module(root, path)
        modules[module.name] = module
    return modules


class Resolver:
    """Resolve imports to the modules and names that define them."""

    def __init__(self, modules: Mapping[str, Module]) -> None:
        """Index the modules the imports are resolved against."""
        self.modules = modules

    def origin(
        self, module: str, attribute: str, _seen: frozenset[tuple[str, str]] = frozenset()
    ) -> tuple[str, str | None]:
        """Follow ``attribute`` of ``module`` through index files to the module and name that define it."""
        if (module, attribute) in _seen or module not in self.modules:
            return module, attribute
        info = self.modules[module]
        if attribute in info.definitions:
            return module, attribute
        if attribute in info.bindings:
            target, name = info.bindings[attribute]
            if name is None:
                return target, None
            return self.origin(target, name, _seen | {(module, attribute)})
        child = f"{module}.{attribute}"
        if child in self.modules:
            return child, None
        return module, attribute

    def resolve(self, module: Module, statement: ImportStatement) -> Iterator[ResolvedImport]:
        """Yield one resolved import per name of a statement, for imports of modules below the source root."""
        node = statement.node
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in {SOURCE_ROOT, TESTS_ROOT} and alias.name in self.modules:
                    yield ResolvedImport(
                        alias.name,
                        alias.name,
                        None,
                        node.lineno,
                        statement.in_function,
                        statement.type_checking,
                        alias.asname,
                    )
            return
        base = _absolute_base(module, node)
        if base.split(".")[0] not in {SOURCE_ROOT, TESTS_ROOT} or base not in self.modules:
            return
        for alias in node.names:
            if alias.name == "*":
                yield ResolvedImport(base, base, "*", node.lineno, statement.in_function, statement.type_checking, None)
                continue
            origin, symbol = self.origin(base, alias.name)
            yield ResolvedImport(
                base,
                origin,
                symbol,
                node.lineno,
                statement.in_function,
                statement.type_checking,
                alias.asname or alias.name,
            )


def _free_names(statement: ast.AST) -> set[str]:
    """Return every identifier a statement mentions."""
    return {node.id for node in ast.walk(statement) if isinstance(node, ast.Name)}


def _import_time_names(statement: ast.AST) -> set[str]:
    """Return the identifiers a statement mentions outside function bodies."""
    names: set[str] = set()
    pending: list[ast.AST] = [statement]
    while pending:
        node = pending.pop()
        if isinstance(node, ast.Name):
            names.add(node.id)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            pending.extend(node.decorator_list)
            pending.append(node.args)
            continue
        if isinstance(node, ast.Lambda):
            continue
        pending.extend(ast.iter_child_nodes(node))
    return names


def _owner_of_line(moved: Mapping[str, ast.stmt], lineno: int) -> str | None:
    """Return the moved name whose definition spans ``lineno``, or ``None``."""
    for name, statement in moved.items():
        if statement.lineno <= lineno <= (statement.end_lineno or statement.lineno):
            return name
    return None


def unit_for_path(path: str) -> str | None:
    """Return the unit of a repository-relative path by the unit definition, which includes the role rule."""
    pure = Path(path)
    if pure.parts[0] != SOURCE_ROOT:
        return None
    return unit_of_path(Path(*pure.parts[1:]))


@dataclass(frozen=True)
class _Split:
    """A module that loses names: who uses each of its imports, the file itself or a name that leaves."""

    moved_statements: Mapping[str, ast.stmt]
    residue_names: set[str]
    moved_names: Mapping[str, set[str]]
    top_imports: set[int]

    def owners(self, statement: ImportStatement, item: ResolvedImport) -> list[str | None]:
        """Return who uses an imported name: ``None`` for the file itself, or the moved names that use it."""
        if not self.moved_statements:
            return [None]
        inside = _owner_of_line(self.moved_statements, item.lineno)
        if inside is not None:
            return [inside]
        if id(statement.node) not in self.top_imports or item.local is None:
            return [None]
        local = item.local.split(".")[0]
        owners: list[str | None] = []
        if local in self.residue_names:
            owners.append(None)
        owners.extend(name for name, names in self.moved_names.items() if local in names)
        return owners or [None]


class _Builder:
    """Collect the nodes and edges of the code with a set of moves applied."""

    def __init__(self, modules: Mapping[str, Module], move_list: MoveList | None) -> None:
        """Assign every file and moved name to its unit."""
        self.modules = modules
        self.resolver = Resolver(modules)
        moves = move_list.moves if move_list is not None else ()
        self.file_moves = {move.path: move for move in moves if move.name is None}
        self.module_paths = {module.name: module.path for module in modules.values()}
        by_path = {module.path: module for module in modules.values()}
        self.name_moves: dict[tuple[str, str], Move] = {}
        self.findings: list[str] = []
        self.index_edits: list[str] = []
        self.edges: list[Edge] = []
        self.unit_of: dict[str, str] = {}
        self.paths: dict[str, str] = {}
        self.post_paths: dict[str, str] = {}
        self.names: dict[str, str] = {}
        for move in moves:
            if move.path not in by_path:
                self.findings.append(f"move source does not exist: {move.key}")
            elif move.name is not None:
                self.name_moves[(by_path[move.path].name, move.name)] = move
        for module in modules.values():
            file_move = self.file_moves.get(module.path)
            unit = file_move.unit if file_move is not None else unit_for_path(module.path)
            if unit is not None:
                self.unit_of[module.name] = unit
                self.paths[module.name] = module.path
                destination = file_move.destination if file_move is not None and file_move.destination else module.path
                self.post_paths[module.name] = destination
                self.names[module.name] = module_name_of(Path(destination))
        for (module_name, name), move in self.name_moves.items():
            node = f"{module_name}{VIRTUAL_SEPARATOR}{name}"
            self.unit_of[node] = move.unit
            self.paths[node] = modules[module_name].path
            self.post_paths[node] = move.destination or modules[module_name].path
            self.names[node] = f"{module_name_of(Path(self.post_paths[node]))}{VIRTUAL_SEPARATOR}{name}"

    def run(self) -> Simulation:
        """Return the simulation."""
        for module in self.modules.values():
            if module.name in self.unit_of:
                self._module_edges(module)
        return Simulation(
            self.unit_of,
            self.edges,
            self._implicit_edges(),
            sorted(set(self.findings)),
            sorted(set(self.index_edits)),
            self.paths,
            self.names,
        )

    def _implicit_edges(self) -> list[tuple[str, str]]:
        """Return a dependency of each node on the ``__init__`` files of the packages of its final path."""
        init_at = {path: node for node, path in self.post_paths.items() if path.endswith("/__init__.py")}
        result: list[tuple[str, str]] = []
        for node, path in self.post_paths.items():
            parent = Path(path).parent
            while parent.parts and parent.parts[0] in {SOURCE_ROOT, TESTS_ROOT}:
                init = init_at.get((parent / "__init__.py").as_posix())
                if init is not None and init != node:
                    result.append((node, init))
                parent = parent.parent
        return result

    def _module_edges(self, module: Module) -> None:
        """Add the edges of one module, splitting it into its residue and the names that leave it."""
        own_moved = {name: move for (owner, name), move in self.name_moves.items() if owner == module.name}
        moved_statements: dict[str, ast.stmt] = {}
        residue: list[ast.stmt] = []
        for statement in module.tree.body:
            defined = [name for name in _target_names(statement) if name in own_moved]
            if defined:
                moved_statements[defined[0]] = statement
            elif not isinstance(statement, (ast.Import, ast.ImportFrom)):
                residue.append(statement)
        residue_names: set[str] = set().union(*(_free_names(statement) for statement in residue)) if residue else set()
        moved_names = {name: _free_names(statement) for name, statement in moved_statements.items()}
        top_imports = {
            id(statement) for statement in module.tree.body if isinstance(statement, (ast.Import, ast.ImportFrom))
        }
        split = _Split(moved_statements, residue_names, moved_names, top_imports)
        for import_statement in collect_statements(module.tree):
            for item in self.resolver.resolve(module, import_statement):
                for owner in split.owners(import_statement, item):
                    source = module.name if owner is None else f"{module.name}{VIRTUAL_SEPARATOR}{owner}"
                    self._import_edges(source, module, item)
        for name, statement in moved_statements.items():
            node = f"{module.name}{VIRTUAL_SEPARATOR}{name}"
            for other in own_moved:
                if other != name and other in moved_names[name]:
                    other_node = f"{module.name}{VIRTUAL_SEPARATOR}{other}"
                    self.edges.append(Edge(node, other_node, module.path, statement.lineno, True))
            for used in sorted((moved_names[name] & (module.definitions - set(own_moved))) - {name}):
                self.findings.append(f"{module.path}: moved name {name} uses {used}, which stays in the file")
                self.edges.append(Edge(node, module.name, module.path, statement.lineno, True))
            if name in residue_names:
                users = [user for user in residue if name in _free_names(user)]
                at_import_time = any(name in _import_time_names(user) for user in users)
                self.edges.append(
                    Edge(module.name, node, module.path, min(user.lineno for user in users), at_import_time)
                )

    def _import_edges(self, source: str, module: Module, item: ResolvedImport) -> None:
        """Add the edges of one imported name: to its origin, or to the module it executes when nothing moved."""
        if item.symbol == "*":
            self.findings.append(f"{module.path}:{item.lineno}: star import of {item.base}")
        import_time = not item.in_function and not item.type_checking
        stays = module.path not in self.file_moves
        name_move = self.name_moves.get((item.origin, item.symbol)) if item.symbol else None
        if name_move is not None:
            if module.is_init and stays:
                self.index_edits.append(f"{module.path} drops the re-export of {item.symbol} (now in {name_move.unit})")
                return
            target = f"{item.origin}{VIRTUAL_SEPARATOR}{item.symbol}"
            self.edges.append(Edge(source, target, module.path, item.lineno, import_time))
            return
        origin_move = self.file_moves.get(self.module_paths.get(item.origin, ""))
        base_move = self.file_moves.get(self.module_paths.get(item.base, ""))
        if module.is_init and stays and origin_move is not None and item.origin != module.name:
            self.index_edits.append(f"{module.path} drops the import of {item.origin} (now in {origin_move.unit})")
            return
        if item.origin in self.unit_of:
            self.edges.append(Edge(source, item.origin, module.path, item.lineno, import_time))
        if item.base != item.origin and item.base in self.unit_of and origin_move is None and base_move is None:
            self.edges.append(Edge(source, item.base, module.path, item.lineno, import_time))


def simulate(modules: Mapping[str, Module], move_list: MoveList | None) -> Simulation:
    """Build the graph of ``modules`` with ``move_list`` applied (``None`` for today)."""
    return _Builder(modules, move_list).run()


def build(root: Path, move_list: MoveList | None) -> tuple[Simulation, dict[str, Module]]:
    """Parse the source tree and simulate ``move_list`` (``None`` for today)."""
    modules = load_modules(root, SOURCE_ROOT)
    return simulate(modules, move_list), modules


def apply_overrides(
    move_list: MoveList, relabels: Mapping[str, str], overrides: Mapping[str, str]
) -> tuple[MoveList, dict[str, str]]:
    """Return the move list with destination units replaced by ``overrides`` (matched on a move's key)."""
    moves = []
    for move in move_list.moves:
        unit = move.unit
        for pattern, replacement in overrides.items():
            if pattern in move.key:
                unit = replacement
        destination = move.destination
        if unit != move.unit and destination:
            destination = f"{SOURCE_ROOT}/{unit}/{Path(destination).name}"
        moves.append(Move(move.path, move.name, unit, move.serves, destination))
    return MoveList(tuple(moves), move_list.owns), dict(relabels)


# --- graph analysis -------------------------------------------------------------------------------------


def unit_graph(
    simulation: Simulation, relabel: Mapping[str, str] | None = None
) -> tuple[Graph, dict[tuple[str, str], set[tuple[str, int]]]]:
    """Return the dependencies between units and, for each, the import statements that cause it."""
    mapping = relabel or {}

    def unit(node: str) -> str:
        name = simulation.unit_of[node]
        return mapping.get(name, name)

    graph: Graph = {unit(node): set() for node in simulation.unit_of}
    causes: dict[tuple[str, str], set[tuple[str, int]]] = defaultdict(set)
    for edge in simulation.edges:
        source, target = unit(edge.source), unit(edge.target)
        if source != target:
            graph[source].add(target)
            causes[(source, target)].add((edge.path, edge.lineno))
    for source_node, target_node in simulation.implicit:
        source, target = unit(source_node), unit(target_node)
        if source != target:
            graph[source].add(target)
            causes[(source, target)].add((simulation.paths[source_node], 0))
    return graph, dict(causes)


def _reaches(graph: Mapping[str, set[str]], start: str, goal: str) -> bool:
    """Return whether ``goal`` can be reached from ``start``."""
    seen = {start}
    pending = [start]
    while pending:
        node = pending.pop()
        if node == goal:
            return True
        for target in graph.get(node, ()):
            if target not in seen:
                seen.add(target)
                pending.append(target)
    return False


def module_cycles(simulation: Simulation) -> tuple[list[list[str]], list[list[str]], list[Edge], list[Edge]]:
    """Return the import-time loops, the loops through package initializers, and two kinds of risky import.

    The risky imports are the function-level or type-only imports that close a loop, and the import-time
    imports of a package initializer by a module in the same loop (which Python tolerates only when the
    initializer is partly initialized in the right order).
    """
    explicit: Graph = {node: set() for node in simulation.unit_of}
    for edge in simulation.edges:
        if edge.import_time:
            explicit[edge.source].add(edge.target)
    with_parents = {node: set(targets) for node, targets in explicit.items()}
    for node, init in simulation.implicit:
        with_parents[node].add(init)
    loops = strongly_connected(explicit)
    components = strongly_connected(with_parents)
    loops_with_parents = [loop for loop in components if loop not in loops]
    member_of = {member: index for index, loop in enumerate(components) for member in loop}
    deferred = [
        edge
        for edge in simulation.edges
        if not edge.import_time and edge.source != edge.target and _reaches(with_parents, edge.target, edge.source)
    ]
    initializer_imports = [
        edge
        for edge in simulation.edges
        if edge.import_time
        and simulation.paths.get(edge.target, "").endswith("/__init__.py")
        and edge.source in member_of
        and member_of.get(edge.target) == member_of[edge.source]
    ]
    return loops, loops_with_parents, deferred, initializer_imports


# --- move list ------------------------------------------------------------------------------------------


def load_move_list(path: Path) -> MoveList:
    """Read and validate a move list."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    moves: list[Move] = []
    for kind in ("file", "name"):
        for entry in data.get(kind, []):
            missing = {"path", "unit", "serves"} | ({"name"} if kind == "name" else set())
            if missing - entry.keys():
                raise ValueError(f"{path}: a [[{kind}]] entry lacks {sorted(missing - entry.keys())}: {entry}")
            moves.append(
                Move(entry["path"], entry.get("name"), entry["unit"], entry["serves"], entry.get("destination", ""))
            )
    keys = [move.key for move in moves]
    if len(keys) != len(set(keys)):
        raise ValueError(f"{path}: a path or name is listed twice")
    owns = {entry["name"]: entry["owns"] for entry in data.get("unit", [])}
    return MoveList(tuple(moves), owns)


# --- importers ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ImporterCount:
    """The files that import one moved file or name."""

    move: Move
    source_files: int
    moving_files: int
    test_files: int
    other_files: int
    string_reference_files: int


def count_importers(root: Path, move_list: MoveList) -> list[ImporterCount]:
    """Count, per move, the files that import it and the test files naming it in a string.

    ``source_files`` are files under ``src`` that stay where they are; ``moving_files`` are importers that are
    themselves listed as moved; ``other_files`` are importers outside ``src`` and ``tests``.
    """
    sources = load_modules(root, SOURCE_ROOT)
    pool = dict(sources)
    for top in (TESTS_ROOT, "scripts"):
        if (root / top).is_dir():
            pool.update(load_modules(root, top))
    resolver = Resolver(sources)
    by_path = {module.path: module for module in sources.values()}
    moving = {move.path for move in move_list.moves if move.name is None}
    result: list[ImporterCount] = []
    for move in move_list.moves:
        target = by_path.get(move.path)
        if target is None:
            result.append(ImporterCount(move, 0, 0, 0, 0, 0))
            continue
        importers: set[str] = set()
        strings: set[str] = set()
        for module in pool.values():
            if module.name == target.name:
                continue
            for statement in collect_statements(module.tree):
                for item in resolver.resolve(module, statement):
                    if item.origin == target.name and (move.name is None or item.symbol == move.name):
                        importers.add(module.path)
            if _mentions(module, target, move.name):
                strings.add(module.path)
        in_source = {path for path in importers if path.startswith(f"{SOURCE_ROOT}/")}
        result.append(
            ImporterCount(
                move,
                len(in_source - moving),
                len(in_source & moving),
                sum(1 for path in importers if path.startswith(f"{TESTS_ROOT}/")),
                sum(1 for path in importers if not path.startswith((f"{SOURCE_ROOT}/", f"{TESTS_ROOT}/"))),
                sum(1 for path in strings if path.startswith(f"{TESTS_ROOT}/")),
            )
        )
    return result


def _mentions(module: Module, target: Module, name: str | None) -> bool:
    """Return whether a file holds a string naming the module (or one of its names) as a dotted path."""
    wanted = target.name if name is None else f"{target.name}.{name}"
    for node in ast.walk(module.tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value
            if value == wanted or (not target.is_init and value.startswith(f"{wanted}.")):
                return True
    return False


# --- report ---------------------------------------------------------------------------------------------


def _describe(title: str, simulation: Simulation, relabel: Mapping[str, str]) -> list[str]:
    """Return the report lines for one simulation."""
    graph, causes = unit_graph(simulation, relabel)
    lines = [f"== {title} =="]
    lines += _unit_lines(simulation, graph, causes, relabel)
    lines += _loop_lines(graph)
    lines += _module_lines(simulation)
    if simulation.index_edits:
        lines.append(f"Index edits required ({len(simulation.index_edits)}):")
        lines.extend(f"  {edit}" for edit in simulation.index_edits)
    if simulation.findings:
        lines.append(f"Findings ({len(simulation.findings)}):")
        lines.extend(f"  {finding}" for finding in simulation.findings)
    return lines


def _unit_lines(
    simulation: Simulation,
    graph: Mapping[str, set[str]],
    causes: Mapping[tuple[str, str], set[tuple[str, int]]],
    relabel: Mapping[str, str],
) -> list[str]:
    """Return the lines naming the units and the dependencies between them."""
    units = sorted(graph)
    files_per_unit: dict[str, int] = defaultdict(int)
    for node, unit in simulation.unit_of.items():
        if VIRTUAL_SEPARATOR not in node:
            files_per_unit[relabel.get(unit, unit)] += 1
    statements = sum(len(value) for value in causes.values())
    lines = [
        f"Units ({len(units)}): " + ", ".join(f"{unit} ({files_per_unit[unit]})" for unit in units),
        f"Dependencies: {sum(len(t) for t in graph.values())} between units, {statements} import statements",
    ]
    for source in units:
        targets = sorted(graph[source])
        lines.append(f"  {source} -> " + (", ".join(targets) if targets else "(nothing)"))
    return lines


def _loop_lines(graph: Mapping[str, set[str]]) -> list[str]:
    """Return the lines naming the two-way pairs, the loops and the layered order."""
    pairs = two_way(graph)
    loops = strongly_connected(graph)
    lines = [
        f"Two-way pairs ({len(pairs)}): " + ("; ".join(f"{a} <-> {b}" for a, b in pairs) or "none"),
        f"Loops ({len(loops)}):",
    ]
    lines.extend(f"  {len(loop)} units: " + ", ".join(loop) for loop in loops)
    if not loops:
        lines.append("  none")
    ordered = layers(graph)
    if ordered is None:
        lines.append("Layered order: none, because of the loop(s) above")
        return lines
    lines.append("Layered order (each layer imports only from the layers before it):")
    lines.extend(f"  {number}: " + ", ".join(layer) for number, layer in enumerate(ordered))
    return lines


def _module_lines(simulation: Simulation) -> list[str]:
    """Return the lines naming the loops between modules and the risky imports."""
    import_time, through_parents, deferred, initializer_imports = module_cycles(simulation)
    lines = [f"Import-time loops between modules ({len(import_time)}):"]
    lines.extend(f"  {len(loop)} modules: " + ", ".join(_shown(simulation, loop)) for loop in import_time)
    lines.append(f"Import-time loops that exist only through package initializers ({len(through_parents)}):")
    lines.extend(f"  {len(loop)} modules: " + ", ".join(_shown(simulation, loop)) for loop in through_parents)
    lines.append(f"Function-level or type-only imports that close a loop ({len(deferred)}):")
    lines.extend(_statements(simulation, deferred))
    lines.append(
        f"Import-time imports of a package initializer by a module in the same loop ({len(initializer_imports)}):"
    )
    lines.extend(_statements(simulation, initializer_imports))
    return lines


def _statements(simulation: Simulation, edges: Iterable[Edge]) -> list[str]:
    """Return one line per distinct import statement and target, in file order."""
    found = {(edge.path, edge.lineno, simulation.names.get(edge.target, edge.target)) for edge in edges}
    return [f"  {path}:{lineno} -> {target}" for path, lineno, target in sorted(found)] or ["  none"]


def table_rows(simulation: Simulation, owns: Mapping[str, str], relabel: Mapping[str, str]) -> list[str]:
    """Return the package table rows (Package, Owns, Imports), lower layers first."""
    graph, _ = unit_graph(simulation, relabel)
    ordered = layers(graph)
    if ordered is None:
        return ["The graph has a loop; there is no layered table."]
    rows = ["| Package | Owns | Imports |", "| --- | --- | --- |"]
    for layer in ordered:
        for unit in layer:
            imports = ", ".join(f"`{target}`" for target in sorted(graph[unit]))
            rows.append(f"| `{unit}` | {owns.get(unit, '')} | {imports} |")
    return rows


def _shown(simulation: Simulation, nodes: Iterable[str]) -> list[str]:
    """Return the names the nodes have after the moves, sorted."""
    return sorted(simulation.names.get(node, node) for node in nodes)


def role_violations(simulation: Simulation) -> list[str]:
    """List imports from a strategy's core files to a file the role rule assigns to another layer."""
    rule_roles = {role for rule in ROLE_RULES for role in rule.roles}
    problems: list[str] = []
    for edge in simulation.edges:
        source_path, target_path = simulation.paths.get(edge.source, ""), simulation.paths.get(edge.target, "")
        if (
            _in_strategy(source_path)
            and _in_strategy(target_path)
            and Path(source_path).stem not in rule_roles
            and Path(target_path).stem in rule_roles
        ):
            problems.append(f"{edge.path}:{edge.lineno} -> {target_path}")
    return sorted(set(problems))


def _in_strategy(path: str) -> bool:
    """Return whether a path is a file directly inside a package of ``src/strategies``."""
    parts = Path(path).parts
    return len(parts) == 4 and parts[:2] == (SOURCE_ROOT, "strategies")


def _repository_root() -> Path:
    """Return the root of the repository this script lives in."""
    return Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, check=True, text=True
        ).stdout.strip()
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Print the report; return 0."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0] if __doc__ else None)
    parser.add_argument("--moves", type=Path, default=None, help="move list (TOML)")
    parser.add_argument("--root", type=Path, default=None, help="repository root")
    parser.add_argument("--relabel", action="append", default=[], metavar="A=B", help="merge target unit A into B")
    parser.add_argument(
        "--override", action="append", default=[], metavar="KEY=UNIT", help="send matching moves to UNIT"
    )
    parser.add_argument("--only", choices=("today", "target"), default=None)
    parser.add_argument("--importers", action="store_true", help="count the importers of each move")
    parser.add_argument("--table", action="store_true", help="print the target package table")
    parser.add_argument("--cycle-through", default=None, metavar="UNIT", help="print a shortest cycle through UNIT")
    args = parser.parse_args(argv)
    root = args.root or _repository_root()
    move_list = load_move_list(args.moves or root / DEFAULT_MOVES)
    relabel = dict(item.split("=", maxsplit=1) for item in args.relabel)
    overrides = dict(item.split("=", maxsplit=1) for item in args.override)
    move_list, relabel = apply_overrides(move_list, relabel, overrides)
    lines: list[str] = []
    if args.only != "target":
        today, _ = build(root, None)
        lines += _describe("today", today, {})
        if args.cycle_through:
            lines += _cycle_lines(today, {}, args.cycle_through)
    if args.only != "today":
        target, _ = build(root, move_list)
        lines += [""] if lines else []
        lines += _describe("target", target, relabel)
        violations = role_violations(target)
        lines.append(
            f"Imports from a strategy's core files to its cli, evaluation or execution files ({len(violations)}):"
        )
        lines.extend(f"  {item}" for item in violations)
        if args.cycle_through:
            lines += _cycle_lines(target, relabel, args.cycle_through)
        if args.table:
            lines += ["", *table_rows(target, move_list.owns, relabel)]
    if args.importers:
        lines += ["", "== importers of each move =="]
        lines.append("	".join(IMPORTER_COLUMNS))
        for count in count_importers(root, move_list):
            lines.append(
                f"{count.move.key}	{count.source_files}	{count.moving_files}	{count.test_files}"
                f"	{count.other_files}	{count.string_reference_files}"
            )
    print("\n".join(lines))
    return 0


def _cycle_lines(simulation: Simulation, relabel: Mapping[str, str], unit: str) -> list[str]:
    """Return the line naming a shortest cycle through ``unit``."""
    graph, _ = unit_graph(simulation, relabel)
    cycle = shortest_cycle(graph, unit)
    return [f"Shortest cycle through {unit}: " + (" -> ".join(cycle) if cycle else "none")]


if __name__ == "__main__":
    sys.exit(main())
