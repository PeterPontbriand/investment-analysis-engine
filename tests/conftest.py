"""Global pytest configurations and safety cleanups."""

import logging

import pytest


@pytest.fixture(autouse=True)
def cleanup_logging_handlers():
    """Automatically flush and detach logging handlers after every test to prevent process hangs."""
    yield
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        try:
            handler.close()
            root_logger.removeHandler(handler)
        except Exception:
            pass
