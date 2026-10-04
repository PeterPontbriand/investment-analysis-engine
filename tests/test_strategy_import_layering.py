"""Keep strategy imports within their declared role layers.

The role rule is design §4: a file's role is its file name inside its strategy package; within a
package a file may import only a lower-ranked role, except that analyzer-level files may import each
other; no strategy imports another; code outside ``src/strategies`` may import only analyzer and
selection roles. Imports of ``__init__.py`` files count, and every ``__init__.py`` under
``src/strategies`` must be empty.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests._strategy_roles import ANALYZER_ROLES, ROLE_RANK

_SRC = Path(__file__).resolve().parents[1] / "src"
_GRAHAM_MEMBERS = frozenset({"graham_number", "graham_growth"})
_ROOT = "src.strategy_wiring"
# The composition root may import these strategy roles and no others: not execution, presenter, cli or
# evaluation files, which belong to the layers below it and to the tiers.
_ROOT_ROLES = ANALYZER_ROLES | {"codec", "envelope", "replay", "selection", "tool"}
# The only importers of the root, listed exactly. An entry must exist and import the root, so a slice adds
# its module here in the change that first makes it import the root (the tier modules and the CLI modules
# are added by the slices that create or rewire them).
_ROOT_IMPORTERS = frozenset({"src.evaluation.composition", "src.evaluation.runner", "src.evaluation.ollama_runner"})
_TRANSITIONS = {
    ("src.evaluation.composition", "src.strategies.fcf_growth.tool", "SWC.2d"),
    ("src.evaluation.composition", "src.strategies.graham_growth.tool", "SWC.2d"),
    ("src.evaluation.composition", "src.strategies.graham_number.tool", "SWC.2d"),
    ("src.evaluation.composition", "src.strategies.momentum.tool", "SWC.2d"),
    ("src.evaluation.catalog", "src.strategies.fcf_growth.tool", "SWC.2d"),
    ("src.evaluation.catalog", "src.strategies.graham_growth.tool", "SWC.2d"),
    ("src.evaluation.catalog", "src.strategies.graham_number.tool", "SWC.2d"),
    ("src.evaluation.catalog", "src.strategies.momentum.tool", "SWC.2d"),
    ("src.workspace.codecs", "src.strategies.fcf_growth.codec", "SWC.3a"),
    ("src.workspace.codecs", "src.strategies.graham_growth.codec", "SWC.3a"),
    ("src.workspace.codecs", "src.strategies.graham_number.codec", "SWC.3a"),
    ("src.workspace.codecs", "src.strategies.momentum.codec", "SWC.3a"),
    ("src.workspace.execution", "src.strategies.fcf_growth.execution", "SWC.3a"),
    ("src.workspace.execution", "src.strategies.graham_growth.execution", "SWC.3a"),
    ("src.workspace.execution", "src.strategies.graham_number.execution", "SWC.3a"),
    ("src.workspace.execution", "src.strategies.momentum.execution", "SWC.3a"),
    ("src.cli_workspace", "src.strategies.fcf_growth.execution", "SWC.3b"),
    ("src.cli_workspace", "src.strategies.graham_growth.execution", "SWC.3b"),
    ("src.cli_workspace", "src.strategies.graham_number.execution", "SWC.3b"),
    ("src.cli_workspace", "src.strategies.momentum.execution", "SWC.3b"),
    ("src.cli", "src.strategies.fcf_growth.execution", "SWC.3c"),
    ("src.cli", "src.strategies.fcf_growth.presenter", "SWC.3c"),
    ("src.cli", "src.strategies.graham_growth.execution", "SWC.3c"),
    ("src.cli", "src.strategies.graham_growth.presenter", "SWC.3c"),
    ("src.cli", "src.strategies.graham_number.execution", "SWC.3c"),
    ("src.cli", "src.strategies.graham_number.presenter", "SWC.3c"),
    ("src.cli", "src.strategies.momentum.execution", "SWC.3c"),
    ("src.cli", "src.strategies.momentum.presenter", "SWC.3c"),
    ("src.reporting.analysis_runs", "src.strategies.fcf_growth.presenter", "SWC.4c"),
    ("src.reporting.analysis_runs", "src.strategies.graham_growth.presenter", "SWC.4c"),
    ("src.reporting.analysis_runs", "src.strategies.graham_number.presenter", "SWC.4c"),
    ("src.reporting.analysis_runs", "src.strategies.momentum.presenter", "SWC.4c"),
}
# Re-exporting package initializers that sit in an import cycle. They belong to eight components: the
# telemetry component also holds the ``src.core.telemetry.sinks`` and ``src.data.repositories`` initializers.
_BENIGN_CYCLE_PACKAGES = frozenset(
    {
        "src.data.sec_edgar",
        "src.data.massive",
        "src.data.yfinance",
        "src.schema",
        "src.core.telemetry",
        "src.core.telemetry.sinks",
        "src.data.repositories",
        "src.evaluation",
        "src.evaluation.fixtures",
        "src.evaluation.cases",
    }
)
_SAMPLE_STRATEGIES = frozenset({"momentum", "graham_number", "graham_growth"})


def _module_name(path: Path) -> str:
    """Return a source module's dotted import name."""
    parts = path.relative_to(_SRC).with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(("src", *parts))


def _resolve_imports(module: str, node: ast.Import | ast.ImportFrom) -> set[str]:
    """Resolve imports to module edges, including imported child modules."""
    if isinstance(node, ast.Import):
        return {alias.name for alias in node.names}
    package = module.split(".")[:-1]
    if node.level:
        package = package[: len(package) - node.level + 1]
        base = ".".join((*package, *(node.module.split(".") if node.module else ())))
    else:
        base = node.module or ""
    if not node.names:
        return {base} if base else set()
    targets = {base} if base else set()
    for alias in node.names:
        if alias.name != "*" and base:
            targets.add(f"{base}.{alias.name}")
    return targets


def _source_graph() -> tuple[dict[str, set[str]], set[tuple[str, str]], set[str]]:
    """Build the source import graph and retain only edges to real modules."""
    paths = sorted(_SRC.rglob("*.py"))
    files = {_module_name(path): path for path in paths}
    init_modules = {_module_name(path) for path in paths if path.name == "__init__.py"}
    graph: dict[str, set[str]] = {name: set() for name in files}
    edges: set[tuple[str, str]] = set()
    for module, path in files.items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for imported in _resolve_imports(module, node):
                    if imported.startswith("tests.") or imported == "tests":
                        edges.add((module, imported))
                        continue
                    target = imported
                    while target and target not in files:
                        target = target.rpartition(".")[0]
                    if target:
                        graph[module].add(target)
                        edges.add((module, target))
        parents = module.split(".")[:-1]
        for end in range(2, len(parents) + 1):
            parent = ".".join(parents[:end])
            if parent in init_modules:
                graph[module].add(parent)
    return graph, edges, init_modules


def _cycles(graph: dict[str, set[str]]) -> list[set[str]]:
    """Return strongly connected components with more than one module."""
    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    result: list[set[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for target in graph[node]:
            if target not in indices:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[target])
        if lowlinks[node] == indices[node]:
            component: set[str] = set()
            while True:
                member = stack.pop()
                on_stack.remove(member)
                component.add(member)
                if member == node:
                    break
            if len(component) > 1:
                result.append(component)

    for node in graph:
        if node not in indices:
            visit(node)
    return result


def _strategy_packages(src: Path) -> frozenset[str]:
    """Return the strategy package names: every non-underscore directory under ``src/strategies``."""
    root = src / "strategies"
    return frozenset(path.name for path in root.iterdir() if path.is_dir() and not path.name.startswith(("_", ".")))


def _role(parts: list[str]) -> str:
    """Return the role of a ``src.strategies.<package>[.<file>]`` module name."""
    return parts[3] if len(parts) > 3 else "__init__"


def _role_order_error(source: str, target: str) -> str | None:
    """Report an import between two files of one strategy that does not go to a lower rank."""
    source_role, target_role = _role(source.split(".")), _role(target.split("."))
    if source_role == target_role or source_role not in ROLE_RANK or target_role not in ROLE_RANK:
        return None
    if source_role in ANALYZER_ROLES and target_role in ANALYZER_ROLES:
        return None
    if ROLE_RANK[target_role] > ROLE_RANK[source_role]:
        return f"role order is not downward: {source} -> {target}"
    if ROLE_RANK[target_role] == ROLE_RANK[source_role]:
        return f"same-rank roles may not import each other: {source} -> {target}"
    return None


def _strategy_edge_error(source: str, target: str, strategies: frozenset[str]) -> str | None:
    """Report a forbidden import whose importer is in ``src/strategies``."""
    source_package, target_package = source.split(".")[2], target.split(".")[2]
    if source_package == "_shared":
        if target_package != "_shared":
            return f"_shared imports a strategy or family module: {source} -> {target}"
    elif source_package == "_graham":
        member_analyzer = target_package in _GRAHAM_MEMBERS and _role(target.split(".")) in ANALYZER_ROLES
        if target_package != "_graham" and not member_analyzer:
            return f"_graham imports beyond the analyzer modules of its members: {source} -> {target}"
    elif source_package in strategies:
        if target_package == "_graham":
            if source_package not in _GRAHAM_MEMBERS:
                return f"_graham is imported outside its member strategies: {source} -> {target}"
        elif target_package in strategies and target_package != source_package:
            return f"strategy import crosses packages: {source} -> {target}"
        elif target_package == source_package:
            return _role_order_error(source, target)
    return None


def _edge_violations(
    edges: set[tuple[str, str]],
    strategies: frozenset[str],
    transitions: set[tuple[str, str, str]] = _TRANSITIONS,
    root_importers: frozenset[str] = _ROOT_IMPORTERS,
) -> list[str]:
    """Check strategy boundaries, role order, the exact transition edges and imports of ``tests``."""
    errors: list[str] = []
    permitted = {(source, target) for source, target, _ in transitions}
    for source, target in sorted(edges):
        source_parts, target_parts = source.split("."), target.split(".")
        if target_parts[0] == "tests":
            errors.append(f"{source} imports tests module {target}")
        elif target == _ROOT:
            if source not in root_importers:
                errors.append(f"module imports the composition root: {source} -> {target}")
        elif len(target_parts) < 3 or target_parts[:2] != ["src", "strategies"]:
            continue
        elif source == _ROOT:
            if target_parts[2] in strategies and _role(target_parts) not in _ROOT_ROLES:
                errors.append(f"composition root imports a role it may not: {source} -> {target}")
        elif len(source_parts) >= 3 and source_parts[:2] == ["src", "strategies"]:
            if error := _strategy_edge_error(source, target, strategies):
                errors.append(error)
        elif target_parts[2] == "_graham":
            errors.append(f"_graham is imported outside its member strategies: {source} -> {target}")
        elif (
            target_parts[2] in strategies
            and _role(target_parts) not in {*ANALYZER_ROLES, "selection"}
            and (source, target) not in permitted
        ):
            errors.append(f"external import exceeds analyzer/selection roles: {source} -> {target}")
    errors.extend(f"stale T13 transition entry: {source} -> {target}" for source, target in sorted(permitted - edges))
    return errors


def _file_violations(src: Path) -> list[str]:
    """Name each file in a strategy package whose role is unknown, and each non-empty initializer."""
    errors: list[str] = []
    for package in sorted(_strategy_packages(src)):
        for path in sorted((src / "strategies" / package).rglob("*.py")):
            relative = path.relative_to(src / "strategies" / package)
            if len(relative.parts) > 1 or (path.stem not in ROLE_RANK and path.stem != "__init__"):
                errors.append(f"unknown role in strategy package: {path.relative_to(src.parent).as_posix()}")
    for path in sorted((src / "strategies").rglob("__init__.py")):
        if path.stat().st_size:
            errors.append(f"strategy package initializer is not empty: {path.relative_to(src.parent).as_posix()}")
    return errors


def _cycle_violations(
    graph: dict[str, set[str]],
    init_modules: set[str],
    allowed: frozenset[str] = _BENIGN_CYCLE_PACKAGES,
) -> list[str]:
    """Check that exactly the allowed package initializers sit in an import cycle."""
    cyclic = {module for component in _cycles(graph) for module in component & init_modules}
    return [
        *(f"unapproved package cycle through {package}" for package in sorted(cyclic - allowed)),
        *(f"stale benign-cycle entry: {package}" for package in sorted(allowed - cyclic)),
    ]


def _root_importer_violations(
    edges: set[tuple[str, str]], files: set[str], importers: frozenset[str] = _ROOT_IMPORTERS
) -> list[str]:
    """Report each listed root importer that no longer exists or no longer imports the root."""
    return [
        f"stale composition-root importer entry: {importer} "
        + ("does not exist" if importer not in files else "does not import the root")
        for importer in sorted(importers)
        if (importer, _ROOT) not in edges
    ]


def _root_cycle_violations(graph: dict[str, set[str]]) -> list[str]:
    """Report the composition root if it sits in any import cycle."""
    return [
        f"composition root is in an import cycle: {sorted(component)}"
        for component in _cycles(graph)
        if _ROOT in component
    ]


def test_strategy_import_layering_and_parent_package_cycles() -> None:
    """Enforce the role graph, exact temporary transitions, file roles and the parent-aware cycle allowlist."""
    graph, edges, init_modules = _source_graph()
    errors = [
        *_edge_violations(edges, _strategy_packages(_SRC)),
        *_file_violations(_SRC),
        *_cycle_violations(graph, init_modules),
        *_root_cycle_violations(graph),
        *_root_importer_violations(edges, set(graph)),
    ]
    assert not errors, "Import-layer violations:\n" + "\n".join(errors)


def test_strategy_set_is_derived_from_the_package_directories(tmp_path: Path) -> None:
    """A new strategy package is covered without editing the test; underscore packages are not strategies."""
    for name in ("momentum", "newcomer", "_shared", "_graham", "__pycache__"):
        (tmp_path / "strategies" / name).mkdir(parents=True)
    (tmp_path / "strategies" / "__init__.py").write_text("", encoding="utf-8")
    strategies = _strategy_packages(tmp_path)
    assert strategies == {"momentum", "newcomer"}
    errors = _edge_violations(
        {("src.strategies.newcomer.analyzer", "src.strategies.momentum.analyzer")}, strategies, set()
    )
    assert errors == [
        "strategy import crosses packages: src.strategies.newcomer.analyzer -> src.strategies.momentum.analyzer"
    ]


def test_t13_fails_when_a_transition_entry_is_stale() -> None:
    """The transition list must shrink in the same change that removes an edge."""
    errors = _edge_violations(set(), _SAMPLE_STRATEGIES)
    assert "stale T13 transition entry: src.cli -> src.strategies.momentum.presenter" in errors
    assert len(errors) == len(_TRANSITIONS)


def test_t13_permits_only_the_listed_transition_edges() -> None:
    """A listed edge passes; the same importer reaching an unlisted role of that strategy fails."""
    listed = {("src.cli", "src.strategies.momentum.presenter")}
    assert _edge_violations(listed, _SAMPLE_STRATEGIES, {("src.cli", "src.strategies.momentum.presenter", "X")}) == []
    unlisted = {("src.cli", "src.strategies.momentum.cli")}
    assert _edge_violations(unlisted, _SAMPLE_STRATEGIES, set()) == [
        "external import exceeds analyzer/selection roles: src.cli -> src.strategies.momentum.cli"
    ]


def test_t13_fails_for_forbidden_role_and_cross_strategy_edges() -> None:
    """An unlisted external role edge and a cross-strategy edge fail immediately."""
    edges = {
        ("src.generic", "src.strategies.momentum.presenter"),
        ("src.strategies.momentum.analyzer", "src.strategies.graham_number.analyzer"),
    }
    errors = _edge_violations(edges, _SAMPLE_STRATEGIES, set())
    assert (
        "external import exceeds analyzer/selection roles: src.generic -> src.strategies.momentum.presenter" in errors
    )
    assert (
        "strategy import crosses packages: src.strategies.momentum.analyzer -> src.strategies.graham_number.analyzer"
        in errors
    )
    assert len(errors) == 2


def test_t13_fails_when_an_analyzer_level_file_imports_a_higher_role() -> None:
    """Analyzer-level files may import each other, and nothing above them."""
    package = "src.strategies.momentum"
    assert _edge_violations({(f"{package}.analyzer", f"{package}.calculators")}, _SAMPLE_STRATEGIES, set()) == []
    errors = _edge_violations({(f"{package}.analyzer", f"{package}.cli")}, _SAMPLE_STRATEGIES, set())
    assert errors == [f"role order is not downward: {package}.analyzer -> {package}.cli"]
    errors = _edge_violations({(f"{package}.models", f"{package}.codec")}, _SAMPLE_STRATEGIES, set())
    assert errors == [f"role order is not downward: {package}.models -> {package}.codec"]


def test_t13_allows_only_downward_imports_between_higher_roles() -> None:
    """A higher role may import any lower role, and an upward import fails."""
    package = "src.strategies.momentum"
    assert _edge_violations({(f"{package}.cli", f"{package}.presenter")}, _SAMPLE_STRATEGIES, set()) == []
    assert _edge_violations({(f"{package}.replay", f"{package}.codec")}, _SAMPLE_STRATEGIES, set()) == []
    errors = _edge_violations({(f"{package}.codec", f"{package}.presenter")}, _SAMPLE_STRATEGIES, set())
    assert errors == [f"role order is not downward: {package}.codec -> {package}.presenter"]


def test_t13_fails_when_two_different_roles_of_equal_rank_import_each_other() -> None:
    """Design §4: a file never imports a role of equal rank, except analyzer-level files among themselves."""
    package = "src.strategies.momentum"
    for first, second in (
        ("selection", "codec"),
        ("tool", "execution"),
        ("cli", "evaluation"),
        ("envelope", "analyzer"),
    ):
        for source, target in ((first, second), (second, first)):
            errors = _edge_violations({(f"{package}.{source}", f"{package}.{target}")}, _SAMPLE_STRATEGIES, set())
            assert errors == [f"same-rank roles may not import each other: {package}.{source} -> {package}.{target}"]


def test_t13_fails_for_a_file_with_an_unrecognized_role(tmp_path: Path) -> None:
    """A file whose name is not a recognized role fails and is named, wherever it sits in the package."""
    package = tmp_path / "src" / "strategies" / "momentum"
    (package / "helpers").mkdir(parents=True)
    for path in (
        package / "__init__.py",
        package / "analyzer.py",
        package / "helpers.py",
        package / "helpers" / "x.py",
    ):
        path.write_text("", encoding="utf-8")
    assert _file_violations(tmp_path / "src") == [
        "unknown role in strategy package: src/strategies/momentum/helpers/x.py",
        "unknown role in strategy package: src/strategies/momentum/helpers.py",
    ]


def test_t13_fails_for_a_non_empty_strategy_initializer(tmp_path: Path) -> None:
    """Every ``__init__.py`` under ``src/strategies`` must be empty."""
    package = tmp_path / "src" / "strategies" / "momentum"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text('"""Docstring."""\n', encoding="utf-8")
    assert _file_violations(tmp_path / "src") == [
        "strategy package initializer is not empty: src/strategies/momentum/__init__.py"
    ]


def test_t13_applies_the_shared_and_family_package_rules() -> None:
    """``_shared`` imports no strategy; ``_graham`` imports only member analyzers and is imported only by members."""
    shared = {("src.strategies._shared.profile", "src.strategies.momentum.analyzer")}
    assert _edge_violations(shared, _SAMPLE_STRATEGIES, set()) == [
        "_shared imports a strategy or family module: "
        "src.strategies._shared.profile -> src.strategies.momentum.analyzer"
    ]
    family = {
        ("src.strategies._graham.replay", "src.strategies.graham_number.analyzer"),
        ("src.strategies.graham_number.replay", "src.strategies._graham.replay"),
    }
    assert _edge_violations(family, _SAMPLE_STRATEGIES, set()) == []
    errors = _edge_violations(
        {
            ("src.strategies._graham.replay", "src.strategies.graham_number.codec"),
            ("src.strategies.momentum.replay", "src.strategies._graham.replay"),
            ("src.reporting.analysis_runs", "src.strategies._graham.replay"),
        },
        _SAMPLE_STRATEGIES,
        set(),
    )
    assert errors == [
        "_graham is imported outside its member strategies: "
        "src.reporting.analysis_runs -> src.strategies._graham.replay",
        "_graham imports beyond the analyzer modules of its members: "
        "src.strategies._graham.replay -> src.strategies.graham_number.codec",
        "_graham is imported outside its member strategies: "
        "src.strategies.momentum.replay -> src.strategies._graham.replay",
    ]


def test_t13_fails_for_a_source_module_that_imports_tests() -> None:
    """No module under ``src`` imports ``tests``."""
    errors = _edge_violations({("src.generic", "tests.helpers")}, _SAMPLE_STRATEGIES, set())
    assert errors == ["src.generic imports tests module tests.helpers"]


def test_t13_fails_for_a_new_package_cycle_outside_the_allowlist() -> None:
    """A parent initializer participating in a new cycle is not silently accepted."""
    graph = {"src.example": {"src.example.child"}, "src.example.child": {"src.example"}}
    errors = _cycle_violations(graph, {"src.example"}, frozenset())
    assert errors == ["unapproved package cycle through src.example"]


def test_t13_fails_for_a_stale_benign_cycle_entry() -> None:
    """An allowlisted package that no longer sits in a cycle must leave the list."""
    errors = _cycle_violations({"src.gone": set()}, {"src.gone"}, frozenset({"src.gone"}))
    assert errors == ["stale benign-cycle entry: src.gone"]


def test_t13_permits_the_root_to_import_only_its_strategy_roles() -> None:
    """The composition root imports analyzer, codec, envelope, replay, selection and tool files and nothing above."""
    package = "src.strategies.momentum"
    for role in sorted(_ROOT_ROLES):
        assert _edge_violations({(_ROOT, f"{package}.{role}")}, _SAMPLE_STRATEGIES, set()) == []
    for role in ("execution", "presenter", "cli", "evaluation"):
        assert _edge_violations({(_ROOT, f"{package}.{role}")}, _SAMPLE_STRATEGIES, set()) == [
            f"composition root imports a role it may not: {_ROOT} -> {package}.{role}"
        ]


def test_t13_restricts_the_importers_of_the_root() -> None:
    """Only the listed modules import the root; foundation modules never do."""
    listed = frozenset({"src.evaluation.runner", "src.cli"})
    allowed = {(importer, _ROOT) for importer in listed}
    assert _edge_violations(allowed, _SAMPLE_STRATEGIES, set(), listed) == []
    forbidden = {
        (importer, _ROOT) for importer in ("src.workspace.codecs", "src.reporting.analysis_runs", "src.data.x")
    }
    assert _edge_violations(forbidden, _SAMPLE_STRATEGIES, set(), listed) == [
        f"module imports the composition root: {importer} -> {_ROOT}"
        for importer in ("src.data.x", "src.reporting.analysis_runs", "src.workspace.codecs")
    ]


def test_t13_fails_when_the_root_is_in_an_import_cycle() -> None:
    """A module the root imports must never import the root back, directly or through others."""
    graph = {_ROOT: {"src.a"}, "src.a": {"src.b"}, "src.b": {_ROOT}, "src.c": set()}
    assert _root_cycle_violations(graph) == [
        f"composition root is in an import cycle: {sorted({_ROOT, 'src.a', 'src.b'})}"
    ]
    assert _root_cycle_violations({_ROOT: {"src.a"}, "src.a": set()}) == []


def test_the_transition_list_no_longer_holds_the_entries_removed_by_the_wiring_slice() -> None:
    """The twelve entries owned by the orchestration slice are gone; every remaining owner is a later slice."""
    assert {owner for _, _, owner in _TRANSITIONS} == {"SWC.2d", "SWC.3a", "SWC.3b", "SWC.3c", "SWC.4c"}
    assert len(_TRANSITIONS) == 32


def test_t13_fails_for_a_root_importer_entry_that_is_missing_or_does_not_import_the_root() -> None:
    """Every listed importer must exist and import the root, so an entry cannot be added ahead of its module."""
    entries = frozenset({"src.evaluation.runner", "src.cli_strategy_wiring", "src.cli"})
    edges = {("src.evaluation.runner", _ROOT), ("src.cli", "src.core.strategy_errors")}
    files = {"src.evaluation.runner", "src.cli"}
    assert _root_importer_violations(edges, files, entries) == [
        "stale composition-root importer entry: src.cli does not import the root",
        "stale composition-root importer entry: src.cli_strategy_wiring does not exist",
    ]
    assert _root_importer_violations(edges, files, frozenset({"src.evaluation.runner"})) == []
