"""Conventions for the test helpers: how a test gets a fixture, and who migrates a database.

A fixture is activated by registering it in a ``conftest.py`` and opting in, never by importing its name from a helper
module. Both checks are AST scans over the ``tests`` folder.
"""

from __future__ import annotations

import ast
from pathlib import Path

from scripts.repository_root import REPOSITORY_ROOT


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _python_files(folder: Path) -> list[Path]:
    return sorted(path for path in folder.rglob("*.py") if "__pycache__" not in path.parts)


def _is_fixture_decorator(decorator: ast.expr) -> bool:
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(target, ast.Attribute):
        return target.attr == "fixture"
    return isinstance(target, ast.Name) and target.id == "fixture"


def _module_name(path: Path, root: Path) -> str:
    return ".".join(path.relative_to(root).with_suffix("").parts)


def _fixtures_of_helper_modules(root: Path) -> dict[str, set[str]]:
    """Map each helper module (a ``_*.py`` file under ``tests``) that defines fixtures to their names."""
    fixtures: dict[str, set[str]] = {}
    for path in _python_files(root / "tests"):
        if not path.name.startswith("_") or path.name == "__init__.py":
            continue
        names = {
            node.name
            for node in ast.walk(_parse(path))
            if isinstance(node, ast.FunctionDef) and any(_is_fixture_decorator(item) for item in node.decorator_list)
        }
        if names:
            fixtures[_module_name(path, root)] = names
    return fixtures


def fixture_import_violations(root: Path) -> list[str]:
    """Return one message per import, in a ``test_*.py`` module, of a fixture defined in a helper module.

    Conftest files are not test modules and are not scanned; neither is the text of a conftest held in a string.
    """
    helpers = _fixtures_of_helper_modules(root)
    violations: list[str] = []
    for path in _python_files(root / "tests"):
        if not path.name.startswith("test_"):
            continue
        for node in ast.walk(_parse(path)):
            if not isinstance(node, ast.ImportFrom) or node.module not in helpers:
                continue
            where = f"{path.relative_to(root).as_posix()}:{node.lineno}"
            violations.extend(
                f"{where}: imports the fixture {alias.name} from {node.module}"
                for alias in node.names
                if alias.name in helpers[node.module]
            )
    return violations


def test_no_test_module_imports_a_fixture_defined_in_a_helper_module() -> None:
    """A fixture is registered in a conftest and opted into; importing its name hides the activation."""
    assert fixture_import_violations(REPOSITORY_ROOT) == []


def test_the_import_scan_reports_a_fixture_imported_into_a_test_module(tmp_path: Path) -> None:
    """The scan finds an imported fixture, and ignores an imported function and a fixture a conftest imports."""
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "_helper.py").write_text(
        "import pytest\n\n\n@pytest.fixture\ndef shared() -> None: ...\n\n\ndef plain() -> None: ...\n",
        encoding="utf-8",
    )
    (tests / "conftest.py").write_text("from tests._helper import shared\n", encoding="utf-8")
    (tests / "test_ok.py").write_text("from tests._helper import plain\n", encoding="utf-8")
    (tests / "test_bad.py").write_text("from tests._helper import plain, shared  # noqa: F401\n", encoding="utf-8")

    assert fixture_import_violations(tmp_path) == ["tests/test_bad.py:1: imports the fixture shared from tests._helper"]
