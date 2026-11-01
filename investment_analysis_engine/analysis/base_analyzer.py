from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import get_args, get_origin

from investment_analysis_engine.core.clock import effective_as_of as _effective_as_of
from investment_analysis_engine.data.instrument_profile import InstrumentProfile


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


class BaseAnalyzer[ResultT, *ConfigT](ABC):
    """Abstract base class for all self-describing quantitative analysis strategies.

    ``ResultT`` is the complete evidence type the strategy returns. ``ConfigT`` holds zero or one
    type: a strategy with no tunable choice subclasses ``BaseAnalyzer[Result]`` and declares
    ``run_analysis(ticker, context)``; a strategy with a typed configuration subclasses
    ``BaseAnalyzer[Result, Config]`` and declares ``run_analysis(ticker, context, config)``. A
    configuration is not added to hold a single value, and no analyzer declares more than one.
    """

    @abstractmethod
    def run_analysis(self, ticker: str, context: AnalysisContext, *config: *ConfigT) -> ResultT:
        """Execute the structural strategy for the ticker under the shared execution context.

        Args:
            ticker: The requested ticker.
            context: Cross-cutting execution concerns for the run.
            *config: The strategy's own typed configuration, absent for a strategy with none.
        """


def _specialization(analyzer_class: type) -> tuple[object, ...] | None:
    """Return the arguments the class gives ``BaseAnalyzer`` directly, or ``None`` when it gives none."""
    for base in getattr(analyzer_class, "__orig_bases__", ()):
        if get_origin(base) is BaseAnalyzer:
            return get_args(base)
    return None


def analyzer_result_type(analyzer_class: type) -> type | None:
    """Return the ``ResultT`` an analyzer class declares.

    Args:
        analyzer_class: A class that subclasses ``BaseAnalyzer[ResultT]`` or
            ``BaseAnalyzer[ResultT, ConfigT]`` directly.

    Returns:
        The declared result type, or ``None`` when the class does not specialize ``BaseAnalyzer`` or
        its result argument is not a concrete type.
    """
    arguments = _specialization(analyzer_class)
    if not arguments:
        return None
    result = arguments[0]
    return result if isinstance(result, type) else None


def analyzer_config_type(analyzer_class: type) -> type | None:
    """Return the config type an analyzer class declares, or ``None`` for a config-free analyzer.

    Args:
        analyzer_class: A class that subclasses ``BaseAnalyzer[ResultT]`` or
            ``BaseAnalyzer[ResultT, ConfigT]`` directly.

    Returns:
        The declared config type, or ``None`` when the analyzer gives no second argument.

    Raises:
        TypeError: If the class does not specialize ``BaseAnalyzer``, declares more than one config
            argument, or declares a config argument that is not a concrete type.
    """
    arguments = _specialization(analyzer_class)
    if arguments is None:
        raise TypeError(f"{analyzer_class.__name__} does not specialize BaseAnalyzer.")
    configs = arguments[1:]
    if len(configs) > 1:
        raise TypeError(f"{analyzer_class.__name__} declares {len(configs)} config types; at most one is allowed.")
    if not configs:
        return None
    config = configs[0]
    if not isinstance(config, type):
        raise TypeError(f"{analyzer_class.__name__} declares no concrete config type.")
    return config
