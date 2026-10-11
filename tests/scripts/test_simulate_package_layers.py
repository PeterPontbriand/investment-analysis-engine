"""Tests for the package-layer simulation, on temporary source trees and on the repository itself."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check_package_dependencies import collect_imports
from scripts.simulate_package_layers import (
    DEFAULT_MOVES,
    Move,
    MoveList,
    RoleRule,
    build,
    count_importers,
    layers,
    load_move_list,
    main,
    module_cycles,
    role_violations,
    shortest_cycle,
    strongly_connected,
    two_way,
    unit_graph,
)

REPO = Path(__file__).resolve().parents[2]


def tree(tmp_path: Path, files: dict[str, str]) -> Path:
    """Write a source tree below ``tmp_path`` and return the root."""
    for relative, text in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def units(root: Path, moves: MoveList | None = None) -> dict[str, set[str]]:
    """Return the unit graph of a tree with the moves applied."""
    simulation, _ = build(root, moves)
    graph, _ = unit_graph(simulation)
    return graph


def moves_of(*moves: Move, rules: tuple[RoleRule, ...] = ()) -> MoveList:
    """Build a move list."""
    return MoveList(moves, rules, {})


BASE = {
    "src/__init__.py": "",
    "src/a/__init__.py": "",
    "src/a/one.py": "from src.b.two import value\n",
    "src/b/__init__.py": "",
    "src/b/two.py": "value = 1\n",
}


def test_graph_analysis_finds_pairs_loops_and_layers() -> None:
    graph = {"a": {"b"}, "b": {"a", "c"}, "c": set(), "d": {"c"}}
    assert two_way(graph) == [("a", "b")]
    assert strongly_connected(graph) == [["a", "b"]]
    assert layers(graph) is None
    assert shortest_cycle(graph, "a") == ["a", "b", "a"]
    assert layers({"a": {"b"}, "b": set(), "c": {"b"}}) == [["b"], ["a", "c"]]


def test_today_matches_the_dependency_check(tmp_path: Path) -> None:
    root = tree(tmp_path, {**BASE, "src/b/three.py": "from . import two\nfrom src.a import one\n"})
    graph = units(root)
    expected = set(collect_imports(root / "src"))
    assert {(a, b) for a, targets in graph.items() for b in targets} == expected


def test_function_level_import_is_a_dependency_and_closes_a_loop(tmp_path: Path) -> None:
    root = tree(tmp_path, {**BASE, "src/b/two.py": "def f() -> None:\n    from src.a.one import value\n"})
    simulation, _ = build(root, None)
    graph, _ = unit_graph(simulation)
    assert two_way(graph) == [("a", "b")]
    import_time, _, deferred, _ = module_cycles(simulation)
    assert import_time == []
    assert [(edge.path, edge.lineno) for edge in deferred] == [("src/b/two.py", 2)]


def test_an_import_through_an_index_file_follows_the_name_to_its_module(tmp_path: Path) -> None:
    files = {
        **BASE,
        "src/c/__init__.py": "from src.b.two import value\n",
        "src/d/__init__.py": "",
        "src/d/user.py": "from src.c import value\n",
    }
    root = tree(tmp_path, files)
    assert units(root)["d"] == {"c", "b"}
    moved = moves_of(Move("src/b/two.py", None, "e", "x", ""))
    assert units(root, moved)["d"] == {"e"}
    simulation, _ = build(root, moved)
    assert simulation.index_edits == ["src/c/__init__.py drops the import of src.b.two (now in e)"]


def test_a_moved_file_changes_the_unit_of_the_edge_it_receives(tmp_path: Path) -> None:
    root = tree(tmp_path, BASE)
    assert units(root, moves_of(Move("src/b/two.py", None, "a", "x", "src/a/two.py")))["a"] == set()


def test_a_moved_name_leaves_the_file_and_keeps_a_dependency_when_still_used(tmp_path: Path) -> None:
    two = "import json\n\n\nclass Shape:\n    kind = json.dumps\n\n\ndef make() -> Shape:\n    return Shape()\n"
    root = tree(tmp_path, {**BASE, "src/b/two.py": two, "src/a/one.py": "from src.b.two import Shape\n"})
    graph = units(root, moves_of(Move("src/b/two.py", "Shape", "c", "x", "src/c/shape.py")))
    assert graph["a"] == {"c"}
    assert graph["b"] == {"c"}
    assert graph["c"] == set()


def test_a_moved_name_that_uses_a_name_left_behind_depends_back_on_the_file(tmp_path: Path) -> None:
    root = tree(tmp_path, {**BASE, "src/b/two.py": "LIMIT = 3\n\n\nclass Shape:\n    limit = LIMIT\n"})
    simulation, _ = build(root, moves_of(Move("src/b/two.py", "Shape", "c", "x", "")))
    assert simulation.findings == ["src/b/two.py: moved name Shape uses LIMIT, which stays in the file"]
    graph, _ = unit_graph(simulation)
    assert graph["c"] == {"b"}


def test_the_role_rule_assigns_role_files_to_other_units(tmp_path: Path) -> None:
    files = {
        "src/__init__.py": "",
        "src/strategies/__init__.py": "",
        "src/strategies/s/__init__.py": "",
        "src/strategies/s/analyzer.py": "",
        "src/strategies/s/cli.py": "from src.strategies.s import analyzer\n",
        "src/strategies/s/presenter.py": "from src.strategies.s import execution\n",
        "src/strategies/s/execution.py": "from src.strategies.s import analyzer\n",
    }
    rules = (RoleRule("src/strategies", {"cli": "cli", "execution": "workspace"}),)
    root = tree(tmp_path, files)
    simulation, _ = build(root, moves_of(rules=rules))
    graph, _ = unit_graph(simulation)
    assert graph["cli"] == {"strategies"}
    assert graph["workspace"] == {"strategies"}
    assert role_violations(simulation, rules) == ["src/strategies/s/presenter.py:1 -> src/strategies/s/execution.py"]


def test_importers_are_counted_by_kind(tmp_path: Path) -> None:
    files = {**BASE, "tests/test_one.py": "from src.b.two import value\nPATCH = 'src.b.two.value'\n"}
    root = tree(tmp_path, files)
    counts = count_importers(root, moves_of(Move("src/b/two.py", None, "c", "x", "")))
    assert (counts[0].source_files, counts[0].test_files, counts[0].string_reference_files) == (1, 1, 1)


def test_main_prints_both_reports(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tree(tmp_path, BASE)
    moves = tmp_path / "moves.toml"
    moves.write_text('[[file]]\npath = "src/b/two.py"\nunit = "c"\nserves = "x"\n', encoding="utf-8")
    assert main(["--root", str(root), "--moves", str(moves), "--importers", "--table"]) == 0
    out = capsys.readouterr().out
    assert "== today ==" in out
    assert "== target ==" in out
    assert "Layered order" in out
    assert "| Package | Owns | Imports |" in out


def test_a_move_list_with_a_missing_field_is_rejected(tmp_path: Path) -> None:
    moves = tmp_path / "moves.toml"
    moves.write_text('[[file]]\npath = "src/b/two.py"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="lacks"):
        load_move_list(moves)


# --- the repository itself ---------------------------------------------------------------------------------


def test_every_listed_source_exists_and_the_target_has_no_loop() -> None:
    move_list = load_move_list(REPO / DEFAULT_MOVES)
    simulation, modules = build(REPO, move_list)
    paths = {module.path for module in modules.values()}
    assert [move.key for move in move_list.moves if move.path not in paths] == []
    assert simulation.findings == []
    graph, _ = unit_graph(simulation)
    assert strongly_connected(graph) == []
    assert layers(graph) is not None
