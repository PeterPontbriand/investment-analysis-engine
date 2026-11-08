"""The help bundle is generated from the served documents and checked for drift; links, trimming and refusals."""

from __future__ import annotations

from pathlib import Path

import pytest

from investment_analysis_engine.help.bundle import load_help_bundle
from investment_analysis_engine.help.locales import DEFAULT_LOCALE
from investment_analysis_engine.strategy_wiring import STRATEGIES
from scripts import generate_help
from scripts.check_help_content import served_document
from scripts.generate_help import (
    HELP_BUNDLE_FILE,
    HelpGenerationError,
    LinkContext,
    build_bundle,
    bundle_text,
    document_ids,
    help_gaps,
    rewrite_links,
    trim,
    write_help,
)
from scripts.generate_strategy_docs import guide_name

GLOSSARY = """# Glossary

Introduction that is not served.

## Group One

<a id="alpha"></a>
### Alpha

Alpha is the first term,
on two lines.

More about alpha, see [Beta](#beta).

---

<a id="beta"></a>
### Beta

Beta has only a definition.

## Command-line terms
<!-- help:exclude -->

<a id="cli"></a>
### CLI

Not served.

## Group Two

<a id="gamma"></a>
### Gamma

Gamma stands alone.

"""

CONTRIBUTOR_GLOSSARY = """# Contributor Glossary

## Terms

<a id="widget"></a>
### Widget

A widget is a thing.
"""

BEGINNER = """# Beginner

Intro text. See [Alpha](GLOSSARY.md#alpha) and [math](FINANCE_MATH.md#shared).

## First

Body with [self](#second-1), [title](#beginner) and `[code](GLOSSARY.md#nope)`.

## Second

Text.

## Second

Again.
"""

FINANCE = """# Finance

Introduction.

## Shared

Shared text. [back](BEGINNER_GUIDE.md#beginner) and [web](https://example.com/page).
"""


def write_repository(root: Path, *, beginner: str = BEGINNER, finance: str = FINANCE, glossary: str = GLOSSARY) -> Path:
    """Write the fixed served documents and the contributor glossary of a small repository and return its root."""
    folder = root / "docs" / "user"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "BEGINNER_GUIDE.md").write_text(beginner, encoding="utf-8")
    (folder / "FINANCE_MATH.md").write_text(finance, encoding="utf-8")
    (folder / "GLOSSARY.md").write_text(glossary, encoding="utf-8")
    contributors = root / "docs" / "project"
    contributors.mkdir(parents=True, exist_ok=True)
    (contributors / "CONTRIBUTOR_GLOSSARY.md").write_text(CONTRIBUTOR_GLOSSARY, encoding="utf-8")
    return root


CONTEXT = LinkContext(
    document_ids={
        "docs/user/BEGINNER_GUIDE.md": "beginner-guide",
        "docs/user/FINANCE_MATH.md": "finance-math",
        "docs/user/strategies/MOMENTUM.md": "momentum",
    },
    title_slugs={
        "docs/user/BEGINNER_GUIDE.md": "beginner",
        "docs/user/FINANCE_MATH.md": "finance",
        "docs/user/strategies/MOMENTUM.md": "momentum-guide",
    },
)


def rewritten(source: str, target: str) -> str:
    return rewrite_links([f"See [the text]({target}) now."], 1, source, CONTEXT)[0]


def test_the_checked_in_bundle_is_current() -> None:
    assert help_gaps() == []


def test_the_checked_in_bundle_loads_and_equals_the_generated_one() -> None:
    assert load_help_bundle(DEFAULT_LOCALE) == build_bundle()


def test_a_bundle_has_a_term_for_every_served_entry_and_a_document_for_every_strategy() -> None:
    bundle = load_help_bundle(DEFAULT_LOCALE)
    assert {item.alias for item in STRATEGIES} <= set(bundle.documents)
    assert {"beginner-guide", "finance-math"} <= set(bundle.documents)
    assert bundle.terms
    assert all(term.definition for term in bundle.terms.values())


def test_the_bundle_text_uses_sorted_keys_two_space_indent_and_a_trailing_line_feed() -> None:
    text = HELP_BUNDLE_FILE.read_bytes().decode("utf-8")
    assert text == bundle_text(load_help_bundle(DEFAULT_LOCALE))
    assert text.endswith("}\n")
    assert not text.endswith("\n\n")
    assert "\r" not in text
    assert text.startswith('{\n  "documents": {')


def test_a_missing_bundle_is_reported_naming_the_command(tmp_path: Path) -> None:
    repository = write_repository(tmp_path / "repo")
    assert help_gaps(tmp_path / "out" / "help_bundle.json", repository) == [
        "help_bundle.json is missing or out of date; run uv run python -m scripts.generate_help"
    ]


def test_a_drifted_bundle_fails_and_regeneration_repairs_it(tmp_path: Path) -> None:
    repository = write_repository(tmp_path / "repo")
    target = tmp_path / "out" / "help_bundle.json"
    assert write_help(target, repository) is True
    assert help_gaps(target, repository) == []
    target.write_bytes(target.read_bytes().replace(b"Alpha", b"Alfa"))
    assert len(help_gaps(target, repository)) == 1
    assert write_help(target, repository) is True
    assert help_gaps(target, repository) == []
    assert write_help(target, repository) is False


def test_a_crlf_copy_is_reported_as_drift(tmp_path: Path) -> None:
    repository = write_repository(tmp_path / "repo")
    target = tmp_path / "help_bundle.json"
    write_help(target, repository)
    target.write_bytes(target.read_bytes().replace(b"\n", b"\r\n"))
    assert len(help_gaps(target, repository)) == 1


def test_check_mode_reports_drift_and_writes_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repository = write_repository(tmp_path / "repo")
    target = tmp_path / "out" / "help_bundle.json"
    assert generate_help.main(["--check"], path=target, repo_root=repository) == 1
    assert "help_bundle.json is missing or out of date" in capsys.readouterr().err
    assert not target.parent.exists()
    assert generate_help.main([], path=target, repo_root=repository) == 0
    assert "wrote help_bundle.json" in capsys.readouterr().out
    assert generate_help.main(["--check"], path=target, repo_root=repository) == 0
    assert generate_help.main([], path=target, repo_root=repository) == 0
    assert "help_bundle.json is current" in capsys.readouterr().out


@pytest.mark.parametrize("check", [False, True])
@pytest.mark.parametrize(
    ("kind", "reason"),
    [
        ("served content", "code span starts with '--'"),
        ("entry rule", "no id line directly above the heading"),
        ("document structure", "exactly one level-1 heading; found 2"),
    ],
)
def test_a_checker_problem_stops_writing_and_comparing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], check: bool, kind: str, reason: str
) -> None:
    files = {
        "served content": {"beginner": BEGINNER.replace("Text.", "Run `--json` now.", 1)},
        "entry rule": {"glossary": GLOSSARY.replace('<a id="gamma"></a>\n', "")},
        "document structure": {"finance": FINANCE + "\n# Second title\n"},
    }[kind]
    repository = write_repository(tmp_path / "repo", **files)
    target = tmp_path / "out" / "help_bundle.json"
    assert generate_help.main(["--check"] if check else [], path=target, repo_root=repository) == 1
    error = capsys.readouterr().err
    assert reason in error
    assert "out of date" not in error
    assert not target.parent.exists()


def test_a_refused_link_is_reported_without_writing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repository = write_repository(tmp_path / "repo", beginner=BEGINNER.replace("[self](#second-1)", "[self](#nowhere)"))
    target = tmp_path / "help_bundle.json"
    assert generate_help.main([], path=target, repo_root=repository) == 1
    assert "help:documents/beginner-guide#nowhere" in capsys.readouterr().err
    assert not target.exists()


@pytest.mark.parametrize(
    ("source", "target", "expected"),
    [
        ("docs/user/BEGINNER_GUIDE.md", "GLOSSARY.md#alpha", "help:terms/alpha"),
        ("docs/user/BEGINNER_GUIDE.md", "./GLOSSARY.md#alpha", "help:terms/alpha"),
        ("docs/user/BEGINNER_GUIDE.md", "../user/GLOSSARY.md#alpha", "help:terms/alpha"),
        ("docs/user/strategies/MOMENTUM.md", "../GLOSSARY.md#alpha", "help:terms/alpha"),
        ("docs/user/GLOSSARY.md", "#alpha", "help:terms/alpha"),
        ("docs/user/BEGINNER_GUIDE.md", "FINANCE_MATH.md", "help:documents/finance-math"),
        ("docs/user/strategies/MOMENTUM.md", "../FINANCE_MATH.md", "help:documents/finance-math"),
        ("docs/user/BEGINNER_GUIDE.md", "FINANCE_MATH.md#shared", "help:documents/finance-math#shared"),
        ("docs/user/BEGINNER_GUIDE.md", "FINANCE_MATH.md#finance", "help:documents/finance-math"),
        ("docs/user/BEGINNER_GUIDE.md", "strategies/MOMENTUM.md#risk", "help:documents/momentum#risk"),
        ("docs/user/BEGINNER_GUIDE.md", "#first", "help:documents/beginner-guide#first"),
        ("docs/user/BEGINNER_GUIDE.md", "#beginner", "help:documents/beginner-guide"),
        ("docs/user/BEGINNER_GUIDE.md", "https://example.com/a#b", "https://example.com/a#b"),
    ],
)
def test_every_row_of_the_rewrite_table(source: str, target: str, expected: str) -> None:
    assert rewritten(source, target) == f"See [the text]({expected}) now."


def test_only_the_target_changes_and_a_title_is_kept() -> None:
    line = 'A [`code` text](GLOSSARY.md#alpha "A title") link.'
    assert rewrite_links([line], 1, "docs/user/BEGINNER_GUIDE.md", CONTEXT) == [
        'A [`code` text](help:terms/alpha "A title") link.'
    ]


def test_links_in_code_spans_and_fenced_blocks_are_left_as_written() -> None:
    lines = ["A `[x](GLOSSARY.md#alpha)` span.", "```text", "[y](GLOSSARY.md#alpha)", "```", "[z](GLOSSARY.md#alpha)"]
    assert rewrite_links(lines, 1, "docs/user/BEGINNER_GUIDE.md", CONTEXT) == [
        "A `[x](GLOSSARY.md#alpha)` span.",
        "```text",
        "[y](GLOSSARY.md#alpha)",
        "```",
        "[z](help:terms/alpha)",
    ]


@pytest.mark.parametrize(
    "target",
    ["http://example.com", "mailto:someone@example.com", "../../README.md", "OTHER.md", "GLOSSARY.md", "../../../x.md"],
)
def test_a_link_that_fits_no_row_is_refused_naming_the_file_line_and_target(target: str) -> None:
    with pytest.raises(HelpGenerationError) as raised:
        rewrite_links(["First line.", f"A [bad]({target}) link."], 10, "docs/user/BEGINNER_GUIDE.md", CONTEXT)
    assert str(raised.value) == f"docs/user/BEGINNER_GUIDE.md:11: the link target {target!r} fits no rewrite rule"


def test_a_link_on_a_later_line_of_a_paragraph_reports_its_own_line() -> None:
    with pytest.raises(HelpGenerationError, match=r"BEGINNER_GUIDE\.md:12:"):
        rewrite_links(["a", "b", "[x](nope.md)"], 10, "docs/user/BEGINNER_GUIDE.md", CONTEXT)


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        (["", "text", ""], "text"),
        (["", "", "a", "", "b", "", ""], "a\n\nb"),
        (["text", "", "---", ""], "text"),
        (["text", "***"], "text"),
        (["text", "", "___", "", ""], "text"),
        (["text", "---", "more"], "text\n---\nmore"),
        (["| a |", "| --- |"], "| a |\n| --- |"),
        ([], ""),
        (["", "---"], ""),
    ],
)
def test_trimming(lines: list[str], expected: str) -> None:
    assert trim(lines) == expected


def test_terms_have_a_short_definition_a_body_and_a_group(tmp_path: Path) -> None:
    bundle = build_bundle(write_repository(tmp_path))
    alpha = bundle.terms["alpha"]
    assert alpha.name == "Alpha"
    assert alpha.definition == "Alpha is the first term, on two lines."
    assert alpha.body == "More about alpha, see [Beta](help:terms/beta)."
    assert alpha.group == "group-one"
    assert bundle.terms["beta"].definition == "Beta has only a definition."
    assert bundle.terms["beta"].body == ""
    assert "cli" not in bundle.terms
    assert [(group.id, group.title, group.terms) for group in bundle.groups] == [
        ("group-one", "Group One", ("alpha", "beta")),
        ("group-two", "Group Two", ("gamma",)),
    ]


def test_a_group_with_no_served_term_is_left_out(tmp_path: Path) -> None:
    glossary = GLOSSARY.replace("## Group Two\n", "## Group Two\n\n## Group Three\n").replace(
        '<a id="gamma"></a>\n### Gamma\n\nGamma stands alone.\n', ""
    )
    bundle = build_bundle(write_repository(tmp_path, glossary=glossary))
    assert [group.id for group in bundle.groups] == ["group-one"]


def test_documents_hold_the_title_the_introduction_and_the_sections_below_level_one(tmp_path: Path) -> None:
    bundle = build_bundle(write_repository(tmp_path))
    beginner = bundle.documents["beginner-guide"]
    assert beginner.title == "Beginner"
    assert (
        beginner.introduction
        == "Intro text. See [Alpha](help:terms/alpha) and [math](help:documents/finance-math#shared)."
    )
    assert [(item.id, item.heading, item.level) for item in beginner.sections] == [
        ("first", "First", 2),
        ("second", "Second", 2),
        ("second-1", "Second", 2),
    ]
    assert beginner.sections[0].markdown == (
        "Body with [self](help:documents/beginner-guide#second-1), [title](help:documents/beginner-guide) "
        "and `[code](GLOSSARY.md#nope)`."
    )
    assert bundle.documents["finance-math"].sections[0].markdown == (
        "Shared text. [back](help:documents/beginner-guide) and [web](https://example.com/page)."
    )


def test_an_excluded_section_is_not_in_the_bundle(tmp_path: Path) -> None:
    beginner = BEGINNER + "\n## Setup\n<!-- help:exclude -->\n\nSetup text.\n"
    bundle = build_bundle(write_repository(tmp_path, beginner=beginner))
    assert "setup" not in [item.id for item in bundle.documents["beginner-guide"].sections]
    assert "help:exclude" not in bundle_text(bundle)


def test_a_section_followed_by_a_thematic_break_is_trimmed(tmp_path: Path) -> None:
    finance = FINANCE.replace("## Shared\n", "## Shared\n\n\n").replace("link).", "link).\n\n---\n\n## Next\n\nText.")
    bundle = build_bundle(write_repository(tmp_path, finance=finance))
    assert not bundle.documents["finance-math"].sections[0].markdown.endswith("-")
    assert bundle.documents["finance-math"].sections[0].markdown.startswith("Shared text.")


def test_a_link_to_a_section_that_is_not_in_the_bundle_fails_the_bundle_model(tmp_path: Path) -> None:
    beginner = BEGINNER.replace("[self](#second-1)", "[self](FINANCE_MATH.md#nothing)")
    with pytest.raises(ValueError, match="names no section 'nothing' of document 'finance-math'"):
        build_bundle(write_repository(tmp_path, beginner=beginner))


def test_document_ids_are_the_fixed_ids_and_each_strategys_alias() -> None:
    item = STRATEGIES[0]
    path = f"docs/user/strategies/{guide_name(item)}.md"
    documents = [
        served_document("docs/user/BEGINNER_GUIDE.md", ["# B\n"]),
        served_document("docs/user/FINANCE_MATH.md", ["# F\n"]),
        served_document("docs/user/GLOSSARY.md", ["# G\n"]),
        served_document(path, ["# S\n"]),
    ]
    assert document_ids(documents) == {
        "docs/user/BEGINNER_GUIDE.md": "beginner-guide",
        "docs/user/FINANCE_MATH.md": "finance-math",
        path: item.alias,
    }
    with pytest.raises(HelpGenerationError, match="matches no document id"):
        document_ids([served_document("docs/user/strategies/UNKNOWN.md", ["# U\n"])])
