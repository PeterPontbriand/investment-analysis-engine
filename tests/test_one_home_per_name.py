"""A name has one import path, and the package root has one definition.

Three checks over the source tree: package initializers hold only a docstring, no module lists in ``__all__`` a
name it does not define, and no file counts folders up from ``__file__`` except where the package root is
defined. The repository-root constant for tests and scripts is checked last.
"""

from __future__ import annotations

import ast
from pathlib import Path

from scripts.repository_root import REPOSITORY_ROOT

_SOURCE_FOLDERS = ("investment_analysis_engine", "tests", "scripts")
# The one initializer that holds code: the settings themselves, not a re-export of its children.
_INITIALIZER_WITH_CODE = "investment_analysis_engine/config/__init__.py"
# Files that may count folders up from ``__file__``, once each: the definition of the package root, and the
# script that runs before ``investment_analysis_engine`` is importable and so cannot import it.
_FOLDER_COUNT_ALLOWED = frozenset(
    {"investment_analysis_engine/core/package_root.py", "scripts/check_package_dependencies.py"}
)

# The repository root is defined once, for tests and scripts, in this file; nothing else derives it.
_REPOSITORY_ROOT_DEFINITION = "scripts/repository_root.py"
_DERIVATION = "PACKAGE_ROOT" + ".parent"
_DERIVATION_MESSAGE = "derives the repository root; import REPOSITORY_ROOT from scripts.repository_root instead"


def _python_files(root: Path, folder: str) -> list[Path]:
    return sorted(path for path in (root / folder).rglob("*.py") if "__pycache__" not in path.parts)


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def initializer_violations(root: Path) -> list[str]:
    """Return one message per statement, in a package initializer, that is not its docstring."""
    violations: list[str] = []
    for path in _python_files(root, "investment_analysis_engine"):
        name = _relative(path, root)
        if path.name != "__init__.py" or name == _INITIALIZER_WITH_CODE:
            continue
        body = _parse(path).body
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            body = body[1:]
        violations.extend(
            f"{name}:{statement.lineno}: package initializer holds more than a docstring" for statement in body
        )
    return violations


def _defined_names(statements: list[ast.stmt]) -> set[str]:
    """Return the names a module body defines itself: not the ones it imports."""
    defined: set[str] = set()
    for statement in statements:
        if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            defined.add(statement.name)
        elif isinstance(statement, ast.TypeAlias):
            defined.add(ast.unparse(statement.name))
        elif isinstance(statement, ast.Assign):
            defined.update(target.id for target in statement.targets if isinstance(target, ast.Name))
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            defined.add(statement.target.id)
        elif isinstance(statement, ast.If | ast.Try | ast.With):
            blocks = [statement.body, getattr(statement, "orelse", []), getattr(statement, "finalbody", [])]
            blocks.extend(handler.body for handler in getattr(statement, "handlers", []))
            for block in blocks:
                defined |= _defined_names(block)
    return defined


def _all_declaration(statements: list[ast.stmt]) -> tuple[int, ast.expr | None] | None:
    """Return the line and value of the module's ``__all__`` assignment, if it has one."""
    for statement in statements:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__all__" for target in statement.targets
        ):
            return statement.lineno, statement.value
        if (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == "__all__"
        ):
            return statement.lineno, statement.value
    return None


def export_violations(root: Path) -> list[str]:
    """Return one message per name a module lists in ``__all__`` without defining it."""
    violations: list[str] = []
    for path in _python_files(root, "investment_analysis_engine"):
        module = _parse(path)
        declaration = _all_declaration(module.body)
        if declaration is None:
            continue
        line, value = declaration
        name = _relative(path, root)
        if not isinstance(value, ast.List | ast.Tuple) or not all(
            isinstance(element, ast.Constant) and isinstance(element.value, str) for element in value.elts
        ):
            violations.append(f"{name}:{line}: __all__ is not a literal list of names")
            continue
        defined = _defined_names(module.body)
        violations.extend(
            f"{name}:{element.lineno}: __all__ lists {element.value!r}, which this module does not define"
            for element in value.elts
            if isinstance(element, ast.Constant) and element.value not in defined
        )
    return violations


def _call_steps(call: ast.Call, derived: set[str]) -> int | None:
    """Return the folders climbed by ``Path(...)``, ``.resolve()``, ``.absolute()`` or ``dirname(...)``."""
    function = call.func
    if isinstance(function, ast.Attribute) and function.attr in {"resolve", "absolute"}:
        return _folder_steps(function.value, derived)
    if isinstance(function, ast.Name) and function.id == "Path" and len(call.args) == 1:
        return _folder_steps(call.args[0], derived)
    if isinstance(function, ast.Attribute) and function.attr == "dirname" and len(call.args) == 1:
        inner = _folder_steps(call.args[0], derived)
        return None if inner is None else inner + 1
    return None


def _parents_steps(node: ast.Subscript, derived: set[str]) -> int | None:
    """Return the folders climbed by ``<path>.parents[N]``."""
    index = node.slice
    if not (isinstance(node.value, ast.Attribute) and node.value.attr == "parents"):
        return None
    inner = _folder_steps(node.value.value, derived)
    if inner is None or not isinstance(index, ast.Constant) or not isinstance(index.value, int):
        return None
    return inner + index.value + 1


def _folder_steps(node: ast.AST, derived: set[str]) -> int | None:
    """Return how many folders ``node`` climbs from ``__file__``, or None when it is not such an expression."""
    if isinstance(node, ast.Name):
        return 0 if node.id == "__file__" or node.id in derived else None
    if isinstance(node, ast.Attribute):
        inner = _folder_steps(node.value, derived)
        if inner is None:
            return None
        return inner + 1 if node.attr == "parent" else inner
    if isinstance(node, ast.Subscript):
        return _parents_steps(node, derived)
    if isinstance(node, ast.Call):
        return _call_steps(node, derived)
    return None


def _mentions_file(node: ast.AST) -> bool:
    return any(isinstance(child, ast.Name) and child.id == "__file__" for child in ast.walk(node))


def folder_count_lines(path: Path) -> list[int]:
    """Return the lines of ``path`` that climb two or more folders from ``__file__``, directly or through a name."""
    module = _parse(path)
    derived = {
        target.id
        for statement in ast.walk(module)
        if isinstance(statement, ast.Assign) and _mentions_file(statement.value)
        for target in statement.targets
        if isinstance(target, ast.Name)
    }
    lines: set[int] = set()
    for node in ast.walk(module):
        if isinstance(node, ast.Attribute | ast.Subscript | ast.Call):
            steps = _folder_steps(node, derived)
            if steps is not None and steps >= 2:
                lines.add(node.lineno)
    return sorted(lines)


def folder_count_violations(root: Path) -> list[str]:
    """Return one message per folder count applied to ``__file__`` beyond the allowed one per allowed file."""
    violations: list[str] = []
    for folder in _SOURCE_FOLDERS:
        for path in _python_files(root, folder):
            name = _relative(path, root)
            lines = folder_count_lines(path)
            if name in _FOLDER_COUNT_ALLOWED:
                lines = lines[1:]
            violations.extend(
                f"{name}:{line}: counts folders up from __file__; import PACKAGE_ROOT from "
                "investment_analysis_engine.core.package_root instead"
                for line in lines
            )
    return violations


def repository_root_derivation_violations(root: Path) -> list[str]:
    """Return one message per file, other than the definition, that derives the repository root."""
    return [
        f"{_relative(path, root)}: {_DERIVATION_MESSAGE}"
        for folder in _SOURCE_FOLDERS
        for path in _python_files(root, folder)
        if _relative(path, root) != _REPOSITORY_ROOT_DEFINITION and _DERIVATION in path.read_text(encoding="utf-8")
    ]


def test_package_initializers_hold_only_a_docstring() -> None:
    assert initializer_violations(REPOSITORY_ROOT) == []


def test_no_module_exports_a_name_it_does_not_define() -> None:
    assert export_violations(REPOSITORY_ROOT) == []


def test_no_file_counts_folders_up_from_itself() -> None:
    assert folder_count_violations(REPOSITORY_ROOT) == []


def test_the_repository_root_is_derived_in_one_file(tmp_path: Path) -> None:
    assert repository_root_derivation_violations(REPOSITORY_ROOT) == []
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "repository_root.py").write_text(f"ROOT = {_DERIVATION}\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_offender.py").write_text(f"ROOT = {_DERIVATION} / 'x'\n", encoding="utf-8")

    assert repository_root_derivation_violations(tmp_path) == [f"tests/test_offender.py: {_DERIVATION_MESSAGE}"]


def test_repository_root_holds_the_project_file() -> None:
    assert (REPOSITORY_ROOT / "pyproject.toml").is_file()
