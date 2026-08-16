"""Storage abstraction for trajectory telemetry."""

from __future__ import annotations

from typing import Protocol

from src.core.telemetry.models import TrajectoryEvent


class TrajectorySink(Protocol):
    """Minimal storage contract shared by JSONL now and SQLite in Step 3.1."""

    def record(self, event: TrajectoryEvent) -> None:
        """Persist one event."""
        ...

    def flush(self) -> None:
        """Flush buffered persistence state."""
        ...

    def close(self) -> None:
        """Release persistence resources."""
        ...
