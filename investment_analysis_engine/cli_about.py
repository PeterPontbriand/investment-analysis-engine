"""The ``about`` command: print the engine's version, installation folder and Git commit.

The command reports which installation the ``ian`` command runs. It asks Git about the installation folder through
subprocesses whose output is captured, and it never fails on its own account: a fact it cannot establish is reported as
absent and the exit status is 0.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Annotated, Final

import typer

from investment_analysis_engine.api.documents import installed_engine_version
from investment_analysis_engine.core.package_root import INSTALLATION_FOLDER
from investment_analysis_engine.reporting.documents.about import AboutDocument

GIT_TIMEOUT_SECONDS: Final = 30
"""How long one Git call may take before it counts as a failed call."""

GitRunner = Callable[[Path, Sequence[str]], "subprocess.CompletedProcess[str]"]
"""Run ``git -C <folder> <arguments>`` with its output captured; raises ``FileNotFoundError`` without Git."""

_NOT_A_CHECKOUT: Final = "none (not a Git checkout)"
_NO_GIT: Final = "none (Git is not installed)"


def run_git(folder: Path, arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run ``git -C <folder> <arguments>`` and capture its output, so nothing from Git reaches the terminal."""
    return subprocess.run(  # noqa: S603
        ["git", "-C", str(folder), *arguments],  # noqa: S607
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=GIT_TIMEOUT_SECONDS,
        check=False,
    )


class GitNotInstalledError(Exception):
    """Git could not be started."""


def _git_output(folder: Path, arguments: Sequence[str], git: GitRunner) -> str | None:
    """Return Git's standard output, or ``None`` when the call exits nonzero or times out.

    Raises:
        GitNotInstalledError: If Git cannot be started.
    """
    try:
        completed = git(folder, arguments)
    except FileNotFoundError as error:
        raise GitNotInstalledError from error
    except (OSError, subprocess.TimeoutExpired):
        return None
    return completed.stdout if completed.returncode == 0 else None


def _is_same_folder(reported: str, folder: Path) -> bool:
    try:
        return Path(reported.strip()).resolve() == folder.resolve()
    except OSError:
        return False


def build_about_document(
    *, folder: Path | None, git: GitRunner = run_git, version: Callable[[], str] = installed_engine_version
) -> tuple[AboutDocument, bool]:
    """Build the document and whether Git was missing, for the installation folder ``folder``.

    The commit is set only when Git reports the folder itself as the top level of a repository: a folder inside some
    other repository is not a checkout of the engine.
    """
    engine_version = version()
    if folder is None:
        return AboutDocument(
            engine_version=engine_version, installation_folder=None, commit=None, uncommitted_changes=None
        ), False
    try:
        top_level = _git_output(folder, ("rev-parse", "--show-toplevel"), git)
        head = _git_output(folder, ("rev-parse", "HEAD"), git) if top_level is not None else None
        commit = (
            head.strip() if head is not None and top_level is not None and _is_same_folder(top_level, folder) else None
        )
        status = _git_output(folder, ("status", "--porcelain"), git) if commit else None
    except GitNotInstalledError:
        return AboutDocument(
            engine_version=engine_version, installation_folder=str(folder), commit=None, uncommitted_changes=None
        ), True
    return AboutDocument(
        engine_version=engine_version,
        installation_folder=str(folder),
        commit=commit or None,
        uncommitted_changes=None if status is None else bool(status.strip()),
    ), False


def format_about(document: AboutDocument, *, git_missing: bool) -> str:
    """Render the document as the three text lines of the command."""
    if document.installation_folder is None:
        folder, commit = "none (installed as a package)", "none"
    else:
        folder = document.installation_folder
        if document.commit is not None:
            commit = document.commit + (" (with uncommitted changes)" if document.uncommitted_changes else "")
        else:
            commit = _NO_GIT if git_missing else _NOT_A_CHECKOUT
    return f"Investment Analysis Engine {document.engine_version}\nInstallation folder: {folder}\nCommit: {commit}"


def about(
    json_output: Annotated[
        bool, typer.Option("--json", help="Write one JSON document to standard output instead of text")
    ] = False,
) -> None:
    """Show the engine's version, installation folder and commit."""
    document, git_missing = build_about_document(folder=INSTALLATION_FOLDER, git=run_git)
    typer.echo(document.model_dump_json() if json_output else format_about(document, git_missing=git_missing))


def register(app: typer.Typer) -> None:
    """Register the ``about`` command on the root Typer app."""
    app.command(name="about")(about)
