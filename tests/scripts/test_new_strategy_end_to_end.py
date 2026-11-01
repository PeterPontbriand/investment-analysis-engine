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
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Final

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

STUB_FILL_ROLES: Final = ("analyzer", "codec", "execution", "cli", "presenter", "replay", "evaluation")
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


def _statement_name(node: ast.stmt) -> str | None:
    """Return the name a top-level function, class or single-name assignment defines, or ``None``."""
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        return node.name
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    return None


def _first_line(node: ast.stmt) -> int:
    """Return the first line of a statement, counting its decorators."""
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        return min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)])
    return node.lineno


def _is_docstring_statement(node: ast.stmt) -> bool:
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)


def fill_source(generated: str, fill: str) -> str:
    """Return ``generated`` with each definition in ``fill`` replacing the one of the same name.

    A fill holds only the imports and the definitions (functions, classes and single-name assignments, each with the
    string that documents it) that complete a generated file; its own module docstring is ignored. A name the generated
    file does not define is inserted before the next fill definition that it does define, or at the end of the file.
    The imports follow the generated file's last import, and the caller's Ruff pass sorts them and drops the unused.
    """
    lines = generated.splitlines(keepends=True)
    fill_lines = fill.splitlines(keepends=True)
    by_name = {name: node for node in ast.parse(generated).body if (name := _statement_name(node)) is not None}
    imports: list[str] = []
    groups: list[tuple[str, str]] = []
    for index, node in enumerate(ast.parse(fill).body):
        end = node.end_lineno
        assert end is not None
        text = "".join(fill_lines[_first_line(node) - 1 : end])
        if isinstance(node, ast.Import | ast.ImportFrom):
            imports.append(text)
        elif (name := _statement_name(node)) is not None:
            groups.append((name, text))
        elif _is_docstring_statement(node) and index > 0 and groups:
            groups[-1] = (groups[-1][0], groups[-1][1] + text)
        else:
            assert _is_docstring_statement(node), f"a fill holds only imports and definitions: {text!r}"
            assert index == 0, f"a fill's only free-standing string is its docstring: {text!r}"
    insertions: dict[int, list[str]] = {}
    replacements: dict[int, tuple[int, str]] = {}
    for position, (name, text) in enumerate(groups):
        if name in by_name:
            node = by_name[name]
            assert node.end_lineno is not None
            replacements[_first_line(node)] = (node.end_lineno, text)
            continue
        later = next((by_name[other] for other, _ in groups[position + 1 :] if other in by_name), None)
        insertions.setdefault(_first_line(later) if later is not None else len(lines) + 1, []).append(text)
    last_import = max(
        (node.end_lineno or 0 for node in ast.parse(generated).body if isinstance(node, ast.Import | ast.ImportFrom)),
        default=0,
    )
    insertions.setdefault(last_import + 1, []).extend(imports)
    out: list[str] = []
    line = 1
    while line <= len(lines) + 1:
        for text in insertions.get(line, []):
            out.append(text if text.startswith(("from ", "import ")) else text.rstrip() + "\n\n\n")
        if line in replacements:
            end, text = replacements[line]
            out.append(text)
            line = end + 1
            continue
        if line <= len(lines):
            out.append(lines[line - 1])
        line += 1
    return "".join(out)


def _apply_fills(copy: Path) -> None:
    """Complete the stubs from the fills and make the reviewed edits to existing files."""
    package = copy / PACKAGE
    for role in STUB_FILL_ROLES:
        path = package / "strategies" / MODULE / f"{role}.py"
        filled = fill_source(path.read_text(encoding="utf-8"), (FILLS / f"{role}.py.fill").read_text(encoding="utf-8"))
        path.write_text(ruff_clean(copy, path, filled), encoding="utf-8", newline="\n")
    shutil.copyfile(FILLS / "cases.py.fill", package / "evaluation" / "cases" / f"{MODULE}.py")
    shutil.copyfile(FILLS / "guide.md.fill", copy / "docs" / "user" / "strategies" / "CI_PROBE.md")
    for name, destination in EXPECTED_FILLS.items():
        shutil.copyfile(FILLS / "expected" / name, copy / destination)
    patches = tomllib.loads((FILLS / "patches.toml").read_text(encoding="utf-8"))["patch"]
    for patch in patches:
        target = copy / patch["path"]
        text = target.read_text(encoding="utf-8")
        assert text.count(patch["old"]) == patch["count"], f"{patch['path']}: anchor {patch['old']!r} moved"
        target.write_text(text.replace(patch["old"], patch["new"]), encoding="utf-8", newline="\n")


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
