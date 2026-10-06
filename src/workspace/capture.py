"""The normalized capture one strategy adapter hands to the terminal execution service."""

from dataclasses import dataclass, field

from src.data.instrument_profile import InstrumentProfile
from src.workspace.models import RunOutcome, StrictJsonMapping
from src.workspace.strategy_types import NativeEvidence


@dataclass(frozen=True)
class ExecutionCapture:
    """One method adapter's capture, normalized for envelope assembly.

    ``native_evidence`` is the method's own typed result, encoded by the codec the caller injects into
    :func:`src.workspace.execution.execute`; each strategy's execution module owns the function that
    builds this capture from its own raw capture type.
    """

    native_evidence: NativeEvidence
    profile: InstrumentProfile | None
    outcome: RunOutcome
    presentation_inputs: StrictJsonMapping = field(default_factory=dict)
