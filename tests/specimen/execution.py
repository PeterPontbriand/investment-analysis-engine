"""The specimen's execution adapter: call the analyzer and capture the evidence."""

from dataclasses import dataclass
from datetime import datetime

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.analysis.run_models import RunOutcome
from tests.specimen.analyzer import SpecimenAnalyzer, SpecimenResult
from tests.specimen.selection import SpecimenSelection


@dataclass(frozen=True)
class SpecimenCapture:
    """The captured evidence of one specimen execution."""

    result: SpecimenResult
    outcome: RunOutcome


@dataclass(frozen=True)
class SpecimenExecution:
    """A capture normalized for a specimen run: the evidence and the terminal outcome."""

    native_evidence: SpecimenResult
    outcome: RunOutcome


def execute_specimen(
    analyzer: SpecimenAnalyzer, ticker: str, selection: SpecimenSelection, *, executed_at: datetime
) -> SpecimenCapture:
    """Run the analyzer for ``selection``; the calculation has no failure outcome."""
    context = AnalysisContext(as_of=selection.as_of, executed_at=executed_at, use_cache=selection.use_cache)
    result = analyzer.run_analysis(ticker, selection.to_specimen_config(), context)
    return SpecimenCapture(result=result, outcome=RunOutcome.COMPLETED)


def from_specimen_capture(capture: SpecimenCapture) -> SpecimenExecution:
    """Normalize a specimen capture."""
    return SpecimenExecution(native_evidence=capture.result, outcome=capture.outcome)
