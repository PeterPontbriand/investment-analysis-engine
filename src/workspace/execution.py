"""Terminal execution/save service: assemble and persist one Analysis Run.

The service owns identity and timing capture and performs the terminal
insertion; it does not call production providers or analyzers itself, and
it does not construct or close their dependencies. A caller-composed
"capture" callable — one of the D1-D4 method adapters (``run_momentum`` +
``capture_momentum``, ``execute_graham_number``, ``execute_graham_growth``,
or ``execute_fcf_growth``), already bound to its borrowed provider/client
dependencies — does that. This keeps :func:`execute` identical regardless
of which of the four methods is being run: it only needs a normalized
:class:`~src.workspace.capture.ExecutionCapture` back from that callable, and
takes its versions and evidence encoder from the injected :class:`RunSpec`, so
this module names no strategy.

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
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID, uuid4

from src.core.clock import utc_now
from src.workspace.capture import ExecutionCapture
from src.workspace.models import StrictJsonMapping
from src.workspace.requests import AnalysisRequest
from src.workspace.runs import AnalysisRun
from src.workspace.strategy_types import NativeEvidence


@dataclass(frozen=True)
class RunSpec:
    """What :func:`execute` needs from one strategy: the versions it writes and its evidence encoder.

    The composition root builds one per declared strategy; this module names none of them.
    """

    method_version: int
    result_schema_version: int
    evidence_codec_version: int
    encode: Callable[[NativeEvidence], StrictJsonMapping]


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


class AnalysisRunSink(Protocol):
    """The one repository capability this service needs: terminal insertion."""

    def insert(self, run: AnalysisRun) -> None:
        """Atomically append one terminal run; raise on any storage failure."""
        ...


def execute(  # noqa: PLR0913
    request: AnalysisRequest,
    *,
    spec: RunSpec,
    capture: Callable[[], ExecutionCapture],
    repository: AnalysisRunSink,
    id_factory: Callable[[], UUID] = uuid4,
    clock: Callable[[], datetime] | None = None,
    batch: BatchContext | None = None,
) -> AnalysisRun:
    """Capture one method execution, assemble its envelope, and persist it.

    Args:
        request: The normalized ticker and validated method selection.
        spec: The selection's strategy's versions and evidence encoder, from the composition root.
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
    resolved_clock = clock if clock is not None else utc_now
    started_at = resolved_clock()
    result = capture()
    completed_at = resolved_clock()

    selection = request.selection

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
        requested_as_of=selection.as_of,
        method_version=spec.method_version,
        result_schema_version=spec.result_schema_version,
        evidence_codec_version=spec.evidence_codec_version,
        status=result.outcome,
        failure_reason_code=result.failure_reason_code,
        result_evidence=spec.encode(result.native_evidence),
        presentation_inputs=result.presentation_inputs or None,
        instrument_profile=result.profile,
    )
    repository.insert(run)
    return run


__all__ = [
    "AnalysisRunSink",
    "BatchContext",
    "RunSpec",
    "execute",
]
