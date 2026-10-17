"""Tests for Markdown sequence-table ordering and completion-date checks."""

from __future__ import annotations

import subprocess
from pathlib import Path

from investment_analysis_engine.core.repository_root import REPOSITORY_ROOT
from scripts.check_sequence_tables import (
    Violation,
    check_repository,
    find_sequence_table_violations,
    list_markdown_files,
)


def table(*rows: str) -> list[str]:
    """Build a representative sequence table with its header and separator."""
    return [
        "| Slice | Scope | Status | Completed |\n",
        "| :--- | :--- | :--- | :--- |\n",
        *(f"| {row} |\n" for row in rows),
    ]


def check(*rows: str) -> list[Violation]:
    """Check a table fixture and return its violations."""
    return find_sequence_table_violations(Path("fixture.md"), table(*rows))


def test_status_order_passes_and_backwards_transition_fails() -> None:
    assert (
        check(
            "A | a | Complete | 2026-01-01",
            "B | b | In progress |",
            "C | c | Next |",
            "D | d | Planned |",
            "E | e | Deferred |",
        )
        == []
    )
    violations = check("A | a | Next |", "B | b | Complete | 2026-01-01")
    assert any("out of order" in violation.reason for violation in violations)


def test_only_allowed_statuses_pass() -> None:
    assert check("A | a | Deferred |") == []
    violations = check("A | a | Unknown |")
    assert any("unknown status" in violation.reason for violation in violations)


def test_complete_rows_require_iso_dates() -> None:
    assert check("A | a | Complete | 2026-01-02") == []
    violations = check("A | a | Complete | 2026-1-2")
    assert any("ISO date" in violation.reason for violation in violations)


def test_complete_dates_are_non_decreasing() -> None:
    assert (
        check(
            "A | a | Complete | 2026-01-01",
            "B | b | Complete | 2026-01-01",
            "C | c | Complete | 2026-01-02",
        )
        == []
    )
    violations = check("A | a | Complete | 2026-01-02", "B | b | Complete | 2026-01-01")
    assert any("non-decreasing" in violation.reason for violation in violations)


def test_non_complete_rows_leave_completed_empty() -> None:
    assert check("A | a | Planned |") == []
    violations = check("A | a | Planned | 2026-01-01")
    assert any("leave Completed empty" in violation.reason for violation in violations)


def test_at_most_one_next_row() -> None:
    assert check("A | a | Next |") == []
    violations = check("A | a | Next |", "B | b | Next |")
    assert any("more than one Next" in violation.reason for violation in violations)


def test_ir_contract_shape_with_complete_after_next_fails() -> None:
    violations = check(
        "IR.1 | [License declaration](#license) | Complete | 2026-09-24",
        "IR.4 | [Python version](#python) | Complete | 2026-09-26",
        "IR.6 | [Watchlist](#watchlist) | Complete | 2026-09-30",
        "IR.3 | [Pending item](#pending) | Next |",
        "IR.2 | [Analyzer envelope](#envelope) | Complete | 2026-09-29",
    )
    assert any("out of order" in violation.reason for violation in violations)


def test_fenced_example_is_ignored() -> None:
    lines = ["```md\n", *table("A | a | Unknown |"), "```\n"]
    assert find_sequence_table_violations(Path("fixture.md"), lines) == []


def test_file_listing_includes_root_and_docs_but_not_other_subtrees(tmp_path: Path) -> None:
    (tmp_path / "docs" / "nested").mkdir(parents=True)
    (tmp_path / "other").mkdir()
    root_file = tmp_path / "README.md"
    docs_file = tmp_path / "docs" / "nested" / "plan.md"
    other_file = tmp_path / "other" / "ignored.md"
    root_file.touch()
    docs_file.touch()
    other_file.touch()
    assert set(list_markdown_files(tmp_path)) == {root_file, docs_file}


_BACKWARDS_TABLE = (
    "| Slice | Scope | Status | Completed |\n| :--- | :--- | :--- | :--- |\n"
    "| A | first | Planned | |\n| B | second | Complete | 2026-01-01 |\n"
)


def test_an_untracked_unignored_file_is_checked_and_an_ignored_file_is_skipped(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text("docs/skipped/\n", encoding="utf-8")
    (tmp_path / "docs" / "skipped").mkdir(parents=True)
    (tmp_path / "docs" / "skipped" / "ignored.md").write_text(_BACKWARDS_TABLE, encoding="utf-8")
    (tmp_path / "docs" / "new.md").write_text(_BACKWARDS_TABLE, encoding="utf-8")

    assert [path.name for path in list_markdown_files(tmp_path)] == ["new.md"]
    violations = check_repository(tmp_path)
    assert violations
    assert {violation.source_file.name for violation in violations} == {"new.md"}


def test_a_git_repository_still_limits_the_listing_to_root_and_docs(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "outside.md").write_text(_BACKWARDS_TABLE, encoding="utf-8")
    (tmp_path / "README.md").write_text("# Root\n", encoding="utf-8")
    assert [path.name for path in list_markdown_files(tmp_path)] == ["README.md"]


def test_repository_sequence_tables_pass() -> None:
    repo_root = REPOSITORY_ROOT
    assert check_repository(repo_root) == []
