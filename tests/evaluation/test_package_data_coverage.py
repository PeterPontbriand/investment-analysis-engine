"""Every data file the evaluation tier reads is named by a ``package-data`` pattern, so an installed package has it."""

import builtins
import tomllib
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from investment_analysis_engine.core.package_root import PACKAGE_ROOT
from investment_analysis_engine.evaluation.cases.momentum import MOMENTUM_CASES
from investment_analysis_engine.evaluation.catalog import run_minimum_deterministic_suite
from investment_analysis_engine.evaluation.composition import compose_fixture_dependencies
from investment_analysis_engine.telemetry.recorder import TrajectoryRecorder
from investment_analysis_engine.telemetry.run_context import RunContext
from tests._recording_sink import RecordingSink

EXECUTED_AT = datetime(2026, 8, 31, 18, 30, tzinfo=UTC)
PIOTROSKI_FIXTURE_FOLDERS = frozenset({"instant_facts", "annual_facts", "filing_headers"})
SOURCE_SUFFIXES = frozenset({".py", ".pyc"})
REPOSITORY = PACKAGE_ROOT.parent


@contextmanager
def _recorded_reads() -> Iterator[set[Path]]:
    """Collect the resolved path of every file opened for reading inside the package folder while active."""
    seen: set[Path] = set()
    real_open = builtins.open
    real_path_open = Path.open

    def note(file: object) -> None:
        if isinstance(file, str | Path):
            resolved = Path(file).resolve()
            if resolved.is_relative_to(PACKAGE_ROOT) and resolved.suffix not in SOURCE_SUFFIXES:
                seen.add(resolved)

    def recording_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        note(file)
        return real_open(file, *args, **kwargs)

    def recording_path_open(self: Path, *args: Any, **kwargs: Any) -> Any:
        note(self)
        return real_path_open(self, *args, **kwargs)

    builtins.open = recording_open
    Path.open = recording_path_open  # type: ignore[method-assign]
    try:
        yield seen
    finally:
        builtins.open = real_open
        Path.open = real_path_open  # type: ignore[method-assign]


def _packaged_files() -> set[Path]:
    """Return every file the ``package-data`` patterns of ``pyproject.toml`` name."""
    with (REPOSITORY / "pyproject.toml").open("rb") as handle:
        patterns: list[str] = tomllib.load(handle)["tool"]["setuptools"]["package-data"][PACKAGE_ROOT.name]
    return {path.resolve() for pattern in patterns for path in PACKAGE_ROOT.glob(pattern) if path.is_file()}


@pytest.mark.asyncio
async def test_every_file_the_golden_catalog_reads_is_named_by_a_package_data_pattern() -> None:
    recorder = TrajectoryRecorder(
        RunContext(run_id=UUID("f0000000-0000-0000-0000-00000000000f"), session_id=UUID(int=16)), RecordingSink()
    )
    with _recorded_reads() as reads:
        report = await run_minimum_deterministic_suite(executed_at=EXECUTED_AT, recorder=recorder)

    assert report.failed_cases == 0
    uncovered = sorted(path.relative_to(PACKAGE_ROOT).as_posix() for path in reads - _packaged_files())
    assert not uncovered, f"Read by the evaluation tier but named by no package-data pattern: {uncovered}"


def test_composing_a_momentum_case_reads_no_piotroski_fixture_file() -> None:
    case = MOMENTUM_CASES[0]
    with _recorded_reads() as reads:
        compose_fixture_dependencies(case, clock_at=EXECUTED_AT)

    assert {path.parent.name for path in reads} & PIOTROSKI_FIXTURE_FOLDERS == set()
