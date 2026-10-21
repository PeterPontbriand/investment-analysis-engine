"""The entry point writes UTF-8, so no command's help crashes a stream that cannot encode its characters.

Standard output and standard error are switched by ``use_utf8_output`` before anything is written. Here a cp1252
stream, the encoding Python picks on Windows when output is redirected, stands in for that console.
"""

from __future__ import annotations

import io
import sys
from unittest.mock import patch

import pytest

from investment_analysis_engine.cli import app
from investment_analysis_engine.main import use_utf8_output
from tests._command_tree import CommandNode, command_nodes

_NODES = command_nodes()


def _cp1252_stream() -> tuple[io.TextIOWrapper, io.BytesIO]:
    raw = io.BytesIO()
    return io.TextIOWrapper(raw, encoding="cp1252", newline=""), raw


def test_the_stream_setup_makes_a_cp1252_stream_write_utf8() -> None:
    stream, raw = _cp1252_stream()

    use_utf8_output(stream)
    stream.write("growth → years − 1")
    stream.flush()

    assert stream.encoding == "utf-8"
    assert raw.getvalue().decode("utf-8") == "growth → years − 1"


def test_the_stream_setup_ignores_a_stream_it_cannot_reconfigure() -> None:
    use_utf8_output(None, io.StringIO(), object())


@pytest.mark.parametrize("node", _NODES, ids=lambda node: node.name)
def test_every_command_renders_its_help_as_utf8_into_a_cp1252_stream(node: CommandNode) -> None:
    stream, raw = _cp1252_stream()
    exit_code: object = None

    with patch.object(sys, "stdout", stream), patch.object(sys, "stderr", stream):
        use_utf8_output(sys.stdout, sys.stderr)
        try:
            app([*node.path, "--help"], prog_name="ian")
        except SystemExit as stop:
            exit_code = stop.code
    stream.flush()

    assert exit_code in (0, None), f"{node.name} --help exited with {exit_code!r}"
    output = raw.getvalue().decode("utf-8")
    assert output.strip(), f"{node.name} --help wrote nothing"
