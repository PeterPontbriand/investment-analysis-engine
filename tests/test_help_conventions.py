"""A command's help is plain language for a user: no planning label and no markup shown literally.

Typer prints a docstring as the help, so a citation of a planning document or a double-backtick span in a docstring
reaches the user as it is. Detail for a maintainer belongs in a comment or in the body of the function.
"""

from __future__ import annotations

import re

from tests._command_tree import command_nodes, help_texts

_FORBIDDEN = re.compile(r"§|Amendment|\bSlice\b|\bStep \d|``")


def forbidden_in(text: str) -> list[str]:
    """Return each planning label or markup form that ``text`` contains, as it is written."""
    return [match.group(0) for match in _FORBIDDEN.finditer(text)]


def _near(text: str, form: str) -> str:
    """Return the text around the first ``form``, on one line, so a failure shows where the label is."""
    start = text.index(form)
    return " ".join(text[max(0, start - 30) : start + len(form) + 30].split())


def test_no_command_help_contains_a_planning_label_or_markup() -> None:
    found = [
        f"{node.name}: {form!r} in '...{_near(text, form)}...'"
        for node in command_nodes()
        for text in help_texts(node)
        for form in dict.fromkeys(forbidden_in(text))
    ]
    assert not found, "help must be plain user language; found " + "; ".join(found)


def test_the_help_scan_reports_each_forbidden_form_and_accepts_plain_help() -> None:
    assert forbidden_in("Remove one entry (Amendment A1, §12).") == ["Amendment", "§"]
    assert forbidden_in("Part of Slice B, then Step 3.5.") == ["Slice", "Step 3"]
    assert forbidden_in("Use ``--no-save`` to preview.") == ["``", "``"]
    assert forbidden_in("Remove an entry → by its 1-based number; the step 3 of 5 stays − plain.") == []
