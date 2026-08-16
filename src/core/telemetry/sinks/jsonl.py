"""Append-only JSON Lines trajectory sink with bounded file retention."""

from __future__ import annotations

from pathlib import Path
from typing import TextIO

from src.core.telemetry.models import TrajectoryEvent


class JSONLTrajectorySink:
    """Persist one run per JSONL file and enforce count/size-based retention.

    Retention is deliberately file-based: each completed run is one telemetry
    file. ``max_log_files`` limits the number of retained run files and
    ``max_total_size`` limits their combined byte size. The active file is never
    deleted while it is open; if that single file exceeds the configured total
    size, it is retained rather than truncated.
    """

    def __init__(self, log_dir: Path, *, max_log_files: int = 100, max_total_size: int = 100 * 1024 * 1024) -> None:
        """Initialize the sink without opening a file."""
        if max_log_files < 1:
            raise ValueError("max_log_files must be at least 1")
        if max_total_size < 1:
            raise ValueError("max_total_size must be at least 1 byte")
        self._log_dir = Path(log_dir)
        self._max_log_files = max_log_files
        self._max_total_size = max_total_size
        self._stream: TextIO | None = None
        self._run_id: str | None = None
        self._closed = False

    @property
    def path(self) -> Path | None:
        """Return the active trajectory path, if a file has been opened."""
        if self._run_id is None:
            return None
        return self._log_dir / "trajectories" / f"{self._run_id}.jsonl"

    def record(self, event: TrajectoryEvent) -> None:
        """Append one event, creating the trajectory directory/file on first use."""
        if self._closed:
            raise RuntimeError("Cannot record telemetry after the sink has been closed.")

        run_id = str(event.run_id)
        if self._stream is None:
            self._run_id = run_id
            trajectory_dir = self._log_dir / "trajectories"
            trajectory_dir.mkdir(parents=True, exist_ok=True)
            self._stream = (trajectory_dir / f"{run_id}.jsonl").open("a", encoding="utf-8")
        elif self._run_id != run_id:
            raise ValueError("JSONLTrajectorySink instances can only persist one run_id.")

        self._stream.write(event.to_json_line())
        self._stream.write("\n")

    def flush(self) -> None:
        """Flush the active file when one exists."""
        if self._stream is not None:
            self._stream.flush()

    def close(self) -> None:
        """Flush, close, and prune retained trajectory files."""
        if self._closed:
            return
        try:
            self.flush()
            if self._stream is not None:
                self._stream.close()
                self._stream = None
            self._prune_retention()
        finally:
            self._closed = True

    def _prune_retention(self) -> None:
        """Delete oldest completed trajectory files until both limits are met."""
        trajectory_dir = self._log_dir / "trajectories"
        if not trajectory_dir.exists():
            return

        files = sorted(trajectory_dir.glob("*.jsonl"), key=lambda path: path.stat().st_mtime)
        while len(files) > self._max_log_files:
            files[0].unlink(missing_ok=True)
            files.pop(0)

        total_size = sum(path.stat().st_size for path in files if path.exists())
        while total_size > self._max_total_size and len(files) > 1:
            oldest = files.pop(0)
            size = oldest.stat().st_size if oldest.exists() else 0
            oldest.unlink(missing_ok=True)
            total_size -= size
