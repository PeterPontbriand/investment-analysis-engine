"""Shared test helper for normalizing Typer/CliRunner output assertions.

CLI error messages rendered through Typer + Rich may contain ANSI escape
sequences (colour, bold, underline) and Rich box/border-drawing characters
(straight and rounded) depending on the terminal environment.  This helper
strips both so that tests can assert on the semantic text without coupling
to terminal-styling details.
"""

import re

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
