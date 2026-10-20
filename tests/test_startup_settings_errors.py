"""A bad engine environment is reported at startup as a one-sentence message on stderr, with exit code 2."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.repository_root import REPOSITORY_ROOT
from tests.conftest import SESSION_FOLDER


def _run_ian(variables: dict[str, str], *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the real entry point in a subprocess whose engine variables are exactly ``variables``."""
    environment = {name: value for name, value in os.environ.items() if not name.lower().startswith("ian_")}
    # The three folders stay inside the test session, so that no run can reach the user's real folders.
    environment.update(
        IAN_CONFIG_DIR=str(SESSION_FOLDER / "config"),
        IAN_DATA_DIR=str(SESSION_FOLDER / "data"),
        IAN_LOG_DIR=str(SESSION_FOLDER / "logs"),
    )
    environment.update(variables)
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "investment_analysis_engine.main", *arguments],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )


def _assert_one_message_failure(run: subprocess.CompletedProcess[str], *named: str) -> None:
    assert run.returncode == 2
    assert run.stdout == ""
    assert "Traceback" not in run.stderr
    assert len(run.stderr.strip().splitlines()) == 1
    for name in named:
        assert name in run.stderr


@pytest.mark.parametrize("arguments", [("momentum", "KO"), ("--help",)])
def test_unknown_engine_variable_is_reported_at_startup(arguments: tuple[str, ...]) -> None:
    run = _run_ian({"IAN_NO_SUCH_SETTING": "1"}, *arguments)

    _assert_one_message_failure(run, "IAN_NO_SUCH_SETTING", "matches no engine setting")


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows environments are case-insensitive, so two spellings cannot coexist"
)
@pytest.mark.parametrize("arguments", [("momentum", "KO"), ("--help",)])
def test_case_duplicate_is_reported_at_startup(arguments: tuple[str, ...]) -> None:
    run = _run_ian({"IAN_DATA_DIR": "one", "ian_data_dir": "two"}, *arguments)

    _assert_one_message_failure(run, "IAN_DATA_DIR", "ian_data_dir", "differ only by letter case")


def test_help_reports_the_same_message_as_a_command_for_a_bad_variable() -> None:
    bad = {"IAN_NO_SUCH_SETTING": "1"}

    assert _run_ian(bad, "--help").stderr == _run_ian(bad, "momentum", "KO").stderr


@pytest.mark.parametrize("arguments", [("momentum", "KO"), ("--help",)])
def test_bad_plain_value_is_reported_at_startup(arguments: tuple[str, ...]) -> None:
    run = _run_ian({"IAN_DATABASE_BUSY_TIMEOUT_MS": "abc"}, *arguments)

    _assert_one_message_failure(run, "IAN_DATABASE_BUSY_TIMEOUT_MS", "valid integer")


@pytest.mark.parametrize("arguments", [("momentum", "KO"), ("--help",)])
def test_bad_nested_value_is_reported_at_startup(arguments: tuple[str, ...]) -> None:
    run = _run_ian({"ian_schema_config__max_validation_retries": "many"}, *arguments)

    _assert_one_message_failure(run, "valid integer")
    assert "ian_schema_config__max_validation_retries".upper() in run.stderr.upper()


@pytest.mark.parametrize("name", ["IAN_CONFIG_DIR", "IAN_DATA_DIR", "IAN_LOG_DIR", "IAN_TELEMETRY_LOG_DIR"])
def test_a_relative_folder_is_reported_at_startup_naming_the_variable(name: str) -> None:
    run = _run_ian({name: "relative/folder"}, "--help")

    _assert_one_message_failure(run, name, "must be an absolute path")
    assert "project folder" not in run.stderr


def test_a_relative_database_file_path_is_reported_at_startup_naming_the_variable() -> None:
    run = _run_ian({"IAN_DATABASE_URL": "sqlite:///data/x.sqlite3"}, "--help")

    _assert_one_message_failure(run, "IAN_DATABASE_URL", "must be an absolute path")


def test_the_env_file_cannot_set_the_variable_that_locates_it(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(f"IAN_CONFIG_DIR={tmp_path}\n", encoding="utf-8")

    run = _run_ian({"IAN_CONFIG_DIR": str(tmp_path)}, "--help")

    _assert_one_message_failure(run, "IAN_CONFIG_DIR", "cannot be set there")
    assert str(tmp_path) in run.stderr
