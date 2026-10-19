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

import logging  # noqa: E402
from collections.abc import Generator  # noqa: E402
from typing import TYPE_CHECKING  # noqa: E402

import pytest  # noqa: E402

from tests._collection_hint import pytest_make_collect_report  # noqa: E402
from tests._live_selection import pytest_addoption, pytest_collection_modifyitems, pytest_configure  # noqa: E402
from tests._network_guard import block_external_sockets, block_live_yahoo  # noqa: E402
from tests._session_isolation import stop_session_if_outside  # noqa: E402

if TYPE_CHECKING:
    from investment_analysis_engine.config import ProjectSettings

__all__ = [
    "block_external_sockets",
    "block_live_yahoo",
    "cleanup_logging_handlers",
    "pytest_addoption",
    "pytest_collection_modifyitems",
    "pytest_configure",
    "pytest_make_collect_report",
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


@pytest.fixture
def isolated_cli_settings(isolated_cli_database: ProjectSettings) -> ProjectSettings:
    """The isolated settings the CLI commands use; requires the module to import isolated_cli_database."""
    return isolated_cli_database
