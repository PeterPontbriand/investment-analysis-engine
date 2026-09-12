"""Persistent OS-owned sidecar locks for coordinated SQLite startup."""

import errno
import os
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl


@dataclass(frozen=True)
class ReadinessLockPolicy:
    """Polling interval for nonblocking ownership attempts, bounded by a deadline."""

    poll_seconds: float = 0.05


class ReadinessLockTimeoutError(TimeoutError):
    """Ownership remained busy until the configured deadline."""


def _lock(descriptor: int) -> None:
    if sys.platform == "win32":
        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
    else:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)


@contextmanager
def readiness_lock(path: Path | None, timeout_ms: int) -> Iterator[None]:
    """Own the stable sidecar until scope exit; memory storage needs no sidecar.

    The file is never truncated or unlinked. Closing its handle releases the
    operating-system lock even after an exception or process termination.
    """
    if path is None:
        yield
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(str(path) + ".readiness.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        deadline = time.monotonic() + timeout_ms / 1_000
        policy = ReadinessLockPolicy()
        while True:
            try:
                _lock(descriptor)
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN):
                    raise
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ReadinessLockTimeoutError("Database startup ownership is busy.") from exc
                time.sleep(min(policy.poll_seconds, remaining))
        yield
    finally:
        os.close(descriptor)
