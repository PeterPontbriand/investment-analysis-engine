"""Terminal execution/save service: assemble and persist one Analysis Run.

The service owns identity and timing capture and performs the terminal
insertion; it does not call production providers or analyzers itself, and
it does not construct or close their dependencies. A caller-composed
"capture" callable — one of the D1-D4 method adapters (``run_momentum`` +
``capture_momentum``, ``execute_graham_number``, ``execute_graham_growth``,
or ``execute_fcf_growth``), already bound to its borrowed provider/client
dependencies — does that. This keeps :func:`execute` identical regardless
of which of the four methods is being run: it only needs a normalized
:class:`ExecutionCapture` back from that callable, and dispatches evidence
encoding through the existing :func:`src.workspace.codecs.encode_evidence`,
which already distinguishes native result types by ``isinstance``.

Ordering and error-visibility guarantees:

- ``capture()`` runs first; a raised exception propagates uncaught. The
  existing CLI error-handling boundary (``execution_errors``) already
  classifies analyzer/provider failures safely, and duplicating that
  classification here would diverge from it. No run is stored for an
  attempt that never produced a capture.
- ``repository.insert(run)`` is the last step. A raised exception (a
  duplicate ID, an unready or closed database, or any other storage
  failure) propagates uncaught: the caller sees a real error, and no run
  is ever silently reported as saved. :func:`execute` never catches a
  persistence exception to fabricate a stored failure record instead.
- ``repository`` is only ever received already composed and ready,
  matching the project's existing pattern of checking database readiness
  once at composition (for example ``_production_historical_client``).
  :func:`execute` performs no separate readiness check of its own;
  insertion happening only after a successful capture, with any failure
  surfaced rather than hidden, is what "ready before work, never a false
  success" means at this layer. Composing a ready repository before
  calling :func:`execute` remains the caller's responsibility.
- Telemetry is not imported or referenced anywhere in this module, so a
  telemetry failure elsewhere can never affect whether a run is captured
  or persisted here.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from src.analysis.strategy.fcf_earnings_growth.models import FCFEarningsGrowthResult
from src.analysis.strategy.graham_growth.service import GrahamGrowthAnalysis
from src.analysis.strategy.graham_number.service import GrahamNumberAnalysis
from src.analysis.strategy.momentum.momentum_analyzer import MomentumRun
from src.data.instrument_profile import InstrumentProfile
from src.workspace.codecs import encode_evidence
from src.workspace.fcf_growth_execution import FCFGrowthCapture
from src.workspace.graham_growth_execution import GrahamGrowthCapture
from src.workspace.graham_number_execution import GrahamNumberCapture
from src.workspace.models import RunOutcome, StrictJsonMapping
from src.workspace.momentum_execution import MomentumCapture
from src.workspace.requests import AnalysisRequest
from src.workspace.runs import AnalysisRun

NativeEvidence = MomentumRun | GrahamNumberAnalysis | GrahamGrowthAnalysis | FCFEarningsGrowthResult

_METHOD_VERSIONS: dict[tuple[str, str], tuple[int, int]] = {
    ("momentum", "sma_crossover"): (1, 1),
    ("graham_number", "graham_number"): (1, 1),
    ("graham_growth_value", "graham_growth_value"): (1, 1),
    ("fcf_earnings_growth", "reported_fcf_eps_cagr"): (2, 3),
}


@dataclass(frozen=True)
class BatchContext:
    """Refresh/watchlist identity to attach to one run within a batch (G1+).

    All four fields travel together because ``AnalysisRun`` itself requires
    ``refresh_id``/``batch_position`` to be both set or both null, and
    likewise for ``watchlist_id``/``watchlist_name``; a direct (non-refresh)
    call to :func:`execute` passes no ``BatchContext`` at all.
    """

    refresh_id: UUID
    batch_position: int
    watchlist_id: UUID
    watchlist_name: str


@dataclass(frozen=True)
class ExecutionCapture:
    """One method adapter's capture, normalized for envelope assembly.

    ``native_evidence`` is the method's own typed result, encoded by the
    existing :func:`~src.workspace.codecs.encode_evidence` dispatch
    unmodified by this service.
    """

    native_evidence: NativeEvidence
    profile: InstrumentProfile | None
    outcome: RunOutcome
    presentation_inputs: StrictJsonMapping = field(default_factory=dict)


class AnalysisRunSink(Protocol):
    """The one repository capability this service needs: terminal insertion."""

    def insert(self, run: AnalysisRun) -> None:
        """Atomically append one terminal run; raise on any storage failure."""
        ...


def from_momentum_capture(capture: MomentumCapture) -> ExecutionCapture:
    """Normalize a Momentum capture; Momentum has no native failure status."""
    return ExecutionCapture(
        native_evidence=capture.run,
        profile=capture.profile,
        outcome=RunOutcome.COMPLETED,
        presentation_inputs=capture.presentation_inputs,
    )


def from_graham_number_capture(capture: GrahamNumberCapture) -> ExecutionCapture:
    """Normalize a Graham Number capture."""
    return ExecutionCapture(native_evidence=capture.analysis, profile=capture.profile, outcome=capture.outcome)


def from_graham_growth_capture(capture: GrahamGrowthCapture) -> ExecutionCapture:
    """Normalize a Graham Growth capture."""
    return ExecutionCapture(native_evidence=capture.analysis, profile=capture.profile, outcome=capture.outcome)


def from_fcf_growth_capture(capture: FCFGrowthCapture) -> ExecutionCapture:
    """Normalize an FCF/Earnings Growth capture."""
    return ExecutionCapture(native_evidence=capture.result, profile=capture.profile, outcome=capture.outcome)


def execute(  # noqa: PLR0913
    request: AnalysisRequest,
    *,
    capture: Callable[[], ExecutionCapture],
    repository: AnalysisRunSink,
    id_factory: Callable[[], UUID] = uuid4,
    clock: Callable[[], datetime] | None = None,
    batch: BatchContext | None = None,
) -> AnalysisRun:
    """Capture one method execution, assemble its envelope, and persist it.

    Args:
        request: The normalized ticker and validated method selection.
        capture: A zero-argument callable that runs the method adapter and
            returns its normalized capture. Invoked exactly once, timed by
            ``clock`` on both sides.
        repository: An already-composed, ready sink for the terminal run.
        id_factory: Produces the new run's identity; defaults to `uuid4`.
        clock: Produces aware UTC instants for `started_at`/`completed_at`;
            defaults to the wall clock.
        batch: Refresh/watchlist identity for one job within a batch (G1+);
            omitted entirely for a direct, non-refresh call, in which case
            the run's refresh/batch/watchlist fields are all null.

    Returns:
        The exact `AnalysisRun` that was inserted.

    Raises:
        Exception: Whatever `capture` or `repository.insert` raise,
            unmodified. Neither is caught or reinterpreted here.
    """
    resolved_clock = clock if clock is not None else lambda: datetime.now(UTC)
    started_at = resolved_clock()
    result = capture()
    completed_at = resolved_clock()

    selection = request.selection
    method_version, result_schema_version = _METHOD_VERSIONS[(selection.analysis_id, selection.method_id)]

    run = AnalysisRun(
        analysis_run_id=id_factory(),
        refresh_id=batch.refresh_id if batch is not None else None,
        batch_position=batch.batch_position if batch is not None else None,
        watchlist_id=batch.watchlist_id if batch is not None else None,
        watchlist_name=batch.watchlist_name if batch is not None else None,
        ticker=request.ticker,
        analysis_id=selection.analysis_id,
        method_id=selection.method_id,
        config_schema_version=selection.config_schema_version,
        requested_config=selection,
        effective_config=selection,
        started_at=started_at,
        completed_at=completed_at,
        requested_as_of=getattr(selection, "as_of", None),
        method_version=method_version,
        result_schema_version=result_schema_version,
        evidence_codec_version=1,
        status=result.outcome,
        failure_reason_code="execution_failed" if result.outcome is RunOutcome.FAILED else None,
        result_evidence=encode_evidence(result.native_evidence),
        presentation_inputs=result.presentation_inputs or None,
        instrument_profile=result.profile,
    )
    repository.insert(run)
    return run


__all__ = [
    "AnalysisRunSink",
    "BatchContext",
    "ExecutionCapture",
    "execute",
    "from_fcf_growth_capture",
    "from_graham_growth_capture",
    "from_graham_number_capture",
    "from_momentum_capture",
]
