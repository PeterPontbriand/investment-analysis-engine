"""The generator's end-to-end test: a throwaway strategy goes through the whole contributor path in a copy.

This is the only end-to-end proof of the layers the specimen strategy cannot reach: the ``ToolName`` member, the
``AnalysisSelection`` union, the ``StrategyBehavior`` bounds and the real ``execute`` with ``AnalysisRun`` validation.
In a temporary copy of the repository the test runs the generator for ``ci_probe``, type-checks the whole copy and
lints what it wrote, fills every site the generator does not write from the hand-written data in ``generator_fills/``,
regenerates the schema and the strategy lists, and requires every site done, the strict type check and the conformance
tests to pass. Every subprocess has a fixed ``PYTHONHASHSEED``, no proxy variables, bytecode writing off and a
timeout, and none makes a network call.

The conformance tests run the files below, with no test deselected: a test that names the production strategies
reads the descriptors instead, and the expected-output files and tables a new strategy writes by hand are sites that
the fills write. Three more files hold tests that a strategy does not change; the main gate runs them whole, and here
only the tests whose node id names the strategy's alias or module run.
"""

import ast
import os
import re
import shutil
import subprocess
import sys
import textwrap
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

import pytest

from scripts.new_strategy import PACKAGE, STUB_ROLES, ruff_clean
from scripts.repository_root import REPOSITORY_ROOT
from scripts.strategy_sites import load_sites
from tests._migrated_database import ALEMBIC_INI

MODULE: Final = "ci_probe"
ALIAS: Final = "ci-probe"
LABEL: Final = "CI Probe"
TIMEOUT_SECONDS: Final = 300
STRICT_TARGETS: Final = ("investment_analysis_engine", "tests", "scripts")
"""The folders of the guide's strict type check, which covers every file a strategy can break."""
FILLS: Final = Path(__file__).resolve().parent / "generator_fills"

COPIED_FOLDERS: Final = ("investment_analysis_engine", "scripts", "tests", "schemas", "docs")
COPIED_FILES: Final = ("pyproject.toml", ALEMBIC_INI.name)
EXCLUDED: Final = ("__pycache__", "*.pyc", ".mypy_cache", ".ruff_cache", ".pytest_cache", "htmlcov", "*.egg-info")
PROXY_VARIABLES: Final = frozenset({"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "FTP_PROXY"})

STUB_FILL_ROLES: Final = ("analyzer", "codec", "application", "presenter", "replay", "evaluation")
"""The generated files with a body the fills write; the others are complete as generated.

The tool handler is complete as generated: its body validates the arguments, builds the context and calls the analyzer.
"""

NOT_DONE_UNTIL_FILLED: Final = frozenset({"codec", "presenter", "replay"})
"""Generated sites whose check runs a stored run, which needs the evaluation file's sample selection to be written."""

NOT_GENERATED_AND_DONE: Final = frozenset({"settings", "watchlist-options"})
"""Sites the generator does not write that are done without a fill: the strategy has no settings and no extra flags."""

CONFORMANCE_TESTS: Final = (
    "tests/test_no_unfilled_stubs.py",
    "tests/test_strategy_wiring_conformance.py",
    "tests/test_save_run_every_direct_command.py",
    "tests/test_strategy_wiring.py",
    "tests/test_cli_strategy_wiring.py",
    "tests/test_strategy_import_layering.py",
    "tests/test_strategy_settings.py",
    "tests/test_provider_check_element.py",
    "tests/test_direct_command_output.py",
    "tests/test_strategy_document_output.py",
    "tests/test_cli_help_output.py",
    "tests/test_one_home_per_name.py",
    "tests/test_specimen_strategy.py",
    "tests/evaluation/test_catalog.py",
    "tests/evaluation/test_composition.py",
    "tests/evaluation/test_models.py",
    "tests/orchestrator/test_analysis_tools.py",
    "tests/reporting/test_strategy_document_shape.py",
    "tests/reporting/test_strategy_documents.py",
    "tests/scripts/test_generate_schemas.py",
    "tests/scripts/test_generate_strategy_docs.py",
    "tests/scripts/test_strategy_sites.py",
    "tests/scripts/test_strategy_status.py",
    "tests/schema",
    "tests/workspace/test_workspace_fail_closed.py",
)

PER_STRATEGY_TESTS: Final = (
    "tests/test_failure_messages.py",
    "tests/test_cli_workspace.py",
    "tests/test_command_validation_failures.py",
)
"""Files whose tests are parametrized over the strategies; only the nodes naming the strategy run in the copy."""

EXPECTED_FILLS: Final = {
    "direct.txt": "tests/expected_output/direct_commands/ci-probe.txt",
    "direct.json": "tests/expected_output/direct_commands/ci-probe.json",
    "document.direct.json": "tests/expected_output/strategy_documents/ci-probe-success.direct.json",
    "document.replay.json": "tests/expected_output/strategy_documents/ci-probe-success.replay.json",
    "help.txt": "tests/expected_output/cli_help/ci-probe.txt",
    "help.add-selection.txt": "tests/expected_output/cli_help/watchlist-add-selection-ci-probe.txt",
}
"""The reviewed expected-output files of the strategy, by fill name in ``generator_fills/expected/``."""


def _environment() -> dict[str, str]:
    """Return the environment of every subprocess: no proxy, no engine settings, a fixed hash seed, no bytecode."""
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() not in PROXY_VARIABLES and not key.upper().startswith("IAN_") and key != "PYTHONPATH"
    }
    environment.update({"PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"})
    return environment


def _run(copy: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run ``python <arguments>`` in the copy and return the completed process."""
    return subprocess.run(  # noqa: S603 - the interpreter running this test, with arguments built here
        [sys.executable, *arguments],
        cwd=copy,
        env=_environment(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=TIMEOUT_SECONDS,
        check=False,
    )


def _output(process: subprocess.CompletedProcess[str]) -> str:
    return f"exit {process.returncode}\n{process.stdout}\n{process.stderr}"


def _copy_repository(destination: Path) -> None:
    """Copy the folders and files the contributor path touches, leaving out caches."""
    for folder in COPIED_FOLDERS:
        shutil.copytree(REPOSITORY_ROOT / folder, destination / folder, ignore=shutil.ignore_patterns(*EXCLUDED))
    for name in COPIED_FILES:
        shutil.copyfile(REPOSITORY_ROOT / name, destination / name)


def _status(copy: Path) -> tuple[int, dict[str, tuple[str, list[str]]]]:
    """Run the status command for ``ci_probe``; return its exit code and, per site, its state and diagnostics."""
    process = _run(copy, "-m", "scripts.strategy_status", MODULE)
    sites: dict[str, tuple[str, list[str]]] = {}
    current = ""
    for line in process.stdout.splitlines():
        header = re.match(r"(done|missing|covered)\s+(\S+)\s", line)
        if header is not None:
            current = header.group(2)
            sites[current] = (header.group(1), [])
        elif line.startswith("    ") and current:
            sites[current][1].append(line.strip())
    return process.returncode, sites


def _assert_strict_types(copy: Path) -> None:
    """Type-check the whole copy with the command the contributor guide documents, not only the touched files."""
    process = _run(copy, "-m", "mypy", "--strict", *STRICT_TARGETS)
    assert process.returncode == 0, _output(process)


def _assert_ruff_clean(copy: Path) -> None:
    for arguments in (("check", "--no-cache", "."), ("format", "--check", ".")):
        process = _run(copy, "-m", "ruff", *arguments)
        assert process.returncode == 0, f"ruff {' '.join(arguments)}\n{_output(process)}"


FILL_MARKER: Final = re.compile(r"#: (body|add) (\S+)")
"""The line that opens a section of a fill: a body to put into a stub, or a whole definition to add."""


def _definitions(tree: ast.Module) -> dict[str, ast.stmt]:
    """Return the top-level definitions by name, and each method of a top-level class as ``Class.method``."""
    found: dict[str, ast.stmt] = {}
    for node in tree.body:
        name = None
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            name = node.name
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
        if name is None:
            continue
        found[name] = node
        if isinstance(node, ast.ClassDef):
            found.update(
                {f"{name}.{member.name}": member for member in node.body if isinstance(member, ast.FunctionDef)}
            )
    return found


def _stub_statements(function: ast.FunctionDef) -> list[ast.stmt]:
    """Return the statements after the docstring of ``function``; none unless the last calls ``unfilled_stub``."""
    body = function.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    last = body[-1] if body else None
    calls_stub = (
        isinstance(last, ast.Expr)
        and isinstance(last.value, ast.Call)
        and isinstance(last.value.func, ast.Name)
        and last.value.func.id == "unfilled_stub"
    )
    return body if calls_stub else []


def _split_fill(fill: str, name: str) -> tuple[str, list[tuple[str, str, str]]]:
    """Split a fill into its imports and its sections ``(kind, definition name, text)``."""
    imports: list[str] = []
    sections: list[tuple[str, str, list[str]]] = []
    for line in fill.splitlines(keepends=True):
        marker = FILL_MARKER.fullmatch(line.rstrip("\n"))
        if marker is not None:
            sections.append((marker.group(1), marker.group(2), []))
        elif sections:
            sections[-1][2].append(line)
        else:
            imports.append(line)
    assert all(isinstance(node, ast.Import | ast.ImportFrom) for node in ast.parse("".join(imports)).body), (
        f"{name}: only imports come before the first section"
    )
    seen = [definition for _, definition, _ in sections]
    assert len(seen) == len(set(seen)), f"{name}: a definition is named twice"
    return "".join(imports), [(kind, definition, "".join(lines).strip("\n")) for kind, definition, lines in sections]


def fill_source(generated: str, fill: str, *, name: str) -> str:
    """Return ``generated`` completed from ``fill``, the file named ``name``.

    A fill holds its imports and then sections, each opened by a line ``#: <kind> <definition>``:

    - ``body``: the statements that replace the stub of a function (``Name``) or a method (``Class.name``). The
      definition keeps the signature, decorators and docstring the template generated; the replaced lines are the
      ones after the docstring, ending with the ``unfilled_stub`` call.
    - ``add``: a whole definition that no template generates; the generated file must not define its name.

    A section that names a definition the generated file lacks, a ``body`` for a definition with no stub, an ``add``
    or an ``add`` of a name the file defines fails, naming the fill and the definition.
    The imports follow the generated file's last import, and the caller's Ruff pass sorts them and drops the unused.
    """
    imports, sections = _split_fill(fill, name)
    tree = ast.parse(generated)
    defined = _definitions(tree)
    lines = generated.splitlines(keepends=True)
    replacements: dict[int, tuple[int, str]] = {}
    added: list[str] = []
    for kind, definition, text in sections:
        node = defined.get(definition)
        if kind == "add":
            assert node is None, f"{name}: {definition} is generated already, so it takes a body"
            added.append(text)
            continue
        assert node is not None, f"{name}: the generated file has no definition {definition}"
        assert isinstance(node, ast.FunctionDef), f"{name}: {definition} is not a function or a method"
        stub = _stub_statements(node)
        assert stub, f"{name}: {definition} has no stub to put a body into"
        assert stub[-1].end_lineno is not None
        indented = textwrap.indent(text, " " * (node.col_offset + 4))
        replacements[stub[0].lineno] = (stub[-1].end_lineno, indented + "\n")
    last_import = max(
        (node.end_lineno or 0 for node in tree.body if isinstance(node, ast.Import | ast.ImportFrom)), default=0
    )
    out: list[str] = []
    line = 1
    while line <= len(lines):
        if line in replacements:
            end, text = replacements[line]
            out.append(text)
            line = end + 1
            continue
        out.append(lines[line - 1])
        if line == last_import:
            out.append(imports)
        line += 1
    return "".join(out).rstrip("\n") + "".join(f"\n\n\n{text}" for text in added) + "\n"


def _apply_patch(text: str, patch: dict[str, Any], where: str) -> str:
    """Apply one reviewed edit: replace ``old`` with ``new``, or bump the integer in each match of ``bump``."""
    if "bump" in patch:
        pattern = re.compile(patch["bump"])
        assert len(pattern.findall(text)) == patch["count"], f"{where}: anchor {patch['bump']!r} moved"

        def successor(match: re.Match[str]) -> str:
            before, after = match.start(1) - match.start(), match.end(1) - match.start()
            return f"{match.group()[:before]}{int(match.group(1)) + 1}{match.group()[after:]}"

        return pattern.sub(successor, text)
    assert text.count(patch["old"]) == patch["count"], f"{where}: anchor {patch['old']!r} moved"
    return text.replace(patch["old"], patch["new"])


def _apply_fills(copy: Path) -> None:
    """Complete the stubs from the fills and make the reviewed edits to existing files."""
    package = copy / PACKAGE
    for role in STUB_FILL_ROLES:
        path = package / "strategies" / MODULE / f"{role}.py"
        fill = f"{role}.py.fill"
        filled = fill_source(path.read_text(encoding="utf-8"), (FILLS / fill).read_text(encoding="utf-8"), name=fill)
        path.write_text(ruff_clean(copy, path, filled), encoding="utf-8", newline="\n")
    shutil.copyfile(FILLS / "cases.py.fill", package / "evaluation" / "cases" / f"{MODULE}.py")
    shutil.copyfile(FILLS / "guide.md.fill", copy / "docs" / "user" / "strategies" / "CI_PROBE.md")
    for name, destination in EXPECTED_FILLS.items():
        shutil.copyfile(FILLS / "expected" / name, copy / destination)
    patches = tomllib.loads((FILLS / "patches.toml").read_text(encoding="utf-8"))["patch"]
    for patch in patches:
        target = copy / patch["path"]
        patched = _apply_patch(target.read_text(encoding="utf-8"), patch, patch["path"])
        target.write_text(patched, encoding="utf-8", newline="\n")
    for target in sorted({copy / patch["path"] for patch in patches if patch["path"].endswith(".py")}):
        cleaned = ruff_clean(copy, target, target.read_text(encoding="utf-8"))
        target.write_text(cleaned, encoding="utf-8", newline="\n")


def _conformance_arguments(*extra: str) -> list[str]:
    return ["-m", "pytest", "--no-cov", "-p", "no:cacheprovider", "-q", "--color=no", *extra]


def _selected_nodes_run_and_pass(copy: Path) -> subprocess.CompletedProcess[str]:
    """Run the nodes of the per-strategy files that name the strategy; at least one must be found."""
    return _run(copy, *_conformance_arguments("-k", f"{ALIAS} or {MODULE}", *PER_STRATEGY_TESTS))


def test_t28_the_generator_takes_a_strategy_through_the_whole_contributor_path(tmp_path: Path) -> None:
    """Generate, type-check, fill, regenerate and run the conformance tests for a throwaway strategy in a copy."""
    sites = load_sites()
    copy = tmp_path / "repository"
    _copy_repository(copy)

    # 1. The generator writes the stubs and the edits; the status command and the stub test report what is left.
    generated = _run(copy, "-m", "scripts.new_strategy", MODULE, "--label", LABEL)
    assert generated.returncode == 0, _output(generated)
    code, state = _status(copy)
    assert code == 1, state
    for site in sites:
        found, messages = state[site.id]
        assert found != "covered", f"{site.id} is reported as covered by this test: {messages}"
        assert not any("UnfilledStubError" in message for message in messages), f"{site.id}: {messages}"
        if site.id in STUB_FILL_ROLES:
            file = f"{PACKAGE}/strategies/{MODULE}/{site.id}.py"
            assert found == "missing", f"{site.id} still calls unfilled_stub but is {found}"
            assert any(message.startswith(f"{file}:") and "calls unfilled_stub(" in message for message in messages), (
                f"{site.id}: {messages}"
            )
            if site.id in NOT_DONE_UNTIL_FILLED:
                dependency = (
                    f"not checked: depends on unfilled evaluation ({PACKAGE}/strategies/{MODULE}/evaluation.py:"
                )
                assert any(message.startswith(dependency) for message in messages), f"{site.id}: {messages}"
        elif site.generated or site.id in NOT_GENERATED_AND_DONE:
            assert found == "done", f"{site.id}: {messages}"
        else:
            assert found == "missing", site.id
    stubs = _run(copy, *_conformance_arguments("--tb=short", "tests/test_no_unfilled_stubs.py"))
    assert stubs.returncode != 0, _output(stubs)
    for role in STUB_FILL_ROLES:
        assert f"{PACKAGE}/strategies/{MODULE}/{role}.py:" in stubs.stdout, f"{role} not reported:\n{stubs.stdout}"

    # 2. The typed stubs type-check as written, and the generator's output needs no manual Ruff fixing.
    _assert_strict_types(copy)
    _assert_ruff_clean(copy)

    # 3. Fill every site the generator does not write, then regenerate the schema and the strategy lists.
    _apply_fills(copy)
    for command in (("-m", "scripts.generate_schemas"), ("-m", "scripts.generate_strategy_docs")):
        process = _run(copy, *command)
        assert process.returncode == 0, _output(process)
    _assert_ruff_clean(copy)

    # 4. Every site is done, with none left to this test; the strict type check and the conformance tests pass.
    code, state = _status(copy)
    assert code == 0, state
    assert {found for found, _ in state.values()} == {"done"}, state
    assert not any("T28" in message for _, messages in state.values() for message in messages)
    _assert_strict_types(copy)
    conformance = _run(copy, *_conformance_arguments(*CONFORMANCE_TESTS))
    assert conformance.returncode == 0, _output(conformance)
    selected = _selected_nodes_run_and_pass(copy)
    assert selected.returncode == 0, _output(selected)


def test_no_conformance_test_is_deselected() -> None:
    """Every conformance test runs in the copy: the list of deselected tests stays empty."""
    listed = tomllib.loads((FILLS / "deselected.toml").read_text(encoding="utf-8")).get("test", [])
    assert listed == [], "a test that fails in the copy is made derived or a site, not deselected"


def test_the_conformance_test_files_exist() -> None:
    """Every file or folder the end-to-end test runs exists in the repository."""
    absent: Sequence[str] = [name for name in CONFORMANCE_TESTS if not (REPOSITORY_ROOT / name).exists()]
    assert not absent
    assert set(STUB_FILL_ROLES) <= set(STUB_ROLES)
    for role in STUB_FILL_ROLES:
        assert (FILLS / f"{role}.py.fill").is_file()
    for name in EXPECTED_FILLS:
        assert (FILLS / "expected" / name).is_file()
    for name in PER_STRATEGY_TESTS:
        assert (REPOSITORY_ROOT / name).is_file()


_GENERATED: Final = '''"""A generated file."""

from investment_analysis_engine.core.strategy_stub import unfilled_stub


class Thing:
    """A class."""

    def method(self, value: int, *, extra: int = 0) -> int:
        """Return a number."""
        del value, extra
        unfilled_stub("thing")


def function(value: int) -> int:
    """Return another number."""
    return value


def stubbed(value: int) -> int:
    """Return a third number."""
    del value
    unfilled_stub("thing")
'''


def test_a_body_goes_into_the_generated_signature_and_nothing_else_of_the_definition_changes() -> None:
    """The signature, the docstring and the lines around the stub stay as generated, however the signature changes."""
    fill = (
        "from math import pi\n\n#: body Thing.method\ndel extra\nreturn value\n\n#: body stubbed\ndel value\nreturn 3\n"
    )
    filled = fill_source(_GENERATED, fill, name="x.py.fill")
    assert "def method(self, value: int, *, extra: int = 0) -> int:" in filled
    assert '        """Return a number."""\n        del extra\n        return value\n' in filled
    assert '    """Return a third number."""\n    del value\n    return 3\n' in filled
    assert "unfilled_stub(" not in filled.replace("import unfilled_stub", "")
    assert "from math import pi" in filled
    ast.parse(filled)


@pytest.mark.parametrize(
    ("fill", "message"),
    [
        ("#: body missing\nreturn 1\n", "x.py.fill: the generated file has no definition missing"),
        ("#: body function\nreturn 1\n", "x.py.fill: function has no stub to put a body into"),
        ("#: body Thing\nreturn 1\n", "x.py.fill: Thing is not a function or a method"),
        ("#: add function\ndef function() -> None: ...\n", "x.py.fill: function is generated already"),
        ("#: body stubbed\nreturn 1\n#: body stubbed\nreturn 2\n", "x.py.fill: a definition is named twice"),
        ("return 1\n#: body stubbed\nreturn 1\n", "x.py.fill: only imports come before the first section"),
    ],
)
def test_a_fill_that_does_not_match_the_generated_file_fails_naming_the_fill_and_the_definition(
    fill: str, message: str
) -> None:
    """A section for an absent definition, a definition without a stub, or a whole function is refused."""
    with pytest.raises(AssertionError, match=re.escape(message)):
        fill_source(_GENERATED, fill, name="x.py.fill")


def test_a_bump_patch_writes_the_successor_of_each_integer_it_finds() -> None:
    """The reviewed edit moves a version or a count by one from the file as it stands, never from a quoted value."""
    text = 'VERSION: Final = "h1-v9"\nassert total == 21\nassert failed == 0\n'
    bumped = _apply_patch(text, {"bump": r'VERSION: Final = "[^"]*?(\d+)"', "count": 1}, "x")
    assert bumped == 'VERSION: Final = "h1-v10"\nassert total == 21\nassert failed == 0\n'
    counted = _apply_patch(text, {"bump": r"== (\d\d+)\n", "count": 1}, "x")
    assert counted == 'VERSION: Final = "h1-v9"\nassert total == 22\nassert failed == 0\n'
    with pytest.raises(AssertionError, match="moved"):
        _apply_patch(text, {"bump": r"== (\d\d+)\n", "count": 2}, "x")
