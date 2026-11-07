"""Tests for the glossary entry checker, on small glossaries."""

from __future__ import annotations

from pathlib import Path

from scripts.check_help_content import (
    CONTRIBUTOR_GLOSSARY,
    EXCLUDE_MARKER,
    SHELL_LANGUAGES,
    USER_GLOSSARY,
    check_glossary,
    check_repository,
    check_served_content,
    code_spans,
    command_line_ids_of,
    parse_glossary,
    served_document,
    served_documents,
    served_paths,
    strategy_guide_paths,
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


GUIDE = "docs/user/strategies/EXAMPLE.md"
GLOSSARY_TEXT = (
    "# Glossary\n\n## Terms\n\n"
    + entry("cache", "Cache")
    + entry("eps", "EPS")
    + f"## Command-line terms\n{EXCLUDE_MARKER}\n\n"
    + entry("cli", "CLI")
)
SERVED_FILES = {
    "docs/user/BEGINNER_GUIDE.md": "# Beginner\n\nText.\n",
    "docs/user/FINANCE_MATH.md": "# Math\n\nText.\n\n## Excluded\n" + EXCLUDE_MARKER + "\n\nText.\n",
    USER_GLOSSARY: GLOSSARY_TEXT,
    "docs/user/strategies/README.md": "# Index\n\nNot served: `ian x`.\n",
}


def served_problems(guide: str, tmp_path: Path, extra: dict[str, str] | None = None) -> list[str]:
    """Write a small repository whose only strategy guide is ``guide`` and return every served-content problem."""
    for relative, text in {**SERVED_FILES, GUIDE: guide, **(extra or {})}.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
    return [str(item) for item in check_served_content(tmp_path)]


class TestServedLeaks:
    def test_a_clean_guide_passes(self, tmp_path: Path) -> None:
        guide = "# G\n\nPlain text with `PASS` and [a term](../GLOSSARY.md#cache).\n\n## S\n\nMore.\n"
        assert served_problems(guide, tmp_path) == []

    def test_a_code_span_starting_with_a_forbidden_prefix_is_reported(self, tmp_path: Path) -> None:
        for span in ("ian graham-number KO", "--as-of", "uv run pytest", "IAN_DATA_DIR"):
            problems = served_problems(f"# G\n\n## Sec\n\nUse `{span}` here.\n", tmp_path)
            assert len(problems) == 1, span
            assert problems[0].startswith(f"{GUIDE}:5: section 'Sec' -- code span starts with"), span

    def test_a_code_span_that_only_contains_a_prefix_passes(self, tmp_path: Path) -> None:
        assert served_problems("# G\n\n## S\n\nThe `ian` program, `uv`, `my--flag` and `as-of`.\n", tmp_path) == []

    def test_a_code_span_wrapped_across_two_lines_is_reported_on_its_first_line(self, tmp_path: Path) -> None:
        problems = served_problems("# G\n\n## S\n\nSee `ian\ngraham-number` now.\n", tmp_path)
        assert len(problems) == 1
        assert ":5: " in problems[0]

    def test_a_fenced_block_with_an_ian_command_line_is_reported(self, tmp_path: Path) -> None:
        for command in ("ian graham-number KO", "uv run ian momentum AAPL", "uv  run  ian runs list", "ian"):
            problems = served_problems(f"# G\n\n## S\n\n```text\n{command}\n```\n", tmp_path)
            assert len(problems) == 1, command
            assert "ian command line" in problems[0]
            assert ":6: " in problems[0]

    def test_a_fenced_block_without_an_ian_command_line_passes(self, tmp_path: Path) -> None:
        assert served_problems("# G\n\n## S\n\n```text\nmaximum = sqrt(22.5)\nianthe uv runner\n```\n", tmp_path) == []

    def test_a_fenced_block_in_any_shell_language_is_reported(self, tmp_path: Path) -> None:
        assert {"bash", "sh", "shell", "console", "powershell", "pwsh", "ps1", "cmd"} == SHELL_LANGUAGES
        for language in sorted(SHELL_LANGUAGES):
            problems = served_problems(f"# G\n\n## S\n\n```{language}\necho hello\n```\n", tmp_path)
            assert len(problems) == 1, language
            assert f"shell language: {language}" in problems[0]

    def test_a_fenced_block_in_another_language_passes(self, tmp_path: Path) -> None:
        assert served_problems("# G\n\n## S\n\n```python\nprint(1)\n```\n```text\nplain\n```\n", tmp_path) == []

    def test_a_link_to_a_repository_file_that_is_not_served_is_reported(self, tmp_path: Path) -> None:
        for target in ("README.md", "../USAGE.md", "../../README.md#x", "../../../outside.md"):
            problems = served_problems(f"# G\n\n## S\n\nSee [it]({target}).\n", tmp_path)
            assert len(problems) == 1, target
            assert "not served" in problems[0] or "outside the repository" in problems[0], target

    def test_a_link_to_a_served_document_passes(self, tmp_path: Path) -> None:
        guide = "# G\n\n## S\n\n[math](../FINANCE_MATH.md#math) [self](#s) [other](OTHER.md)\n"
        other = {"docs/user/strategies/OTHER.md": "# O\n\nText.\n"}
        assert served_problems(guide, tmp_path, extra=other) == []

    def test_an_external_link_passes(self, tmp_path: Path) -> None:
        assert served_problems("# G\n\n## S\n\n[x](https://example.com/a.md#b)\n", tmp_path) == []

    def test_a_link_to_an_excluded_section_of_a_served_document_is_reported(self, tmp_path: Path) -> None:
        for target in ("../FINANCE_MATH.md#excluded", "#quick-start", "#on-the-command-line"):
            guide = (
                f"# G\n\n## Quick start\n{EXCLUDE_MARKER}\n\nRun it.\n\n## S\n\nSee [it]({target}).\n"
                f"\n### On the command line\n{EXCLUDE_MARKER}\n\nText.\n"
            )
            problems = served_problems(guide, tmp_path)
            assert len(problems) == 1, target
            assert "excluded section" in problems[0], target

    def test_a_link_to_a_namesake_of_an_excluded_section_uses_the_github_suffix(self, tmp_path: Path) -> None:
        guide = f"# G\n\n## Same\n{EXCLUDE_MARKER}\n\nOne.\n\n## Same\n\nTwo, see [a](#same) and [b](#same-1).\n"
        problems = served_problems(guide, tmp_path)
        assert len(problems) == 1
        assert "excluded section" in problems[0]
        assert problems[0].endswith("#same")

    def test_a_link_to_the_user_glossary_without_an_entry_id_is_reported(self, tmp_path: Path) -> None:
        problems = served_problems("# G\n\n## S\n\nSee [terms](../GLOSSARY.md).\n", tmp_path)
        assert len(problems) == 1
        assert "with no entry id" in problems[0]

    def test_a_link_to_a_command_line_term_is_reported(self, tmp_path: Path) -> None:
        problems = served_problems("# G\n\n## S\n\nSee [cli](../GLOSSARY.md#cli).\n", tmp_path)
        assert len(problems) == 1
        assert "term that is not served" in problems[0]

    def test_a_link_to_a_contributor_term_is_reported(self, tmp_path: Path) -> None:
        guide = "# G\n\n## S\n\nSee [x](../../project/CONTRIBUTOR_GLOSSARY.md#base-analyzer).\n"
        problems = served_problems(guide, tmp_path)
        assert len(problems) == 1
        assert "repository file that is not served" in problems[0]

    def test_a_link_to_a_served_term_passes(self, tmp_path: Path) -> None:
        assert served_problems("# G\n\n## S\n\nSee [e](../GLOSSARY.md#eps).\n", tmp_path) == []

    def test_a_link_inside_a_code_span_is_not_checked(self, tmp_path: Path) -> None:
        assert served_problems("# G\n\n## S\n\nWrite `[x](../USAGE.md)`.\n", tmp_path) == []

    def test_the_text_under_the_title_is_served(self, tmp_path: Path) -> None:
        problems = served_problems("# G\n\nUse `--flag`.\n", tmp_path)
        assert problems == [f"{GUIDE}:3: section 'G' -- code span starts with '--': `--flag`"]

    def test_a_served_glossary_entry_is_checked(self, tmp_path: Path) -> None:
        text = GLOSSARY_TEXT.replace("More detail.", "See [use](../USAGE.md).", 1)
        problems = served_problems("# G\n\nText.\n", tmp_path, extra={USER_GLOSSARY: text})
        assert len(problems) == 1
        assert problems[0].startswith(f"{USER_GLOSSARY}:")
        assert "section 'Cache'" in problems[0]

    def test_the_command_line_section_of_the_glossary_is_not_checked(self, tmp_path: Path) -> None:
        head, tail = GLOSSARY_TEXT.rsplit("More detail.", 1)
        text = head + "Run `ian x`." + tail
        assert served_problems("# G\n\nText.\n", tmp_path, extra={USER_GLOSSARY: text}) == []

    def test_a_missing_served_document_is_reported(self, tmp_path: Path) -> None:
        problems = [str(item) for item in check_served_content(tmp_path)]
        assert "docs/user/BEGINNER_GUIDE.md:0: section '' -- the served document does not exist" in problems


class TestExcludedSections:
    def test_an_excluded_section_and_its_subsections_are_not_checked(self, tmp_path: Path) -> None:
        guide = (
            f"# G\n\n## Quick start\n{EXCLUDE_MARKER}\n\n```bash\nuv run ian x\n```\n\n### Options\n\n`--a`\n\n"
            "## Served\n\nFine.\n"
        )
        assert served_problems(guide, tmp_path) == []

    def test_a_section_after_an_excluded_one_is_checked_again(self, tmp_path: Path) -> None:
        guide = f"# G\n\n## Quick start\n{EXCLUDE_MARKER}\n\n`--a`\n\n## Served\n\n`--b`\n"
        problems = served_problems(guide, tmp_path)
        assert len(problems) == 1
        assert "section 'Served'" in problems[0]

    def test_an_on_the_command_line_subsection_is_excluded(self, tmp_path: Path) -> None:
        guide = (
            f"# G\n\n## Data\n\nExplanation.\n\n### On the command line\n{EXCLUDE_MARKER}\n\n"
            "`--no-cache` bypasses it.\n\n```bash\nuv run ian x\n```\n"
        )
        assert served_problems(guide, tmp_path) == []

    def test_an_on_the_command_line_subsection_without_the_marker_is_reported(self, tmp_path: Path) -> None:
        problems = served_problems("# G\n\n## Data\n\nText.\n\n### On the command line\n\nText.\n", tmp_path)
        assert len(problems) == 1
        assert "must carry" in problems[0]

    def test_an_on_the_command_line_subsection_that_is_not_last_is_reported(self, tmp_path: Path) -> None:
        guide = f"# G\n\n## Data\n\n### On the command line\n{EXCLUDE_MARKER}\n\nText.\n\n### After\n\nMore.\n"
        problems = served_problems(guide, tmp_path)
        assert len(problems) == 1
        assert "last subsection of its parent" in problems[0]
        assert "'After'" in problems[0]

    def test_an_on_the_command_line_subsection_before_the_next_parent_passes(self, tmp_path: Path) -> None:
        guide = (
            f"# G\n\n## Data\n\n### Part\n\n#### On the command line\n{EXCLUDE_MARKER}\n\nText.\n\n"
            f"### Sibling\n\nMore.\n\n### On the command line\n{EXCLUDE_MARKER}\n\nText.\n\n## Next\n\nText.\n"
        )
        assert served_problems(guide, tmp_path) == []

    def test_a_marker_that_is_not_after_a_heading_is_reported(self, tmp_path: Path) -> None:
        problems = served_problems(f"# G\n\n## S\n\nText.\n{EXCLUDE_MARKER}\n", tmp_path)
        assert len(problems) == 1
        assert "directly after a heading" in problems[0]

    def test_an_excluded_document_title_is_reported(self, tmp_path: Path) -> None:
        problems = served_problems(f"# G\n{EXCLUDE_MARKER}\n\nText.\n", tmp_path)
        assert any("title cannot be excluded" in text for text in problems)


class TestServedSet:
    def test_the_served_documents_are_the_guides_finance_math_the_glossary_and_the_strategy_guides(
        self, tmp_path: Path
    ) -> None:
        served_problems("# G\n\nText.\n", tmp_path)
        assert served_paths(tmp_path) == (
            "docs/user/BEGINNER_GUIDE.md",
            "docs/user/FINANCE_MATH.md",
            USER_GLOSSARY,
            GUIDE,
        )

    def test_the_strategy_index_is_not_a_strategy_guide(self, tmp_path: Path) -> None:
        served_problems("# G\n\nText.\n", tmp_path)
        assert strategy_guide_paths(tmp_path) == (GUIDE,)

    def test_the_repository_serves_every_path_and_has_no_leak(self) -> None:
        documents = served_documents(REPOSITORY_ROOT)
        assert [document.path for document in documents] == list(served_paths(REPOSITORY_ROOT))
        assert check_served_content(REPOSITORY_ROOT) == []

    def test_a_guide_serves_its_title_text_and_every_section_outside_an_excluded_one(self) -> None:
        text = f"# Title\nIntro.\n\n## A\nText.\n\n## B\n{EXCLUDE_MARKER}\nHidden.\n\n### C\nHidden.\n\n## D\nShown.\n"
        document = served_document("docs/user/strategies/X.md", text.splitlines(keepends=True))
        assert document.title == "Title"
        assert [(section.heading, section.level) for section in document.sections] == [
            ("Title", 1),
            ("A", 2),
            ("D", 2),
        ]
        first = document.sections[0]
        assert (first.first_line, first.last_line, first.lines) == (1, 2, ("Intro.",))

    def test_a_section_ends_at_the_next_heading_of_any_level(self) -> None:
        lines = "# T\n## A\nOne.\n### B\nTwo.\n## C\nThree.\n".splitlines(keepends=True)
        sections = served_document("docs/user/strategies/X.md", lines).sections
        assert [(s.heading, s.first_line, s.last_line, s.lines) for s in sections] == [
            ("T", 1, 1, ()),
            ("A", 2, 3, ("One.",)),
            ("B", 4, 5, ("Two.",)),
            ("C", 6, 7, ("Three.",)),
        ]

    def test_a_section_slug_counts_excluded_headings_like_github(self) -> None:
        lines = f"# T\n## Same\n{EXCLUDE_MARKER}\nX.\n## Same\nY.\n".splitlines(keepends=True)
        sections = served_document("docs/user/strategies/X.md", lines).sections
        assert [section.slug for section in sections] == ["t", "same-1"]

    def test_the_glossary_serves_only_entries_outside_the_excluded_section(self) -> None:
        document = served_document(USER_GLOSSARY, GLOSSARY_TEXT.splitlines(keepends=True))
        assert [(section.heading, section.anchor_id) for section in document.sections] == [
            ("Cache", "cache"),
            ("EPS", "eps"),
        ]
        assert document.sections[0].lines == ("A short definition.", "", "More detail.")

    def test_code_spans_come_from_prose_only(self) -> None:
        lines = "# T\nA `one` and `two\nwords`.\n\n```text\n`no`\n```\n".splitlines(keepends=True)
        (section,) = served_document("docs/user/strategies/X.md", lines).sections
        assert code_spans(section) == [(2, "one"), (2, "two words")]
