"""Make the ``ian`` command available in any folder.

Run from the installation folder as ``uv run python -m scripts.install_command``. The script installs the
dependency-free ``ian-launcher`` package from this installation's ``launcher`` folder with
``uv tool install --editable``. uv puts the ``ian`` command into its command folder (``uv tool dir --bin``), and the
command runs this installation from any folder. When ``ian-launcher`` is already installed, possibly from another copy
of the application, ``--reinstall`` is added so that ``ian`` points at this copy.

The script never passes ``--force``: uv refuses to overwrite an ``ian`` command that ``ian-launcher`` does not own, and
the script then exits 1 with uv's message and one more naming the command folder. When the command folder is not on
``PATH``, ``uv tool update-shell`` is run, and a new terminal is needed.

Apart from the repository-root constant, it uses only the standard library.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from scripts.repository_root import REPOSITORY_ROOT

PACKAGE_NAME = "ian-launcher"
"""The package that provides the ``ian`` command."""

LAUNCHER_FOLDER = REPOSITORY_ROOT / "launcher"
"""The folder of the launcher package, inside the installation folder."""

REMOVAL_COMMAND = f"uv tool uninstall {PACKAGE_NAME}"
"""The command that removes the ``ian`` command."""


class InstallCommandError(Exception):
    """The command cannot be installed; the message says why."""


def _uv(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Run ``uv`` with ``arguments`` and return the finished process with its output as text."""
    return subprocess.run(["uv", *arguments], capture_output=True, check=False, text=True)


def command_folder() -> Path:
    """Return the folder where ``uv`` keeps its commands, as ``uv tool dir --bin`` reports it."""
    result = _uv("tool", "dir", "--bin")
    folder = result.stdout.strip()
    if result.returncode != 0 or not folder:
        raise InstallCommandError("`uv tool dir --bin` did not report the folder where uv keeps its commands")
    return Path(folder)


def is_installed() -> bool:
    """Return whether ``uv tool list`` shows ``ian-launcher``."""
    result = _uv("tool", "list")
    return any(line.split(maxsplit=1)[:1] == [PACKAGE_NAME] for line in result.stdout.splitlines())


def is_on_path(folder: Path, path_value: str) -> bool:
    """Return whether ``folder`` is one of the entries of ``path_value``."""

    def normal(entry: str) -> str:
        return os.path.normcase(os.path.normpath(entry))

    return normal(str(folder)) in {normal(entry) for entry in path_value.split(os.pathsep) if entry}


def install_launcher(bin_folder: Path) -> None:
    """Install ``ian-launcher`` editable from this installation, never forcing over another program's ``ian``.

    Raises:
        InstallCommandError: uv refused or failed; the message holds uv's message, and for a refusal to overwrite an
            existing ``ian`` also says that another program provides it.
    """
    arguments = ["tool", "install", "--editable", str(LAUNCHER_FOLDER)]
    if is_installed():
        arguments.append("--reinstall")
    result = _uv(*arguments)
    if result.returncode == 0:
        return
    uv_message = (result.stderr or result.stdout).strip()
    if "already exists" in uv_message:
        raise InstallCommandError(
            f"{uv_message}\nAnother program already provides an `ian` command in {bin_folder}, so it was left as it is."
        )
    raise InstallCommandError(uv_message or "`uv tool install` failed")


def executable_path(bin_folder: Path) -> Path:
    """Return the path of the ``ian`` executable that uv places in ``bin_folder``."""
    return bin_folder / ("ian.exe" if sys.platform == "win32" else "ian")


def main() -> int:
    """Install the ``ian`` command for this installation; print what was done; return the process exit code."""
    try:
        bin_folder = command_folder()
        install_launcher(bin_folder)
        if not is_on_path(bin_folder, os.environ.get("PATH", "")):
            subprocess.run(["uv", "tool", "update-shell"], check=False)
            print(f"{bin_folder} was not on the path; `uv tool update-shell` was run. Open a new terminal.")
    except InstallCommandError as error:
        print(f"install_command: {error}", file=sys.stderr)
        return 1
    print(f"The `ian` command is {executable_path(bin_folder)}")
    print(f"It runs the installation in {REPOSITORY_ROOT}")
    print(f"To remove it, run `{REMOVAL_COMMAND}`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
