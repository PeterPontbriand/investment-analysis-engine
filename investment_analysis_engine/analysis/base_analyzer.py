from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import TypeVar, get_args, get_origin

from investment_analysis_engine.core.clock import effective_as_of as _effective_as_of
from investment_analysis_engine.data.instrument_profile import InstrumentProfile

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
        return _effective_as_of(self.as_of, self.executed_at)


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


class ConfigFreeAnalyzer[ResultT](ABC):
    """Abstract base class for an analysis strategy that takes no configuration.

    The strategy's calculation has no tunable choice: every fact it needs comes from its
    dependencies and the ``AnalysisContext``, so ``run_analysis`` takes only the ticker and the
    context. A strategy with a tunable choice subclasses ``BaseAnalyzer`` instead.
    """

    @abstractmethod
    def run_analysis(self, ticker: str, context: AnalysisContext) -> ResultT:
        """Execute the structural strategy for the ticker under the shared execution context."""


def analyzer_result_type(analyzer_class: type) -> type | None:
    """Return the ``ResultT`` an analyzer class declares, for either analyzer form.

    Args:
        analyzer_class: A class that subclasses ``BaseAnalyzer[ConfigT, ResultT]`` or
            ``ConfigFreeAnalyzer[ResultT]`` directly.

    Returns:
        The declared result type, or ``None`` when the class specializes neither form or its result
        argument is not a concrete type.
    """
    for base in getattr(analyzer_class, "__orig_bases__", ()):
        origin = get_origin(base)
        if origin is BaseAnalyzer:
            result = get_args(base)[1]
        elif origin is ConfigFreeAnalyzer:
            result = get_args(base)[0]
        else:
            continue
        return result if isinstance(result, type) else None
    return None


def analyzer_config_type(analyzer_class: type) -> type | None:
    """Return the config type an analyzer class declares, or ``None`` for a config-free analyzer.

    Args:
        analyzer_class: A class that subclasses ``BaseAnalyzer[ConfigT, ResultT]`` or
            ``ConfigFreeAnalyzer[ResultT]`` directly.

    Returns:
        The declared config type, or ``None`` when the analyzer is config-free.

    Raises:
        TypeError: If the class specializes neither form, or declares a config argument that is not
            a concrete type.
    """
    for base in getattr(analyzer_class, "__orig_bases__", ()):
        origin = get_origin(base)
        if origin is ConfigFreeAnalyzer:
            return None
        if origin is BaseAnalyzer:
            config = get_args(base)[0]
            if not isinstance(config, type):
                raise TypeError(f"{analyzer_class.__name__} declares no concrete config type.")
            return config
    raise TypeError(f"{analyzer_class.__name__} specializes neither BaseAnalyzer nor ConfigFreeAnalyzer.")
