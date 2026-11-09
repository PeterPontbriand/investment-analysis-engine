"""Tests for the ``ian`` launcher; the process, the signal handler and ``uv`` lookup are all replaced."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import FrameType

import pytest

from launcher import ian_launcher
from scripts.repository_root import REPOSITORY_ROOT

UV = "C:/tools/uv.exe"
ARGUMENTS = ["watchlist", "create", "Smoke Test", "--name", "two words"]


class ExecutedError(Exception):
    """Raised by the replacement for ``os.execvp``, which never returns in the real program."""

    def __init__(self, file: str, args: list[str]) -> None:
        """Keep the program and the argument list the launcher tried to run."""
        super().__init__(file)
        self.file = file
        self.args_list = args


@pytest.fixture
def installation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    monkeypatch.setattr(ian_launcher, "INSTALLATION_FOLDER", tmp_path)
    monkeypatch.setattr(shutil, "which", lambda _name: UV)
    return tmp_path


def _expected(folder: Path) -> list[str]:
    return [UV, "run", "--project", str(folder), "ian", *ARGUMENTS]


def _windows(monkeypatch: pytest.MonkeyPatch, returncode: int = 0) -> tuple[list[list[str]], list[int]]:
    monkeypatch.setattr(ian_launcher, "IS_WINDOWS", True)
    commands: list[list[str]] = []
    ignored: list[int] = []

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, returncode)

    def fake_signal(number: int, handler: Callable[[int, FrameType | None], object] | int | None) -> None:
        if handler == signal.SIG_IGN:
            ignored.append(number)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(signal, "signal", fake_signal)
    return commands, ignored


@pytest.mark.usefixtures("installation")
def test_windows_runs_a_child_with_the_arguments_unchanged_and_ignores_sigint(
    installation: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands, ignored = _windows(monkeypatch)
    assert ian_launcher.run(ARGUMENTS) == 0
    assert commands == [_expected(installation)]
    assert ignored == [signal.SIGINT]


@pytest.mark.usefixtures("installation")
def test_windows_passes_the_child_exit_code_through(monkeypatch: pytest.MonkeyPatch) -> None:
    _windows(monkeypatch, returncode=3)
    assert ian_launcher.run([]) == 3


def test_other_systems_replace_the_process_and_leave_sigint_alone(
    installation: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ian_launcher, "IS_WINDOWS", False)
    signal_calls: list[tuple[object, ...]] = []

    def fake_execvp(file: str, args: list[str]) -> None:
        raise ExecutedError(file, args)

    monkeypatch.setattr(os, "execvp", fake_execvp)
    monkeypatch.setattr(signal, "signal", lambda *args: signal_calls.append(args))
    with pytest.raises(ExecutedError) as raised:
        ian_launcher.run(ARGUMENTS)
    assert raised.value.file == UV
    assert raised.value.args_list == _expected(installation)
    assert signal_calls == []


def test_a_missing_uv_writes_one_message_and_exits_one(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    assert ian_launcher.run(ARGUMENTS) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.count("\n") == 1
    assert "needs uv" in captured.err


def test_a_moved_installation_names_the_folder_and_the_install_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(ian_launcher, "INSTALLATION_FOLDER", tmp_path / "gone")
    monkeypatch.setattr(shutil, "which", lambda _name: UV)
    assert ian_launcher.run(ARGUMENTS) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.count("\n") == 1
    assert str(tmp_path / "gone") in captured.err
    assert "uv run python -m scripts.install_command" in captured.err


@pytest.mark.usefixtures("installation")
def test_main_exits_with_the_exit_code_of_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    _windows(monkeypatch, returncode=5)
    monkeypatch.setattr(sys, "argv", ["ian", "health"])
    with pytest.raises(SystemExit) as raised:
        ian_launcher.main()
    assert raised.value.code == 5


def test_the_installation_folder_is_the_repository_root() -> None:
    assert Path(ian_launcher.__file__).resolve().parent.parent == REPOSITORY_ROOT
