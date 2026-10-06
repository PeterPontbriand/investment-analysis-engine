"""Compare ``--help`` of the application and of each direct command, byte for byte, with stored output.

The stored files under ``tests/expected_output/cli_help/`` were generated from the commands as they were declared
in ``src/cli.py``, before the direct commands moved into their strategy files, and match that output exactly.
The application's file also pins the order of the commands, which follows the order they are added in.

To change the expected output deliberately, regenerate the files and review the diff::

    uv run python -m tests._cli_help_output
"""

from __future__ import annotations

import pytest

from tests._cli_help_output import HELP_TARGETS, expected_path, render_help


@pytest.mark.parametrize("target", HELP_TARGETS, ids=lambda target: target or "application")
def test_help_matches_the_stored_output(target: str) -> None:
    """Each help text is exactly the stored bytes."""
    assert render_help(target) == expected_path(target).read_bytes()


def test_application_help_lists_the_commands_in_the_documented_order() -> None:
    """The strategy commands follow ``refresh`` and ``health``, in declaration order, before ``evaluate``."""
    lines = render_help("").decode("utf-8").splitlines()
    names = [line.split()[1] for line in lines if line.startswith("│ ") and not line.startswith("│  ")]
    commands = [name for name in names if not name.startswith("-")]
    assert commands == [
        "refresh",
        "health",
        "momentum",
        "graham-number",
        "graham-growth",
        "fcf-growth",
        "evaluate",
        "watchlist",
        "runs",
    ]
