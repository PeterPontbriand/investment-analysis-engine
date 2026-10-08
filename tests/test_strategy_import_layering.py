"""Keep strategy imports within their declared role layers.

The role rule is design §4: a file's role is its file name inside its strategy package; within a
package a file may import only a lower-ranked role, except that analyzer-level files may import each
other; no strategy imports another; code outside ``src/strategies`` may import only analyzer and
selection roles, except that a case module under ``src/evaluation/cases`` may also import the tool role
of the strategy package it is named for. Only a strategy's ``evaluation`` file imports from
``src/evaluation``, and only the fixture-id, fixture-context and fixture modules. The CLI tier imports only the
``cli`` role of a strategy package, and only the listed CLI modules import the tier. Imports of ``__init__.py``
files count, and every ``__init__.py`` under ``src/strategies`` must be empty.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

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
_ROOT_IMPORTERS = frozenset(
    {
        "src.evaluation.composition",
        "src.evaluation.runner",
        "src.evaluation.ollama_runner",
        "src.evaluation.strategy_fixtures",
        "src.cli_strategy_wiring",
        "src.cli_run_support",
        "src.cli_workspace",
    }
)
# The evaluation tier pairs each strategy's fixture composition with its core bundle. It may import the root
# and the ``evaluation`` file of each strategy package, and only the generic evaluation modules listed here
# import it. As for the root, an entry must exist and import the tier.
_TIER = "src.evaluation.strategy_fixtures"
_TIER_IMPORTERS = frozenset({"src.evaluation.composition"})
# A strategy's ``evaluation`` file (and ``_graham/evaluation.py``) may import exactly these modules from
# ``src.evaluation``: the case-level context and its checks, and the fixture modules, which also hold the
# fixture identifiers. It never imports the composition, the tier, the catalog, the cases or the runners.
_STRATEGY_EVALUATION_IMPORTS = frozenset({"src.evaluation.fixture_context"})
_FIXTURE_MODULE_PREFIX = "src.evaluation.fixtures."
# The CLI tier pairs each strategy's watchlist selection builder and refresh executor with its core bundle. It
# may import the root and the ``cli`` file of each strategy package, and only the CLI modules listed here import
# it. As for the root, an entry must exist and import the tier.
_CLI_TIER = "src.cli_strategy_wiring"
_CLI_TIER_IMPORTERS = frozenset({"src.cli", "src.cli_workspace"})
# The modules only listed importers may import: the root and the two tiers, with the name each is reported by.
_IMPORTERS = MappingProxyType({_ROOT: _ROOT_IMPORTERS, _TIER: _TIER_IMPORTERS, _CLI_TIER: _CLI_TIER_IMPORTERS})
_RESTRICTED_MODULES = MappingProxyType(
    {_ROOT: "the composition root", _TIER: "the evaluation tier", _CLI_TIER: "the CLI tier"}
)
# Each tier's report name and the one strategy role it may import.
_TIER_ROLES = MappingProxyType({_TIER: ("evaluation tier", "evaluation"), _CLI_TIER: ("CLI tier", "cli")})
_TRANSITIONS: set[tuple[str, str, str]] = set()
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


def _is_own_case_tool(source_parts: list[str], target_parts: list[str]) -> bool:
    """Return whether a case module imports the tool role of the strategy package it is named for."""
    return (
        len(source_parts) == 4
        and source_parts[:3] == ["src", "evaluation", "cases"]
        and target_parts[2] == source_parts[3]
        and _role(target_parts) == "tool"
    )


def _is_strategy_evaluation(source_parts: list[str]) -> bool:
    """Return whether a module is the ``evaluation`` file of a strategy or family package."""
    return len(source_parts) == 4 and source_parts[:2] == ["src", "strategies"] and source_parts[3] == "evaluation"


def _strategy_evaluation_may_import(target: str) -> bool:
    """Return whether a strategy's ``evaluation`` file may import ``target`` from ``src.evaluation``."""
    return target in _STRATEGY_EVALUATION_IMPORTS or target.startswith(_FIXTURE_MODULE_PREFIX)


def _boundary_error(source: str, target: str, importers: Mapping[str, frozenset[str]]) -> str | None:
    """Report an import of ``tests``, of the root or a tier by a module not listed, or beyond the fixture modules."""
    source_parts, target_parts = source.split("."), target.split(".")
    if target_parts[0] == "tests":
        return f"{source} imports tests module {target}"
    if target in importers and source not in importers[target]:
        return f"module imports {_RESTRICTED_MODULES[target]}: {source} -> {target}"
    if (
        _is_strategy_evaluation(source_parts)
        and target_parts[:2] == ["src", "evaluation"]
        and target != _TIER
        and not _strategy_evaluation_may_import(target)
    ):
        return f"strategy evaluation file imports beyond the fixture modules: {source} -> {target}"
    if (
        len(source_parts) >= 4
        and source_parts[:2] == ["src", "strategies"]
        and source_parts[3] != "evaluation"
        and target_parts[:2] == ["src", "evaluation"]
    ):
        return f"strategy file other than evaluation imports the evaluation package: {source} -> {target}"
    return None


def _edge_violations(
    edges: set[tuple[str, str]],
    strategies: frozenset[str],
    transitions: set[tuple[str, str, str]] = _TRANSITIONS,
    importers: Mapping[str, frozenset[str]] = _IMPORTERS,
) -> list[str]:
    """Check strategy boundaries, role order, the exact transition edges and imports of ``tests``."""
    errors: list[str] = []
    permitted = {(source, target) for source, target, _ in transitions}
    for source, target in sorted(edges):
        source_parts, target_parts = source.split("."), target.split(".")
        if error := _boundary_error(source, target, importers):
            errors.append(error)
        elif len(target_parts) < 3 or target_parts[:2] != ["src", "strategies"]:
            continue
        elif source == _ROOT:
            if target_parts[2] in strategies and _role(target_parts) not in _ROOT_ROLES:
                errors.append(f"composition root imports a role it may not: {source} -> {target}")
        elif source in _TIER_ROLES:
            name, role = _TIER_ROLES[source]
            if target_parts[2] not in strategies or _role(target_parts) != role:
                errors.append(f"{name} imports a role it may not: {source} -> {target}")
        elif len(source_parts) >= 3 and source_parts[:2] == ["src", "strategies"]:
            if error := _strategy_edge_error(source, target, strategies):
                errors.append(error)
        elif target_parts[2] == "_graham":
            errors.append(f"_graham is imported outside its member strategies: {source} -> {target}")
        elif (
            target_parts[2] in strategies
            and _role(target_parts) not in {*ANALYZER_ROLES, "selection"}
            and (source, target) not in permitted
            and not _is_own_case_tool(source_parts, target_parts)
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


def _tier_importer_violations(
    edges: set[tuple[str, str]], files: set[str], importers: frozenset[str] = _TIER_IMPORTERS
) -> list[str]:
    """Report each listed evaluation-tier importer that no longer exists or no longer imports the tier."""
    return [
        f"stale evaluation-tier importer entry: {importer} "
        + ("does not exist" if importer not in files else "does not import the tier")
        for importer in sorted(importers)
        if (importer, _TIER) not in edges
    ]


def _cli_tier_importer_violations(
    edges: set[tuple[str, str]], files: set[str], importers: frozenset[str] = _CLI_TIER_IMPORTERS
) -> list[str]:
    """Report each listed CLI-tier importer that no longer exists or no longer imports the tier."""
    return [
        f"stale CLI-tier importer entry: {importer} "
        + ("does not exist" if importer not in files else "does not import the tier")
        for importer in sorted(importers)
        if (importer, _CLI_TIER) not in edges
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
        *_tier_importer_violations(edges, set(graph)),
        *_cli_tier_importer_violations(edges, set(graph)),
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
    listed = {("src.reporting.analysis_runs", "src.strategies.momentum.presenter", "X")}
    errors = _edge_violations(set(), _SAMPLE_STRATEGIES, listed)
    assert errors == ["stale T13 transition entry: src.reporting.analysis_runs -> src.strategies.momentum.presenter"]


def test_t13_permits_only_the_listed_transition_edges() -> None:
    """A listed edge passes; the same importer reaching an unlisted role of that strategy fails."""
    listed = {("src.reporting.analysis_runs", "src.strategies.momentum.presenter")}
    assert (
        _edge_violations(
            listed, _SAMPLE_STRATEGIES, {("src.reporting.analysis_runs", "src.strategies.momentum.presenter", "X")}
        )
        == []
    )
    unlisted = {("src.reporting.analysis_runs", "src.strategies.momentum.cli")}
    assert _edge_violations(unlisted, _SAMPLE_STRATEGIES, set()) == [
        "external import exceeds analyzer/selection roles: src.reporting.analysis_runs -> src.strategies.momentum.cli"
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
    assert _edge_violations(allowed, _SAMPLE_STRATEGIES, set(), {_ROOT: listed}) == []
    forbidden = {
        (importer, _ROOT) for importer in ("src.workspace.codecs", "src.reporting.analysis_runs", "src.data.x")
    }
    assert _edge_violations(forbidden, _SAMPLE_STRATEGIES, set(), {_ROOT: listed}) == [
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


def test_the_transition_list_is_empty() -> None:
    """Every slice that owned a transition edge has removed it; SWC.7 verifies the list stays empty."""
    assert set() == _TRANSITIONS


def test_the_transition_list_no_longer_holds_the_entries_removed_by_the_direct_commands_slice() -> None:
    """The eight direct-command entries are gone: ``src.cli`` imports no strategy execution adapter or presenter."""
    assert not [entry for entry in _TRANSITIONS if entry[2] == "SWC.3c"]
    assert not [entry for entry in _TRANSITIONS if entry[0] == "src.cli"]


def test_the_transition_list_no_longer_holds_the_entries_removed_by_the_cli_tier_slice() -> None:
    """The four CLI-tier entries are gone: the workspace CLI module imports no strategy execution adapter."""
    assert not [entry for entry in _TRANSITIONS if entry[2] == "SWC.3b"]
    assert not [entry for entry in _TRANSITIONS if entry[0] == "src.cli_workspace"]


def test_the_transition_list_no_longer_holds_the_entries_removed_by_the_workspace_consumers_slice() -> None:
    """The eight workspace-consumer entries are gone: neither workspace module imports a strategy codec or adapter."""
    assert not [entry for entry in _TRANSITIONS if entry[2] == "SWC.3a"]
    assert not [entry for entry in _TRANSITIONS if entry[0] in {"src.workspace.codecs", "src.workspace.execution"}]


def test_the_transition_list_no_longer_holds_the_entries_removed_by_the_evaluation_slice() -> None:
    """The eight evaluation-slice entries are gone: no transition names an evaluation module or SWC.2d."""
    assert not [entry for entry in _TRANSITIONS if entry[2] == "SWC.2d" or entry[0].startswith("src.evaluation")]
    assert not {entry for entry in _TRANSITIONS if entry[0] in {"src.evaluation.composition", "src.evaluation.catalog"}}


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


def test_t13_restricts_the_importers_of_the_evaluation_tier() -> None:
    """Only the listed generic evaluation modules import the tier; nothing else does."""
    listed = frozenset({"src.evaluation.composition"})
    allowed = {("src.evaluation.composition", _TIER)}
    assert _edge_violations(allowed, _SAMPLE_STRATEGIES, set(), {_TIER: listed}) == []
    importers = ("src.cli", "src.evaluation.catalog", "src.strategies.momentum.cli")
    forbidden = {(importer, _TIER) for importer in importers}
    assert _edge_violations(forbidden, _SAMPLE_STRATEGIES, set(), {_TIER: listed}) == [
        f"module imports the evaluation tier: {importer} -> {_TIER}" for importer in importers
    ]


def test_t13_fails_for_a_tier_importer_entry_that_is_missing_or_does_not_import_the_tier() -> None:
    """Every listed tier importer must exist and import the tier, so an entry cannot outlive its import."""
    entries = frozenset({"src.evaluation.composition", "src.evaluation.gone", "src.evaluation.catalog"})
    edges = {("src.evaluation.composition", _TIER), ("src.evaluation.catalog", "src.core.strategy_errors")}
    files = {"src.evaluation.composition", "src.evaluation.catalog"}
    assert _tier_importer_violations(edges, files, entries) == [
        "stale evaluation-tier importer entry: src.evaluation.catalog does not import the tier",
        "stale evaluation-tier importer entry: src.evaluation.gone does not exist",
    ]
    assert _tier_importer_violations(edges, files, frozenset({"src.evaluation.composition"})) == []


def test_t13_permits_the_tier_to_import_only_the_root_and_strategy_evaluation_files() -> None:
    """The tier imports the root and a strategy's evaluation file; no other role and not the family package."""
    package = "src.strategies.momentum"
    ok = {(_TIER, _ROOT), (_TIER, f"{package}.evaluation")}
    assert _edge_violations(ok, _SAMPLE_STRATEGIES, set()) == []
    bad = {(_TIER, f"{package}.tool"), (_TIER, f"{package}.analyzer"), (_TIER, "src.strategies._graham.evaluation")}
    assert _edge_violations(bad, _SAMPLE_STRATEGIES, set()) == [
        f"evaluation tier imports a role it may not: {_TIER} -> {target}"
        for target in ("src.strategies._graham.evaluation", f"{package}.analyzer", f"{package}.tool")
    ]


def test_t13_limits_what_a_strategy_evaluation_file_imports_from_the_evaluation_package() -> None:
    """A strategy's evaluation file (and the family's) imports the fixture modules and context, nothing else."""
    for source in ("src.strategies.momentum.evaluation", "src.strategies._graham.evaluation"):
        allowed = {
            (source, "src.evaluation.fixture_context"),
            (source, "src.evaluation.fixtures.graham"),
            (source, "src.evaluation.fixtures.market_data"),
        }
        assert _edge_violations(allowed, _SAMPLE_STRATEGIES, set()) == []
        forbidden = [
            "src.evaluation",
            "src.evaluation.cases.momentum",
            "src.evaluation.catalog",
            "src.evaluation.composition",
            "src.evaluation.fixtures",
            "src.evaluation.models",
            "src.evaluation.runner",
        ]
        assert _edge_violations({(source, target) for target in forbidden}, _SAMPLE_STRATEGIES, set()) == [
            f"strategy evaluation file imports beyond the fixture modules: {source} -> {target}" for target in forbidden
        ]
    assert _edge_violations({("src.strategies.momentum.evaluation", _TIER)}, _SAMPLE_STRATEGIES, set()) == [
        f"module imports the evaluation tier: src.strategies.momentum.evaluation -> {_TIER}"
    ]


def test_t13_permits_a_case_module_to_import_only_its_own_strategys_tool_role() -> None:
    """A case module is single-strategy: it may import the tool role of the package it is named for, and no more."""
    cases = "src.evaluation.cases"
    allowed = {
        (f"{cases}.momentum", "src.strategies.momentum.tool"),
        (f"{cases}.graham_number", "src.strategies.graham_number.tool"),
        (f"{cases}.momentum", "src.strategies.momentum.analyzer"),
    }
    assert _edge_violations(allowed, _SAMPLE_STRATEGIES, set()) == []
    forbidden = {
        (f"{cases}.momentum", "src.strategies.graham_number.tool"),
        (f"{cases}.momentum", "src.strategies.momentum.codec"),
        (f"{cases}.momentum", "src.strategies.momentum.evaluation"),
        (f"{cases}.graham_number", "src.strategies.graham_growth.tool"),
        (f"{cases}.helpers", "src.strategies.momentum.tool"),
        ("src.evaluation.catalog", "src.strategies.momentum.tool"),
        ("src.evaluation.composition", "src.strategies.momentum.tool"),
    }
    assert _edge_violations(forbidden, _SAMPLE_STRATEGIES, set()) == [
        f"external import exceeds analyzer/selection roles: {source} -> {target}"
        for source, target in sorted(forbidden)
    ]


def test_t13_keeps_every_other_strategy_file_out_of_the_evaluation_package() -> None:
    """Only a strategy's evaluation file may import from ``src.evaluation``; no other role may."""
    edges = {
        ("src.strategies.momentum.analyzer", "src.evaluation.fixture_context"),
        ("src.strategies.momentum.tool", "src.evaluation.composition"),
        ("src.strategies._shared.profile", "src.evaluation.models"),
    }
    assert _edge_violations(edges, _SAMPLE_STRATEGIES, set()) == [
        f"strategy file other than evaluation imports the evaluation package: {source} -> {target}"
        for source, target in sorted(edges)
    ]


def test_t13_restricts_the_importers_of_the_cli_tier() -> None:
    """Only the listed CLI modules import the CLI tier; nothing else does, not even a strategy's own cli file."""
    listed = frozenset({"src.cli_workspace"})
    allowed = {("src.cli_workspace", _CLI_TIER)}
    assert _edge_violations(allowed, _SAMPLE_STRATEGIES, set(), {_CLI_TIER: listed}) == []
    importers = ("src.evaluation.composition", "src.reporting.analysis_runs", "src.strategies.momentum.cli")
    forbidden = {(importer, _CLI_TIER) for importer in importers}
    assert _edge_violations(forbidden, _SAMPLE_STRATEGIES, set(), {_CLI_TIER: listed}) == [
        f"module imports the CLI tier: {importer} -> {_CLI_TIER}" for importer in importers
    ]


def test_t13_fails_for_a_cli_tier_importer_entry_that_is_missing_or_does_not_import_the_tier() -> None:
    """Every listed CLI-tier importer must exist and import the tier, so an entry cannot outlive its import."""
    entries = frozenset({"src.cli", "src.cli_gone", "src.cli_workspace"})
    edges = {("src.cli_workspace", _CLI_TIER), ("src.cli", "src.cli_support")}
    files = {"src.cli", "src.cli_workspace"}
    assert _cli_tier_importer_violations(edges, files, entries) == [
        "stale CLI-tier importer entry: src.cli does not import the tier",
        "stale CLI-tier importer entry: src.cli_gone does not exist",
    ]
    assert _cli_tier_importer_violations(edges, files, frozenset({"src.cli_workspace"})) == []


def test_t13_permits_the_cli_tier_to_import_only_the_root_and_strategy_cli_files() -> None:
    """The CLI tier imports the root and a strategy's cli file; no other role and not the family package."""
    package = "src.strategies.momentum"
    ok = {(_CLI_TIER, _ROOT), (_CLI_TIER, f"{package}.cli")}
    assert _edge_violations(ok, _SAMPLE_STRATEGIES, set()) == []
    bad = {
        (_CLI_TIER, f"{package}.execution"),
        (_CLI_TIER, f"{package}.analyzer"),
        (_CLI_TIER, f"{package}.evaluation"),
        (_CLI_TIER, "src.strategies._graham.replay"),
    }
    assert _edge_violations(bad, _SAMPLE_STRATEGIES, set()) == [
        f"CLI tier imports a role it may not: {_CLI_TIER} -> {target}"
        for target in (
            "src.strategies._graham.replay",
            f"{package}.analyzer",
            f"{package}.evaluation",
            f"{package}.execution",
        )
    ]


def test_t13_lists_the_cli_tier_as_an_importer_of_the_root() -> None:
    """The CLI tier pairs its entries with the core bundles, so it is a listed root importer; a stray module is not."""
    assert _CLI_TIER in _ROOT_IMPORTERS
    assert _edge_violations({(_CLI_TIER, _ROOT)}, _SAMPLE_STRATEGIES, set()) == []
    assert _edge_violations({("src.strategies.momentum.cli", _ROOT)}, _SAMPLE_STRATEGIES, set()) == [
        f"module imports the composition root: src.strategies.momentum.cli -> {_ROOT}"
    ]
