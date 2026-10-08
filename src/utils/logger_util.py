import atexit
import contextlib
import logging
import os
import sys
import threading
import time
import traceback
import zipfile
from logging.handlers import QueueHandler, QueueListener, TimedRotatingFileHandler
from queue import Queue
from types import TracebackType
from typing import Any, ClassVar, override

from src.config import settings

# --- GLOBAL LOGGING SYSTEM STATE ---

_global_logging_initialized: bool = False
# Create a queue for logging records
_log_queue: Queue[logging.LogRecord] = Queue()
_listeners: list[QueueListener] = []
_fmt_str = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
_datefmt = "%Y-%m-%d %H:%M:%S"


# --- CUSTOM CROSS-PLATFORM COMPRESSION FILE HANDLER ---
class ThreadSafeSizeAwareTimedRotatingFileHandler(TimedRotatingFileHandler):
    """
    A thread-safe, cross-platform handler that rotates files by time and size.

    Fully optimized for Windows, Docker (Linux), and macOS with clean exit hooks.
    """

    _active_compression_threads: ClassVar[list[threading.Thread]] = []
    _shutdown_lock = threading.Lock()

    def __init__(
        self,
        filename: str,
        max_bytes: int,
        backup_count: int,
        encoding: str | None = None,
        *_args: Any,
        **_kwargs: Any,
    ) -> None:
        """Initialize the handler with filename, maxBytes, and backupCount."""
        super().__init__(filename=filename, encoding=encoding, backupCount=backup_count)
        self.maxBytes = max_bytes
        self._rollover_lock = threading.Lock()

    @override
    def shouldRollover(self, record: logging.LogRecord) -> bool:
        """Determine if the log should be rolled over based on size and time."""
        with self._rollover_lock:
            if super().shouldRollover(record):
                return True

            if self.maxBytes > 0 and os.path.exists(self.baseFilename):
                msg = self.format(record)
                approx_msg_size = len(msg.encode("utf-8")) if isinstance(msg, str) else len(msg)
                current_size = os.path.getsize(self.baseFilename)
                if current_size + approx_msg_size >= self.maxBytes:
                    return True
            return False

    def _safe_compress(self, source_path: str) -> None:
        """Safely compress a source file using threading to avoid blocking."""
        current_thread = threading.current_thread()
        try:
            if not os.path.exists(source_path):
                return
            zip_path = f"{source_path}.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(source_path, os.path.basename(source_path))
            os.remove(source_path)
        except Exception as e:
            # Delayed import to avoid circular dependency trees
            import sys  # noqa: PLC0415

            print(f"Error compressing log file {source_path}: {e}", file=sys.stderr)
        finally:
            with self._shutdown_lock:
                if current_thread in self._active_compression_threads:
                    self._active_compression_threads.remove(current_thread)

    @override
    def doRollover(self) -> None:
        """Override the doRollover method to handle log file compression."""
        with self._rollover_lock:
            if self.stream:
                self.stream.close()
                self.stream = None

            if not os.path.exists(self.baseFilename) or os.path.getsize(self.baseFilename) == 0:
                # Still must compute the next rollover timestamp boundary even if skipping
                current_time = int(time.time())
                new_rollover_at = self.computeRollover(current_time)
                while new_rollover_at <= current_time:
                    new_rollover_at = new_rollover_at + self.interval
                self.rolloverAt = new_rollover_at

                if not self.delay:
                    self.stream = self._open()
                return

            current_time = int(self.rolloverAt - self.interval)
            is_time_rollover = time.time() >= self.rolloverAt
            time_suffix = self.suffix
            formatted_time = time.strftime(time_suffix, time.localtime(current_time))

            if is_time_rollover:
                dst_file = f"{self.baseFilename}.{formatted_time}"
                if os.path.exists(dst_file) or os.path.exists(f"{dst_file}.zip"):
                    dst_file = self._get_unique_index_path(f"{self.baseFilename}.{formatted_time}")
            else:
                dst_file = self._get_unique_index_path(f"{self.baseFilename}.{formatted_time}")

            try:
                os.rename(self.baseFilename, dst_file)
                t = threading.Thread(target=self._safe_compress, args=(dst_file,), daemon=True)
                with self._shutdown_lock:
                    self._active_compression_threads.append(t)
                t.start()
            except OSError as e:
                # Delayed import to avoid circular dependency trees
                import sys  # noqa: PLC0415

                print(f"Failed to rotate log file: {e}", file=sys.stderr)

            # Compute and update the next rollover timestamp boundary (stops infinite rollover loop)
            curr_time = int(time.time())
            new_rollover_at = self.computeRollover(curr_time)
            while new_rollover_at <= curr_time:
                new_rollover_at = new_rollover_at + self.interval
            self.rolloverAt = new_rollover_at

            if self.backupCount > 0:
                self.handle_backup_count()

            if not self.delay:
                self.stream = self._open()

    def _get_unique_index_path(self, base_target: str) -> str:
        """Get a unique index path for the log file."""
        index = 1
        while True:
            dst_file = f"{base_target}.{index}"
            if not os.path.exists(dst_file) and not os.path.exists(f"{dst_file}.zip"):
                return dst_file
            index += 1

    def handle_backup_count(self) -> None:
        """Handle the backup count by removing old log files if necessary."""
        dir_name, base_name = os.path.split(self.baseFilename)
        if not os.path.exists(dir_name):
            return
        all_files = os.listdir(dir_name)
        matches = []
        for f in all_files:
            if f.startswith(base_name) and f != base_name:
                full_path = os.path.join(dir_name, f)
                try:
                    matches.append((full_path, os.path.getmtime(full_path)))
                except OSError:
                    continue
        matches.sort(key=lambda x: x[1])
        if len(matches) > self.backupCount:
            for i in range(len(matches) - self.backupCount):
                with contextlib.suppress(OSError):
                    os.remove(matches[i][0])


# --- LIFECYCLE ROUTINES ---
def wait_for_log_compression_shutdown() -> None:
    """Block exits cleanly until background compression jobs finish."""
    with ThreadSafeSizeAwareTimedRotatingFileHandler._shutdown_lock:
        threads_to_join = list(ThreadSafeSizeAwareTimedRotatingFileHandler._active_compression_threads)
    if threads_to_join:
        # Delayed import to avoid circular dependency trees
        import sys  # noqa: PLC0415

        print(
            f"Finishing {len(threads_to_join)} background log compressions...",
            file=sys.stderr,
        )
        for thread in threads_to_join:
            if thread.is_alive():
                thread.join(timeout=10.0)


def setup_global_logging() -> None:
    """
    Set up global logging.

    Called EXACTLY ONCE at the absolute entry point of the application.
    Routes every record from every logger, ours and third-party, at ``settings.log_level`` and above
    through a queue to one rotating log file. There is no console handler: nothing is written to
    standard output or standard error by logging.
    """
    # global boolean gate; needed to prevent double-initialization hooks from attaching to root loggers.
    global _global_logging_initialized  # noqa: PLW0603
    if _global_logging_initialized:
        return

    # 1. Base File Formatter (Plain Text)
    file_formatter = logging.Formatter(fmt=_fmt_str, datefmt=_datefmt, style="%")

    # 2. Instantiate File Handler
    file_path = settings.log_dir / settings.log_file_name
    file_handler = ThreadSafeSizeAwareTimedRotatingFileHandler(
        filename=str(file_path),
        max_bytes=settings.log_max_bytes,
        when=settings.log_when,
        interval=settings.log_interval,
        backup_count=settings.log_backup_count,
        encoding=settings.log_encoding,
    )
    file_handler.setFormatter(file_formatter)

    # 3. Attach QueueListener to write the file asynchronously
    listener = QueueListener(_log_queue, file_handler, respect_handler_level=True)
    listener.start()
    _listeners.append(listener)

    # 4. Send every logger's records to the queue through the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)
    root_logger.addHandler(QueueHandler(_log_queue))

    # 5. REGISTER THE UNCAUGHT EXCEPTION HOOK
    sys.excepthook = handle_uncaught_exception

    # Handle worker thread exceptions cleanly across Windows, Mac, and Linux
    def handle_thread_exception(args: threading.ExceptHookArgs) -> None:
        """Intercept unhandled thread exceptions and route them to the central logger."""
        if args.exc_type and args.exc_value and args.exc_traceback:
            handle_uncaught_exception(args.exc_type, args.exc_value, args.exc_traceback)
        else:
            # Fallback for empty exception structures to ensure visibility
            logger = logging.getLogger("system.crash")
            logger.critical(f"Thread exception occurred in thread: {args.thread}")

    threading.excepthook = handle_thread_exception

    _global_logging_initialized = True


def teardown_global_logging() -> None:
    """Stop execution hooks, flush pipelines, and join file handles cleanly across test runs."""
    global _global_logging_initialized  # noqa: PLW0603

    # 1. Stop all background listener threads completely
    for listener in _listeners:
        if hasattr(listener, "stop"):
            listener.stop()
    _listeners.clear()

    # 2. Clear any lingering records in the queue safely
    if _log_queue:
        with contextlib.suppress(AttributeError), _log_queue.mutex:
            _log_queue.queue.clear()

    # 3. Force-flush and close all handlers attached to the root logger to release file locks
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        try:
            handler.flush()
        except Exception:
            pass
        finally:
            handler.close()
            root_logger.removeHandler(handler)

    # 4. Shutdown the rest of the log subsystem and wait for worker compression threads
    logging.shutdown()
    wait_for_log_compression_shutdown()

    # 5. RESET THE GATE: Allow subsequent tests to completely re-initialize the logging pipeline
    _global_logging_initialized = False


# Automatic hook registration to protect Docker containers on sudden SIGTERM
atexit.register(teardown_global_logging)


def handle_uncaught_exception(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: TracebackType | None,
) -> None:
    """
    Intercept uncaught exceptions globally.

    Log them with full stack traces to the log file, then print the standard traceback on standard error,
    before the application finishes crashing.
    """
    # Don't log KeyboardInterrupt (Ctrl+C) as a scary system crash error
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    # Fetch the root logger or a generic system logger to dispatch the record
    logger = logging.getLogger("system.crash")

    # Format the traceback into a clean, human-readable multi-line string
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))

    # Log the crash at CRITICAL level so it stands out visually
    logger.critical(f"Uncaught exception encountered:\n{error_msg}")

    # Logging writes only to the file, so show the user the traceback on standard error as Python would
    sys.__excepthook__(exc_type, exc_value, exc_traceback)
