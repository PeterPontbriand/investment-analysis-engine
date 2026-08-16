"""Execution identity passed through a CLI run and its telemetry recorder."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class RunContext:
    """Stable identity for one application execution.

    ``session_id`` groups runs belonging to one application process/session;
    ``run_id`` identifies exactly one top-level execution trajectory. A normal
    single-command CLI invocation creates one context and therefore one run.
    """

    run_id: UUID
    session_id: UUID

    @classmethod
    def new(cls, *, session_id: UUID | None = None) -> RunContext:
        """Create a new run identity, optionally joining an existing session."""
        return cls(run_id=uuid4(), session_id=session_id or uuid4())


_current_run_context: ContextVar[RunContext | None] = ContextVar("current_run_context", default=None)


def set_current_run_context(context: RunContext) -> None:
    """Set the run identity for the current CLI/application execution context."""
    _current_run_context.set(context)


def get_current_run_context() -> RunContext | None:
    """Return the current CLI run identity, if one has been established."""
    return _current_run_context.get()
