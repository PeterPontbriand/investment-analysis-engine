"""The normalized capture one strategy adapter hands to the terminal execution service."""

from dataclasses import dataclass, field

from investment_analysis_engine.analysis.run_models import RunOutcome, StrictJsonMapping
from investment_analysis_engine.core.provider_failure_element import ProviderFailure
from investment_analysis_engine.data.instrument_profile import InstrumentProfile
from investment_analysis_engine.workspace.strategy_types import NativeEvidence


@dataclass(frozen=True)
class ExecutionCapture:
    """One method adapter's capture, normalized for envelope assembly.

    ``native_evidence`` is the method's own typed result, encoded by the codec the caller injects into
    :func:`investment_analysis_engine.workspace.execution.execute`; each strategy's execution module owns the function
    that builds this capture from its own raw capture type. ``failure_reason_code`` is the stable code of a ``failed``
    outcome, derived once from the native status and the stored provider failure, and is ``None`` for every other
    outcome. ``provider_failure`` is the ``provider_failure`` element of a ``failed`` outcome whose cause was a
    classified provider failure; it is carried in memory for the automatic provider check and is never stored.
    """

    native_evidence: NativeEvidence
    profile: InstrumentProfile | None
    outcome: RunOutcome
    presentation_inputs: StrictJsonMapping = field(default_factory=dict)
    failure_reason_code: str | None = None
    provider_failure: ProviderFailure | None = None

    def __post_init__(self) -> None:
        """Require a stable failure code exactly when the outcome is ``failed``, and a provider failure only then."""
        if (self.outcome is RunOutcome.FAILED) != (self.failure_reason_code is not None):
            raise ValueError("failure_reason_code is set if and only if the outcome is failed.")
        if self.provider_failure is not None and self.outcome is not RunOutcome.FAILED:
            raise ValueError("provider_failure requires the failed outcome.")
