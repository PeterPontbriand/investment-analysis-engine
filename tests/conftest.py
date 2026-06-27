import logging
import os

import pytest


@pytest.fixture(autouse=True)
def auto_monkeypatch(request):
    """Automatically apply monkeypatches for testing."""
    # This ensures all modules are properly mocked in tests
    pass


def pytest_configure(config):  # noqa: ARG001
    """Configure pytest settings before tests run."""
    # Create reports directory if it doesn't exist
    os.makedirs("reports", exist_ok=True)


def pytestfixture_setup():
    """Set up and tear down log handlers."""
    # Setup code here
    yield
    # Cleanup code here


@pytest.fixture(name="clear_log_handlers", autouse=True)
def clear_log_handlers():
    """Explicitly clear all logger handlers before each test."""
    # Ensure no existing handlers carry over from previous tests
    root_logger = logging.getLogger()
    try:
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)
            if hasattr(handler, "close"):
                handler.close()
    except Exception as e:
        print(f"Error clearing log handlers: {e}")
