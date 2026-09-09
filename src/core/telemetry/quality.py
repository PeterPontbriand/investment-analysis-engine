"""Attach data-quality failures to existing execution trajectory spans."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from uuid import UUID, uuid4

from src.core.telemetry.models import TrajectoryEventType
from src.core.telemetry.recorder import TrajectoryRecord, TrajectoryRecorder
from src.core.telemetry.run_context import get_current_run_context
from src.data.quality import QualityDecision
from src.data.quality_reporting import quality_observer

logger = logging.getLogger(__name__)


def _record(recorder: TrajectoryRecorder, decision: QualityDecision, span_id: UUID, parent: UUID | None) -> None:
    recorder.record(
        TrajectoryRecord(
            event_type=TrajectoryEventType.ERROR,
            component="data_quality",
            span_id=span_id,
            parent_span_id=parent,
            payload={"quality_decision": asdict(decision)},
        )
    )


@contextmanager
def record_quality(
    recorder: TrajectoryRecorder, *, span_id: UUID, parent_span_id: UUID | None = None
) -> Iterator[None]:
    """Route quality failures through the recorder's sanitization boundary."""

    def record(decision: QualityDecision) -> None:
        _record(recorder, decision, span_id, parent_span_id)

    with quality_observer(record):
        yield


@contextmanager
def record_cli_quality() -> Iterator[None]:
    """Lazily record direct CLI quality failures under the established run ID."""
    recorder: TrajectoryRecorder | None = None
    span_id = uuid4()

    def record(decision: QualityDecision) -> None:
        nonlocal recorder
        context = get_current_run_context()
        if context is None:
            return
        if recorder is None:
            recorder = TrajectoryRecorder.from_settings(context)
        _record(recorder, decision, span_id, None)

    try:
        with quality_observer(record):
            yield
    finally:
        if recorder is not None:
            try:
                recorder.close()
            except Exception:
                logger.debug("Quality recorder close failed.", exc_info=True)
