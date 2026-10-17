"""Verify repository and telemetry entry points in fresh Python processes."""

import subprocess
import sys

import pytest

from investment_analysis_engine.core.repository_root import REPOSITORY_ROOT


@pytest.mark.parametrize(
    "first_module",
    [
        "investment_analysis_engine.data.repositories",
        "investment_analysis_engine.data.repositories.trajectory",
        "investment_analysis_engine.telemetry",
        "investment_analysis_engine.telemetry.sinks.sqlite",
    ],
)
def test_repository_and_telemetry_import_order(first_module: str) -> None:
    script = (
        f"import {first_module}\n"
        "from investment_analysis_engine.data.repositories.trajectory import SQLiteTrajectoryRepository\n"
        "from investment_analysis_engine.telemetry.sinks.sqlite import SQLiteTrajectorySink, read_trajectory\n"
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
