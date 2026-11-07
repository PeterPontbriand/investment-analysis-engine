"""The served documents name no ``ian`` command, and exactly one guide is served for each strategy.

``scripts/check_help_content.py`` checks the served content for code spans that start with a flag, an environment
variable or ``ian``. It cannot know the name of a command without the application, so this test reads the names from
the Typer application each time it runs and fails on a code span whose first word is one of them.
"""

from __future__ import annotations

from collections.abc import Iterable

import typer
from typer.core import TyperGroup

from investment_analysis_engine.cli import app
from investment_analysis_engine.strategy_wiring import STRATEGIES
from scripts.check_help_content import (
    STRATEGY_GUIDE_DIRECTORY,
    ServedDocument,
    code_spans,
    served_document,
    served_documents,
    strategy_guide_paths,
)
from scripts.generate_strategy_docs import guide_name
from scripts.repository_root import REPOSITORY_ROOT


def command_names() -> frozenset[str]:
    """Return the name of every command and command group directly under ``ian``, hidden ones included.

    A subcommand is always reached through its group, whose name starts the code span, so the names below the first
    level are not needed; some of them (``status``, ``list``) are ordinary words that served text may put in a code
    span.
    """
    command = typer.main.get_command(app)
    assert isinstance(command, TyperGroup)
    return frozenset(command.commands)


def command_name_problems(documents: Iterable[ServedDocument], names: frozenset[str]) -> list[str]:
    """Return one message for each code span of the served content whose first word is a command name."""
    problems: list[str] = []
    for document in documents:
        for section in document.sections:
            for line, content in code_spans(section):
                words = content.split()
                if words and words[0] in names:
                    problems.append(
                        f"{document.path}:{line}: section '{section.heading}' -- code span starts with the name of "
                        f"an ian command, {words[0]!r}: `{content}`"
                    )
    return problems


class TestCommandNames:
    def test_the_names_are_read_from_the_application(self) -> None:
        names = command_names()
        assert {"watchlist", "runs", "refresh"} <= names
        assert {item.alias for item in STRATEGIES} <= names

    def test_a_code_span_that_starts_with_a_command_name_is_reported(self) -> None:
        text = "# T\nUse `graham-number KO` or `watchlist` or `runs list`.\n\n## S\nAlso `momentum`.\n"
        document = served_document("docs/user/strategies/X.md", text.splitlines(keepends=True))
        problems = command_name_problems([document], command_names())
        assert len(problems) == 4
        assert problems[0].startswith("docs/user/strategies/X.md:2: section 'T' -- code span starts with the name of")
        assert problems[3].startswith("docs/user/strategies/X.md:5: section 'S' --")

    def test_a_code_span_that_only_contains_a_command_name_passes(self) -> None:
        text = "# T\nA `status = unavailable`, a `PASS`, `the watchlist` and `x momentum`.\n"
        document = served_document("docs/user/strategies/X.md", text.splitlines(keepends=True))
        assert command_name_problems([document], command_names()) == []

    def test_a_command_name_outside_a_code_span_or_in_a_fenced_block_passes(self) -> None:
        text = "# T\nThe watchlist and momentum.\n\n```text\nwatchlist list\n```\n"
        document = served_document("docs/user/strategies/X.md", text.splitlines(keepends=True))
        assert command_name_problems([document], command_names()) == []

    def test_no_served_document_has_a_code_span_that_starts_with_a_command_name(self) -> None:
        assert command_name_problems(served_documents(REPOSITORY_ROOT), command_names()) == []


class TestStrategyGuides:
    def test_one_guide_is_served_for_each_strategy_and_no_other_file_of_the_folder(self) -> None:
        expected = {f"{STRATEGY_GUIDE_DIRECTORY}/{guide_name(item)}.md" for item in STRATEGIES}
        assert set(strategy_guide_paths(REPOSITORY_ROOT)) == expected
        assert len(strategy_guide_paths(REPOSITORY_ROOT)) == len(STRATEGIES)

    def test_every_strategy_guide_exists_and_is_served(self) -> None:
        served = {document.path for document in served_documents(REPOSITORY_ROOT)}
        for item in STRATEGIES:
            assert f"{STRATEGY_GUIDE_DIRECTORY}/{guide_name(item)}.md" in served
