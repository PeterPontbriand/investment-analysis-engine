"""Tests for the package dependency checker, on temporary source trees."""

from __future__ import annotations

from pathlib import Path

from scripts.check_package_dependencies import (
    ARCHITECTURE_DOC,
    SOURCE_ROOT_NAME,
    check_repository,
    collect_imports,
    list_units,
)

HEADER = "| Package | Owns | Imports | Two-way with |\n| --- | --- | --- | --- |\n"


def row(package: str, imports: tuple[str, ...] = (), two_way: tuple[str, ...] = ()) -> str:
    """Build one table row."""
    imports_cell = ", ".join(f"`{name}`" for name in imports)
    two_way_cell = ", ".join(f"`{name}`" for name in two_way)
    return f"| `{package}` | Owns something. | {imports_cell} | {two_way_cell} |\n"


def build_repo(tmp_path: Path, files: dict[str, str], rows: list[str]) -> Path:
    """Write a source tree and an architecture document holding the given table rows."""
    for relative, text in files.items():
        path = tmp_path / SOURCE_ROOT_NAME / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    doc = tmp_path / ARCHITECTURE_DOC
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(
        "# Title\n\n## 12. Planned work\n\n| a | b |\n\n## 13. Module boundaries\n\nIntro.\n\n"
        + HEADER
        + "".join(rows)
        + "\n## 14. Next\n",
        encoding="utf-8",
    )
    return tmp_path


FILES = {
    "alpha/__init__.py": "",
    "alpha/mod.py": "from src.beta.thing import value\n",
    "beta/__init__.py": "",
    "beta/thing.py": "value = 1\n",
}


def test_clean_pass(tmp_path: Path) -> None:
    root = build_repo(tmp_path, FILES, [row("alpha", ("beta",)), row("beta")])
    assert check_repository(root) == []


def test_reports_an_import_the_table_does_not_declare(tmp_path: Path) -> None:
    root = build_repo(tmp_path, FILES, [row("alpha"), row("beta")])
    findings = check_repository(root)
    assert len(findings) == 1
    assert "'alpha' imports 'beta'" in findings[0]
    assert "alpha/mod.py:1" in findings[0]
    assert "add 'beta' to the Imports cell of 'alpha'" in findings[0]


def test_reports_a_declared_import_no_code_uses(tmp_path: Path) -> None:
    root = build_repo(tmp_path, FILES, [row("alpha", ("beta",)), row("beta", ("alpha",))])
    findings = check_repository(root)
    assert len(findings) == 1
    assert "'beta' lists 'alpha'" in findings[0]
    assert "remove 'alpha' from the Imports cell of 'beta'" in findings[0]


def test_reports_a_unit_missing_from_the_table_and_a_row_with_no_unit(tmp_path: Path) -> None:
    root = build_repo(tmp_path, FILES, [row("alpha", ("beta",)), row("ghost")])
    findings = check_repository(root)
    assert any("Unit 'beta' exists" in finding and "add a row" in finding for finding in findings)
    assert any("Table row 'ghost' has no unit" in finding and "remove the row" in finding for finding in findings)


def test_reports_an_undeclared_two_way_pair(tmp_path: Path) -> None:
    files = {**FILES, "beta/back.py": "import src.alpha.mod\n"}
    root = build_repo(tmp_path, files, [row("alpha", ("beta",)), row("beta", ("alpha",))])
    findings = check_repository(root)
    assert len(findings) == 1
    assert "'alpha' and 'beta' import each other but are not declared two-way" in findings[0]


def test_reports_a_declared_two_way_pair_that_is_no_longer_two_way(tmp_path: Path) -> None:
    root = build_repo(tmp_path, FILES, [row("alpha", ("beta",), ("beta",)), row("beta", (), ("alpha",))])
    findings = check_repository(root)
    assert len(findings) == 1
    assert "'alpha' and 'beta' are declared two-way but no longer import each other" in findings[0]


def test_reports_every_finding_in_one_run(tmp_path: Path) -> None:
    root = build_repo(tmp_path, FILES, [row("alpha", ("gamma",)), row("ghost")])
    assert len(check_repository(root)) >= 4


def test_counts_an_import_inside_a_function(tmp_path: Path) -> None:
    files = {**FILES, "beta/lazy.py": "def load() -> None:\n    from src.alpha import mod\n"}
    edges = collect_imports(build_repo(tmp_path, files, [row("alpha"), row("beta")]) / SOURCE_ROOT_NAME)
    assert ("beta", "alpha") in edges
    assert edges[("beta", "alpha")][0][1] == 2


def test_groups_main_and_cli_modules_into_one_cli_unit(tmp_path: Path) -> None:
    files = {
        "__init__.py": "",
        "main.py": "from src.alpha import mod\n",
        "cli.py": "import src.beta.thing\n",
        "cli_support.py": "from src import config\n",
        "config.py": "settings = 1\n",
        "alpha/__init__.py": "",
        "alpha/mod.py": "",
        "beta/__init__.py": "",
        "beta/thing.py": "",
    }
    source_root = build_repo(tmp_path, files, [row("cli")]) / SOURCE_ROOT_NAME
    assert list_units(source_root) == {"alpha", "beta", "cli", "config"}
    edges = collect_imports(source_root)
    assert set(edges) == {("cli", "alpha"), ("cli", "beta"), ("cli", "config")}


def test_ignores_imports_within_one_unit(tmp_path: Path) -> None:
    files = {**FILES, "alpha/other.py": "from src.alpha.mod import x\n"}
    root = build_repo(tmp_path, files, [row("alpha", ("beta",)), row("beta")])
    assert check_repository(root) == []


def test_reports_a_missing_table(tmp_path: Path) -> None:
    root = build_repo(tmp_path, FILES, [])
    (root / ARCHITECTURE_DOC).write_text("# Title\n\n## 13. Module boundaries\n\nNo table.\n", encoding="utf-8")
    findings = check_repository(root)
    assert len(findings) == 1
    assert "no table found" in findings[0]


ROLE_FILES = {
    "strategies/__init__.py": "",
    "strategies/s/__init__.py": "",
    "strategies/s/analyzer.py": "VALUE = 1\n",
    "strategies/s/other.py": "from src.strategies.s import analyzer\n",
    "strategies/s/cli.py": "from src.strategies.s import analyzer\n",
    "strategies/s/evaluation.py": "from src.strategies.s import analyzer\n",
    "strategies/s/execution.py": "from src.strategies.s import analyzer\n",
    "strategies/_graham/__init__.py": "",
    "strategies/_graham/helper.py": "VALUE = 1\n",
    "strategies/_graham/cli.py": "from src.strategies._graham import helper\n",
    "strategies/_graham/deeper/cli.py": "",
    "strategies/cli.py": "",
    "user/__init__.py": "",
}


def test_role_files_of_a_strategy_package_belong_to_cli_evaluation_and_workspace(tmp_path: Path) -> None:
    source_root = build_repo(tmp_path, ROLE_FILES, []) / SOURCE_ROOT_NAME
    assert list_units(source_root) == {"cli", "evaluation", "strategies", "user", "workspace"}
    edges = collect_imports(source_root)
    assert set(edges) == {
        ("cli", "strategies"),
        ("evaluation", "strategies"),
        ("workspace", "strategies"),
    }


def test_an_import_of_a_role_file_is_attributed_to_the_file_in_both_import_forms(tmp_path: Path) -> None:
    files = {
        **ROLE_FILES,
        "user/dotted.py": "import src.strategies.s.cli\nimport src.strategies.s.evaluation\n",
        "user/named.py": (
            "from src.strategies.s import execution\nfrom src.strategies._graham import cli as graham_cli\n"
        ),
        "user/relative.py": "from ..strategies.s import cli\n",
    }
    source_root = build_repo(tmp_path, files, []) / SOURCE_ROOT_NAME
    edges = collect_imports(source_root)
    imported_by_user = {imported for importer, imported in edges if importer == "user"}
    assert imported_by_user == {"cli", "evaluation", "workspace"}
    assert [(path.as_posix(), line) for path, line in edges[("user", "cli")]] == [
        ("user/dotted.py", 1),
        ("user/named.py", 2),
        ("user/relative.py", 1),
    ]
    assert [(path.as_posix(), line) for path, line in edges[("user", "workspace")]] == [("user/named.py", 1)]


def test_any_other_file_of_a_strategy_package_stays_in_strategies(tmp_path: Path) -> None:
    files = {
        **ROLE_FILES,
        "user/named.py": (
            "from src.strategies.s import analyzer, other\n"
            "from src.strategies._graham import helper\n"
            "import src.strategies.s.analyzer\n"
            "import src.strategies._graham.deeper.cli\n"
            "from src.strategies import cli\n"
        ),
    }
    source_root = build_repo(tmp_path, files, []) / SOURCE_ROOT_NAME
    edges = collect_imports(source_root)
    assert {imported for importer, imported in edges if importer == "user"} == {"strategies"}
    assert [line for _, line in edges[("user", "strategies")]] == [1, 1, 2, 3, 4, 5]
