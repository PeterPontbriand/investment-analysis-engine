"""The in-memory trajectory sink that tests pass to a ``TrajectoryRecorder``."""

from investment_analysis_engine.core.trajectory_events import TrajectoryEvent


class RecordingSink:
    """Keep every recorded event in memory, and note whether the recorder flushed and closed the sink."""

    def __init__(self) -> None:
        """Start with no events, not flushed and not closed."""
        self.events: list[TrajectoryEvent] = []
        self.flushed = False
        self.closed = False

    def record(self, event: TrajectoryEvent) -> None:
        """Keep one event."""
        self.events.append(event)

    def flush(self) -> None:
        """Note that the recorder asked for a flush."""
        self.flushed = True

    def close(self) -> None:
        """Note that the recorder released the sink."""
        self.closed = True
