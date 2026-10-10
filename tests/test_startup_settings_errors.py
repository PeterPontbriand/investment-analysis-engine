"""A bad engine environment is reported at startup as one sentence on stderr, with exit code 2."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _run_ian(variables: dict[str, str], *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the real entry point in a subprocess whose engine variables are exactly ``variables``."""
    environment = {name: value for name, value in os.environ.items() if not name.lower().startswith("ian_")}
    environment.update(variables)
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "src.main", *arguments],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )


def _assert_one_sentence_failure(run: subprocess.CompletedProcess[str], *named: str) -> None:
    assert run.returncode == 2
    assert run.stdout == ""
    assert "Traceback" not in run.stderr
    assert len(run.stderr.strip().splitlines()) == 1
    for name in named:
        assert name in run.stderr


@pytest.mark.parametrize("arguments", [("momentum", "KO"), ("--help",)])
def test_unknown_engine_variable_is_reported_at_startup(arguments: tuple[str, ...]) -> None:
    run = _run_ian({"IAN_NO_SUCH_SETTING": "1"}, *arguments)

    _assert_one_sentence_failure(run, "IAN_NO_SUCH_SETTING", "matches no engine setting")


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows environments are case-insensitive, so two spellings cannot coexist"
)
@pytest.mark.parametrize("arguments", [("momentum", "KO"), ("--help",)])
def test_case_duplicate_is_reported_at_startup(arguments: tuple[str, ...]) -> None:
    run = _run_ian({"IAN_DATA_DIR": "one", "ian_data_dir": "two"}, *arguments)

    _assert_one_sentence_failure(run, "IAN_DATA_DIR", "ian_data_dir", "differ only by letter case")


def test_help_reports_the_same_sentence_as_a_command_for_a_bad_variable() -> None:
    bad = {"IAN_NO_SUCH_SETTING": "1"}

    assert _run_ian(bad, "--help").stderr == _run_ian(bad, "momentum", "KO").stderr


@pytest.mark.parametrize("arguments", [("momentum", "KO"), ("--help",)])
def test_bad_plain_value_is_reported_at_startup(arguments: tuple[str, ...]) -> None:
    run = _run_ian({"IAN_DATABASE_BUSY_TIMEOUT_MS": "abc"}, *arguments)

    _assert_one_sentence_failure(run, "IAN_DATABASE_BUSY_TIMEOUT_MS", "valid integer")


@pytest.mark.parametrize("arguments", [("momentum", "KO"), ("--help",)])
def test_bad_nested_value_is_reported_at_startup(arguments: tuple[str, ...]) -> None:
    run = _run_ian({"ian_schema_config__max_validation_retries": "many"}, *arguments)

    _assert_one_sentence_failure(run, "valid integer")
    assert "ian_schema_config__max_validation_retries".upper() in run.stderr.upper()
