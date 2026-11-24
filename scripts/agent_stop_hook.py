"""Claude Code Stop hook: run the slice check when an agent ends a turn with unchecked changes.

Claude Code runs this script when the implementer finishes responding and passes a JSON event on standard input. The
script checks only when files changed since its last passing run: it runs the documentation checks for a
documentation-only change and the slice check (the quality-gate wrapper with its slice option) otherwise. A failure is
written to standard error and the script exits with status 2, which makes Claude Code send it back to the agent. The
script never loops (it exits at once when ``stop_hook_active`` is set) and stops the agent on issue #116 evidence.
Standard library only.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

STATE_FOLDER: Final[Path] = Path(".tmp") / "agent-stop-hook"
LAST_PASS_FILE: Final[Path] = STATE_FOLDER / "last-pass"
"""Where the fingerprint of the last passing run is stored, relative to the repository root."""

FAILURE_TAIL_LINES: Final[int] = 40
EXIT_PASSED: Final[int] = 0
EXIT_SEND_BACK: Final[int] = 2

ISSUE_116_MESSAGE: Final[str] = (
    "Issue #116 evidence: stop, keep this run directory, report to the spec author, and re-run nothing (AGENTS.md §10)."
)
ISSUE_116_MARKERS: Final[tuple[str, ...]] = ("winerror 10055", "socket snapshot")

DOCUMENTATION_CHECK_SCRIPTS: Final[tuple[str, ...]] = (
    "scripts/check_doc_links.py",
    "scripts/check_help_content.py",
    "scripts/check_sequence_tables.py",
    "scripts/check_package_dependencies.py",
)
RUFF_CHECKS: Final[tuple[tuple[str, ...], ...]] = (
    ("uv", "run", "--no-sync", "ruff", "check", "."),
    ("uv", "run", "--no-sync", "ruff", "format", "--check", "."),
)
GATE_OUTPUT_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\S.*gate-output\.txt\s*$", re.MULTILINE)
FAILED_STEP_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\s+(?P<name>.+?)\s+FAILED\s+[\d.]+ s\s*$", re.MULTILINE)


def should_check(
    event: Mapping[str, Any],
    paths: Sequence[str],
    current_fingerprint: str,
    last_pass: str | None,
) -> bool:
    """Return whether the checks must run for this Stop event."""
    if event.get("stop_hook_active") is True:
        return False
    if not paths:
        return False
    return current_fingerprint != last_pass


def fingerprint(head: str, diff: bytes, untracked: Mapping[str, bytes]) -> str:
    """Return the SHA-256 digest over HEAD, the diff against HEAD and each untracked file's path and bytes."""
    digest = hashlib.sha256()
    digest.update(head.encode("utf-8"))
    digest.update(b"\0")
    digest.update(diff)
    for path in sorted(untracked):
        digest.update(b"\0")
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(untracked[path])
    return digest.hexdigest()


def summarize_failure(output: str) -> str:
    """Return the message sent back to the agent for a failed check, given its complete output."""
    lowered = output.lower()
    if any(marker in lowered for marker in ISSUE_116_MARKERS):
        return ISSUE_116_MESSAGE
    lines = output.splitlines()
    failed_steps = [name for name in (m.group("name") for m in FAILED_STEP_PATTERN.finditer(output)) if name != "total"]
    if failed_steps:
        report = ["Failing steps: " + ", ".join(failed_steps)]
    else:
        report = [f"Last {FAILURE_TAIL_LINES} lines of output:", *lines[-FAILURE_TAIL_LINES:]]
    gate_output = GATE_OUTPUT_PATTERN.findall(output)
    if gate_output:
        report.append(f"Complete output: {gate_output[-1].strip()}")
    return "\n".join(report)


def wrapper_command(platform: str) -> list[str]:
    """Return the slice-check command for a platform name such as ``sys.platform``."""
    if platform.startswith("win"):
        return [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "scripts/run-quality-gates.ps1",
            "-Slice",
        ]
    return ["bash", "scripts/run-quality-gates.sh", "--slice"]


def documentation_commands(python: str) -> list[list[str]]:
    """Return the documentation checks, each as a command line, using the given interpreter."""
    commands = [[python, script] for script in DOCUMENTATION_CHECK_SCRIPTS]
    commands.extend(list(check) for check in RUFF_CHECKS)
    return commands


def plan_checks(
    paths: Sequence[str], is_docs_only: Callable[[Sequence[str]], bool], platform: str, python: str
) -> list[list[str]]:
    """Choose the commands to run for the changed paths."""
    if is_docs_only(paths):
        return documentation_commands(python)
    return [wrapper_command(platform)]


def run_git(root: Path, *args: str) -> bytes:
    """Run a git command in the repository and return its standard output."""
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, check=True)  # noqa: S603, S607
    return result.stdout


def repository_root() -> Path:
    """Return the repository root reported by git."""
    output = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, check=True)  # noqa: S603, S607
    return Path(output.stdout.decode("utf-8").strip())


def changed_paths(root: Path) -> list[str]:
    """Return the paths changed against the merge base with origin/main, plus untracked files."""
    base = run_git(root, "merge-base", "HEAD", "origin/main").decode("utf-8").strip()
    tracked = run_git(root, "diff", "--name-only", base).decode("utf-8").splitlines()
    untracked = untracked_paths(root)
    return sorted({*tracked, *untracked})


def untracked_paths(root: Path) -> list[str]:
    """Return the untracked paths that git does not ignore."""
    return run_git(root, "ls-files", "--others", "--exclude-standard").decode("utf-8").splitlines()


def current_fingerprint(root: Path) -> str:
    """Return the fingerprint of the working tree."""
    head = run_git(root, "rev-parse", "HEAD").decode("utf-8").strip()
    diff = run_git(root, "diff", "HEAD", "--binary")
    untracked = {path: (root / path).read_bytes() for path in untracked_paths(root) if (root / path).is_file()}
    return fingerprint(head, diff, untracked)


def read_last_pass(root: Path) -> str | None:
    """Return the stored fingerprint of the last passing run, or None."""
    stored = root / LAST_PASS_FILE
    if not stored.is_file():
        return None
    return stored.read_text(encoding="utf-8").strip() or None


def write_last_pass(root: Path, value: str) -> None:
    """Store the fingerprint of a passing run."""
    (root / STATE_FOLDER).mkdir(parents=True, exist_ok=True)
    (root / LAST_PASS_FILE).write_text(value + "\n", encoding="utf-8")


def load_is_docs_only(root: Path) -> Callable[[Sequence[str]], bool]:
    """Load ``is_docs_only`` from ``scripts/ci_changes.py`` (this script runs with ``scripts/`` as its folder)."""
    spec = importlib.util.spec_from_file_location("ci_changes", root / "scripts" / "ci_changes.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("scripts/ci_changes.py cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    function: Callable[[Sequence[str]], bool] = module.is_docs_only
    return function


def run_checks(root: Path, commands: Sequence[Sequence[str]]) -> tuple[bool, str]:
    """Run the commands in order and return whether all passed with their combined output."""
    combined: list[str] = []
    for command in commands:
        result = subprocess.run(  # noqa: S603
            list(command), cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
        )
        combined.append(result.stdout)
        combined.append(result.stderr)
        if result.returncode != 0:
            return False, "\n".join(combined)
    return True, "\n".join(combined)


def main() -> int:
    """Read the Stop event, run the checks when needed and return the hook's exit status."""
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        event = {}
    if not isinstance(event, dict) or event.get("stop_hook_active") is True:
        return EXIT_PASSED
    root = repository_root()
    paths = changed_paths(root)
    fingerprint_now = current_fingerprint(root)
    if not should_check(event, paths, fingerprint_now, read_last_pass(root)):
        return EXIT_PASSED
    commands = plan_checks(paths, load_is_docs_only(root), sys.platform, sys.executable)
    passed, output = run_checks(root, commands)
    if passed:
        write_last_pass(root, fingerprint_now)
        return EXIT_PASSED
    sys.stderr.write(summarize_failure(output) + "\n")
    return EXIT_SEND_BACK


if __name__ == "__main__":
    raise SystemExit(main())
