"""The native status that gives a chosen run outcome, for tests that build an ``ExecutionCapture`` by outcome."""

from typing import Final

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.core.analysis_status import CalculationStatus

NATIVE_STATUS_OF_OUTCOME: Final = {
    RunOutcome.COMPLETED: CalculationStatus.OK,
    RunOutcome.NOT_APPLICABLE: CalculationStatus.NOT_APPLICABLE,
    RunOutcome.UNAVAILABLE: CalculationStatus.INPUT_UNAVAILABLE,
    RunOutcome.FAILED: CalculationStatus.PROVIDER_ERROR,
}
