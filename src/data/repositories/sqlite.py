"""Scoped SQLite connections with verified pragmas and explicit transactions."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import Lock

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.pool import NullPool, StaticPool

from src.config import ProjectSettings


class SQLiteDatabase:
    """Own a SQLite engine and bounded connection scopes.

    File-backed operations use independent connections, closed at scope exit.
    In-memory databases retain one connection for sequential test use only;
    overlapping scopes are rejected. Call close after all scopes have exited.
    Callers must not commit, roll back, or change connection policy themselves.
    """

    def __init__(self, settings: ProjectSettings) -> None:
        """Build a lazy engine from validated settings without creating tables."""
        url = make_url(settings.database_url)
        self._database = url.database or ":memory:"
        self._memory = self._database == ":memory:"
        self._timeout_ms = settings.database_busy_timeout_ms
        self._lock = Lock()
        self._active = 0
        self._closed = False
        self._engine = create_engine(url, creator=self._connect, poolclass=StaticPool if self._memory else NullPool)

    def _connect(self) -> sqlite3.Connection:
        if not self._memory:
            Path(self._database).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            self._database, timeout=self._timeout_ms / 1_000, autocommit=True, check_same_thread=False
        )
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(f"PRAGMA busy_timeout = {self._timeout_ms}")
                cursor.execute("PRAGMA foreign_keys = ON")
                expected_mode = "memory" if self._memory else "wal"
                cursor.execute("PRAGMA journal_mode" if self._memory else "PRAGMA journal_mode = WAL")
                if cursor.fetchone() != (expected_mode,):
                    raise RuntimeError("SQLite journal mode could not be established.")
                cursor.execute("PRAGMA foreign_keys")
                if cursor.fetchone() != (1,):
                    raise RuntimeError("SQLite foreign-key enforcement could not be established.")
                cursor.execute("PRAGMA busy_timeout")
                if cursor.fetchone() != (self._timeout_ms,):
                    raise RuntimeError("SQLite busy timeout could not be established.")
            finally:
                cursor.close()
            # Python 3.12+ modern transaction control covers SELECT and DDL too.
            connection.autocommit = False
        except BaseException:
            connection.close()
            raise
        return connection

    @contextmanager
    def _connection(self) -> Iterator[Connection]:
        with self._lock:
            if self._closed:
                raise RuntimeError("SQLiteDatabase is closed.")
            if self._memory and self._active:
                raise RuntimeError("In-memory SQLite supports only sequential connection scopes.")
            self._active += 1
        try:
            with self._engine.connect() as connection:
                yield connection
        finally:
            with self._lock:
                self._active -= 1

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
        """Commit on success, roll back on failure, and release the connection."""
        with self._connection() as connection, connection.begin():
            yield connection

    @contextmanager
    def read(self) -> Iterator[Connection]:
        """Provide a query-only consistent snapshot, rolled back at scope exit."""
        with self._connection() as connection:
            connection.exec_driver_sql("PRAGMA query_only = ON")
            try:
                yield connection
            finally:
                connection.rollback()
                # StaticPool retains its connection for subsequent memory writes.
                if self._memory:
                    connection.exec_driver_sql("PRAGMA query_only = OFF")

    def close(self) -> None:
        """Dispose idle resources once; reject disposal while scopes are active."""
        with self._lock:
            if self._active:
                raise RuntimeError("Cannot close SQLiteDatabase while connection scopes are active.")
            if not self._closed:
                self._engine.dispose()
                self._closed = True
