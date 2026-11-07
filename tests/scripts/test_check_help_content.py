"""Tests for the glossary entry checker, on small glossaries."""

from __future__ import annotations

from pathlib import Path

from scripts.check_help_content import (
    CONTRIBUTOR_GLOSSARY,
    EXCLUDE_MARKER,
    USER_GLOSSARY,
    check_glossary,
    check_repository,
    command_line_ids_of,
    parse_glossary,
)
from scripts.repository_root import REPOSITORY_ROOT


def entry(identifier: str, name: str, definition: str = "A short definition.") -> str:
    """Build one well-formed entry."""
    return f'<a id="{identifier}"></a>\n### {name}\n{definition}\n\nMore detail.\n\n'


def check(text: str, *, path: str = USER_GLOSSARY, cli: frozenset[str] = frozenset()) -> list[str]:
    """Check glossary text and return each problem as text."""
    lines = text.splitlines(keepends=True)
    return [str(item) for item in check_glossary(path, lines, command_line_ids=cli, repo_root=Path.cwd())]


class TestEntryStructure:
    def test_a_well_formed_glossary_passes(self) -> None:
        assert check("# G\n\n## S\n\n" + entry("cache", "Cache") + entry("eps", "EPS (Earnings Per Share)")) == []

    def test_a_missing_id_line_is_reported_with_file_and_entry(self) -> None:
        problems = check("## S\n\n### Cache\nA short definition.\n")
        assert len(problems) == 1
        assert problems[0].startswith(f"{USER_GLOSSARY}:3: entry 'Cache' -- no id line")

    def test_an_id_line_separated_by_a_blank_line_is_reported(self) -> None:
        assert any("no id line" in text for text in check('<a id="cache"></a>\n\n### Cache\nA definition.\n'))

    def test_an_id_with_an_underscore_capital_or_stray_hyphen_is_reported(self) -> None:
        for bad in ("as_of", "Cache", "a--b", "-a", "a-", "a1"):
            assert any("single hyphens" in text for text in check(entry(bad, "Thing"))), bad

    def test_a_duplicate_id_is_reported(self) -> None:
        problems = check(entry("dup", "First") + entry("dup", "Second"))
        assert len(problems) == 1
        assert "already the id of entry 'First'" in problems[0]

    def test_an_id_equal_to_its_own_heading_slug_is_allowed(self) -> None:
        assert check(entry("ticker", "Ticker")) == []

    def test_an_id_equal_to_a_different_entrys_heading_slug_is_reported(self) -> None:
        problems = check(entry("ticker", "Symbol") + entry("symbol-id", "Ticker"))
        assert len(problems) == 1
        assert "heading slug of a different entry, 'Ticker'" in problems[0]

    def test_a_name_with_a_code_span_is_reported(self) -> None:
        assert any("name is not plain text" in text for text in check(entry("as-of-date", "`as_of`")))

    def test_a_combined_heading_is_one_entry(self) -> None:
        assert check(entry("basic-and-diluted-eps", "Basic EPS / Diluted EPS")) == []


class TestShortDefinition:
    def test_a_definition_of_exactly_200_characters_passes(self) -> None:
        assert check(entry("x", "X", "a" * 199 + ".")) == []

    def test_a_longer_definition_is_reported(self) -> None:
        problems = check(entry("x", "X", "a" * 200 + "."))
        assert len(problems) == 1
        assert "201 characters" in problems[0]

    def test_two_parts_pass_and_three_are_reported(self) -> None:
        assert check(entry("x", "X", "One. Two.")) == []
        assert any("3 sentences; the limit" in text for text in check(entry("x", "X", "One. Two. Three.")))

    def test_a_decimal_number_is_not_a_break(self) -> None:
        assert check(entry("x", "X", "A P/B of 1.5 is a limit. It is fixed at 22.5 here.")) == []

    def test_each_forbidden_character_is_reported(self) -> None:
        for bad in ("a `code` b.", "a *b* c.", "a snake_case b.", "a [link](x) b."):
            assert any("not plain text" in text for text in check(entry("x", "X", bad))), bad

    def test_a_definition_may_wrap_across_lines(self) -> None:
        assert check('<a id="x"></a>\n### X\nFirst half\nsecond half.\n\nMore.\n') == []

    def test_a_missing_or_non_prose_first_paragraph_is_reported(self) -> None:
        assert any("no short definition" in t for t in check('<a id="x"></a>\n### X\n'))
        assert any("no short definition" in t for t in check('<a id="x"></a>\n### X\n```text\ncode\n```\n'))

    def test_a_link_in_a_later_paragraph_is_allowed(self) -> None:
        text = '<a id="x"></a>\n### X\nShort.\n\nSee [site](https://example.com) and `code`.\n'
        assert check(text) == []


def marked_text() -> str:
    """A glossary with one marked section between two unmarked ones."""
    return (
        "## Investor\n\n"
        + entry("cache", "Cache")
        + f"## Command line\n{EXCLUDE_MARKER}\n\n"
        + entry("cli", "CLI")
        + "## After\n\n"
        + entry("eps", "EPS")
    )


class TestExcludeMarker:
    def test_entries_in_a_marked_section_are_excluded_until_the_next_section(self) -> None:
        parsed = parse_glossary(marked_text().splitlines(keepends=True))
        assert {item.name: item.excluded for item in parsed.entries} == {"Cache": False, "CLI": True, "EPS": False}

    def test_command_line_ids_are_those_of_excluded_entries(self) -> None:
        assert command_line_ids_of(marked_text().splitlines(keepends=True)) == {"cli"}

    def test_the_marker_after_an_entry_heading_excludes_only_that_entry(self) -> None:
        text = f'<a id="a"></a>\n### A\n{EXCLUDE_MARKER}\nDefinition.\n\n' + entry("b", "B")
        parsed = parse_glossary(text.splitlines(keepends=True))
        assert [item.excluded for item in parsed.entries] == [True, False]
        assert parsed.entries[0].short_definition == "Definition."

    def test_a_marker_not_directly_after_a_heading_is_reported(self) -> None:
        problems = check("## S\n\n" + EXCLUDE_MARKER + "\n" + entry("cache", "Cache"))
        assert len(problems) == 1
        assert "directly after a heading" in problems[0]

    def test_a_deeper_heading_inside_a_marked_section_does_not_end_it(self) -> None:
        text = f"## Marked\n{EXCLUDE_MARKER}\n\n#### Deeper\n\n" + entry("cli", "CLI")
        assert [item.excluded for item in parse_glossary(text.splitlines(keepends=True)).entries] == [True]


def linked(target: str) -> str:
    """An entry whose second paragraph links to ``target``."""
    return '<a id="x"></a>\n### X\nShort.\n\nSee [it](' + target + ").\n"


class TestInvestorLinks:
    def test_a_link_to_a_contributor_term_is_reported(self) -> None:
        problems = check(linked("../project/CONTRIBUTOR_GLOSSARY.md#wal"))
        assert len(problems) == 1
        assert "contributor term" in problems[0]

    def test_a_link_to_a_command_line_term_is_reported(self) -> None:
        problems = check(linked("#cli"), cli=frozenset({"cli"}))
        assert len(problems) == 1
        assert "command-line term" in problems[0]

    def test_a_link_to_another_investor_term_or_an_external_page_passes(self) -> None:
        assert check(linked("#cache")) == []
        assert check(linked("https://example.com/#cli"), cli=frozenset({"cli"})) == []

    def test_a_command_line_entry_may_link_to_a_command_line_term(self) -> None:
        text = f"## CLI\n{EXCLUDE_MARKER}\n\n" + linked("#cli")
        assert check(text, cli=frozenset({"cli"})) == []

    def test_the_contributor_glossary_may_link_to_investor_terms(self) -> None:
        assert check(linked("../user/GLOSSARY.md#cache"), path=CONTRIBUTOR_GLOSSARY) == []

    def test_a_link_inside_a_code_span_is_not_a_link(self) -> None:
        text = '<a id="x"></a>\n### X\nShort.\n\nWrite `[it](../project/CONTRIBUTOR_GLOSSARY.md)`.\n'
        assert check(text) == []


class TestRepository:
    def test_the_repository_glossaries_pass(self) -> None:
        assert check_repository(REPOSITORY_ROOT) == []

    def test_a_missing_glossary_is_reported(self, tmp_path: Path) -> None:
        problems = check_repository(tmp_path)
        assert [item.reason for item in problems] == ["the glossary file does not exist"] * 2
