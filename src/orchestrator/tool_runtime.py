"""Shared runtime and handler shapes for the production analysis tools.

``ToolRuntime`` carries the two cross-cutting concerns every handler needs: the injected execution clock and
the optional instrument-profile resolver. Everything else a handler needs is the strategy's own dependency
class, defined beside its handler in the strategy's ``tool`` module.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from src.data.instrument_profile import InstrumentProfile


@dataclass(frozen=True)
class ToolRuntime:
    """Injected clock and optional profile resolver shared by all analysis-tool handlers."""

    clock: Callable[[], datetime]
    profile_resolver: Callable[[str], InstrumentProfile] | None = None

    def resolve_profile(self, ticker: str) -> InstrumentProfile | None:
        """Resolve optional injected profile evidence once for one tool invocation."""
        resolver = self.profile_resolver
        return resolver(ticker) if resolver is not None else None

    def validated_clock_value(self) -> datetime:
        """Return an unambiguous injected execution timestamp."""
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Analysis tool clock must return a timezone-aware datetime.")
        return value


class AnalysisToolHandler[ResultT](Protocol):
    """A bound tool handler that returns one strategy's native result."""

    def __call__(self, **raw_arguments: object) -> ResultT:
        """Validate raw tool arguments, run the analyzer and return its native result."""
        ...


class ToolHandlerBinder[DepsT, ResultT](Protocol):
    """Build a strategy's handler from its dependency class and the shared runtime."""

    def __call__(self, dependencies: DepsT, runtime: ToolRuntime, /) -> AnalysisToolHandler[ResultT]:
        """Return the handler bound to the injected dependencies."""
        ...
