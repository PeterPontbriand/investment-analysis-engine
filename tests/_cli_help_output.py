"""Render ``--help`` for the application and for each direct strategy command at a fixed terminal width.

Shared by ``tests/test_cli_help_output.py`` and the regeneration entry point::

    uv run python -m tests._cli_help_output

Regeneration rewrites the files under ``tests/expected_output/cli_help/`` from the current code, so an intended
change to a command's options, help text or position shows up as a reviewed diff to those files.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from src.cli import app

EXPECTED_DIRECTORY = Path(__file__).resolve().parent / "expected_output" / "cli_help"

# The application itself, then each direct strategy command; "" is the application's own help.
HELP_TARGETS: tuple[str, ...] = ("", "momentum", "graham-number", "graham-growth", "fcf-growth")

_ENVIRONMENT = {"COLUMNS": "80", "TERMINAL_WIDTH": "80", "NO_COLOR": "1", "TERM": "dumb"}


def render_help(target: str) -> bytes:
    """Return the ``--help`` output of ``target`` (the application when empty) with LF line endings."""
    arguments = [target, "--help"] if target else ["--help"]
    result = CliRunner().invoke(app, arguments, env=_ENVIRONMENT)
    if result.exit_code != 0:
        raise RuntimeError(f"--help for {target or 'the application'} exited with {result.exit_code}")
    return result.stdout_bytes.replace(b"\r\n", b"\n")


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
