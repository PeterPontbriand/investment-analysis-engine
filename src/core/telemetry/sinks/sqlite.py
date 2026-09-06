"""Atomic, immutable SQLite storage for sanitized trajectory events."""

import json
import math
from datetime import UTC
from threading import Lock
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from src.core.telemetry.models import TrajectoryEvent
from src.data.repositories.schema import schema_metadata, trajectory_events
from src.data.repositories.sqlite import SQLiteDatabase


def _validate_json(value: object) -> None:
    """Reject non-JSON objects and non-finite numbers without coercion."""
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Telemetry numbers must be finite.")
        return
    if isinstance(value, list):
        for item in value:
            _validate_json(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("Telemetry JSON object keys must be strings.")
            _validate_json(item)
        return
    raise TypeError("Telemetry nested values must be JSON-compatible.")


def _encode(event: TrajectoryEvent) -> dict[str, object]:
    """Encode the event using UTC timestamps and canonical nested JSON."""
    if event.timestamp.utcoffset() is None:
        raise ValueError("Telemetry timestamps must be timezone-aware.")
    if event.latency_ms is not None and not math.isfinite(event.latency_ms):
        raise ValueError("Telemetry latency must be finite.")
    nested = {"tool_args", "tool_result_summary", "payload", "error"}
    row: dict[str, object] = {}
    for name in TrajectoryEvent.model_fields:
        value = getattr(event, name)
        if name in nested:
            _validate_json(value)
            row[f"{name}_json"] = (
                None
                if value is None
                else json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
            )
        elif name == "timestamp":
            row[name] = event.timestamp.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
        else:
            row[name] = str(value) if isinstance(value, UUID) else value
    return row


def read_trajectory(database: SQLiteDatabase, run_id: UUID) -> list[TrajectoryEvent]:
    """Reconstruct one run in sequence order from a consistent database snapshot.

    Missing runs return an empty list. Unsupported persistence encodings and
    malformed stored envelopes raise explicit errors; gaps remain gaps. The
    database is borrowed and must already have been migrated by its owner.
    """
    with database.read() as connection:
        version = connection.execute(
            select(schema_metadata.c.metadata_value).where(
                schema_metadata.c.metadata_key == "persistence_encoding_version"
            )
        ).scalar_one_or_none()
        if version != 1:
            raise ValueError("Unsupported or missing trajectory persistence encoding version.")
        stored = connection.execute(
            select(trajectory_events)
            .where(trajectory_events.c.run_id == str(run_id))
            .order_by(trajectory_events.c.sequence)
        ).mappings()
        events: list[TrajectoryEvent] = []
        for row in stored:
            decoded = dict(row)
            for name in ("tool_args", "tool_result_summary", "payload", "error"):
                encoded = decoded.pop(f"{name}_json")
                decoded[name] = None if encoded is None else json.loads(encoded)
            event = TrajectoryEvent.model_validate(decoded)
            # Re-encoding also checks finite JSON values, UTC representation,
            # UUID normalization, and storage values Pydantic might coerce.
            if _encode(event) != dict(row):
                raise ValueError("Malformed trajectory persistence encoding.")
            events.append(event)
        return events


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
        self._close_database = close_database
        self._closed = False
        self._lock = Lock()

    def record(self, event: TrajectoryEvent) -> None:
        """Atomically persist an event or verify an identical retry."""
        with self._lock:
            if self._closed:
                raise RuntimeError("Cannot record telemetry after the sink has been closed.")
            row = _encode(event)
            with self._database.transaction() as connection:
                # Write first so concurrent retries serialize before comparison.
                connection.execute(
                    insert(trajectory_events).values(**row).on_conflict_do_nothing(index_elements=["event_id"])
                )
                stored = (
                    connection.execute(select(trajectory_events).where(trajectory_events.c.event_id == row["event_id"]))
                    .mappings()
                    .one()
                )
                if dict(stored) != row:
                    raise ValueError("Conflicting telemetry event_id; stored events are immutable.")

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
