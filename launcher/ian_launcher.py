"""The ``ian`` command: run the installation of Investment Analysis Engine this launcher was installed from.

This module is the whole of the ``ian-launcher`` package, which has no dependencies. ``scripts/install_command.py``
installs it in editable mode, so this file stays in the installation's own ``launcher`` folder and the installation is
found by climbing from the file once. The launcher then runs ``uv run --project <installation folder> ian`` with the
arguments it was given. On Windows it runs that as a child process and ignores Ctrl+C itself, leaving the interrupt to
the child, which is the program the user is stopping; elsewhere it replaces its own process with the command.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

INSTALLATION_FOLDER = Path(__file__).resolve().parent.parent
"""The installation folder: the folder that holds this module's ``launcher`` folder."""

IS_WINDOWS = os.name == "nt"
"""Whether the launcher runs on Windows, where it starts a child process instead of replacing itself."""

INSTALL_COMMAND = "uv run python -m scripts.install_command"
"""The command that points ``ian`` at a copy of the application."""


def run(arguments: list[str]) -> int:
    """Run ``ian`` of the installation with ``arguments`` and return the exit code; write a message on a failure.

    On macOS and Linux this does not return when the command starts: the process is replaced by the command.
    """
    uv = shutil.which("uv")
    if uv is None:
        sys.stderr.write("ian needs uv, which was not found on the path. Install uv and open a new terminal.\n")
        return 1
    folder = INSTALLATION_FOLDER
    if not (folder / "pyproject.toml").is_file():
        sys.stderr.write(
            f"The installation folder {folder} no longer holds the application. "
            f"Run `{INSTALL_COMMAND}` from the current copy to point `ian` at it.\n"
        )
        return 1
    command = [uv, "run", "--project", str(folder), "ian", *arguments]
    if IS_WINDOWS:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        return subprocess.run(command, check=False).returncode
    os.execvp(uv, command)


def main() -> None:
    """Run the command line entry point: exit with the exit code of the installation's ``ian``."""
    sys.exit(run(sys.argv[1:]))
