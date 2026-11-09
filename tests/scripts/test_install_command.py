"""Tests for the installer of the ``ian`` command; every subprocess call is mocked and nothing touches PATH."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from scripts import install_command
from scripts.install_command import (
    LAUNCHER_FOLDER,
    InstallCommandError,
    command_folder,
    install_launcher,
    is_installed,
    is_on_path,
    main,
)
from scripts.repository_root import REPOSITORY_ROOT

BIN = Path("C:/Users/x/.local/bin")


class FakeUv:
    """Stands in for ``subprocess.run``: answers each ``uv`` call by its subcommand and records every call."""

    def __init__(
        self,
        *,
        listed: str = "",
        install_returncode: int = 0,
        install_stderr: str = "",
        bin_folder: Path = BIN,
    ) -> None:
        """Set the answers: the ``uv tool list`` text, the install result and the command folder."""
        self.calls: list[list[str]] = []
        self._listed = listed
        self._install_returncode = install_returncode
        self._install_stderr = install_stderr
        self._bin_folder = bin_folder

    def __call__(self, args: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        match args[1:3]:
            case ["tool", "dir"]:
                return subprocess.CompletedProcess(args, 0, f"{self._bin_folder}\n", "")
            case ["tool", "list"]:
                return subprocess.CompletedProcess(args, 0, self._listed, "")
            case ["tool", "install"]:
                return subprocess.CompletedProcess(args, self._install_returncode, "", self._install_stderr)
        return subprocess.CompletedProcess(args, 0, "", "")

    def installs(self) -> list[list[str]]:
        return [call for call in self.calls if call[1:3] == ["tool", "install"]]

    def update_shell_calls(self) -> list[list[str]]:
        return [call for call in self.calls if call[1:3] == ["tool", "update-shell"]]


def _use(monkeypatch: pytest.MonkeyPatch, fake: FakeUv) -> FakeUv:
    monkeypatch.setattr(subprocess, "run", fake)
    return fake


def test_a_first_install_is_editable_from_the_launcher_folder_without_reinstall_or_force(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _use(monkeypatch, FakeUv())
    install_launcher(BIN)
    assert fake.installs() == [["uv", "tool", "install", "--editable", str(LAUNCHER_FOLDER)]]


def test_an_install_over_an_existing_launcher_adds_reinstall_and_never_force(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _use(monkeypatch, FakeUv(listed="ian-launcher v0.1.0 (E:/other copy/launcher)\n- ian\n"))
    install_launcher(BIN)
    assert fake.installs() == [["uv", "tool", "install", "--editable", str(LAUNCHER_FOLDER), "--reinstall"]]
    assert all("--force" not in call for call in fake.calls)


def test_is_installed_matches_only_the_launcher_package(monkeypatch: pytest.MonkeyPatch) -> None:
    _use(monkeypatch, FakeUv(listed="ian-launcher-extra v1\nruff v0.1\n"))
    assert not is_installed()
    _use(monkeypatch, FakeUv(listed="ruff v0.1\nian-launcher v0.1.0\n- ian\n"))
    assert is_installed()


def test_a_refusal_to_overwrite_carries_uvs_message_and_names_the_command_folder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refusal = "error: Executable already exists: ian.exe (use `--force` to overwrite)"
    _use(monkeypatch, FakeUv(install_returncode=2, install_stderr=refusal))
    with pytest.raises(InstallCommandError) as raised:
        install_launcher(BIN)
    message = str(raised.value)
    assert refusal in message
    assert "Another program already provides an `ian` command" in message
    assert str(BIN) in message


def test_another_install_failure_reports_uvs_message_only(monkeypatch: pytest.MonkeyPatch) -> None:
    _use(monkeypatch, FakeUv(install_returncode=1, install_stderr="error: no network"))
    with pytest.raises(InstallCommandError) as raised:
        install_launcher(BIN)
    assert str(raised.value) == "error: no network"


def test_update_shell_runs_only_when_the_command_folder_is_off_the_path(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = _use(monkeypatch, FakeUv())
    monkeypatch.setenv("PATH", os.pathsep.join(["elsewhere", str(BIN)]))
    assert main() == 0
    assert fake.update_shell_calls() == []
    off_path = _use(monkeypatch, FakeUv())
    monkeypatch.setenv("PATH", "elsewhere")
    assert main() == 0
    assert off_path.update_shell_calls() == [["uv", "tool", "update-shell"]]
    assert "new terminal" in capsys.readouterr().out


def test_main_prints_the_executable_the_installation_and_the_removal_command(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _use(monkeypatch, FakeUv())
    monkeypatch.setenv("PATH", str(BIN))
    assert main() == 0
    output = capsys.readouterr().out
    assert str(install_command.executable_path(BIN)) in output
    assert str(REPOSITORY_ROOT) in output
    assert "uv tool uninstall ian-launcher" in output


def test_main_exits_one_on_a_refusal_and_prints_both_messages(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _use(monkeypatch, FakeUv(install_returncode=2, install_stderr="error: Executable already exists: ian.exe"))
    monkeypatch.setenv("PATH", str(BIN))
    assert main() == 1
    captured = capsys.readouterr()
    assert "Executable already exists" in captured.err
    assert "Another program already provides" in captured.err
    assert captured.out == ""


def test_command_folder_reads_the_uv_report_and_fails_when_uv_reports_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _use(monkeypatch, FakeUv(bin_folder=Path("C:/Users/y/bin")))
    assert command_folder() == Path("C:/Users/y/bin")
    assert fake.calls == [["uv", "tool", "dir", "--bin"]]
    monkeypatch.setattr(subprocess, "run", lambda args, **_kwargs: subprocess.CompletedProcess(args, 2, "", "error"))
    with pytest.raises(InstallCommandError):
        command_folder()


def test_is_on_path_compares_normalized_entries() -> None:
    folder = Path("bin") / "tools"
    assert is_on_path(folder, os.pathsep.join(["x", str(folder) + os.sep]))
    assert not is_on_path(folder, "")
