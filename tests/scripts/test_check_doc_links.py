"""Tests for the repo-wide Markdown link/anchor checker, especially slug generation."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.check_doc_links import (
    check_repository,
    check_repository_diagrams,
    check_repository_uv_run_ian,
    classify_fence_lines,
    file_heading_slugs,
    find_broken_links_in_file,
    find_mermaid_blocks_in_file,
    find_uv_run_ian_lines_in_file,
    list_tracked_markdown_files,
    slugify,
)
from scripts.repository_root import REPOSITORY_ROOT


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

    def test_links_inside_inline_code_spans_are_skipped(self, repo: Path) -> None:
        source = repo / "source.md"
        lines = [
            "`[example](sub/missing.md)` and ``[another](#missing-anchor)``\n",
            "[real link](sub/missing.md)\n",
        ]
        broken = find_broken_links_in_file(source, lines, repo_root=repo, heading_slug_cache={})
        assert len(broken) == 1
        assert broken[0].link_text == "real link"

    def test_reports_every_break_in_one_pass(self, repo: Path) -> None:
        source = repo / "source.md"
        lines = ["[a](sub/missing1.md)\n", "[b](sub/missing2.md)\n", "[c](#missing-anchor)\n"]
        broken = find_broken_links_in_file(source, lines, repo_root=repo, heading_slug_cache={})
        assert len(broken) == 3


class TestRepositoryIntegration:
    def test_check_repository_passes_for_repository_markdown(self) -> None:
        repo_root = REPOSITORY_ROOT
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

    def test_an_untracked_unignored_file_is_checked_and_an_ignored_file_is_skipped(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        (tmp_path / ".gitignore").write_text("skipped/\n", encoding="utf-8")
        (tmp_path / "skipped").mkdir()
        (tmp_path / "skipped" / "ignored.md").write_text("[dangling](missing.md)\n", encoding="utf-8")
        (tmp_path / "new.md").write_text("[dangling](missing.md)\n", encoding="utf-8")

        assert {path.name for path in list_tracked_markdown_files(tmp_path)} == {"new.md"}
        broken = check_repository(tmp_path)
        assert [item.source_file.name for item in broken] == ["new.md"]

    def test_a_tracked_file_deleted_from_disk_is_not_read(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        (tmp_path / "gone.md").write_text("# Gone\n", encoding="utf-8")
        subprocess.run(["git", "add", "gone.md"], cwd=tmp_path, check=True)
        (tmp_path / "gone.md").unlink()
        assert list_tracked_markdown_files(tmp_path) == []


class TestMermaidBlocks:
    def test_reports_the_opening_line_of_a_mermaid_block(self) -> None:
        lines = ["Text\n", "```mermaid\n", "flowchart LR\n", "```\n"]
        found = find_mermaid_blocks_in_file(Path("doc.md"), lines)
        assert [block.line_number for block in found] == [2]
        assert "doc.md:2" in str(found[0])

    def test_reports_a_tilde_fence_and_an_uppercase_language(self) -> None:
        assert len(find_mermaid_blocks_in_file(Path("doc.md"), ["~~~Mermaid\n", "graph TD\n", "~~~\n"])) == 1

    def test_ignores_other_languages_and_mermaid_text_inside_another_fence(self) -> None:
        lines = ["```text\n", "```mermaid\n", "```\n", "```python\n", "x = 1\n", "```\n"]
        assert find_mermaid_blocks_in_file(Path("doc.md"), lines) == []

    def test_check_repository_diagrams_fails_on_a_tracked_mermaid_block(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        (tmp_path / "bad.md").write_text("```mermaid\ngraph TD\n```\n", encoding="utf-8")
        (tmp_path / "good.md").write_text("```text\nA -> B\n```\n", encoding="utf-8")
        subprocess.run(["git", "add", "bad.md", "good.md"], cwd=tmp_path, check=True)
        found = check_repository_diagrams(tmp_path)
        assert [block.source_file.name for block in found] == ["bad.md"]

    def test_repository_markdown_has_no_mermaid_blocks(self) -> None:
        assert check_repository_diagrams(REPOSITORY_ROOT) == []


class TestUvRunIanLines:
    def test_accepts_the_installed_command_and_the_installer_line(self) -> None:
        lines = ["```bash\n", "ian db status\n", "uv run python -m scripts.install_command\n", "```\n"]
        assert find_uv_run_ian_lines_in_file(Path("doc.md"), lines) == []

    def test_reports_uv_run_ian_in_a_fenced_block_and_in_prose(self) -> None:
        lines = ["Use `uv run ian --help` here.\n", "```bash\n", "uv run ian db status\n", "```\n"]
        found = find_uv_run_ian_lines_in_file(Path("doc.md"), lines)
        assert [line.line_number for line in found] == [1, 3]
        assert "doc.md:3" in str(found[1])
        assert "Make the `ian` command available" in str(found[1])

    def test_reports_uv_run_with_flags_before_ian_in_both_places(self) -> None:
        lines = ["```bash\n", "uv run --no-sync ian db status\n", "```\n", "Run `uv run --no-sync ian health`.\n"]
        assert [line.line_number for line in find_uv_run_ian_lines_in_file(Path("doc.md"), lines)] == [2, 4]

    def test_ignores_other_uv_run_commands_and_longer_words(self) -> None:
        lines = ["uv run --no-sync alembic upgrade head\n", "uv run python -m ian_tools\n", "uv run ian-extra\n"]
        assert find_uv_run_ian_lines_in_file(Path("doc.md"), lines) == []

    def test_check_repository_covers_user_docs_and_readme_only(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        text = "uv run ian db status\n"
        (tmp_path / "docs" / "user" / "strategies").mkdir(parents=True)
        (tmp_path / "docs" / "project").mkdir(parents=True)
        (tmp_path / "docs" / "user" / "strategies" / "GUIDE.md").write_text(text, encoding="utf-8")
        (tmp_path / "README.md").write_text(text, encoding="utf-8")
        (tmp_path / "docs" / "project" / "PLAN.md").write_text(text, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
        found = check_repository_uv_run_ian(tmp_path)
        assert sorted(line.source_file.name for line in found) == ["GUIDE.md", "README.md"]

    def test_repository_documentation_has_no_uv_run_ian_lines(self) -> None:
        assert check_repository_uv_run_ian(REPOSITORY_ROOT) == []


class TestFenceLines:
    def test_a_four_backtick_block_can_hold_a_three_backtick_block(self) -> None:
        lines = ["````text\n", "```mermaid\n", "graph TD\n", "```\n", "````\n", "after\n"]
        kinds = [fence.kind for fence in classify_fence_lines(lines)]
        assert kinds == ["open", "inside", "inside", "inside", "close", "outside"]
        assert find_mermaid_blocks_in_file(Path("doc.md"), lines) == []

    def test_a_tilde_fence_is_not_closed_by_backticks_and_a_fence_with_text_does_not_close(self) -> None:
        lines = ["~~~\n", "```\n", "~~~ text\n", "~~~\n", "x\n"]
        kinds = [fence.kind for fence in classify_fence_lines(lines)]
        assert kinds == ["open", "inside", "inside", "close", "outside"]
