"""Package dependency checker for the top-level units under ``investment_analysis_engine/``.

Reads the package table in ``docs/project/ARCHITECTURE.md`` (the section titled
"Module boundaries"), computes the real import graph from the code, and reports
every disagreement between the two in one run. Standard library only; it never
modifies a file.

A *unit* is each directory directly under ``investment_analysis_engine/``, plus each top-level module under
``investment_analysis_engine/`` by its file name (``config``, ``strategy_wiring``). The exceptions are ``cli``, which
groups ``investment_analysis_engine/main.py`` and every ``investment_analysis_engine/cli*.py``, and the role files: a
file named ``cli.py``, ``evaluation.py`` or ``execution.py`` directly inside a package under
``investment_analysis_engine/strategies/`` belongs to ``cli``, ``evaluation`` or ``workspace`` respectively (the rule is
data in ``scripts/package_graph.py``). ``investment_analysis_engine/__init__.py`` is ignored.

A *dependency* is any ``import investment_analysis_engine.X...`` or ``from investment_analysis_engine.X... import ...``
anywhere in a file under ``investment_analysis_engine/``, including imports inside functions, attributed
to the file the import names: ``import investment_analysis_engine.strategies.x.cli`` and
``from investment_analysis_engine.strategies.x import cli`` both depend on the unit of ``cli.py``.
Imports within one unit are ignored.

The table has the columns ``Package | Layer | Owns | Imports``. Package names are
written in backticks; the ``Imports`` cell lists unit names in backticks; the
``Layer`` cell holds a whole number. A unit that imports no other unit is in
layer 0, and any other unit is one more than the highest layer among the units it
imports (``layers`` in ``scripts/package_graph.py``). Rows are ordered by layer,
then by package name.

The check fails on any import loop between units, reporting each loop once with an
example import per edge; while a loop exists, layers are undefined and no layer or
order finding is reported. It also fails on any difference between the table and the
code: a missing, stale or unknown row, an undeclared or stale import, a wrong Layer
cell, or rows out of order. Exit status is 1 when any finding is reported.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):
    # Run as ``python scripts/check_package_dependencies.py``: the repository root is not on the path yet, so
    # ``investment_analysis_engine.core.package_root`` cannot be imported and the root is found by counting folders
    # here, once.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.package_graph import layers, shortest_cycle, strongly_connected, unit_of_path  # noqa: E402

SOURCE_ROOT_NAME = "investment_analysis_engine"
ARCHITECTURE_DOC = Path("docs/project/ARCHITECTURE.md")
TABLE_SECTION_TITLE = "Module boundaries"
TABLE_HEADER = ("Package", "Layer", "Owns", "Imports")

_SECTION_HEADING_RE = re.compile(r"^##\s+(?:\d+\.\s+)?(.*?)\s*$")
_BACKTICKED_RE = re.compile(r"`([^`]+)`")

Edge = tuple[str, str]
Occurrence = tuple[Path, int]


@dataclass(frozen=True)
class DeclaredRow:
    """One row of the package table."""

    package: str
    layer_cell: str
    imports: frozenset[str]


def _unit_for_module(name_parts: list[str], source_root: Path) -> str | None:
    """Map an imported module path below the source root to the unit of the file it names.

    The longest leading run of parts that names a directory or a module file is followed; a name that is
    not a module (an attribute of the last package) resolves to that package's ``__init__.py``.
    """
    if not name_parts:
        return None
    path = Path()
    for part in name_parts:
        if (source_root / path / part).is_dir():
            path /= part
        elif (source_root / path / f"{part}.py").is_file():
            return unit_of_path(path / f"{part}.py")
        else:
            break
    if path.parts:
        return unit_of_path(path / "__init__.py")
    return unit_of_path(Path(f"{name_parts[0]}.py"))


def _imported_units(node: ast.stmt, relative_path: Path, source_root: Path) -> list[str]:
    """Return the units a single import statement refers to (possibly several)."""
    candidates: list[list[str]] = []
    if isinstance(node, ast.Import):
        candidates = [alias.name.split(".")[1:] for alias in node.names if alias.name.split(".")[0] == SOURCE_ROOT_NAME]
    elif isinstance(node, ast.ImportFrom):
        candidates = _from_import_candidates(node, relative_path)
    units = (_unit_for_module(parts, source_root) for parts in candidates)
    return [unit for unit in units if unit is not None]


def _from_import_candidates(node: ast.ImportFrom, relative_path: Path) -> list[list[str]]:
    """Return the module paths below the source root that a ``from`` import refers to."""
    module_parts = node.module.split(".") if node.module else []
    if node.level:
        package = list(relative_path.parts[:-1])
        module_parts = package[: len(package) - (node.level - 1)] + module_parts
    elif module_parts[:1] == [SOURCE_ROOT_NAME]:
        module_parts = module_parts[1:]
    else:
        return []
    return [[*module_parts, alias.name] for alias in node.names]


def list_units(source_root: Path) -> set[str]:
    """Return every unit that has at least one Python file below ``source_root``."""
    units: set[str] = set()
    for path in source_root.rglob("*.py"):
        unit = unit_of_path(path.relative_to(source_root))
        if unit is not None:
            units.add(unit)
    return units


def collect_imports(source_root: Path) -> dict[Edge, list[Occurrence]]:
    """Return every cross-unit import as ``{(importer, imported): [(file, line), ...]}``."""
    edges: dict[Edge, list[Occurrence]] = defaultdict(list)
    for path in sorted(source_root.rglob("*.py")):
        relative_path = path.relative_to(source_root)
        importer = unit_of_path(relative_path)
        if importer is None:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            for imported in _imported_units(node, relative_path, source_root):
                if imported != importer:
                    edges[(importer, imported)].append((relative_path, node.lineno))
    return dict(edges)


def read_declared_table(architecture_text: str) -> tuple[list[DeclaredRow], list[str]]:
    """Parse the package table; return its rows and any problems found reading it."""
    lines = architecture_text.splitlines()
    problems: list[str] = []
    in_section = False
    table_lines: list[str] = []
    for line in lines:
        heading = _SECTION_HEADING_RE.match(line)
        if heading is not None:
            if in_section:
                break
            in_section = heading.group(1) == TABLE_SECTION_TITLE
            continue
        if in_section and line.lstrip().startswith("|"):
            table_lines.append(line)
    if not table_lines:
        return [], [f"{ARCHITECTURE_DOC}: no table found in the section titled '{TABLE_SECTION_TITLE}'."]
    header = tuple(cell.strip() for cell in table_lines[0].strip().strip("|").split("|"))
    if header != TABLE_HEADER:
        problems.append(
            f"{ARCHITECTURE_DOC}: table header must be '{' | '.join(TABLE_HEADER)}', found '{' | '.join(header)}'."
        )
        return [], problems
    rows: list[DeclaredRow] = []
    for line in table_lines[2:]:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != len(TABLE_HEADER):
            problems.append(
                f"{ARCHITECTURE_DOC}: table row has {len(cells)} cells, "
                f"expected {len(TABLE_HEADER)}: {line.strip()[:60]}"
            )
            continue
        names = _BACKTICKED_RE.findall(cells[0])
        if len(names) != 1:
            problems.append(f"{ARCHITECTURE_DOC}: the Package cell must hold one backticked name, found '{cells[0]}'.")
            continue
        rows.append(
            DeclaredRow(
                package=names[0],
                layer_cell=cells[1],
                imports=frozenset(_BACKTICKED_RE.findall(cells[3])),
            )
        )
    return rows, problems


def _example(occurrences: list[Occurrence]) -> str:
    path, line = occurrences[0]
    return f"{SOURCE_ROOT_NAME}/{path.as_posix()}:{line}"


def _compare_units(rows: list[DeclaredRow], units: set[str]) -> list[str]:
    """Return the findings about units without rows, rows without units, and duplicate or unknown names."""
    findings: list[str] = []
    by_package = {row.package: row for row in rows}
    seen: set[str] = set()
    for row in rows:
        if row.package in seen:
            findings.append(f"Table lists '{row.package}' twice; keep one row.")
        seen.add(row.package)
    for unit in sorted(units - set(by_package)):
        findings.append(f"Unit '{unit}' exists under {SOURCE_ROOT_NAME}/ but has no table row; add a row for it.")
    for package in sorted(set(by_package) - units):
        findings.append(f"Table row '{package}' has no unit under {SOURCE_ROOT_NAME}/; remove the row.")
    for package in sorted(by_package):
        for target in sorted(by_package[package].imports):
            if target not in units and target != package:
                findings.append(f"Row '{package}' names '{target}', which is not a unit; remove it from the row.")
    return findings


def _compare_imports(rows: list[DeclaredRow], units: set[str], edges: dict[Edge, list[Occurrence]]) -> list[str]:
    """Return the findings about imports the table does not declare or declares without a use."""
    findings: list[str] = []
    by_package = {row.package: row for row in rows}
    actual: dict[str, set[str]] = defaultdict(set)
    for importer, imported in edges:
        actual[importer].add(imported)
    for unit in sorted(units & set(by_package)):
        declared = by_package[unit].imports
        for target in sorted(actual[unit] - declared):
            findings.append(
                f"'{unit}' imports '{target}' (first at {_example(edges[(unit, target)])}) but its Imports cell "
                f"does not list it; add '{target}' to the Imports cell of '{unit}'."
            )
        for target in sorted(declared - actual[unit]):
            findings.append(
                f"'{unit}' lists '{target}' in its Imports cell but no code imports it; "
                f"remove '{target}' from the Imports cell of '{unit}'."
            )
    return findings


def _actual_graph(units: set[str], edges: dict[Edge, list[Occurrence]]) -> dict[str, set[str]]:
    """Return the unit graph, with every unit present, built from the collected imports."""
    graph: dict[str, set[str]] = {unit: set() for unit in units}
    for importer, imported in edges:
        graph.setdefault(importer, set()).add(imported)
        graph.setdefault(imported, set())
    return graph


def _compare_loops(graph: dict[str, set[str]], edges: dict[Edge, list[Occurrence]]) -> list[str]:
    """Return one finding per import loop, written as the shortest cycle through the loop's first unit."""
    findings: list[str] = []
    for component in strongly_connected(graph):
        cycle = shortest_cycle(graph, component[0])
        if cycle is None:  # pragma: no cover - a component always holds a cycle through each member
            continue
        units = [f"'{unit}'" for unit in component]
        listed = units[0] if len(units) == 1 else f"{', '.join(units[:-1])} and {units[-1]}"
        route = " -> ".join(cycle)
        examples = "; ".join(
            f"{source} -> {target} at {_example(edges[(source, target)])}"
            for source, target in zip(cycle, cycle[1:], strict=False)
        )
        findings.append(
            f"{listed} form an import loop: {route} ({examples}). "
            f"Remove one of these imports, or move the code, so the loop breaks."
        )
    return findings


def _compare_layers(rows: list[DeclaredRow], units: set[str], graph: dict[str, set[str]]) -> list[str]:
    """Return the findings about wrong Layer cells and rows out of layer-then-name order."""
    grouped = layers(graph)
    if grouped is None:  # pragma: no cover - the caller reports loops instead of calling this
        return []
    actual = {unit: number for number, members in enumerate(grouped) for unit in members}
    findings: list[str] = []
    numbered: list[tuple[int, str]] = []
    for row in rows:
        if row.package not in units:
            continue
        number = actual[row.package]
        if not row.layer_cell.isdecimal():
            findings.append(f"The Layer cell of '{row.package}' is not a whole number; write its layer, {number}.")
        elif int(row.layer_cell) != number:
            findings.append(
                f"'{row.package}' is in layer {number}, but its Layer cell says {int(row.layer_cell)}; "
                f"change the cell to {number}."
            )
        numbered.append((number, row.package))
    for (earlier_layer, earlier), (later_layer, later) in zip(numbered, numbered[1:], strict=False):
        if (earlier_layer, earlier) > (later_layer, later):
            findings.append(
                f"The row for '{later}' (layer {later_layer}) comes after the row for '{earlier}' "
                f"(layer {earlier_layer}); order the rows by layer, then by name."
            )
            break
    return findings


def compare(rows: list[DeclaredRow], units: set[str], edges: dict[Edge, list[Occurrence]]) -> list[str]:
    """Return one message per disagreement between the table and the code.

    While an import loop exists, layers are undefined, so the loops are reported in place of the layer and order
    findings.
    """
    graph = _actual_graph(units, edges)
    findings = _compare_units(rows, units) + _compare_imports(rows, units, edges)
    loops = _compare_loops(graph, edges)
    if loops:
        return findings + loops
    return findings + _compare_layers(rows, units, graph)


def check_repository(repo_root: Path) -> list[str]:
    """Check the table against the code under ``repo_root`` and return every finding."""
    source_root = repo_root / SOURCE_ROOT_NAME
    architecture_path = repo_root / ARCHITECTURE_DOC
    rows, problems = read_declared_table(architecture_path.read_text(encoding="utf-8"))
    if problems:
        return problems
    return compare(rows, list_units(source_root), collect_imports(source_root))


def main() -> int:
    """Check the repository this script lives in; print every finding; return the exit code."""
    repo_root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, check=True, text=True
        ).stdout.strip()
    )
    findings = check_repository(repo_root)
    if not findings:
        print("check_package_dependencies: the package table matches the code.")
        return 0
    for finding in findings:
        print(finding)
    print(
        f"check_package_dependencies: {len(findings)} finding(s); fix the table in {ARCHITECTURE_DOC}.", file=sys.stderr
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
