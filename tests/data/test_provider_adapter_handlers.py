"""Completion test: no provider adapter module may catch every exception.

A provider failure is classified at the adapter boundary by the library-call helper in
``src/data/provider_failure.py``, which holds the one broad catch around a third-party call. An adapter that catches
``Exception``, ``BaseException`` or everything (a bare ``except``) would report a defect as a provider outage, so the
scan fails on any such handler.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_SOURCE = Path(__file__).resolve().parents[2] / "src" / "data"
_ADAPTER_MODULES = sorted(
    [
        *(_SOURCE / "yfinance").glob("*.py"),
        *(_SOURCE / "sec_edgar").glob("*.py"),
        _SOURCE / "http_json.py",
    ]
)
_BROAD_NAMES = frozenset({"Exception", "BaseException"})


def _is_broad(handler: ast.ExceptHandler) -> bool:
    """Return whether *handler* is bare or names ``Exception``/``BaseException``, alone or in a tuple."""
    if handler.type is None:
        return True
    caught = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return any(isinstance(node, ast.Name) and node.id in _BROAD_NAMES for node in caught)


def _broad_handlers(path: Path) -> set[tuple[str, str]]:
    """Return ``(module, enclosing symbol)`` for each broad handler in *path*."""
    found: set[tuple[str, str]] = set()

    def visit(node: ast.AST, scope: tuple[str, ...]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ExceptHandler) and _is_broad(child):
                found.add((path.relative_to(_SOURCE).as_posix(), ".".join(scope) or "<module>"))
            named = isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
            visit(child, (*scope, child.name) if named else scope)  # type: ignore[attr-defined]

    visit(ast.parse(path.read_text(encoding="utf-8")), ())
    return found


def test_the_scan_covers_every_adapter_module() -> None:
    names = {path.relative_to(_SOURCE).as_posix() for path in _ADAPTER_MODULES}

    assert {
        "yfinance/client.py",
        "yfinance/financial_facts.py",
        "sec_edgar/financial_facts.py",
        "sec_edgar/filing_document.py",
        "http_json.py",
    } <= names


def test_no_adapter_module_catches_everything() -> None:
    found = {handler for path in _ADAPTER_MODULES for handler in _broad_handlers(path)}

    assert found == set()


@pytest.mark.parametrize(
    "source",
    [
        "try:\n    pass\nexcept Exception:\n    pass\n",
        "try:\n    pass\nexcept BaseException as error:\n    pass\n",
        "try:\n    pass\nexcept:\n    pass\n",
        "try:\n    pass\nexcept (OSError, Exception):\n    pass\n",
    ],
    ids=["Exception", "BaseException", "bare", "tuple containing Exception"],
)
def test_the_scan_detects_each_broad_form(source: str) -> None:
    handler = next(node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ExceptHandler))

    assert _is_broad(handler)


def test_the_scan_ignores_narrow_handlers() -> None:
    tree = ast.parse("try:\n    pass\nexcept (OSError, KeyError):\n    pass\n")
    handler = next(node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler))

    assert not _is_broad(handler)
