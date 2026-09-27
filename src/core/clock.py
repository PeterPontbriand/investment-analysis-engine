"""The shared wall-clock read and point-in-time boundary derivation for the whole codebase.

Before touching any timestamp comparison in the data layer, read "Time and the analysis
boundary" (``docs/project/ARCHITECTURE.md``, §3) for the full picture: ``executed_at``,
``effective_as_of``, ``utc_now()``, and why ``FROZEN_CLOCK_SKEW_TOLERANCE`` is sized the way it
is and applies only to live (non-``as_of``) runs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def utc_now() -> datetime:
    """Return the current timezone-aware instant. The one call site permitted to read the real clock."""
    return datetime.now(UTC)


def effective_as_of(as_of: datetime | None, executed_at: datetime) -> datetime:
    """Return the point-in-time cutoff: the requested boundary, or the execution clock."""
    return as_of or executed_at


FROZEN_CLOCK_SKEW_TOLERANCE = timedelta(minutes=10)
