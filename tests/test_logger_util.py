import contextlib
import logging
import os
import sys
import threading
import time
import uuid
from logging.handlers import QueueHandler
from unittest import mock

import pytest

from src.config import settings
from src.utils.logger_util import (
    ConsoleColorFormatter,
    ThreadSafeSizeAwareTimedRotatingFileHandler,
    handle_uncaught_exception,
    setup_global_logging,
    setup_logger,
    teardown_global_logging,
)


@pytest.fixture(autouse=True)
def manage_logging_lifecycle(tmp_path):
    """
    Scam-isolation fixture.

    Overrides settings log pathways to a temporary directory
    and handles clean global environment setup/teardown between every test iteration.
    """
    # 1. Reset utility tracking state variables prior to running tests
    import src.utils.logger_util as lu  # noqa: PLC0415

    lu._global_logging_initialized = False
    lu._listeners = []

    # Empty out queue explicitly
    while not lu._log_queue.empty():
        with contextlib.suppress(BaseException):
            lu._log_queue.get_nowait()

    # 2. Redirect log destination configurations to temporary sandbox directories
    original_log_dir = settings.log_dir
    original_log_file = settings.log_file_name

    settings.log_dir = tmp_path
    settings.log_file_name = f"test_{uuid.uuid4().hex}.log"

    yield tmp_path

    # 3. Terminate global worker processes completely on teardown
    teardown_global_logging()

    # Restore configuration state invariants
    settings.log_dir = original_log_dir
    settings.log_file_name = original_log_file


def test_basic_logging_and_handler_routing():
    """Verify standard single logger handler attaches QueueHandler and logs metadata."""
    logger_name = f"test-module-{uuid.uuid4().hex}"
    setup_global_logging()

    logger_context = setup_logger(logger_name)

    unique_msg = "Explicit path tracking verification"

    # Validate Context Manager metadata injection works
    with logger_context as adapter:
        assert hasattr(adapter.logger, "handlers")
        assert len(adapter.logger.handlers) == 1

        queue_handler = adapter.logger.handlers[0]
        assert isinstance(queue_handler, QueueHandler)

        adapter.set_extra({"user_id": "test_user"})
        adapter.info(unique_msg)

        # Ask the adapter directly where its file is located
        active_log_file = adapter.log_file_path

        # Verify the log file path property resolved successfully
        assert active_log_file is not None
        assert active_log_file.exists()

        time.sleep(0.1)  # Brief yield to allow async queue to flush to disk

        # Safely read the file contents directly through the adapter interface
        file_contents = adapter.read_log_contents()

    # CRITICAL SECURITY ASSERTIONS:
    # 1. Confirm the primary log message was captured
    assert unique_msg in file_contents

    # 2. Confirm the contextual metadata was injected and formatted into the text string
    assert "user_id:test_user" in file_contents


def test_console_color_formatter():
    """Verify that ConsoleColorFormatter attaches ANSI tags and rolls back state correctly."""
    formatter = ConsoleColorFormatter(fmt="%(levelname)s: %(message)s")
    record = logging.LogRecord("test", logging.INFO, "pathname", 1, "Log message", (), None)

    formatted_text = formatter.format(record)

    # Assert colored output contains ANSI escape sequences
    assert "\x1b[32;20mINFO\x1b[0m" in formatted_text

    # Assert underlying properties remain plain text for file logs safety
    assert record.levelname == "INFO"


def test_thread_safe_size_aware_rotation(tmp_path):
    """Verify size thresholds safely trigger unique incrementing background zip rotations."""
    log_file_path = tmp_path / "rotation_test.log"

    # Create handler with a tiny limit (50 bytes) to force quick rotations
    handler = ThreadSafeSizeAwareTimedRotatingFileHandler(
        filename=str(log_file_path), max_bytes=50, backup_count=2, when="D", interval=1
    )
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)

    record = logging.LogRecord("test", logging.INFO, "path", 1, "A" * 60, (), None)

    # 1. First big log message triggers a rotation criterion
    assert handler.shouldRollover(record) is True

    # Write a record to file manually to simulate logging pipeline execution
    handler.stream = handler._open()
    handler.emit(record)

    # Run the rollover
    handler.doRollover()

    # Close active file stream cleanly
    if handler.stream:
        handler.stream.close()

    # Give the thread pool background worker time to compress file records
    time.sleep(0.5)

    # 2. Check that the original file was zipped and a new empty log was created
    all_files = os.listdir(tmp_path)
    zip_archives = [f for f in all_files if f.endswith(".zip")]

    assert len(zip_archives) >= 1
    assert "rotation_test.log" in all_files


def test_multithreaded_stress_logging():
    """Verifies queue listener can ingest massive concurrent load across background threads."""
    setup_global_logging()
    logger_context = setup_logger("threaded_stress")

    thread_count = 5
    logs_per_thread = 20
    threads = []

    # Enter the context manager once to get the operational adapter for workers
    with logger_context as adapter:

        def worker() -> None:
            for i in range(logs_per_thread):
                # Log directly through the thread-safe adapter instance
                adapter.info(f"Thread worker output frame index line {i}")
                time.sleep(0.001)

        for _ in range(thread_count):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Capture the active path directly from the adapter before pipeline teardown
        log_file_path = adapter.log_file_path

    # Flush structural pipelines completely
    teardown_global_logging()

    # Ensure the path property resolved successfully and the file exists
    assert log_file_path is not None
    assert log_file_path.exists()

    with open(log_file_path, encoding="utf-8") as f:
        lines = f.readlines()

    # Total messages written must equal cumulative cross products
    assert len(lines) == (thread_count * logs_per_thread)


def test_global_uncaught_exception_hook():
    """Assert hook captures sys events and maps them directly into critical queue items."""
    setup_global_logging()

    try:
        raise ValueError("Critical simulated compute calculation failure")
    except ValueError:
        exc_info = sys.exc_info()

    # Add a strict guard assertion to satisfy the linter and verify values are not None
    assert exc_info[0] is not None
    assert exc_info[1] is not None
    assert exc_info[2] is not None

    exc_type, exc_value, exc_traceback = exc_info

    # Actively fire standard mock exception catcher directly into runtime framework
    with mock.patch("logging.Logger.critical") as mock_logger_critical:
        handle_uncaught_exception(exc_type, exc_value, exc_traceback)

        # Verify the exception hook intercepted the stack trace and called critical logging
        assert mock_logger_critical.called
        log_arg = str(mock_logger_critical.call_args[0][0])
        assert "ValueError" in log_arg
        assert "Critical simulated compute calculation failure" in log_arg


def test_context_metadata_is_cleanly_wiped_on_exit():
    """Verify that contextual metadata is entirely cleared after exiting the context block."""
    setup_global_logging()
    logger_context = setup_logger("test_leak_prevention")

    # 1. Enter the context and establish target metadata variables
    with logger_context as adapter:
        adapter.set_extra({"user_id": "session_9999", "agent_id": "finance_bot"})

        # Confirm that the dictionary is populated actively inside the block scope
        assert adapter.extra.get("user_id") == "session_9999"
        assert adapter.extra.get("agent_id") == "finance_bot"

        adapter.info("Logging active transactional metadata session.")

    # 2. Assert against the adapter state immediately outside the context block
    # This proves that LoggerContext.__exit__() successfully triggered its dictionary cleanup
    assert len(adapter.extra) == 0
    assert "user_id" not in adapter.extra
    assert "agent_id" not in adapter.extra

    # 3. Double-check the physical file records to ensure data integrity
    time.sleep(0.1)  # Brief yield to allow the async queue to write to disk
    file_contents = adapter.read_log_contents()

    # The file must contain the historical entry text, proving it wrote successfully before clearing
    assert "user_id:session_9999" in file_contents
    assert "agent_id:finance_bot" in file_contents


if __name__ == "__main__":
    pytest.main([__file__])
