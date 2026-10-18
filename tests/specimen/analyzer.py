"""The specimen's configuration, result and analyzer: a deterministic calculation with no provider."""

from dataclasses import dataclass
from datetime import datetime

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext, BaseAnalyzer, require_ticker


@dataclass(frozen=True)
class SpecimenConfig:
    """The calculation's one input."""

    value: float


@dataclass(frozen=True)
class SpecimenResult:
    """The complete evidence of one specimen run."""

    ticker: str
    value: float
    multiplier: float
    scaled: float
    effective_as_of: datetime


class SpecimenAnalyzer(BaseAnalyzer[SpecimenConfig, SpecimenResult]):
    """Scale the input value by the injected multiplier, which composition reads from the specimen's settings."""

    def __init__(self, *, multiplier: float) -> None:
        """Retain the multiplier the composition root supplies."""
        self._multiplier = multiplier

    def run_analysis(self, ticker: str, config: SpecimenConfig, context: AnalysisContext) -> SpecimenResult:
        """Return ``config.value`` times the multiplier, with the run's effective point in time."""
        return SpecimenResult(
            ticker=require_ticker(ticker),
            value=config.value,
            multiplier=self._multiplier,
            scaled=config.value * self._multiplier,
            effective_as_of=context.effective_as_of,
        )
