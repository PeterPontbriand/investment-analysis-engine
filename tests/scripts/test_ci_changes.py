"""Tests for the CI change classifier."""

from __future__ import annotations

from scripts.ci_changes import is_docs_only, parse_paths


def test_empty_input_is_not_docs_only() -> None:
    assert parse_paths("") == []
    assert is_docs_only([]) is False


def test_markdown_file_at_the_root_is_docs_only() -> None:
    assert is_docs_only(["README.md"]) is True


def test_non_markdown_file_under_docs_is_docs_only() -> None:
    assert is_docs_only(["docs/user/image.png"]) is True


def test_markdown_under_code_folder_is_not_docs_only() -> None:
    assert is_docs_only(["investment_analysis_engine/data/NOTES.md"]) is False
    assert is_docs_only(["tests/fixtures/sample.md"]) is False
    assert is_docs_only(["schemas/readme.md"]) is False


def test_mix_of_docs_and_python_is_not_docs_only() -> None:
    assert is_docs_only(["docs/project/MASTER_PLAN.md", "scripts/ci_changes.py"]) is False


def test_parse_paths_handles_trailing_nul() -> None:
    assert parse_paths("README.md\0docs/a.md\0") == ["README.md", "docs/a.md"]
