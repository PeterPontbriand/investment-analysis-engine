"""A real SQLite lock held by a second connection, for the tests of storage errors that follow the readiness check.

:func:`held_lock` blocks every writer; with ``block_reads`` it also blocks readers, by taking the write lock in
exclusive locking mode. The readiness check itself reads the file, so a test that wants the error to come after
readiness passed takes the lock with :func:`lock_after_readiness`, which takes it once the real readiness check
has returned.
:func:`short_wait_settings` gives settings whose busy wait is a tenth of a second.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.data.repositories.readiness import ReadinessOutcome, ensure_database_ready
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from tests._migrated_database import migrated_database_url

SHORT_WAIT_MS = 100
"""The busy wait of :func:`short_wait_settings`, the longest any of these tests waits for a lock."""


def short_wait_settings(tmp_path: Path) -> tuple[ProjectSettings, Path]:
    """Return settings for a migrated database copy that waits :data:`SHORT_WAIT_MS` for a lock, and its file."""
    url = migrated_database_url(tmp_path)
    settings = ProjectSettings(database_url=url, database_busy_timeout_ms=SHORT_WAIT_MS)
    return settings, Path(url.removeprefix("sqlite:///"))


class Lock:
    """A write lock held by its own connection until :meth:`release`; safe to release from any thread."""

    def __init__(self, path: Path, *, block_reads: bool) -> None:
        """Take the lock now: a write transaction that is never committed."""
        self._connection = sqlite3.connect(path, isolation_level=None, check_same_thread=False, timeout=0)
        if block_reads:
            self._connection.execute("PRAGMA locking_mode=EXCLUSIVE")
        self._connection.execute("BEGIN IMMEDIATE")
        self._connection.execute("CREATE TABLE lock_probe (x INTEGER)")
        self._held = True

    def release(self) -> None:
        """Roll the transaction back and close the connection; a second call does nothing."""
        if self._held:
            self._held = False
            self._connection.execute("ROLLBACK")
            self._connection.close()


@contextmanager
def held_lock(path: Path, *, block_reads: bool = False) -> Iterator[Lock]:
    """Hold a write lock on ``path`` for the block."""
    lock = Lock(path, block_reads=block_reads)
    try:
        yield lock
    finally:
        lock.release()


@contextmanager
def lock_after_readiness(monkeypatch: pytest.MonkeyPatch, path: Path, *, block_reads: bool) -> Iterator[None]:
    """Run the real readiness check, then take the lock, for every operation that opens a database in the block.

    The first readiness check that returns takes the lock and later ones leave it as it is, so the error a test sees is
    the one of the operation's own database scope and not readiness's. The lock is released on exit.
    """
    held: list[Lock] = []

    def ready_then_lock(database: SQLiteDatabase) -> ReadinessOutcome:
        outcome = ensure_database_ready(database)
        if not held:
            held.append(Lock(path, block_reads=block_reads))
        return outcome

    monkeypatch.setattr("investment_analysis_engine.application.database.ensure_database_ready", ready_then_lock)
    try:
        yield
    finally:
        for lock in held:
            lock.release()
