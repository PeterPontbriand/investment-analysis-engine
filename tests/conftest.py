"""Global pytest configurations and safety cleanups."""

import logging
from collections.abc import Generator

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
