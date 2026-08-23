"""Immutable resolver execution trace for investor-facing diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ResolutionStage(StrEnum):
    """High-level resolver stage that produced a diagnostic event."""

    VALIDATION = "validation"
    OVERRIDE = "override"
    CACHE = "cache"
    PROVIDER = "provider"
    DERIVATION = "derivation"


class ResolutionOutcome(StrEnum):
    """Machine-readable outcome for one resolver trace event."""

    NOT_USED = "not_used"
    ATTEMPTED = "attempted"
    HIT = "hit"
    MISS = "miss"
    REJECTED = "rejected"
    SUCCESS = "success"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"
    ERROR = "error"


@dataclass(frozen=True)
class ResolutionEvent:
    """One truthful resolver decision/event retained for diagnostics."""

    field_name: str
    stage: ResolutionStage
    outcome: ResolutionOutcome
    message: str

    def __post_init__(self) -> None:
        """Require non-empty human-readable identifiers/messages."""
        if not self.field_name.strip():
            raise ValueError("ResolutionEvent.field_name must be non-empty.")
        if not self.message.strip():
            raise ValueError("ResolutionEvent.message must be non-empty.")


@dataclass(frozen=True)
class ResolutionTrace:
    """Ordered immutable collection of resolver events."""

    events: tuple[ResolutionEvent, ...] = ()

    def append(self, event: ResolutionEvent) -> ResolutionTrace:
        """Return a new trace with *event* appended."""
        return ResolutionTrace(events=(*self.events, event))

    def extend(self, other: ResolutionTrace) -> ResolutionTrace:
        """Return a new trace with all events from *other* appended."""
        if not other.events:
            return self
        return ResolutionTrace(events=(*self.events, *other.events))

    def __bool__(self) -> bool:
        """Return whether this trace contains any retained events."""
        return bool(self.events)
