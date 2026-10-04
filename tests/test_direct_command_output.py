r"""Compare the output of the four direct commands, byte for byte, with stored expected output.

``momentum``, ``graham-number``, ``graham-growth`` and ``fcf-growth`` run in their default text mode and with
``--json`` against deterministic fixtures: no network, provider or model call. The stored files under
``tests/expected_output/direct_commands/`` were generated from the behavior before the strategy modules were
relocated, so this test is the check that a refactoring slice changed no user-visible output.

Exactly two things are normalized. The values of four JSON fields, because they are wall-clock readings that differ
between any two runs: ``resolved_at``, ``effective_as_of``, ``analysis_timestamp`` and ``retrieved_at``. And
``\r\n`` becomes ``\n``, because the test runner's text stream translates line endings on Windows, and CI runs on
Windows, Linux and macOS. Nothing else is normalized, and the exit code and the empty standard error are asserted.

To change the expected output deliberately, regenerate the files and review the diff::

    uv run python -m tests._direct_command_output
"""

from __future__ import annotations

import pytest

from tests._direct_command_output import cases, expected_path, normalize, run_command


@pytest.mark.parametrize(("command", "mode"), list(cases()), ids=str)
def test_direct_command_output_matches_the_stored_output(command: str, mode: str) -> None:
    """Each command prints exactly the stored bytes and exits cleanly."""
    output = run_command(command, mode)
    assert output.exit_code == 0
    assert output.stderr == b""
    assert output.stdout == expected_path(command, mode).read_bytes()


def test_normalization_replaces_only_the_wall_clock_field_values_and_line_endings() -> None:
    """The four wall-clock fields lose their values and CRLF becomes LF; every other byte is kept."""
    raw = (
        b'{"resolved_at": "2026-10-04T11:40:43+00:00", "effective_as_of": "x", "analysis_timestamp": "y",\r\n'
        b' "retrieved_at": "z", "as_of": "2026-01-01", "note": "resolved_at", "lone\rcarriage": 1}'
    )
    assert normalize(raw) == (
        b'{"resolved_at": "<wall-clock>", "effective_as_of": "<wall-clock>", "analysis_timestamp": "<wall-clock>",\n'
        b' "retrieved_at": "<wall-clock>", "as_of": "2026-01-01", "note": "resolved_at", "lone\rcarriage": 1}'
    )
