"""Global pytest configurations and safety cleanups."""

import os

# Typer and Rich read FORCE_COLOR when they are imported or first render, so it must be set before
# any import that can load them. Forcing styled CLI output for every pytest run makes a raw
# CLI-text assertion fail locally exactly as it would on a CI runner, rather than only in CI.
os.environ["FORCE_COLOR"] = "1"

import logging  # noqa: E402
from collections.abc import Generator  # noqa: E402

import pytest

from tests._live_selection import pytest_addoption, pytest_collection_modifyitems, pytest_configure
from tests._network_guard import block_external_sockets, block_live_yahoo

__all__ = [
    "block_external_sockets",
    "block_live_yahoo",
    "cleanup_logging_handlers",
    "pytest_addoption",
    "pytest_collection_modifyitems",
    "pytest_configure",
]


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
