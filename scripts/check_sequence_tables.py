"""Validate status ordering and completion dates in repository sequence tables."""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

_STATUSES = ("Complete", "In progress", "Next", "Planned", "Deferred")
_STATUS_ORDER = {status: index for index, status in enumerate(_STATUSES)}
_FENCE_RE = re.compile(r"^(```+|~~~+)")


@dataclass(frozen=True)
class Violation:
    """One sequence-table rule violation."""

    source_file: Path
    line_number: int
    reason: str

    def __str__(self) -> str:
        """Render the violation with its source location."""
        return f"{self.source_file}:{self.line_number}: {self.reason}"


def _cells(line: str) -> list[str]:
    """Split a simple pipe-delimited Markdown table row into trimmed cells."""
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_separator(cells: list[str]) -> bool:
    """Return whether cells are a Markdown table separator row."""
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _validate_row(
    source_file: Path, line_number: int, status: str, completed: str
) -> tuple[list[Violation], int | None, date | None]:
    """Validate one row and return its violations, status rank, and parsed completion date."""
    if status not in _STATUS_ORDER:
        return (
            [
                Violation(
                    source_file,
                    line_number,
                    f"unknown status {status!r}; allowed statuses: {', '.join(_STATUSES)}",
                )
            ],
            None,
            None,
        )

    violations: list[Violation] = []
    status_order = _STATUS_ORDER[status]
    parsed_date: date | None = None
    if status == "Complete":
        try:
            parsed_date = date.fromisoformat(completed)
            if parsed_date.isoformat() != completed:
                raise ValueError
        except ValueError:
            violations.append(Violation(source_file, line_number, "Complete row must have an ISO date in Completed"))
            parsed_date = None
    elif completed:
        violations.append(Violation(source_file, line_number, f"{status} row must leave Completed empty"))
    return violations, status_order, parsed_date


def _validate_table(source_file: Path, header: list[str], start: int, lines: list[str]) -> tuple[list[Violation], int]:
    """Validate the data rows after a sequence-table header."""
    violations: list[Violation] = []
    previous_status = -1
    previous_complete_date: date | None = None
    next_count = 0
    second_next_line: int | None = None
    row_index = start
    while row_index < len(lines):
        row_line = lines[row_index].rstrip("\r\n")
        if not row_line.strip().startswith("|"):
            break
        row = _cells(row_line)
        if len(row) != len(header):
            break
        status_line = row_index + 1
        status, completed = row[-2:]
        row_violations, status_order, parsed_date = _validate_row(source_file, status_line, status, completed)
        violations.extend(row_violations)
        if status_order is not None and status_order < previous_status:
            violations.append(Violation(source_file, status_line, f"status {status!r} is out of order"))
        if status_order is not None:
            previous_status = status_order
        if status == "Next":
            next_count += 1
            if next_count == 2:
                second_next_line = status_line
        if parsed_date is not None:
            if previous_complete_date is not None and parsed_date < previous_complete_date:
                violations.append(Violation(source_file, status_line, "Complete dates must be in non-decreasing order"))
            previous_complete_date = parsed_date
        row_index += 1
    if next_count > 1:
        violations.append(
            Violation(source_file, second_next_line or start, "sequence table has more than one Next row")
        )
    return violations, row_index


def find_sequence_table_violations(source_file: Path, lines: list[str]) -> list[Violation]:
    """Find all rule violations in sequence tables in ``lines``."""
    violations: list[Violation] = []
    index = 0
    in_fence = False
    fence_marker = ""
    while index < len(lines):
        line = lines[index].rstrip("\r\n")
        fence_match = _FENCE_RE.match(line.strip())
        if fence_match:
            marker = fence_match.group(1)[:3]
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif line.strip().startswith(fence_marker):
                in_fence = False
            index += 1
            continue
        if in_fence:
            index += 1
            continue

        header = _cells(line)
        if len(header) < 2 or header[-2:] != ["Status", "Completed"] or index + 1 >= len(lines):
            index += 1
            continue
        separator = _cells(lines[index + 1].rstrip("\r\n"))
        if len(separator) != len(header) or not _is_separator(separator):
            index += 1
            continue

        table_violations, row_index = _validate_table(source_file, header, index + 2, lines)
        violations.extend(table_violations)
        index = max(row_index, index + 2)
    return violations


def list_markdown_files(repo_root: Path) -> list[Path]:
    """List Markdown files under docs and at the repository root."""
    files = set(repo_root.glob("*.md"))
    docs = repo_root / "docs"
    if docs.is_dir():
        files.update(path for path in docs.rglob("*.md") if path.is_file())
    return sorted(files)


def check_repository(repo_root: Path) -> list[Violation]:
    """Check all root and docs Markdown files for sequence-table violations."""
    violations: list[Violation] = []
    for markdown_file in list_markdown_files(repo_root):
        lines = markdown_file.read_text(encoding="utf-8").splitlines(keepends=True)
        violations.extend(find_sequence_table_violations(markdown_file, lines))
    return violations


def main() -> int:
    """Check the repository this script lives in and report every violation."""
    repo_root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, check=True, text=True
        ).stdout.strip()
    )
    violations = check_repository(repo_root)
    if not violations:
        sys.stdout.write("check_sequence_tables: all sequence tables are valid.\n")
        return 0
    for violation in violations:
        sys.stdout.write(f"{violation}\n")
    sys.stderr.write(f"check_sequence_tables: {len(violations)} violation(s) found.\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
