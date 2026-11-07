"""Tests for ``<a id>`` anchors and the glossary rule of the Markdown link checker."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check_doc_links import file_anchor_ids, find_broken_links_in_file

GLOSSARY_TEXT = (
    '# Glossary\n\n## Terms\n\n<a id="pe-ratio"></a>\n### P/E (Price-to-Earnings Ratio)\nPrice over earnings.\n'
)


@pytest.fixture
def glossary_repo(tmp_path: Path) -> Path:
    """A tree holding a user glossary with one entry whose id differs from its heading slug."""
    glossary = tmp_path / "docs" / "user" / "GLOSSARY.md"
    glossary.parent.mkdir(parents=True)
    glossary.write_text(GLOSSARY_TEXT, encoding="utf-8")
    return tmp_path


def broken_in(root: Path, source: Path, lines: list[str]) -> list[tuple[str, str]]:
    """Return each broken link of ``lines`` as ``(target, reason)``."""
    found = find_broken_links_in_file(source, lines, repo_root=root, heading_slug_cache={})
    return [(item.target, item.reason) for item in found]


class TestAnchorIds:
    def test_an_id_line_is_an_anchor(self) -> None:
        assert file_anchor_ids(['<a id="x-y"></a>\n', "### X\n"]) == {"x-y"}

    def test_an_id_inside_a_fence_is_ignored(self) -> None:
        assert file_anchor_ids(["```\n", '<a id="x"></a>\n', "```\n"]) == set()

    def test_an_id_that_shares_a_line_with_text_is_ignored(self) -> None:
        assert file_anchor_ids(['text <a id="x"></a>\n']) == set()

    def test_a_link_to_an_id_resolves_in_an_ordinary_file(self, tmp_path: Path) -> None:
        (tmp_path / "target.md").write_text('<a id="my-id"></a>\n### Heading\n', encoding="utf-8")
        assert broken_in(tmp_path, tmp_path / "source.md", ["[x](target.md#my-id)\n"]) == []

    def test_a_link_to_a_heading_slug_still_resolves_in_an_ordinary_file(self, tmp_path: Path) -> None:
        (tmp_path / "target.md").write_text("### Heading\n", encoding="utf-8")
        assert broken_in(tmp_path, tmp_path / "source.md", ["[x](target.md#heading)\n"]) == []


class TestGlossaryLinks:
    def test_a_link_to_an_entry_id_passes(self, glossary_repo: Path) -> None:
        lines = ["[p/e](docs/user/GLOSSARY.md#pe-ratio)\n"]
        assert broken_in(glossary_repo, glossary_repo / "README.md", lines) == []

    def test_a_link_to_a_heading_slug_is_reported(self, glossary_repo: Path) -> None:
        lines = ["[p/e](docs/user/GLOSSARY.md#pe-price-to-earnings-ratio)\n"]
        broken = broken_in(glossary_repo, glossary_repo / "README.md", lines)
        assert len(broken) == 1
        assert "heading slug" in broken[0][1]

    def test_a_link_to_a_section_heading_is_reported(self, glossary_repo: Path) -> None:
        broken = broken_in(glossary_repo, glossary_repo / "README.md", ["[t](docs/user/GLOSSARY.md#terms)\n"])
        assert len(broken) == 1
        assert "heading slug" in broken[0][1]

    def test_a_link_to_an_unknown_anchor_is_reported(self, glossary_repo: Path) -> None:
        broken = broken_in(glossary_repo, glossary_repo / "README.md", ["[x](docs/user/GLOSSARY.md#nothing)\n"])
        assert len(broken) == 1
        assert "no entry id" in broken[0][1]

    def test_a_link_without_an_anchor_passes(self, glossary_repo: Path) -> None:
        assert broken_in(glossary_repo, glossary_repo / "README.md", ["[g](docs/user/GLOSSARY.md)\n"]) == []

    def test_a_same_file_link_inside_a_glossary_must_use_the_id(self, glossary_repo: Path) -> None:
        source = glossary_repo / "docs" / "user" / "GLOSSARY.md"
        lines = [*GLOSSARY_TEXT.splitlines(keepends=True), "[a](#pe-ratio) [b](#pe-price-to-earnings-ratio)\n"]
        assert [target for target, _ in broken_in(glossary_repo, source, lines)] == ["#pe-price-to-earnings-ratio"]

    def test_the_contributor_glossary_is_held_to_the_same_rule(self, tmp_path: Path) -> None:
        glossary = tmp_path / "docs" / "project" / "CONTRIBUTOR_GLOSSARY.md"
        glossary.parent.mkdir(parents=True)
        glossary.write_text('<a id="wal"></a>\n### WAL (Write-Ahead Logging)\nA mode.\n', encoding="utf-8")
        base = "docs/project/CONTRIBUTOR_GLOSSARY.md"
        lines = [f"[ok]({base}#wal) [bad]({base}#wal-write-ahead-logging)\n"]
        broken = broken_in(tmp_path, tmp_path / "README.md", lines)
        assert [target.split("#")[1] for target, _ in broken] == ["wal-write-ahead-logging"]
