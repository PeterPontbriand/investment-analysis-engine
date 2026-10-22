"""The real entry point, with output redirected under the cp1252 encoding, writes UTF-8 and does not crash.

Each case runs ``python -m investment_analysis_engine.main`` in a subprocess with ``PYTHONIOENCODING=cp1252`` and its
output captured, which is how Python 3.12 to 3.14 encode redirected output on Windows.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from scripts.repository_root import REPOSITORY_ROOT

_ARROW = "→"


def _run(
    code: str | None, *arguments: str, folder: Path, variables: dict[str, str] | None = None
) -> subprocess.CompletedProcess[bytes]:
    """Run the entry point, or ``python -c code``, in a subprocess whose output is cp1252 unless it is switched.

    The subprocess keeps its settings, data and log folders under ``folder``.
    """
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.lower().startswith("ian_") and name not in ("PYTHONUTF8", "PYTHONIOENCODING", "FORCE_COLOR")
    }
    # The three folders stay under the test's own folder, so that no run can reach the user's real folders or write
    # into the session's log folder.
    environment.update(
        IAN_CONFIG_DIR=str(folder / "config"),
        IAN_DATA_DIR=str(folder / "data"),
        IAN_LOG_DIR=str(folder / "logs"),
        PYTHONIOENCODING="cp1252",
    )
    environment.update(variables or {})
    command = [sys.executable, "-m", "investment_analysis_engine.main"]
    if code is not None:
        command = [sys.executable, "-c", code]
    return subprocess.run(  # noqa: S603 - the interpreter running this test, with arguments built here
        [*command, *arguments], cwd=REPOSITORY_ROOT, env=environment, capture_output=True, timeout=120, check=False
    )


def test_importing_the_entry_point_leaves_the_streams_alone(tmp_path: Path) -> None:
    run = _run(
        "import sys; import investment_analysis_engine.main; print(sys.stdout.encoding, sys.stderr.encoding)",
        folder=tmp_path,
    )

    assert run.returncode == 0
    assert run.stdout.decode("ascii").split() == ["cp1252", "cp1252"]


def test_fcf_growth_help_is_utf8_when_redirected_under_cp1252(tmp_path: Path) -> None:
    run = _run(None, "fcf-growth", "--help", folder=tmp_path)

    assert run.returncode == 0, run.stderr.decode("utf-8", errors="replace")
    assert _ARROW in run.stdout.decode("utf-8")
    assert run.stderr == b""


def test_a_settings_error_with_a_character_cp1252_cannot_encode_is_utf8_on_stderr(tmp_path: Path) -> None:
    folder = f"relative/{_ARROW}folder"

    run = _run(None, "--help", folder=tmp_path, variables={"IAN_CONFIG_DIR": folder})

    assert run.returncode == 2
    assert run.stdout == b""
    message = run.stderr.decode("utf-8")
    assert folder in message
    assert "must be an absolute path" in message
    assert "Traceback" not in message
