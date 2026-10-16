"""Verify repository and telemetry entry points in fresh Python processes."""

import subprocess
import sys

import pytest

from src.core.repository_root import REPOSITORY_ROOT


@pytest.mark.parametrize(
    "first_module",
    [
        "src.data.repositories",
        "src.data.repositories.trajectory",
        "src.telemetry",
        "src.telemetry.sinks.sqlite",
    ],
)
def test_repository_and_telemetry_import_order(first_module: str) -> None:
    script = (
        f"import {first_module}\n"
        "from src.data.repositories import SQLiteTrajectoryRepository\n"
        "from src.data.repositories.trajectory import SQLiteTrajectoryRepository as direct\n"
        "from src.telemetry.sinks.sqlite import SQLiteTrajectorySink, read_trajectory\n"
        "assert SQLiteTrajectoryRepository is direct\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
