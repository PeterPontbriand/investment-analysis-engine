import logging
import signal
import sys
from multiprocessing import Queue
from types import FrameType

from .logger_util import setup_logger

logger = logging.getLogger(__name__)


def worker(
    log_queue: Queue,
    logger_name: str = "default_logger",
) -> None:
    """
    Handle queued logging records from child processes.

    Create a worker process that continuously listens for and handles logging
    records from a shared queue. Implement clean shutdown on SIGINT or SIGTERM.

    Args:
        log_queue: Queue used to receive logging records
        logger_name: Name of the logger to use

    """

    def signal_handler(sig: int, frame: FrameType | None) -> None:  # noqa: ARG001
        """Handle interrupt signals."""
        logger.info(f"{logger_name} received signal {sig}: exiting...")
        sys.exit(0)

    # Register signal handlers for clean shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Initialize logger context manager using centralized utility
    logger_context = setup_logger(logger_name)

    try:
        # Enter the context manager to resolve the operational adapter wrapper
        with logger_context as adapter:
            while True:
                record_dict: dict[str, str] = log_queue.get()
                if not isinstance(record_dict, dict):
                    continue

                # Convert dictionary to log record and dispatch it
                record = logging.makeLogRecord(record_dict)

                # Access the inner logger to process raw LogRecord instances safely
                adapter.logger.handle(record)

    except KeyboardInterrupt:
        logger.info(f"{logger_name} shutting down gracefully")
    except Exception as e:
        logger.error(f"{logger_name} encountered fatal error: {e!s}", exc_info=True)
        raise

    finally:
        # Intentionally remove manual teardown calls to allow the global
        # atexit engine to finalize stream and compression lifecycles safely.
        pass
