"""No file under ``src/`` raises ``typer.BadParameter``.

A check a command makes in its own code raises ``InvalidParameterError`` and is reported as an ``invalid_parameter``
failure with exit 1. Exit 2 means the parser rejected the command line, so no command code may produce it. The scan
reads the syntax tree, not the text, so a comment or a string that names the class is not a finding.
"""

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
_FORBIDDEN = frozenset({"BadParameter"})


def _called_name(node: ast.expr) -> str | None:
    """Return the last name of a called class or function: ``typer.BadParameter`` and ``BadParameter`` give the same."""
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def bad_parameter_sites(source: str, filename: str) -> list[str]:
    """Return ``file:line`` for each place the source raises or constructs a forbidden usage error."""
    sites: list[str] = []
    for node in ast.walk(ast.parse(source, filename=filename)):
        if isinstance(node, ast.Raise) and node.exc is not None:
            raised = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
            if _called_name(raised) in _FORBIDDEN:
                sites.append(f"{filename}:{node.lineno}")
        elif isinstance(node, ast.Call) and _called_name(node.func) in _FORBIDDEN:
            sites.append(f"{filename}:{node.lineno}")
    return sorted(set(sites))


def test_no_file_under_src_raises_bad_parameter() -> None:
    sites: list[str] = []
    for path in sorted(_SRC.rglob("*.py")):
        sites.extend(bad_parameter_sites(path.read_text(encoding="utf-8"), path.relative_to(_SRC.parent).as_posix()))
    assert not sites, "typer.BadParameter is raised at: " + ", ".join(sites)


def test_the_scan_finds_a_raise_and_names_the_file_and_line() -> None:
    source = "import typer\n\n\ndef check() -> None:\n    raise typer.BadParameter('x')\n"
    assert bad_parameter_sites(source, "src/example.py") == ["src/example.py:5"]
    assert bad_parameter_sites("from typer import BadParameter\n\nraise BadParameter\n", "src/other.py") == [
        "src/other.py:3"
    ]


def test_the_scan_ignores_text_that_only_names_the_class() -> None:
    source = '"""Mentions typer.BadParameter."""\n# raise typer.BadParameter\nNAME = "BadParameter"\n'
    assert bad_parameter_sites(source, "src/example.py") == []
