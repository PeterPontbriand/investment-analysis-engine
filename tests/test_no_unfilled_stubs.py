"""No generated stub is left in the package.

``scripts/new_strategy.py`` writes files whose unfilled bodies call ``unfilled_stub``. The suite fails while any such
call remains under ``investment_analysis_engine/``, naming each file and line, so a file with an unfilled body cannot
merge. The strategy generator's end-to-end test runs this module in its copy to see the stubs reported.
"""

import ast
from pathlib import Path
from typing import Final

from scripts.repository_root import REPOSITORY_ROOT

STUB_FUNCTION: Final = "unfilled_stub"
PACKAGE_FOLDER: Final = "investment_analysis_engine"


def find_unfilled_stubs(root: Path) -> list[str]:
    """Return ``path:line: unfilled_stub("<site>")`` for every call to ``unfilled_stub`` under ``root``'s package."""
    found: list[str] = []
    for path in sorted((root / PACKAGE_FOLDER).rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=relative)):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            name = function.id if isinstance(function, ast.Name) else getattr(function, "attr", None)
            if name == STUB_FUNCTION:
                site = ast.unparse(node.args[0]) if node.args else ""
                found.append(f"{relative}:{node.lineno}: {STUB_FUNCTION}({site})")
    return found


def test_t29_no_unfilled_stub_remains_in_the_package() -> None:
    """Every body in the package has been written: no call to ``unfilled_stub`` is left."""
    found = find_unfilled_stubs(REPOSITORY_ROOT)
    assert not found, "Unfilled generated bodies remain:\n" + "\n".join(found)


def test_t29_names_each_file_and_line(tmp_path: Path) -> None:
    """A call is reported with its file, its line and its site, however the function is reached."""
    package = tmp_path / PACKAGE_FOLDER / "strategies" / "fresh"
    package.mkdir(parents=True)
    (package / "codec.py").write_text(
        "from x import unfilled_stub\n\n\ndef encode() -> None:\n    unfilled_stub('codec')\n", encoding="utf-8"
    )
    (package / "cli.py").write_text("import y\n\ny.unfilled_stub('cli')\nz = 1\n", encoding="utf-8")
    assert find_unfilled_stubs(tmp_path) == [
        f"{PACKAGE_FOLDER}/strategies/fresh/cli.py:3: unfilled_stub('cli')",
        f"{PACKAGE_FOLDER}/strategies/fresh/codec.py:5: unfilled_stub('codec')",
    ]


def test_t29_ignores_a_mention_that_is_not_a_call(tmp_path: Path) -> None:
    """The definition, an import and a docstring that names the function are not unfilled bodies."""
    package = tmp_path / PACKAGE_FOLDER
    package.mkdir()
    lines = [
        '"""Mentions unfilled_stub() in a docstring."""',
        "",
        "from x import unfilled_stub",
        "",
        "reference = unfilled_stub",
    ]
    (package / "named.py").write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert find_unfilled_stubs(tmp_path) == []
