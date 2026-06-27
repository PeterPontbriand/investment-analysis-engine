import atexit
import contextlib
import logging
import os
import sys
import threading
import time
import traceback
import zipfile
from collections.abc import Mapping, MutableMapping
from logging.handlers import QueueHandler, QueueListener, TimedRotatingFileHandler
from pathlib import Path
from queue import Queue
from types import TracebackType
from typing import Any, ClassVar, override

from ..config import settings

# --- GLOBAL LOGGING SYSTEM STATE ---

_global_logging_initialized: bool = False
# Create a queue for logging records
_log_queue: Queue[logging.LogRecord] = Queue()
_listeners: list[QueueListener] = []
_fmt_str = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
_datefmt = "%Y-%m-%d %H:%M:%S"


# Custom log formatter
class ConsoleColorFormatter(logging.Formatter):
    """Custom formatter that adds ANSI color coding to console output logs."""

    # ANSI Escape Sequences
    GREY = "\x1b[38;20m"
    GREEN = "\x1b[32;20m"
    YELLOW = "\x1b[33;20m"
    RED = "\x1b[31;20m"
    BOLD_RED = "\x1b[31;1m"
    RESET = "\x1b[0m"

    # Map log levels to target colors
    COLORS: ClassVar[dict[int, str]] = {
        logging.DEBUG: GREY,
        logging.INFO: GREEN,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: BOLD_RED,
    }

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the record.

        Args:
            record: The log record to format.

        Returns:
            str: The formatted log message.

        """
        # Clone the record levelname to wrap it in escape characters cleanly
        original_levelname = record.levelname
        color = self.COLORS.get(record.levelno, self.RESET)

        # Colorize just the LEVELNAME component for readability
        record.levelname = f"{color}{original_levelname}{self.RESET}"

        # Format using the standard pattern layout rules
        result = super().format(record)

        # Restore the original state so other handlers (like the file) stay plain
        record.levelname = original_levelname
        return result


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
    Constructs the thread-safe handler pipeline for both File and Console
    output and starts background queue execution.
    """
    # global boolean gate; needed to prevent double-initialization hooks from attaching to root loggers.
    global _global_logging_initialized  # noqa: PLW0603
    if _global_logging_initialized:
        return

    # 1. Base File Formatter (Plain Text)
    file_formatter = logging.Formatter(fmt=_fmt_str, datefmt=_datefmt, style="%")

    # 2. Colored Console Formatter
    console_formatter = ConsoleColorFormatter(fmt=_fmt_str, datefmt=_datefmt, style="%")

    # 3. Instantiate File Handler
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

    # 4. Instantiate Console (stdout) Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)

    # 5. Attach QueueListener to manage BOTH handlers asynchronously
    listener = QueueListener(_log_queue, file_handler, console_handler, respect_handler_level=True)
    listener.start()
    _listeners.append(listener)

    # 6. REGISTER THE UNCAUGHT EXCEPTION HOOK
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
    """Stop execution hooks, flush pipelines, and join file handles."""
    for listener in _listeners:
        if hasattr(listener, "stop"):
            listener.stop()
    if len(_listeners) == 0 and _log_queue:
        _log_queue.queue.clear()

    logging.shutdown()
    wait_for_log_compression_shutdown()


# Automatic hook registration to protect Docker containers on sudden SIGTERM
atexit.register(teardown_global_logging)


# --- ADAPTERS & MANAGERS ---
class ContextualAdapter(logging.LoggerAdapter):
    """Set up a logger with contextual data and append parameters to log outputs."""

    def __init__(
        self,
        logger: logging.Logger,
        extra: Mapping[str, object] | None = None,
    ) -> None:
        """Initialize the contextual logger adapter instance."""
        super().__init__(logger, extra or {})

    # pyright: ignore[reportIncompatibleVariableOverride]
    @property
    def log_file_path(self) -> Path | None:
        """
        Get the absolute filesystem path of the active log file destination.

        Return None if no file handler is currently active or registered globally.
        """
        # Delayed import to dynamically modify internal global variables from within an isolated scope.
        import sys  # noqa: PLC0415

        current_module = sys.modules[__name__]
        for listener in current_module._listeners:
            for handler in listener.handlers:
                if isinstance(handler, ThreadSafeSizeAwareTimedRotatingFileHandler):
                    return Path(handler.baseFilename)
        return None

    def read_log_contents(self) -> str:
        """
        Read and return the entire current plain-text contents of the active log file.

        Return an empty string if the file is missing, empty, or temporarily locked by the OS.
        """
        path = self.log_file_path
        if not path or not path.exists():
            return ""

        try:
            # Use explicit encoding to ensure parity across Windows, macOS, and Linux
            with open(path, encoding=settings.log_encoding) as f:
                return f.read()
        except OSError:
            # Fail safely if a background process holds an exclusive Windows lock
            return ""

    def set_extra(self, extra: Mapping[str, str]) -> None:
        """Update the logger's extra context with new values safely."""
        current_extra = dict(self.extra) if self.extra else {}
        current_extra.update(extra)
        self.extra = current_extra

    def process(
        self, msg: object, kwargs: MutableMapping[str, str | Mapping[str, str]]
    ) -> tuple[object, MutableMapping[str, str | Mapping[str, str]]]:
        """Process the log message and append all active contextual metadata keys to the output string."""
        # 1. Capture dynamic metadata dictionary attributes set via adapter.set_extra()
        if self.extra:
            # Format dictionary items cleanly into a scannable string (e.g., "[user_id:1234, request_id:ABCD]")
            context_string = ", ".join(f"{k}:{v}" for k, v in self.extra.items())
            msg = f"{msg!s} [{context_string}]"

        # 2. Keep support intact for on-the-fly inline log extensions if needed
        if "extra" in kwargs and isinstance(kwargs["extra"], dict) and "context_data" in kwargs["extra"]:
            context_data = kwargs["extra"]["context_data"]
            msg = f"{msg!s} | {context_data}"

        return super().process(msg, kwargs)


class LoggerContext:
    """Provide a thread-safe context manager lifecycle for isolated module metadata."""

    def __init__(self, logger: logging.Logger) -> None:
        """Initialize the context container with an empty metadata adapter."""
        self.adapter = ContextualAdapter(logger, {})

    def __enter__(self) -> ContextualAdapter:
        """Enter the context block scope and return the contextual adapter instance."""
        # Create a completely fresh dictionary for this specific execution block scope
        self.adapter.extra = {}
        return self.adapter

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the context block scope and clear the internal adapter dictionary."""
        # Completely wipe the dictionary references on exit
        current_extra = dict(self.adapter.extra) if self.adapter.extra else {}
        current_extra.clear()
        self.adapter.extra = current_extra


def handle_uncaught_exception(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: TracebackType | None,
) -> None:
    """
    Intercept uncaught exceptions globally.

    Log them with full stack traces to both the console and file handlers before the
    application finishes crashing.
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


def setup_logger(logger_name: str) -> LoggerContext:
    """
    Create and configure a logger with the specified name, returning it as a context manager.

    Args:
        logger_name: Name of the logger to create

    Returns:
        A configured logger as a context manager

    """
    # Defensive fall-back insurance in case setup_global_logging wasn't called explicitly
    if not _global_logging_initialized:
        setup_global_logging()

    logger = logging.getLogger(logger_name)
    logger.setLevel(settings.log_level)

    # Prevent appending multiple QueueHandlers if the logger is re-fetched
    if not any(isinstance(h, QueueHandler) for h in logger.handlers):
        queue_handler = QueueHandler(_log_queue)
        logger.addHandler(queue_handler)

    return LoggerContext(logger)


def get_log_queue_contents() -> list[str]:
    """Retrieve contents from the global log queue as formatted strings."""
    records = []
    while not _log_queue.empty():
        try:
            item = _log_queue.get_nowait()
            # If it's already a LogRecord instance, use it directly;
            # otherwise, build it from a dictionary (like worker.py sends)
            record = item if isinstance(item, logging.LogRecord) else logging.makeLogRecord(item)

            formatter = logging.Formatter(_fmt_str, _datefmt)
            records.append(formatter.format(record))
        except Exception:
            pass
    return records
