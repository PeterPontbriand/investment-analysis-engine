"""Operational logging during real commands: records reach the log file and never the terminal.

Each test runs the real ``ian momentum`` entry point in a subprocess (see ``_logging_command_driver``) against a
fresh throwaway data and log directory, with the network replaced, and reads what the process wrote.
"""

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from src.utils.logger_util import handle_uncaught_exception

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
LOG_LINE = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \| ")
DOWNLOAD_RECORD = "src.data.yfinance.client | INFO | Downloading market data for tool execution: OFFLINE"


@dataclass(frozen=True)
class CommandRun:
    """What one driver subprocess produced."""

    returncode: int
    stdout: str
    stderr: str
    log: str


def _default_locations() -> dict[str, tuple[int, int]]:
    """Return the size and modification time of every file under the project's default data and log folders."""
    state: dict[str, tuple[int, int]] = {}
    for folder in (REPOSITORY_ROOT / "data", REPOSITORY_ROOT / "logs"):
        for path in sorted(folder.rglob("*")) if folder.exists() else []:
            if path.is_file():
                status = path.stat()
                state[path.relative_to(REPOSITORY_ROOT).as_posix()] = (status.st_size, status.st_mtime_ns)
    return state


def _run(tmp_path: Path, name: str, *arguments: str) -> CommandRun:
    root = tmp_path / name
    # Engine settings are read as IAN_<NAME> on every platform.
    environment = {
        **os.environ,
        "IAN_DATA_DIR": str(root / "data"),
        "IAN_LOG_DIR": str(root / "logs"),
        "IAN_TELEMETRY_LOG_DIR": str(root / "telemetry"),
        "PYTHONPATH": str(REPOSITORY_ROOT),
        "PYTHONIOENCODING": "utf-8",
        # The pytest process forces colour for the CLI tests (tests/conftest.py); a real run writes to a pipe
        # without it, so the child must not inherit it.
        "NO_COLOR": "1",
    }
    environment.pop("FORCE_COLOR", None)
    before = _default_locations()
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "tests.utils._logging_command_driver", *arguments],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    log_file = root / "logs" / "app.log"
    assert _default_locations() == before, "the command wrote under the project's default data or log folders"
    if arguments[0] != "crash":  # the crash scenario fails before the command opens its database
        assert list((root / "data").glob("*.sqlite3")), "the command did not create its database under its own folder"
    if "--no-logging" not in arguments:  # that run installs no logging, so it has no log file
        assert log_file.exists(), "the command did not create its log file under its own folder"
    return CommandRun(
        completed.returncode,
        completed.stdout,
        completed.stderr,
        log_file.read_text(encoding="utf-8") if log_file.exists() else "",
    )


def test_a_successful_command_logs_to_the_file_and_nothing_reaches_the_terminal(tmp_path: Path) -> None:
    run = _run(tmp_path, "success", "success")

    assert run.returncode == 0
    assert DOWNLOAD_RECORD in run.log
    assert "Momentum" in run.stdout
    assert not LOG_LINE.search(run.stdout)
    assert run.stderr == ""


def test_a_failing_command_flushes_its_records_to_the_file_before_exiting(tmp_path: Path) -> None:
    run = _run(tmp_path, "fail", "fail")

    assert run.returncode == 1
    assert DOWNLOAD_RECORD in run.log
    assert run.stdout == ""
    assert run.stderr.strip() == "Unable to analyze OFFLINE: yfinance returned no data for it."


def test_third_party_records_at_info_reach_the_file(tmp_path: Path) -> None:
    run = _run(tmp_path, "third-party", "success")

    assert "alembic.runtime.migration | INFO | Running upgrade" in run.log


def test_json_stdout_is_byte_identical_with_and_without_logging(tmp_path: Path) -> None:
    logged = _run(tmp_path, "json-logged", "fail", "--json")
    unlogged = _run(tmp_path, "json-unlogged", "fail", "--json", "--no-logging")

    assert logged.returncode == unlogged.returncode == 1
    assert logged.stdout == unlogged.stdout
    assert logged.stderr == unlogged.stderr == ""
    assert logged.stdout.startswith("{")
    assert json.loads(logged.stdout)["status"] == "input_unavailable"
    assert DOWNLOAD_RECORD in logged.log
    assert unlogged.log == ""


def test_a_successful_json_command_writes_only_the_document_to_stdout(tmp_path: Path) -> None:
    run = _run(tmp_path, "json-success", "success", "--json")

    assert run.returncode == 0
    assert run.stdout.startswith("{")
    assert json.loads(run.stdout)["ticker"] == "OFFLINE"
    assert not LOG_LINE.search(run.stdout)
    assert run.stderr == ""
    assert DOWNLOAD_RECORD in run.log


def test_an_unexpected_error_reports_the_same_sentence_and_logs_its_cause_and_traceback(tmp_path: Path) -> None:
    run = _run(tmp_path, "unexpected", "unexpected")

    assert run.returncode == 1
    assert run.stdout == ""
    assert run.stderr == "Momentum analysis failed unexpectedly for OFFLINE.\n"
    assert "ERROR | Unexpected failure reported to the user as: Momentum analysis failed unexpectedly" in run.log
    assert "Traceback (most recent call last):" in run.log
    assert "RuntimeError: driver unexpected" in run.log


def test_an_unhandled_exception_reaches_standard_error_and_the_file(tmp_path: Path) -> None:
    run = _run(tmp_path, "crash", "crash")

    assert run.returncode == 1
    assert "driver crash" in run.stderr
    assert "system.crash | CRITICAL | Uncaught exception encountered." in run.log
    assert "RuntimeError: driver crash" in run.log


def test_the_exception_hook_logs_the_crash_and_prints_the_traceback(
    caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    try:
        raise RuntimeError("hook crash")
    except RuntimeError as error:
        with caplog.at_level("CRITICAL", logger="system.crash"):
            handle_uncaught_exception(type(error), error, error.__traceback__)

    assert "hook crash" in caplog.text
    # Python 3.13 and later colour a traceback when FORCE_COLOR is set, which splits the text with escape codes.
    assert "RuntimeError: hook crash" in ANSI_ESCAPE.sub("", capsys.readouterr().err)
