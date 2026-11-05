"""The package map and graph analysis used by the dependency check.

Standard library only. This module defines which unit a file under ``investment_analysis_engine/`` belongs to and
analyzes a graph of units; it reads no file and modifies none.

A *unit* is each directory directly under ``investment_analysis_engine/``, plus each top-level module under
``investment_analysis_engine/`` by its file name (``config``, ``strategy_wiring``). The exceptions are ``cli``, which
groups ``investment_analysis_engine/main.py`` and every ``investment_analysis_engine/cli*.py``, and the role files
below. ``investment_analysis_engine/__init__.py`` is ignored.

The *role rule* is one rule: a file directly inside a package under ``investment_analysis_engine/strategies/``
(including ``_graham``) whose name, without ``.py``, is the name of a unit in ``ROLE_UNITS`` (``cli``,
``evaluation``, ``workspace`` or ``application``) belongs to that unit. Every other file under
``investment_analysis_engine/strategies/`` belongs to ``strategies``.
"""

from __future__ import annotations

import sys
from collections import defaultdict, deque
from collections.abc import Iterable, Mapping
from pathlib import Path

CLI_UNIT = "cli"

Graph = dict[str, set[str]]


ROLE_PARENT = "strategies"
"""The package whose strategy packages hold role files."""

ROLE_UNITS = frozenset({"cli", "evaluation", "workspace", "application"})
"""The units a file inside a strategy package can belong to by its name."""


def _role_unit(relative_path: Path) -> str | None:
    """Return the unit a file's name gives it inside a strategy package (relative to the source root), or ``None``."""
    parts = relative_path.parts
    if len(parts) != 3 or relative_path.suffix != ".py" or parts[0] != ROLE_PARENT:
        return None
    return relative_path.stem if relative_path.stem in ROLE_UNITS else None


def unit_of_path(relative_path: Path) -> str | None:
    """Return the unit a path (relative to the source root) belongs to, or ``None`` if ignored."""
    parts = relative_path.parts
    if not parts or "__pycache__" in parts:
        return None
    role_unit = _role_unit(relative_path)
    if role_unit is not None:
        return role_unit
    if len(parts) > 1:
        return None if parts[0].startswith(("_", ".")) else parts[0]
    stem = relative_path.stem
    if relative_path.suffix != ".py" or stem == "__init__":
        return None
    if stem in {"main", CLI_UNIT} or stem.startswith(f"{CLI_UNIT}_"):
        return CLI_UNIT
    return stem


def strongly_connected(graph: Mapping[str, Iterable[str]]) -> list[list[str]]:
    """Return the strongly connected components with more than one member (or a self edge), sorted."""
    index = 0
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    result: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = lowlink[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for target in sorted(graph.get(node, ())):
            if target not in indices:
                visit(target)
                lowlink[node] = min(lowlink[node], lowlink[target])
            elif target in on_stack:
                lowlink[node] = min(lowlink[node], indices[target])
        if lowlink[node] == indices[node]:
            component: list[str] = []
            while True:
                member = stack.pop()
                on_stack.discard(member)
                component.append(member)
                if member == node:
                    break
            if len(component) > 1 or node in set(graph.get(node, ())):
                result.append(sorted(component))

    sys.setrecursionlimit(max(sys.getrecursionlimit(), 10_000))
    for node in sorted(graph):
        if node not in indices:
            visit(node)
    return sorted(result)


def layers(graph: Mapping[str, set[str]]) -> list[list[str]] | None:
    """Return the units grouped by the longest import path below them, or ``None`` when there is a loop."""
    if strongly_connected(graph):
        return None
    level: dict[str, int] = {}

    def depth(node: str) -> int:
        if node not in level:
            level[node] = 1 + max((depth(target) for target in graph.get(node, ())), default=-1)
        return level[node]

    for node in graph:
        depth(node)
    grouped: dict[int, list[str]] = defaultdict(list)
    for node, value in level.items():
        grouped[value].append(node)
    return [sorted(grouped[value]) for value in sorted(grouped)]


def shortest_cycle(graph: Mapping[str, set[str]], through: str) -> list[str] | None:
    """Return a shortest cycle that passes ``through``, as a list starting and ending with it."""
    queue: deque[list[str]] = deque([[through]])
    seen = {through}
    while queue:
        path = queue.popleft()
        for target in sorted(graph.get(path[-1], ())):
            if target == through:
                return [*path, through]
            if target not in seen:
                seen.add(target)
                queue.append([*path, target])
    return None
