"""The shared wall-clock read and point-in-time boundary derivation for the whole codebase."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def utc_now() -> datetime:
    """Return the current timezone-aware instant. The one call site permitted to read the real clock."""
    return datetime.now(UTC)


def effective_as_of(as_of: datetime | None, executed_at: datetime) -> datetime:
    """Return the point-in-time cutoff: the requested boundary, or the execution clock."""
    return as_of or executed_at


FROZEN_CLOCK_SKEW_TOLERANCE = timedelta(minutes=10)
