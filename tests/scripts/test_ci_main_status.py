"""Tests for the ``main`` failure report planner."""

from __future__ import annotations

from scripts.ci_main_status import plan_main_report

URL = "https://example.test/run/1"
SHA = "0123456789abcdef"


def test_all_green_does_nothing() -> None:
    report = plan_main_report({"a": "success", "b": "success"}, URL, SHA, "title", None)
    assert report.action == "none"
    assert report.issue is None


def test_skipped_jobs_only_does_nothing() -> None:
    report = plan_main_report({"a": "skipped", "b": "skipped"}, URL, SHA, "title", 5)
    assert report.action == "none"


def test_failure_without_open_issue_creates_one() -> None:
    report = plan_main_report({"a": "success", "quality-and-test": "failure"}, URL, SHA, "fix thing", None)
    assert report.action == "create"
    assert report.issue is None
    assert report.title == "main is red"
    assert "`0123456` fix thing" in report.body
    assert URL in report.body
    assert "- `quality-and-test`: failure" in report.body
    assert "`a`" not in report.body


def test_failure_with_open_issue_comments_on_it() -> None:
    report = plan_main_report({"a": "cancelled"}, URL, SHA, "t", 42)
    assert report.action == "comment"
    assert report.issue == 42
    assert "- `a`: cancelled" in report.body
