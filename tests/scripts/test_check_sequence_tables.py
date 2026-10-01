"""Tests for Markdown sequence-table ordering and completion-date checks."""

from __future__ import annotations

from pathlib import Path

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


def test_repository_sequence_tables_pass() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assert check_repository(repo_root) == []
