"""Unit tests for validating the custom thread-safe size-aware rotating logging handler."""

import logging
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.utils.logger_util import (
    ConsoleColorFormatter,
    LoggerContext,
    ThreadSafeSizeAwareTimedRotatingFileHandler,
    _log_queue,
    get_log_queue_contents,
    setup_logger,
    wait_for_log_compression_shutdown,
)


@pytest.fixture
def temp_log_dir(tmp_path: Path) -> Path:
    """Fixture providing an isolated temporary directory for logging tests."""
    return tmp_path


def test_console_color_formatter() -> None:
    """Verify ConsoleColorFormatter wraps log levels with ANSI escape sequences."""
    formatter = ConsoleColorFormatter(fmt="%(levelname)s | %(message)s")
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Sample log message",
        args=None,
        exc_info=None,
    )
    formatted = formatter.format(record)

    # Assert color coding wrap on level name
    assert ConsoleColorFormatter.GREEN in formatted
    assert ConsoleColorFormatter.RESET in formatted
    # Check that original levelname state was restored correctly
    assert record.levelname == "INFO"


def test_size_based_rollover_with_zip_compression(temp_log_dir: Path) -> None:
    """Verify log files properly roll over and compress to .zip files when reaching max size."""
    log_file = temp_log_dir / "test_size_rollover.log"

    # Setup handler with a tiny max_bytes bound (100 bytes) to force instant rotation
    handler = ThreadSafeSizeAwareTimedRotatingFileHandler(
        filename=str(log_file),
        max_bytes=100,
        backup_count=2,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))

    logger = logging.getLogger("test_size_rollover")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    # Write some logs exceeding 100 bytes
    logger.info("Line 1: A very long string designed to fill the log handler buffer up immediately.")
    logger.info("Line 2: Triggering the rollover limit on this second write.")

    # Force close the stream to trigger flush
    handler.close()
    logger.removeHandler(handler)

    # Ensure background compression thread executes completely
    wait_for_log_compression_shutdown()

    # Assertions
    # 1. The active log file should exist (or be clean)
    assert log_file.exists()

    # 2. There should be exactly ONE active .log file and ONE compressed .zip file in the directory
    all_files = list(temp_log_dir.glob("*"))
    log_files = [f for f in all_files if f.suffix == ".log"]
    zip_files = [f for f in all_files if f.suffix == ".zip"]

    assert len(log_files) == 1
    assert len(zip_files) >= 1

    # 3. Read the ZIP archive to verify contents were rotated and zipped safely
    rotated_zip = zip_files[0]
    with zipfile.ZipFile(rotated_zip, "r") as zip_ref:
        namelist = zip_ref.namelist()
        assert len(namelist) == 1
        # Extract and verify the file content inside the ZIP is indeed our first write
        content = zip_ref.read(namelist[0]).decode("utf-8")
        assert "Line 1" in content


def test_timed_rollover_at_simulated_interval(temp_log_dir: Path) -> None:
    """Verify custom handler rolls over and updates rolloverAt successfully on time boundaries."""
    log_file = temp_log_dir / "test_time_rollover.log"

    # Initialize with 1-second interval rotation
    handler = ThreadSafeSizeAwareTimedRotatingFileHandler(
        filename=str(log_file),
        max_bytes=10000,
        backup_count=1,
        when="S",
        interval=1,
        encoding="utf-8",
    )

    initial_rollover_at = handler.rolloverAt

    # Simulate time skipping past the rolloverAt threshold
    future_time = initial_rollover_at + 10
    with patch("time.time", return_value=future_time):
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py", lineno=1, msg="Time test", args=None, exc_info=None
        )
        # Check that handler should trigger a rollover now
        assert handler.shouldRollover(record) is True

        # Trigger rollover explicitly
        handler.doRollover()

        # Verify rolloverAt was updated successfully to the next boundary (avoids infinite loop)
        assert handler.rolloverAt > initial_rollover_at

    handler.close()
    wait_for_log_compression_shutdown()


def test_contextual_adapter_and_context_manager() -> None:
    """Verify ContextualAdapter appends dictionary metadata context to printed messages."""
    logger = logging.getLogger("test_context")
    logger.setLevel(logging.INFO)

    # Test Context manager allocation
    context = LoggerContext(logger)
    with context as adapter:
        adapter.set_extra({"request_id": "ABC-123", "user_id": "999"})
        # Process some log message
        msg, kwargs = adapter.process("Running momentum backtest", {})

        # Assert metadata is formatted cleanly into the message string
        assert "Running momentum backtest" in msg
        assert "request_id:ABC-123" in msg
        assert "user_id:999" in msg


def test_setup_logger_idempotency() -> None:
    """Verify setup_logger does not stack duplicate QueueHandlers on multiple requests."""
    logger_name = "test_idempotency_logger"

    # Trigger first config
    ctx_1 = setup_logger(logger_name)
    logger_instance = ctx_1.adapter.logger
    handlers_count_1 = len(logger_instance.handlers)

    # Trigger second config
    setup_logger(logger_name)
    handlers_count_2 = len(logger_instance.handlers)

    # Assert handlers count did not change/double
    assert handlers_count_1 == handlers_count_2
    assert any(isinstance(h, logging.handlers.QueueHandler) for h in logger_instance.handlers)


def test_get_log_queue_contents() -> None:
    """Verify get_log_queue_contents flushes records cleanly."""
    # Seed the queue with dummy log records
    record = logging.LogRecord(
        name="test_queue",
        level=logging.INFO,
        pathname="test.py",
        lineno=5,
        msg="Seeded record",
        args=None,
        exc_info=None,
    )
    _log_queue.put(record)

    contents = get_log_queue_contents()
    assert len(contents) == 1
    assert "Seeded record" in contents[0]
    assert _log_queue.empty() is True
