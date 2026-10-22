"""The normalized capture one strategy adapter hands to the terminal execution service."""

from dataclasses import dataclass, field

from investment_analysis_engine.analysis.run_models import RunOutcome, StrictJsonMapping
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.failure_classification import failure_reason_code
from investment_analysis_engine.core.provider_failure_element import ProviderFailure
from investment_analysis_engine.data.instrument_profile import InstrumentProfile
from investment_analysis_engine.workspace.strategy_types import NativeEvidence


@dataclass(frozen=True)
class ExecutionCapture:
    """One method adapter's capture, normalized for envelope assembly.

    A strategy supplies facts: ``native_evidence``, its own typed result, encoded by the codec the caller injects into
    :func:`investment_analysis_engine.workspace.execution.execute`; the ``profile``; ``native_status``, the status the
    strategy reports (``None`` for a strategy that reports none); ``presentation_inputs``; and the ``provider_failure``
    it recorded, if any. The capture derives the rest. ``outcome`` is :meth:`RunOutcome.from_status` of the native
    status. ``failure_reason_code`` is the stable code of a ``failed`` outcome and ``None`` for every other outcome.
    ``provider_failure`` is kept only for a ``failed`` outcome; it is carried in memory for the automatic provider check
    and is never stored.
    """

    native_evidence: NativeEvidence
    profile: InstrumentProfile | None
    native_status: CalculationStatus | None
    presentation_inputs: StrictJsonMapping = field(default_factory=dict)
    provider_failure: ProviderFailure | None = None
    outcome: RunOutcome = field(init=False)
    failure_reason_code: str | None = field(init=False)

    def __post_init__(self) -> None:
        """Derive the outcome, the failure code of a failed outcome, and the provider failure a failed outcome keeps."""
        status = self.native_status
        outcome = RunOutcome.from_status(status)
        code: str | None = None
        kept: ProviderFailure | None = None
        if outcome is RunOutcome.FAILED and status is not None:
            code = failure_reason_code(status, self.provider_failure).value
            kept = self.provider_failure
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "failure_reason_code", code)
        object.__setattr__(self, "provider_failure", kept)
