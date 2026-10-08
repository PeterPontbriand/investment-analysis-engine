# Logging Utility Module

## Overview

This module routes every log record the application produces into one rotating log file, through a non-blocking queue (`QueueHandler` and `QueueListener`) so that file writing does not slow the analysis. It installs a single queue handler on the root logger, so records from the project's modules and from third-party libraries (`yfinance`, `alembic` and others) all reach the file at the configured level and above. It has no console handler: nothing is written to standard output or standard error by logging, which keeps `--json` output and the command's own messages untouched.

## Key Features

- **Asynchronous, Non-Blocking Architecture**: Thread-safe logging that routes records through a central memory queue to keep analytical execution flows fast.
- **File-Only Output**: Writes log entries to `logs/app.log` (set `LOG_DIR` to move it) and never to the terminal.
- **Enhanced Cross-Platform Rotation**: Subclasses `TimedRotatingFileHandler` to seamlessly enforce *both* time-based (e.g., daily) and size-based limits (`maxBytes`) without filename collisions.
- **Thread-Safe Log Compression**: Automatically compresses older logs into standard `.zip` files via background threads, strictly avoiding native Windows host file-locking crashes (`PermissionError`).
- **Global Failure Interception**: Logs an uncaught exception as `CRITICAL` with its full traceback, from the command-line entry point and from secondary threads, and shows the standard traceback on standard error.
- **Docker-Safe Graceful Exits**: Hooks directly into Python's `atexit` cycle to fully finish and zip pending log files when receiving container termination signals (`SIGTERM`).

---

## Lifecycle

`setup_global_logging()` is called once, by `src/main.py`, before any command runs. It starts the queue listener that writes the log file, attaches one queue handler to the root logger at `settings.log_level`, and installs the uncaught-exception hooks. `teardown_global_logging()` stops the listener, which writes every queued record before it returns. `main()` calls it in a `finally` block and an `atexit` hook calls it again, so a command that exits with a failure status still flushes its records.

---

## Usage

Module code logs the usual way, with no setup:

```python
import logging

logger = logging.getLogger(__name__)
logger.info("Downloading market data for %s", ticker)
```

The record goes to `logs/app.log` (or `LOG_DIR/<log_file_name>`) as `timestamp | logger name | LEVEL | message`. Nothing appears on the terminal, so a message the user must see belongs in the command's own output, not in a log call.

An exception that a command handler reports with a generic sentence is logged with its traceback by `execution_errors`. An exception that no handler catches is logged as `CRITICAL` under `system.crash` by `main()`, and Typer shows its own traceback on standard error.

---

## API Reference

### `setup_global_logging()`
Start the background queue processor and file handler, attach the root queue handler, and hook up main-thread and thread-level crash interception. Safe to call twice; the second call does nothing.

### `teardown_global_logging()`
Stop the listener, flush the queue, close the handlers and wait for background compression. Registered with `atexit`.

### `handle_uncaught_exception(exc_type, exc_value, exc_traceback)`
Log the exception as `CRITICAL` under `system.crash`, then print the standard traceback on standard error.

---

## Best Practices

1. **Let the entry point own the lifecycle**: Do not call setup or teardown from module code. Stopping the listener early loses later records.
2. **Never instantiate handlers manually**: Do not attach custom handlers with `logger.addHandler()`. A second handler on the log file causes file-locking failures on Windows.
3. **Do not print from logging**: There is no console handler by design; standard output carries the command's result and standard error its messages.
