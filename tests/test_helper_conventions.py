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


# A module belongs here only when its subject is migration; any other module that needs a migrated database copies the
# template through ``migrated_database_url`` or the ``migrated_database`` fixture.
_MIGRATION_TESTS = frozenset(
    {
        "tests/_migrated_database.py",
        "tests/data/repositories/test_migrations.py",
        "tests/data/repositories/test_persistence_smoke.py",
        "tests/data/repositories/test_readiness_concurrency.py",
        "tests/data/repositories/test_schema.py",
    }
)
_THIS_FILE = "tests/test_helper_conventions.py"
_INI_NAME = "alembic" + ".ini"
_UPGRADE_HELPER = "upgrade_to_head"
_RULE = "only a module whose subject is migration may; the others use tests._migrated_database.migrated_database_url"


def _upgrade_helper_names(tree: ast.Module) -> set[str]:
    """Return every name under which a module can call the upgrade helper: its own name and any import alias."""
    names = {_UPGRADE_HELPER}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names if alias.name == _UPGRADE_HELPER)
    return names


def migration_violations(root: Path) -> list[str]:
    """Return one message per place, under ``tests``, that names the Alembic ini file or upgrades a database to head.

    That is: the ini file's name, a ``command.upgrade(..., "head")`` call, and any call to ``upgrade_to_head``, as a
    bare name, an import alias or an attribute. The modules in ``_MIGRATION_TESTS`` are exempt, and so is this scan,
    which spells all three.
    """
    violations: list[str] = []
    for path in _python_files(root / "tests"):
        name = path.relative_to(root).as_posix()
        if name in _MIGRATION_TESTS or name == _THIS_FILE:
            continue
        tree = _parse(path)
        helper_names = _upgrade_helper_names(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == _INI_NAME:
                violations.append(f"{name}:{node.lineno}: names {_INI_NAME}; {_RULE}")
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            if (
                isinstance(function, ast.Attribute)
                and function.attr == "upgrade"
                and any(isinstance(argument, ast.Constant) and argument.value == "head" for argument in node.args)
            ):
                violations.append(f"{name}:{node.lineno}: upgrades to head; {_RULE}")
            elif (isinstance(function, ast.Name) and function.id in helper_names) or (
                isinstance(function, ast.Attribute) and function.attr == _UPGRADE_HELPER
            ):
                violations.append(f"{name}:{node.lineno}: calls {_UPGRADE_HELPER}; {_RULE}")
    return violations


def test_no_test_names_the_alembic_ini_or_upgrades_to_head_outside_the_migration_modules() -> None:
    """A test that needs a migrated database copies the template; only the modules that test migration upgrade."""
    assert migration_violations(REPOSITORY_ROOT) == []


def test_the_migration_scan_reports_the_ini_file_and_every_upgrade_to_head_outside_the_migration_modules(
    tmp_path: Path,
) -> None:
    tests = tmp_path / "tests"
    (tests / "data" / "repositories").mkdir(parents=True)
    (tests / "test_ini.py").write_text(f'CONFIG = "{_INI_NAME}"\n', encoding="utf-8")
    (tests / "test_head.py").write_text('command.upgrade(config, "head")\ncommand.upgrade(config, "0001")\n')
    (tests / "test_bare.py").write_text("from tests._migrated_database import upgrade_to_head\nupgrade_to_head(c)\n")
    (tests / "test_alias.py").write_text("from tests._migrated_database import upgrade_to_head as up\nup(c)\n")
    (tests / "test_attribute.py").write_text("import tests._migrated_database as m\nm.upgrade_to_head(c)\n")
    (tests / "test_ok.py").write_text('command.downgrade(config, "base")\nalembic_config(url)\n', encoding="utf-8")
    (tests / "data" / "repositories" / "test_schema.py").write_text("upgrade_to_head(c)\n", encoding="utf-8")

    assert migration_violations(tmp_path) == [
        f"tests/test_alias.py:2: calls {_UPGRADE_HELPER}; {_RULE}",
        f"tests/test_attribute.py:2: calls {_UPGRADE_HELPER}; {_RULE}",
        f"tests/test_bare.py:2: calls {_UPGRADE_HELPER}; {_RULE}",
        f"tests/test_head.py:1: upgrades to head; {_RULE}",
        f"tests/test_ini.py:1: names {_INI_NAME}; {_RULE}",
    ]
