"""Render ``--help`` for the application and for each direct strategy command at a fixed terminal width.

Shared by ``tests/test_cli_help_output.py`` and the regeneration entry point::

    uv run python -m tests._cli_help_output

Regeneration rewrites the files under ``tests/expected_output/cli_help/`` from the current code, so an intended
change to a command's options, help text or position shows up as a reviewed diff to those files.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import typer.rich_utils
from typer.testing import CliRunner

from src.cli import app
from tests._cli_helpers import normalize_cli_output

EXPECTED_DIRECTORY = Path(__file__).resolve().parent / "expected_output" / "cli_help"

# The application itself, then each direct strategy command; "" is the application's own help.
HELP_TARGETS: tuple[str, ...] = ("", "momentum", "graham-number", "graham-growth", "fcf-growth")

# Typer reads TERMINAL_WIDTH once, when ``typer.rich_utils`` is imported, and Rich otherwise takes the width from
# the runner's terminal, so the width is fixed on the module value Typer passes to every Rich console it builds.
TERMINAL_COLUMNS = 80


def render_help(target: str) -> bytes:
    """Return the ``--help`` output of ``target`` (the application when empty), normalized line by line.

    ``normalize_cli_output`` removes ANSI styling and box-drawing characters, whose corner style differs between
    a Windows console and other platforms, and collapses spacing; the line structure, wrapping at the fixed
    width, the text and the order of the lines are kept.
    """
    arguments = [target, "--help"] if target else ["--help"]
    with patch.object(typer.rich_utils, "MAX_WIDTH", TERMINAL_COLUMNS):
        result = CliRunner().invoke(app, arguments)
    if result.exit_code != 0:
        raise RuntimeError(f"--help for {target or 'the application'} exited with {result.exit_code}")
    lines = (normalize_cli_output(line) for line in result.stdout.splitlines())
    return "".join(f"{line}\n" for line in lines if line).encode("utf-8")


def expected_path(target: str) -> Path:
    """Return the stored help file of one target."""
    return EXPECTED_DIRECTORY / f"{target or 'application'}.txt"


def regenerate() -> None:
    """Rewrite every stored help file from the current behavior."""
    EXPECTED_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for target in HELP_TARGETS:
        expected_path(target).write_bytes(render_help(target))


if __name__ == "__main__":
    regenerate()
