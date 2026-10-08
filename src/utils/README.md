# Logging Utility Module

## Overview

This module provides a production-grade, asynchronous, centralized logging architecture optimized for multi-threaded CLI data analysis. It utilizes a completely non-blocking, queue-based approach (`QueueHandler` and `QueueListener`) to offload heavy I/O file writing from your primary data execution threads, ensuring fluid performance across Windows, macOS, and Docker (Linux).

## Key Features

- **Asynchronous, Non-Blocking Architecture**: Thread-safe logging that routes records through a central memory queue to keep analytical execution flows fast.
- **Dual-Output Routing**: Dispatches log entries to both native standard console output (`sys.stdout`) and a dedicated file pipeline concurrently.
- **Enhanced Cross-Platform Rotation**: Subclasses `TimedRotatingFileHandler` to seamlessly enforce *both* time-based (e.g., daily) and size-based limits (`maxBytes`) without filename collisions.
- **Thread-Safe Log Compression**: Automatically compresses older logs into standard `.zip` files via background threads, strictly avoiding native Windows host file-locking crashes (`PermissionError`).
- **ANSI Terminal Colorization**: Features high-visibility, color-coded level tags on the console, while maintaining standard plain-text formatting in the log files for seamless log scanning.
- **Global Failure Interception**: Catches and logs uncaught exceptions with full stack traces across both the main execution flow and secondary worker threads automatically.
- **Docker-Safe Graceful Exits**: Hooks directly into Python's `atexit` cycle to fully finish and zip pending log files when receiving container termination signals (`SIGTERM`).

---

## Architectural Lifecycle Separation

To maintain strict thread-safety and avoid breaking background log queues, this system explicitly separates your lifecycles into two distinct layers:
1. **Global Logging System**: Started once at application launch and stopped once at application exit. It owns the queue processor, the console streamers, and the background compression worker pools.
2. **Context Logging Adapters**: Spawned dynamically within structural modules or request handlers to wrap one module logger without altering the core global logging pipes.

---

## Usage Instructions

### 1. System Initialization (Application Entry Point)

Invoke `setup_global_logging()` exactly **once** at the absolute entry point of your CLI tool (e.g., in `main.py` or `typer_main.py`) before spawning worker threads or initializing specific module loggers.

```python
import logging
from src.utils.logger_util import setup_global_logging, setup_logger

# Initialize async message routing pipes and system crash hooks once
setup_global_logging()

# Fetch your module-level logger wrapper
logger_context = setup_logger(__name__)
```

### 2. Standard Logging Operations

To use the logger normally, access its `.logger` property. You do **not** need to wrap routine log lines inside context blocks.

```python
def process_data_array():
    logger_context.logger.info("Initializing analytical array workspace...")
```

### 3. Context Adapters

`with setup_logger(__name__) as adapter` yields a `ContextualAdapter`. A caller may pass `extra={"context_data": ...}` to a log call to append that value inline to the message. Nothing else is appended.

---

## API Reference
 
### `setup_global_logging()`
Construct the central core logging pipeline. Start the background queue processor, set up plain text file bindings, initialize the ANSI console formatter, and hook up main and thread-level crash interception.

### `setup_logger(logger_name: str) -> LoggerContext`
Fetch a standard logger by namespace identifier and map its message outputs directly into the global worker queue.
- **Returns**: A tracking `LoggerContext` container block.

---

## Best Practices

1. **Let `atexit` Handle the Lifecycle**: Do not call teardown or stop functions manually. Stopping global listeners prematurely permanently breaks the logging architecture for remaining threads.
2. **Never Instantiate Handlers Manually**: Do not attach custom handlers directly via `logger.addHandler()`. This creates multiple open file descriptors to `app.log`, resulting in severe runtime file-locking failures on Windows. All routing must be handled through `setup_global_logging()`.
3. **Keep Context Adapters Scoped**: Use the `with setup_logger(...)` pattern only inside local code chunks that need the adapter. Do not leak or re-instantiate the adapter variable outside the block scope.
