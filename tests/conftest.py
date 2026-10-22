"""Global pytest configurations and safety cleanups."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

# Every engine variable is removed and the three folders are pointed into one temporary session folder, before any
# import that can load the package: the settings are built when the package is first imported. A test therefore
# cannot reach the user's real settings, database or logs, whatever it forgets to override. The case-insensitive
# match mirrors how the engine reads its variables.
for _name in [name for name in os.environ if name.upper().startswith("IAN_")]:
    del os.environ[_name]
SESSION_FOLDER = Path(tempfile.mkdtemp(prefix="ian-tests-")).resolve()
os.environ["IAN_CONFIG_DIR"] = str(SESSION_FOLDER / "config")
os.environ["IAN_DATA_DIR"] = str(SESSION_FOLDER / "data")
os.environ["IAN_LOG_DIR"] = str(SESSION_FOLDER / "logs")

# Typer and Rich read FORCE_COLOR when they are imported or first render, so it must be set before
# any import that can load them. Forcing styled CLI output for every pytest run makes a raw
# CLI-text assertion fail locally exactly as it would on a CI runner, rather than only in CI.
os.environ["FORCE_COLOR"] = "1"

# The automatic provider check sends a test request to a provider after a provider failure. No test may do that, so
# the suite turns the check off here, once, through the setting every command reads. A test of the check injects a
# fake probe instead; a test of the setting's default removes this variable first.
os.environ["IAN_PROVIDER_CHECK"] = "false"

# Two paths record telemetry through the settings without being asked: the command-line quality telemetry and the
# orchestrator's default recorder, both through ``TrajectoryRecorder.from_settings``. No test records telemetry through
# the settings, so the suite turns it off here, once. A test of telemetry passes its own recorder, and a test of the
# setting's default sets the variable itself.
os.environ["IAN_TELEMETRY_LEVEL"] = "OFF"

import logging  # noqa: E402
from collections.abc import Generator  # noqa: E402

import pytest  # noqa: E402

from tests._cli_isolation import isolated_cli_settings, stub_yahoo_identity_metadata  # noqa: E402
from tests._collection_hint import pytest_make_collect_report  # noqa: E402
from tests._live_selection import pytest_addoption, pytest_collection_modifyitems, pytest_configure  # noqa: E402
from tests._migrated_database import migrated_database  # noqa: E402
from tests._network_guard import block_external_sockets, block_live_yahoo  # noqa: E402
from tests._session_isolation import (  # noqa: E402
    SESSION_DATABASE_RULE,
    SESSION_TELEMETRY_RULE,
    session_database_file,
    session_telemetry_files,
    stop_session_if_outside,
)
from tests._socket_snapshot import pytest_runtest_makereport  # noqa: E402

__all__ = [
    "block_external_sockets",
    "block_live_yahoo",
    "cleanup_logging_handlers",
    "isolated_cli_settings",
    "migrated_database",
    "pytest_addoption",
    "pytest_collection_modifyitems",
    "pytest_configure",
    "pytest_make_collect_report",
    "pytest_runtest_makereport",
    "stub_yahoo_identity_metadata",
]


def pytest_sessionstart(session: pytest.Session) -> None:  # noqa: ARG001 - fixed hook signature
    """Stop the session before any test runs if a resolved folder or the database lies outside the session folder."""
    from investment_analysis_engine.config import settings  # noqa: PLC0415

    stop_session_if_outside(SESSION_FOLDER, settings)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:  # noqa: ARG001 - fixed hook signature
    """Remove the session folder."""
    shutil.rmtree(SESSION_FOLDER, ignore_errors=True)


@pytest.fixture(autouse=True)
def cleanup_logging_handlers() -> Generator[None, None, None]:
    """Automatically flush and detach logging handlers after every test to prevent process hangs."""
    yield
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        try:
            handler.close()
            root_logger.removeHandler(handler)
        except Exception:
            pass


@pytest.fixture(autouse=True)
def fail_if_session_database_exists() -> Generator[None, None, None]:
    """Fail the test that leaves a database at the session's own ``database_url``.

    That file is the default database in the session data folder. Only a test that reaches the default database
    creates it, so its existence after a test means the test did not isolate the database. The file is removed, with
    its journal files, so that only the test that created it fails.
    """
    from investment_analysis_engine.config import settings  # noqa: PLC0415

    yield
    leftover = session_database_file(settings)
    if leftover is None or not leftover.exists():
        return
    for path in (leftover, *(leftover.with_name(leftover.name + suffix) for suffix in ("-wal", "-shm", "-journal"))):
        path.unlink(missing_ok=True)
    pytest.fail(f"{leftover} existed after the test. {SESSION_DATABASE_RULE}", pytrace=False)


@pytest.fixture(autouse=True)
def fail_if_session_telemetry_folder_has_a_file() -> Generator[None, None, None]:
    """Fail the test that leaves a file in the session's telemetry folder.

    The suite turns telemetry through the settings off, so a file in the folder after a test means the test turned it
    on, or wrote a log, outside its own folder. A test that records telemetry passes its own recorder. Each file is
    removed, so that only the test that created it fails.
    """
    from investment_analysis_engine.config import settings  # noqa: PLC0415

    yield
    leftovers = session_telemetry_files(settings)
    if not leftovers:
        return
    for path in leftovers:
        path.unlink(missing_ok=True)
    names = ", ".join(str(path) for path in leftovers)
    pytest.fail(f"{names} existed after the test. {SESSION_TELEMETRY_RULE}", pytrace=False)


@pytest.fixture(autouse=True)
def restore_current_run_context() -> Generator[None, None, None]:
    """Give each test the run context it started with, so a context one test sets does not reach the next.

    The command-line callback sets the context once for a process and keeps it, so without this a test that invokes the
    CLI leaves its run identity to every test after it.
    """
    from investment_analysis_engine.telemetry.run_context import _current_run_context  # noqa: PLC0415

    before = _current_run_context.get()
    yield
    _current_run_context.set(before)
