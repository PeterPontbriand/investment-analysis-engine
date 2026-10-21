"""One JSON rule: every ``json.dumps`` and ``json.dump`` call writes its characters as they are.

A call without ``ensure_ascii=False`` writes each non-ASCII character as an escape sequence (a backslash, ``u`` and
four hex digits), so the text a user reads and the text a digest or cache key is computed from would depend on which
call wrote it. The scan covers the package,
the scripts and the tests. Pydantic's ``model_dump_json`` already writes this way and needs no argument.
"""

from __future__ import annotations

import ast

from scripts.repository_root import REPOSITORY_ROOT

_ROOTS = ("investment_analysis_engine", "scripts", "tests")
_WRITERS = frozenset({"dumps", "dump"})


def calls_without_ensure_ascii_false(source: str) -> list[int]:
    """Return the line of each ``json.dumps`` or ``json.dump`` call in ``source`` that lacks ``ensure_ascii=False``.

    The call is found through ``import json``, ``import json as alias`` and ``from json import dumps``.
    """
    tree = ast.parse(source)
    modules: set[str] = set()
    functions: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.asname or alias.name for alias in node.names if alias.name == "json")
        elif isinstance(node, ast.ImportFrom) and node.module == "json":
            functions.update(alias.asname or alias.name for alias in node.names if alias.name in _WRITERS)
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        is_writer = (
            isinstance(function, ast.Attribute)
            and function.attr in _WRITERS
            and isinstance(function.value, ast.Name)
            and function.value.id in modules
        ) or (isinstance(function, ast.Name) and function.id in functions)
        if not is_writer:
            continue
        keeps_characters = any(
            keyword.arg == "ensure_ascii" and isinstance(keyword.value, ast.Constant) and keyword.value.value is False
            for keyword in node.keywords
        )
        if not keeps_characters:
            lines.append(node.lineno)
    return sorted(lines)


def test_every_json_dumps_and_dump_call_passes_ensure_ascii_false() -> None:
    found: list[str] = []
    for root in _ROOTS:
        for path in sorted((REPOSITORY_ROOT / root).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            lines = calls_without_ensure_ascii_false(path.read_text(encoding="utf-8"))
            found.extend(f"{path.relative_to(REPOSITORY_ROOT).as_posix()}:{line}" for line in lines)
    assert not found, "json.dumps and json.dump must pass ensure_ascii=False; missing at " + ", ".join(found)


def test_the_json_scan_reports_a_call_without_the_argument_and_accepts_the_rest() -> None:
    source = "\n".join(
        [
            "import json",
            "import json as j",
            "from json import dumps, dump as write",
            "json.dumps({})",  # 4: no argument
            "json.dumps({}, ensure_ascii=True)",  # 5: wrong value
            "j.dump({}, handle)",  # 6: aliased module
            "dumps({})",  # 7: imported name
            "write({}, handle)",  # 8: imported under another name
            "json.dumps({}, ensure_ascii=False)",
            "j.dumps({}, indent=2, ensure_ascii=False)",
            "json.loads('{}')",
            "other.dumps({})",
            "model.model_dump_json()",
        ]
    )

    assert calls_without_ensure_ascii_false(source) == [4, 5, 6, 7, 8]
