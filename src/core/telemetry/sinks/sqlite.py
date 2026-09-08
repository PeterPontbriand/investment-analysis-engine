"""Synchronous trajectory adapter with explicit locking and database ownership."""

from threading import Lock
from uuid import UUID

from src.core.telemetry.models import TrajectoryEvent
from src.data.repositories import trajectory
from src.data.repositories.sqlite import SQLiteDatabase


def read_trajectory(database: SQLiteDatabase, run_id: UUID) -> list[TrajectoryEvent]:
    """Reconstruct ordered events through the repository using a borrowed database.

    Missing runs return an empty list; malformed or unsupported storage raises.
    """
    return trajectory.SQLiteTrajectoryRepository(database).read_trajectory(run_id)


class SQLiteTrajectorySink:
    """Write events through a caller-owned, already-migrated database.

    Each record commits before returning. Identical event-ID retries are no-ops;
    conflicting IDs or run/sequence pairs raise errors. The recorder owns
    fail-open handling and sanitization. Closing this sink leaves the shared
    database open by default. Runtime composition can transfer disposal to the
    sink with ``close_database=True`` when it creates a dedicated database.
    """

    def __init__(self, database: SQLiteDatabase, *, close_database: bool = False) -> None:
        """Retain the database without opening connections or creating tables."""
        self._database = database
        self._repository = trajectory.SQLiteTrajectoryRepository(database)
        self._close_database = close_database
        self._closed = False
        self._lock = Lock()

    def record(self, event: TrajectoryEvent) -> None:
        """Atomically persist an event or verify an identical retry."""
        with self._lock:
            if self._closed:
                raise RuntimeError("Cannot record telemetry after the sink has been closed.")
            self._repository.record(event)

    def flush(self) -> None:
        """Wait for an active write; records are committed without buffering."""
        with self._lock:
            pass

    def close(self) -> None:
        """Idempotently stop writes and dispose the database only when owned."""
        with self._lock:
            if self._closed:
                return
            if self._close_database:
                self._database.close()
            self._closed = True
