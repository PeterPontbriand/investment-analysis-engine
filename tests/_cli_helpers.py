"""Shared test helpers for CLI-invoking tests.

CLI error messages rendered through Typer + Rich may contain ANSI escape
sequences (colour, bold, underline) and Rich box/border-drawing characters
(straight and rounded) depending on the terminal environment.  ``normalize_cli_output``
strips both so that tests can assert on the semantic text without coupling
to terminal-styling details. The isolation fixtures for CLI tests are in ``tests/_cli_isolation.py``.
"""

import re
from dataclasses import replace
from unittest.mock import MagicMock

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def normalize_cli_output(output: str) -> str:
    """Strip ANSI terminal-control sequences and normalize Rich box/border layout.

    This makes substring assertions robust across local execution, Windows
    terminals, and headless CI runners where Typer/Rich may or may not emit
    styling codes.  Handles both straight (│┌┐└┘) and rounded (╭╮╰╯)
    border-drawing characters.
    """
    text = _ANSI_ESCAPE_RE.sub("", output)
    for ch in "─│┌┐└┘╭╮╰╯":
        text = text.replace(ch, " ")
    return " ".join(text.split())


def carry_profile(mock_run: MagicMock) -> None:
    """Make a mocked ``MomentumAnalyzer.run_analysis`` return its canned run carrying the caller's profile.

    The real analyzer embeds ``context.instrument_profile`` in the run it returns, and the
    ``momentum`` presenters read it from there; a bare canned run would not carry it.
    """
    canned = mock_run.return_value
    mock_run.side_effect = lambda **kwargs: replace(canned, instrument_profile=kwargs["context"].instrument_profile)
