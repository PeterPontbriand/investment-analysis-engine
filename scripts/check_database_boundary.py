"""Database boundary checker: SQLite-specific code stays inside ``investment_analysis_engine/data/repositories/``.

Parses every Python file under ``investment_analysis_engine/`` and reports every SQLite-specific use found outside
``investment_analysis_engine/data/repositories/`` (including its ``migration_scripts/`` folder), in one run, with the
file, the line and the kind. Standard library only; it never modifies a file. Files outside
``investment_analysis_engine/`` (``tests/``, ``scripts/``) are not checked. There is no list of exceptions: code that
needs one of these moves into ``data/repositories/``.

Four kinds are reported, each under its own name:

* ``sqlite3 module``: importing ``sqlite3`` or one of its submodules, in any import form.
* ``sqlalchemy dialect``: importing ``sqlalchemy.dialects`` or anything below it, including
  ``from sqlalchemy import dialects``, or reaching it through an imported module name, as in
  ``sqlalchemy.dialects.sqlite.insert``.
* ``raw SQL``: a call to a method named ``exec_driver_sql``; importing ``text`` from ``sqlalchemy`` or from a
  ``sqlalchemy`` submodule (``from sqlalchemy import text``, ``from sqlalchemy.sql import text``); or reaching
  it through an imported module name (``sqlalchemy.text(...)``, ``sqlalchemy.sql.text(...)``).
* ``sqlite_errorcode``: reading an attribute named ``sqlite_errorcode``, or reading it by name with ``getattr`` or
  ``hasattr`` and a literal string.

A name is attributed to ``sqlalchemy`` only through the file's own import statements (at any depth, including inside
functions), so an unrelated name ``text`` is never reported. Dialect-neutral SQLAlchemy Core and URL parsing are not
reported. Known limits: a module imported by ``importlib`` or ``__import__``, a star import and a rebinding of an
imported name are not followed. Exit status is 1 when any offence is reported.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SOURCE_ROOT_NAME = "investment_analysis_engine"
ALLOWED_FOLDER = Path("data") / "repositories"
"""The one folder below the source root where SQLite-specific code is allowed."""

SQLITE3_MODULE = "sqlite3 module"
SQLALCHEMY_DIALECT = "sqlalchemy dialect"
RAW_SQL = "raw SQL"
SQLITE_ERRORCODE = "sqlite_errorcode"

_ERRORCODE_NAME = "sqlite_errorcode"
_EXEC_DRIVER_SQL = "exec_driver_sql"


@dataclass(frozen=True, order=True)
class Offence:
    """One SQLite-specific use outside the allowed folder.

    Attributes:
        path: The file, relative to the repository root, in POSIX form.
        line: The 1-based line of the use.
        kind: One of the four kind names.
        detail: What was found, for the reader.
    """

    path: str
    line: int
    kind: str
    detail: str

    def __str__(self) -> str:
        """Return the offence as ``file:line: kind: detail``."""
        return f"{self.path}:{self.line}: {self.kind}: {self.detail}"


def _is_below_sqlalchemy(parts: list[str]) -> bool:
    return bool(parts) and parts[0] == "sqlalchemy"


def _dotted(node: ast.expr) -> list[str] | None:
    """Return the names of a pure ``a.b.c`` chain, or ``None`` when the expression is anything else."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    parts.reverse()
    return parts


def _import_bindings(tree: ast.AST) -> dict[str, list[str]]:
    """Return the full dotted path each imported name stands for, from every import in the file."""
    bindings: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                full = alias.name.split(".")
                bindings[alias.asname or full[0]] = full if alias.asname else full[:1]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            module = node.module.split(".")
            for alias in node.names:
                bindings[alias.asname or alias.name] = [*module, alias.name]
    return bindings


def _import_offences(node: ast.stmt) -> list[tuple[int, str, str]]:
    """Return the offences of one import statement as ``(line, kind, detail)``."""
    found: list[tuple[int, str, str]] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            full = alias.name.split(".")
            if full[0] == "sqlite3":
                found.append((node.lineno, SQLITE3_MODULE, f"import {alias.name}"))
            elif full[:2] == ["sqlalchemy", "dialects"]:
                found.append((node.lineno, SQLALCHEMY_DIALECT, f"import {alias.name}"))
    elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
        module = node.module.split(".")
        if module[0] == "sqlite3":
            found.append((node.lineno, SQLITE3_MODULE, f"from {node.module} import ..."))
        for alias in node.names:
            full = [*module, alias.name]
            if full[:2] == ["sqlalchemy", "dialects"]:
                found.append((node.lineno, SQLALCHEMY_DIALECT, f"from {node.module} import {alias.name}"))
            elif _is_below_sqlalchemy(module) and alias.name == "text":
                found.append((node.lineno, RAW_SQL, f"from {node.module} import text"))
    return found


def _is_literal_errorcode_read(node: ast.Call) -> bool:
    """Return whether the call is ``getattr(x, "sqlite_errorcode", ...)`` or ``hasattr(x, "sqlite_errorcode")``."""
    return (
        isinstance(node.func, ast.Name)
        and node.func.id in ("getattr", "hasattr")
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value == _ERRORCODE_NAME
    )


def _use_offences(tree: ast.AST, bindings: dict[str, list[str]]) -> list[tuple[int, str, str]]:
    """Return the offences that are uses rather than imports, as ``(line, kind, detail)``."""
    found: list[tuple[int, str, str]] = []
    inner = {id(node.value) for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == _EXEC_DRIVER_SQL:
                found.append((node.lineno, RAW_SQL, f"call to {_EXEC_DRIVER_SQL}"))
            if _is_literal_errorcode_read(node):
                found.append((node.lineno, SQLITE_ERRORCODE, f"reading {_ERRORCODE_NAME} by name"))
        if not isinstance(node, ast.Attribute):
            continue
        if node.attr == _ERRORCODE_NAME and isinstance(node.ctx, ast.Load):
            found.append((node.lineno, SQLITE_ERRORCODE, f"reading attribute {_ERRORCODE_NAME}"))
        if id(node) in inner:
            continue
        chain = _dotted(node)
        if chain is None or chain[0] not in bindings:
            continue
        full = [*bindings[chain[0]], *chain[1:]]
        if full[:2] == ["sqlalchemy", "dialects"]:
            found.append((node.lineno, SQLALCHEMY_DIALECT, f"use of {'.'.join(full)}"))
        elif _is_below_sqlalchemy(full) and len(full) > 1 and full[-1] == "text":
            found.append((node.lineno, RAW_SQL, f"use of {'.'.join(full)}"))
    return found


def check_file(path: Path, display_path: str) -> list[Offence]:
    """Return every offence in one file, in line order."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = _use_offences(tree, _import_bindings(tree))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            found.extend(_import_offences(node))
    return sorted({Offence(display_path, line, kind, detail) for line, kind, detail in found})


def check_repository(repo_root: Path) -> list[Offence]:
    """Return every offence below ``repo_root``'s source root and outside the allowed folder."""
    source_root = repo_root / SOURCE_ROOT_NAME
    offences: list[Offence] = []
    for path in sorted(source_root.rglob("*.py")):
        relative = path.relative_to(source_root)
        if relative.parts[: len(ALLOWED_FOLDER.parts)] == ALLOWED_FOLDER.parts:
            continue
        offences.extend(check_file(path, (Path(SOURCE_ROOT_NAME) / relative).as_posix()))
    return offences


def main() -> int:
    """Check the repository this script lives in; print every offence; return the exit code."""
    repo_root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, check=True, text=True
        ).stdout.strip()
    )
    offences = check_repository(repo_root)
    if not offences:
        print(
            f"check_database_boundary: no SQLite-specific code outside {SOURCE_ROOT_NAME}/{ALLOWED_FOLDER.as_posix()}/."
        )
        return 0
    for offence in offences:
        print(offence)
    print(
        f"check_database_boundary: {len(offences)} offence(s); move SQLite-specific code into "
        f"{SOURCE_ROOT_NAME}/{ALLOWED_FOLDER.as_posix()}/.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
