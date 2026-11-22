"""Keep ``.tmp/quality-runs/`` small: prune old gate run directories and clean a finished run's own directory.

Standard library only: the managed quality-gate wrappers run it with system Python, before their first step and after
their last. The rules live here and nowhere else.

Two entry points:

* ``prune_old_runs`` (command ``prune <runs-root> <own-run-dir>``) deletes whole run directories under the runs root
  beyond the newest ``KEEP_COUNT``. A directory is never deleted when it is younger than ``MIN_AGE`` (a concurrent
  or stuck run is never touched), when its name is not a gate run directory's name, or when it is the run's own.
* ``clean_finished_run`` (command ``clean <run-dir>``) deletes everything in one run directory except
  ``KEPT_FILE_NAME``. A wrapper calls it only after every step passed; a failed run keeps its whole directory.

The PowerShell and shell wrappers name run directories differently (``RUN_NAME_PATTERNS``), so a name only identifies a
gate directory. "Newest" and "age" come from modification times: the later of the directory's own and its
``KEPT_FILE_NAME``'s, when that file exists. The directories kept are counted among recognized gate directories only,
and the run's own directory counts as one of them.

A failure to delete (for example a file locked on Windows) never raises and never changes the exit status: it is
reported as a warning naming the path, and the work carries on.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import re
import shutil
import stat
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

KEEP_COUNT = 20
MIN_AGE_SECONDS = 24 * 60 * 60
KEPT_FILE_NAME = "gate-output.txt"

# Name formats of the two wrappers: PowerShell writes local time (yyyyMMddHHmmssfff), the PID and a 32-character
# hex GUID; the shell wrapper writes UTC time (yyyyMMddHHmmss), the PID and a number.
RUN_NAME_PATTERNS = (
    re.compile(r"\d{17}-\d+-[0-9a-f]{32}"),
    re.compile(r"\d{14}-\d+-\d+"),
)


@dataclass
class CleanupResult:
    """What one cleanup did: the paths it removed and the warnings it printed."""

    removed: list[Path] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


def is_run_directory_name(name: str) -> bool:
    """Return whether ``name`` is the name of a gate run directory in either wrapper's format."""
    return any(pattern.fullmatch(name) for pattern in RUN_NAME_PATTERNS)


def run_activity_time(run_dir: Path) -> float:
    """Return the later of the directory's modification time and its ``KEPT_FILE_NAME``'s, in epoch seconds."""
    latest = run_dir.stat().st_mtime
    with contextlib.suppress(OSError):
        latest = max(latest, (run_dir / KEPT_FILE_NAME).stat().st_mtime)
    return latest


def _warn(result: CleanupResult, path: Path, error: BaseException) -> None:
    message = f"warning: could not delete {path}: {error}"
    result.failures.append(message)
    print(message, file=sys.stderr)


def _delete(path: Path, result: CleanupResult) -> bool:
    """Delete a file, link or folder tree; report a failure as a warning. Return whether it is gone."""
    failed = False

    def on_error(function: Callable[..., object], failing: str, error: BaseException) -> None:
        nonlocal failed
        if isinstance(error, PermissionError):
            # A read-only file is made writable and removed once more; a locked file stays a failure.
            try:
                os.chmod(failing, stat.S_IWRITE)
                function(failing)
            except OSError as retry_error:
                failed = True
                _warn(result, Path(failing), retry_error)
            return
        failed = True
        _warn(result, Path(failing), error)

    try:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path, onexc=on_error)
        else:
            path.unlink()
    except OSError as error:
        failed = True
        _warn(result, path, error)
    return not failed and not path.exists()


def prune_old_runs(
    runs_root: Path,
    own_run: Path,
    *,
    now: float | None = None,
    keep_count: int = KEEP_COUNT,
    min_age_seconds: float = MIN_AGE_SECONDS,
) -> CleanupResult:
    """Delete recognized gate run directories under ``runs_root`` beyond the newest ``keep_count``.

    Args:
        runs_root: The ``.tmp/quality-runs`` folder.
        own_run: The calling run's own directory; it is counted among the kept ones and never deleted.
        now: The current time in epoch seconds; the system clock when omitted.
        keep_count: How many of the newest recognized directories to keep.
        min_age_seconds: A directory younger than this is never deleted.

    Returns:
        The directories removed and the warnings printed for deletions that failed.
    """
    result = CleanupResult()
    current = time.time() if now is None else now
    own_name = own_run.name
    candidates: list[tuple[float, str, Path]] = []
    try:
        entries = list(runs_root.iterdir())
    except OSError as error:
        _warn(result, runs_root, error)
        return result
    for entry in entries:
        if not is_run_directory_name(entry.name) or entry.is_symlink() or not entry.is_dir():
            continue
        try:
            activity = run_activity_time(entry)
        except OSError as error:
            _warn(result, entry, error)
            continue
        candidates.append((activity, entry.name, entry))
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    for activity, name, entry in candidates[keep_count:]:
        if name == own_name or current - activity < min_age_seconds:
            continue
        if _delete(entry, result):
            result.removed.append(entry)
    return result


def clean_finished_run(run_dir: Path) -> CleanupResult:
    """Delete everything in ``run_dir`` except ``KEPT_FILE_NAME``.

    Args:
        run_dir: A passing run's own directory; its name must be a gate run directory's name.

    Returns:
        The paths removed and the warnings printed for deletions that failed.

    Raises:
        ValueError: If the folder's name is not a gate run directory's name, so a wrong argument deletes nothing.
    """
    if not is_run_directory_name(run_dir.name):
        raise ValueError(f"{run_dir} is not a gate run directory")
    result = CleanupResult()
    try:
        entries = list(run_dir.iterdir())
    except OSError as error:
        _warn(result, run_dir, error)
        return result
    for entry in entries:
        if entry.name == KEPT_FILE_NAME:
            continue
        if _delete(entry, result):
            result.removed.append(entry)
    return result


def main(argv: list[str] | None = None) -> int:
    """Run one of the two commands; return 0 unless the arguments are wrong."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0] if __doc__ else None)
    commands = parser.add_subparsers(dest="command", required=True)
    prune = commands.add_parser("prune", help="delete old run directories under the runs root")
    prune.add_argument("runs_root", type=Path)
    prune.add_argument("own_run", type=Path)
    clean = commands.add_parser("clean", help="delete everything in a finished run's directory but gate-output.txt")
    clean.add_argument("run_dir", type=Path)
    arguments = parser.parse_args(argv)
    if arguments.command == "prune":
        pruned = prune_old_runs(arguments.runs_root, arguments.own_run)
        print(f"Removed {len(pruned.removed)} old run directories; {len(pruned.failures)} deletions failed.")
    else:
        try:
            cleaned = clean_finished_run(arguments.run_dir)
        except ValueError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        print(f"Removed {len(cleaned.removed)} items, kept {KEPT_FILE_NAME}; {len(cleaned.failures)} deletions failed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
