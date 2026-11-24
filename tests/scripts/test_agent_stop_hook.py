"""Tests for the agent Stop hook's decisions; none runs the real quality-gate wrapper."""

from __future__ import annotations

from scripts.agent_stop_hook import (
    ISSUE_116_MESSAGE,
    fingerprint,
    plan_checks,
    should_check,
    summarize_failure,
    wrapper_command,
)
from scripts.ci_changes import is_docs_only


def test_stop_hook_active_never_checks() -> None:
    assert should_check({"stop_hook_active": True}, ["a.py"], "new", None) is False


def test_no_changed_paths_never_checks() -> None:
    assert should_check({}, [], "new", None) is False


def test_same_fingerprint_as_last_pass_skips_the_check() -> None:
    assert should_check({}, ["a.py"], "same", "same") is False


def test_changed_fingerprint_checks() -> None:
    assert should_check({"stop_hook_active": False}, ["a.py"], "new", "old") is True
    assert should_check({}, ["a.py"], "new", None) is True


def test_fingerprint_depends_on_head_diff_and_untracked_files() -> None:
    base = fingerprint("head", b"diff", {"a.txt": b"1"})
    assert base == fingerprint("head", b"diff", {"a.txt": b"1"})
    assert base != fingerprint("other", b"diff", {"a.txt": b"1"})
    assert base != fingerprint("head", b"other", {"a.txt": b"1"})
    assert base != fingerprint("head", b"diff", {"a.txt": b"2"})
    assert base != fingerprint("head", b"diff", {"b.txt": b"1"})


def test_docs_only_paths_choose_the_documentation_checks() -> None:
    commands = plan_checks(["docs/project/README.md"], is_docs_only, "win32", "python")
    assert ["python", "scripts/check_doc_links.py"] in commands
    assert ["uv", "run", "--no-sync", "ruff", "format", "--check", "."] in commands
    assert wrapper_command("win32") not in commands


def test_code_paths_choose_the_slice_check() -> None:
    assert plan_checks(["scripts/x.py"], is_docs_only, "win32", "python") == [wrapper_command("win32")]
    assert plan_checks(["scripts/x.py"], is_docs_only, "linux", "python") == [
        ["bash", "scripts/run-quality-gates.sh", "--slice"]
    ]
    assert wrapper_command("win32")[-1] == "-Slice"


def test_failure_summary_names_failing_steps_and_the_output_file() -> None:
    output = (
        "Gate summary\n  ruff check                                   FAILED      1.2 s\n"
        ".tmp/quality-runs/x/gate-output.txt\n"
    )
    summary = summarize_failure(output)
    assert "ruff check" in summary
    assert ".tmp/quality-runs/x/gate-output.txt" in summary


def test_failure_summary_without_steps_keeps_the_last_40_lines() -> None:
    output = "\n".join(f"line {number}" for number in range(100))
    summary = summarize_failure(output)
    assert "line 99" in summary
    assert "line 60" in summary
    assert "line 59" not in summary


def test_issue_116_evidence_replaces_the_summary() -> None:
    assert summarize_failure("OSError: WinError 10055 no buffer space") == ISSUE_116_MESSAGE
    assert summarize_failure("...\nsocket snapshot\n...") == ISSUE_116_MESSAGE


def test_failure_summary_leaves_out_the_total_row() -> None:
    output = "  mypy   FAILED      1.0 s\n  total   FAILED      5.0 s\n"
    assert summarize_failure(output).startswith("Failing steps: mypy")
    assert "total" not in summarize_failure(output)
