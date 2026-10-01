"""Tests for the repo-wide Markdown link/anchor checker, especially slug generation."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.check_doc_links import (
    check_repository,
    file_heading_slugs,
    find_broken_links_in_file,
    list_tracked_markdown_files,
    slugify,
)


class TestSlugify:
    def test_lowercases_and_hyphenates_spaces(self) -> None:
        assert slugify("Time and the analysis boundary") == "time-and-the-analysis-boundary"

    def test_strips_a_leading_number_and_period(self) -> None:
        assert slugify("3. Time and the analysis boundary") == "3-time-and-the-analysis-boundary"

    def test_ampersand_produces_a_double_hyphen(self) -> None:
        """GitHub removes punctuation but maps each surrounding space to its own hyphen."""
        assert slugify("FCF & Earnings Growth") == "fcf--earnings-growth"

    def test_strips_backtick_code_span_delimiters(self) -> None:
        assert slugify("`BaseAnalyzer`") == "baseanalyzer"

    def test_strips_bold_delimiters(self) -> None:
        assert slugify("**Bold** heading") == "bold-heading"

    def test_strips_inline_link_syntax_keeping_link_text(self) -> None:
        assert slugify("[Architecture](ARCHITECTURE.md) overview") == "architecture-overview"

    def test_keeps_underscores_and_hyphens_literal(self) -> None:
        assert slugify("as_of and effective_as_of") == "as_of-and-effective_as_of"
        assert slugify("Already-hyphenated") == "already-hyphenated"

    def test_parentheses_are_removed_not_hyphenated(self) -> None:
        assert slugify("Graham analysis (Step 2.3 implemented)") == "graham-analysis-step-23-implemented"

    def test_en_dash_and_em_dash_are_stripped_like_github(self) -> None:
        """GitHub's slugger strips Unicode general-punctuation (dashes included), not just ASCII."""
        assert slugify("4.10 Step 3.4 – Local Research Workspace & Analysis Run Library") == (
            "410-step-34--local-research-workspace--analysis-run-library"
        )
        assert slugify("12. Contract Amendment A1 — Watchlist Entry Model") == (
            "12-contract-amendment-a1--watchlist-entry-model"
        )


class TestFileHeadingSlugs:
    def test_single_heading(self) -> None:
        lines = ["# Title\n", "\n", "## One Heading\n"]
        assert file_heading_slugs(lines) == {"title", "one-heading"}

    def test_duplicate_headings_get_numbered_suffixes(self) -> None:
        lines = ["## Overview\n", "## Overview\n", "## Overview\n"]
        assert file_heading_slugs(lines) == {"overview", "overview-1", "overview-2"}

    def test_headings_inside_fenced_code_blocks_are_ignored(self) -> None:
        lines = [
            "## Real Heading\n",
            "```text\n",
            "## Not A Heading\n",
            "```\n",
            "## Another Real Heading\n",
        ]
        assert file_heading_slugs(lines) == {"real-heading", "another-real-heading"}

    def test_tilde_fences_are_also_respected(self) -> None:
        lines = ["~~~\n", "## Not A Heading\n", "~~~\n", "## Real Heading\n"]
        assert file_heading_slugs(lines) == {"real-heading"}

    def test_trailing_hashes_are_stripped(self) -> None:
        lines = ["## Heading ##\n"]
        assert file_heading_slugs(lines) == {"heading"}


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A minimal two-file Markdown fixture tree, not a real git repository."""
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "target.md").write_text("# Target Doc\n\n## A Section\n\n## A Section\n", encoding="utf-8")
    return tmp_path


class TestFindBrokenLinksInFile:
    def test_valid_same_file_anchor_is_not_reported(self, repo: Path) -> None:
        source = repo / "source.md"
        lines = ["# Source\n", "\n", "## Some Section\n", "\n", "[link](#some-section)\n"]
        assert find_broken_links_in_file(source, lines, repo_root=repo, heading_slug_cache={}) == []

    def test_broken_same_file_anchor_is_reported(self, repo: Path) -> None:
        source = repo / "source.md"
        lines = ["# Source\n", "[link](#does-not-exist)\n"]
        broken = find_broken_links_in_file(source, lines, repo_root=repo, heading_slug_cache={})
        assert len(broken) == 1
        assert "does-not-exist" in broken[0].reason

    def test_valid_cross_file_path_is_not_reported(self, repo: Path) -> None:
        source = repo / "source.md"
        lines = ["[link](sub/target.md)\n"]
        assert find_broken_links_in_file(source, lines, repo_root=repo, heading_slug_cache={}) == []

    def test_missing_cross_file_path_is_reported(self, repo: Path) -> None:
        source = repo / "source.md"
        lines = ["[link](sub/missing.md)\n"]
        broken = find_broken_links_in_file(source, lines, repo_root=repo, heading_slug_cache={})
        assert len(broken) == 1
        assert "does not exist" in broken[0].reason

    def test_valid_cross_file_anchor_is_not_reported(self, repo: Path) -> None:
        source = repo / "source.md"
        lines = ["[link](sub/target.md#a-section-1)\n"]
        assert find_broken_links_in_file(source, lines, repo_root=repo, heading_slug_cache={}) == []

    def test_broken_cross_file_anchor_is_reported(self, repo: Path) -> None:
        source = repo / "source.md"
        lines = ["[link](sub/target.md#no-such-section)\n"]
        broken = find_broken_links_in_file(source, lines, repo_root=repo, heading_slug_cache={})
        assert len(broken) == 1
        assert "no-such-section" in broken[0].reason

    def test_anchor_into_a_directory_target_is_reported(self, repo: Path) -> None:
        source = repo / "source.md"
        lines = ["[link](sub#anchor)\n"]
        broken = find_broken_links_in_file(source, lines, repo_root=repo, heading_slug_cache={})
        assert len(broken) == 1
        assert "directory" in broken[0].reason

    def test_directory_target_without_anchor_is_valid(self, repo: Path) -> None:
        source = repo / "source.md"
        lines = ["[link](sub)\n"]
        assert find_broken_links_in_file(source, lines, repo_root=repo, heading_slug_cache={}) == []

    def test_external_links_are_skipped(self, repo: Path) -> None:
        source = repo / "source.md"
        lines = [
            "[web](https://example.com/does/not/exist#nope)\n",
            "[mail](mailto:nobody@example.com)\n",
        ]
        assert find_broken_links_in_file(source, lines, repo_root=repo, heading_slug_cache={}) == []

    def test_images_are_not_treated_as_links(self, repo: Path) -> None:
        source = repo / "source.md"
        lines = ["![broken image](sub/missing.png)\n"]
        assert find_broken_links_in_file(source, lines, repo_root=repo, heading_slug_cache={}) == []

    def test_links_inside_fenced_code_blocks_are_skipped(self, repo: Path) -> None:
        source = repo / "source.md"
        lines = ["```text\n", "[example](sub/missing.md)\n", "```\n"]
        assert find_broken_links_in_file(source, lines, repo_root=repo, heading_slug_cache={}) == []

    def test_reports_every_break_in_one_pass(self, repo: Path) -> None:
        source = repo / "source.md"
        lines = ["[a](sub/missing1.md)\n", "[b](sub/missing2.md)\n", "[c](#missing-anchor)\n"]
        broken = find_broken_links_in_file(source, lines, repo_root=repo, heading_slug_cache={})
        assert len(broken) == 3


class TestRepositoryIntegration:
    def test_check_repository_passes_for_repository_markdown(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        assert check_repository(repo_root) == []

    def test_check_repository_finds_and_lists_a_real_git_repos_markdown_files(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        (tmp_path / "good.md").write_text("# Good\n\n[self](#good)\n", encoding="utf-8")
        (tmp_path / "bad.md").write_text("[dangling](missing.md)\n", encoding="utf-8")
        subprocess.run(["git", "add", "good.md", "bad.md"], cwd=tmp_path, check=True)

        tracked = list_tracked_markdown_files(tmp_path)
        assert {path.name for path in tracked} == {"good.md", "bad.md"}

        broken = check_repository(tmp_path)
        assert len(broken) == 1
        assert broken[0].source_file.name == "bad.md"
