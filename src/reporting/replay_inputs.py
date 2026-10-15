"""What a stored-run replay is given besides the decoded evidence: the view, the run's own facts and the errors.

``project_run`` decodes a stored run and hands each strategy's projector the facts the run itself captured. This
leaf module holds the types both sides share, so a projector in a strategy package and the generic replay in
``run_replay`` agree on them without importing each other.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

from src.analysis.run_models import StrictJsonMapping
from src.core.failure_codes import FailureReasonCode
from src.data.instrument_profile import InstrumentProfile
from src.reporting.presentation import PresentationMode


class UnsupportedProjectionError(ValueError):
    """The run's projection version, or its (analysis_id, method_id), has no v1 replay."""

    reason_code: ClassVar[FailureReasonCode] = FailureReasonCode.UNSUPPORTED_PROJECTION


@dataclass(frozen=True)
class ReplayOptions:
    """Explicit view selection for one replay.

    Locale and time formatting are not configurable: projection v1 reuses
    the existing formatting helpers, which are already fixed to the
    en-CA-style number/currency conventions and ISO-8601 UTC timestamps
    the direct commands already show.
    """

    mode: PresentationMode = PresentationMode.CONCISE


@dataclass(frozen=True)
class ReplayInputs:
    """The facts a stored run captured at execution time, which a replay shows instead of recomputing.

    Attributes:
        ticker: The run's ticker.
        instrument_profile: The profile composed when the run executed, if any. Replay shows this one, never the
            copy inside the native evidence, which an analyzer may leave unset.
        presentation_inputs: Values the live presenter derives at render time and the run stored, such as
            Momentum's SMA spread; ``None`` when the run stored none.
    """

    ticker: str
    instrument_profile: InstrumentProfile | None
    presentation_inputs: StrictJsonMapping | None


ReplayProjector = Callable[[ReplayInputs, object, object, ReplayOptions], str]
"""A strategy's projector as the generic replay calls it: inputs, decoded evidence, stored selection, options."""

__all__ = ["ReplayInputs", "ReplayOptions", "ReplayProjector", "UnsupportedProjectionError"]
