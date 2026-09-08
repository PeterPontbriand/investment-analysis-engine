"""Verify repository and telemetry entry points in fresh Python processes."""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "first_module",
    [
        "src.data.repositories",
        "src.data.repositories.trajectory",
        "src.core.telemetry",
        "src.core.telemetry.sinks.sqlite",
    ],
)
def test_repository_and_telemetry_import_order(first_module: str) -> None:
    script = (
        f"import {first_module}\n"
        "from src.data.repositories import SQLiteTrajectoryRepository\n"
        "from src.data.repositories.trajectory import SQLiteTrajectoryRepository as direct\n"
        "from src.core.telemetry.sinks import SQLiteTrajectorySink, read_trajectory\n"
        "assert SQLiteTrajectoryRepository is direct\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[3],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
