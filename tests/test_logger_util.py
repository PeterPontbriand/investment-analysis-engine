import contextlib
import logging
import threading
import time
import uuid
from logging.handlers import QueueHandler

import pytest

from src.utils.logger_util import setup_global_logging, setup_logger, teardown_global_logging


@pytest.fixture(autouse=True)
def clean_logging_state():
    """Ensure a pristine global logging configuration and clear files before every test."""
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
        h.close()

    yield

    with contextlib.suppress(Exception):
        teardown_global_logging()

    for h in root.handlers[:]:
        root.removeHandler(h)
        h.close()


def test_basic_logging_and_handler_routing():
    """Verify standard single logger handler attaches QueueHandler and logs metadata."""
    logger_name = f"test-module-{uuid.uuid4().hex}"
    setup_global_logging()

    logger_context = setup_logger(logger_name)
    unique_msg = "Explicit path tracking verification"

    # 1. Fetch file reference by setting up a temporary look-ahead context
    with logger_context as adapter:
        active_log_file = adapter.log_file_path

    # 2. Clear target file completely OUTSIDE of active log context operations
    if active_log_file and active_log_file.exists():
        active_log_file.write_text("", encoding="utf-8")

    # 3. Perform execution run
    with logger_context as adapter:
        assert hasattr(adapter.logger, "handlers")
        assert len(adapter.logger.handlers) == 1

        queue_handler = adapter.logger.handlers[0]
        assert isinstance(queue_handler, QueueHandler)

        adapter.set_extra({"user_id": "test_user"})
        adapter.info(unique_msg)

    teardown_global_logging()

    assert active_log_file is not None
    assert active_log_file.exists()

    with open(active_log_file, encoding="utf-8") as f:
        file_contents = f.read()

    assert unique_msg in file_contents


def test_multithreaded_stress_logging():
    """Verifies queue listener can ingest massive concurrent load across background threads."""
    setup_global_logging()
    logger_context = setup_logger("threaded_stress")

    thread_count = 5
    logs_per_thread = 20
    threads = []

    # 1. Grab the log file path cleanly
    with logger_context as adapter:
        log_file_path = adapter.log_file_path

    # 2. Execute concurrent workers within the active logging block
    with logger_context as adapter:

        def worker() -> None:
            for i in range(logs_per_thread):
                adapter.info(f"Thread worker output frame index line {i}")
                time.sleep(0.001)

        for _ in range(thread_count):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 3. Force-flush the background QueueListener to disk BEFORE the context manager closes
        teardown_global_logging()

    assert log_file_path is not None
    assert log_file_path.exists()

    # 4. Read file and match against the specific, unique message pattern produced by this run
    with open(log_file_path, encoding="utf-8") as f:
        lines = [line for line in f if "Thread worker output frame index line" in line]

    assert len(lines) == (thread_count * logs_per_thread)
