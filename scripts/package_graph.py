"""The package map and graph analysis shared by the dependency check and the layering simulation.

Standard library only. This module defines which unit a file under ``src/`` belongs to and analyzes a graph of
units; it reads no file and modifies none.

A *unit* is each directory directly under ``src/``, plus each top-level module under ``src/`` by its file name
(``config``, ``strategy_wiring``). The exceptions are ``cli``, which groups ``src/main.py`` and every
``src/cli*.py``, and the role files below. ``src/__init__.py`` is ignored.

The *role rule* assigns three files of each strategy package to the layer they adapt the strategy to: a file named
``cli.py``, ``evaluation.py`` or ``execution.py`` directly inside a package under ``src/strategies/`` (including
``_graham``) belongs to the unit ``cli``, ``evaluation`` or ``workspace`` respectively. Every other file under
``src/strategies/`` belongs to ``strategies``. The rule is the data in ``ROLE_RULES``.
"""

from __future__ import annotations

import sys
from collections import defaultdict, deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

CLI_UNIT = "cli"

Graph = dict[str, set[str]]


@dataclass(frozen=True)
class RoleRule:
    """Files named ``<role>.py`` directly inside a package under ``under`` belong to the mapped unit."""

    under: str
    roles: Mapping[str, str]


ROLE_RULES = (RoleRule("strategies", {"cli": "cli", "evaluation": "evaluation", "execution": "workspace"}),)


def _role_unit(relative_path: Path) -> str | None:
    """Return the unit the role rule assigns to a path relative to the source root, or ``None``."""
    parts = relative_path.parts
    if len(parts) != 3 or relative_path.suffix != ".py":
        return None
    for rule in ROLE_RULES:
        if parts[0] == rule.under:
            return rule.roles.get(relative_path.stem)
    return None


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


def two_way(graph: Mapping[str, set[str]]) -> list[tuple[str, str]]:
    """Return the unit pairs that import each other, sorted."""
    return sorted((a, b) for a, targets in graph.items() for b in targets if a < b and a in graph.get(b, set()))


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
