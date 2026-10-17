"""The script that reads the SEC identity from the .env file of the settings folder."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.repository_root import REPOSITORY_ROOT
from scripts.user_sec_identity import main

_IDENTITY = "Probe probe@example.invalid"


def _run(folder: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    code = main({"IAN_CONFIG_DIR": str(folder)})
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_without_a_file_nothing_is_printed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _run(tmp_path / "absent", capsys) == (0, "", "")


def test_without_the_key_nothing_is_printed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / ".env").write_text("IAN_LOG_LEVEL=DEBUG\n", encoding="utf-8")

    assert _run(tmp_path, capsys) == (0, "", "")


def test_the_value_is_printed_with_nothing_else(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / ".env").write_text(f'IAN_LOG_LEVEL=DEBUG\nSEC_USER_AGENT="{_IDENTITY}"\n', encoding="utf-8")

    assert _run(tmp_path, capsys) == (0, f"{_IDENTITY}\n", "")


def test_the_key_is_found_in_another_letter_case(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / ".env").write_text(f"Sec_User_Agent={_IDENTITY!r}\n", encoding="utf-8")

    assert _run(tmp_path, capsys) == (0, f"{_IDENTITY}\n", "")


def test_two_spellings_exit_with_code_2_and_a_message_that_names_them_but_no_value(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".env").write_text("SEC_USER_AGENT=first-value\nsec_user_agent=second-value\n", encoding="utf-8")

    code, out, err = _run(tmp_path, capsys)

    assert (code, out) == (2, "")
    assert "SEC_USER_AGENT and sec_user_agent" in err
    assert "first-value" not in err
    assert "second-value" not in err


def test_it_runs_as_a_module_from_the_repository_root(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(f"SEC_USER_AGENT={_IDENTITY!r}\n", encoding="utf-8")
    environment = {"IAN_CONFIG_DIR": str(tmp_path)}

    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "scripts.user_sec_identity"],
        cwd=REPOSITORY_ROOT,
        env={**os.environ, **environment},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )

    assert (completed.returncode, completed.stdout.strip(), completed.stderr) == (0, _IDENTITY, "")
