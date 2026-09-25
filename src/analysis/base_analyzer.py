from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import TypeVar

from src.data.instrument_profile import InstrumentProfile

# Type variables for a strategy's own config shape and its typed result.
# Unbound: a strategy's config may be a Pydantic BaseModel, a frozen dataclass, or any other
# typed shape (see AGENTS.md's heterogeneous strategy independence guidance) — the base does
# not assume BaseModel.
ConfigT = TypeVar("ConfigT")
ResultT = TypeVar("ResultT")


@dataclass(frozen=True)
class AnalysisContext:
    """Cross-cutting execution concerns shared by every analysis strategy.

    ``as_of`` and ``executed_at`` carry genuinely different meanings and must not be
    collapsed into one another: ``as_of`` is the requested point-in-time boundary, or
    ``None`` when the caller did not request one; ``executed_at`` is the run's own
    execution clock, a single timezone-aware read of "now" taken once per run. For a
    historical run the two diverge — today's quote is not evidence for a boundary in the
    past, and a cache entry's freshness is judged against when the run actually executed,
    not against the boundary it requested. ``effective_as_of`` derives the point-in-time
    cutoff analysis-layer code should treat data as bounded by (``as_of`` when given,
    otherwise ``executed_at``); ``use_cache`` governs every cache read and write for the
    run; ``instrument_profile`` is the identity evidence for the run, embedded in every
    result regardless of whether the calculation consulted it.
    """

    as_of: datetime | None
    executed_at: datetime
    use_cache: bool
    instrument_profile: InstrumentProfile | None = None

    @property
    def effective_as_of(self) -> datetime:
        """Return the point-in-time cutoff: the requested boundary, or the execution clock."""
        return self.as_of or self.executed_at


def require_ticker(ticker: str) -> str:
    """Normalize and require a nonblank ticker."""
    normalized = ticker.strip().upper()
    if not normalized:
        raise ValueError("A nonblank ticker is required.")
    return normalized


class BaseAnalyzer[ConfigT, ResultT](ABC):
    """Abstract base class for all self-describing quantitative analysis strategies."""

    @abstractmethod
    def run_analysis(self, ticker: str, config: ConfigT, context: AnalysisContext) -> ResultT:
        """Execute the structural strategy with its own strategy-specific configuration."""
