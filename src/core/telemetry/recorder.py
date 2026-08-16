"""Trajectory recorder coordinating event IDs, ordering, redaction, and sink failures."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from src.config import settings
from src.core.telemetry.models import TelemetryMode, TrajectoryEvent, TrajectoryEventType
from src.core.telemetry.redaction import redact_value, sanitize_exception_message
from src.core.telemetry.run_context import RunContext
from src.core.telemetry.sinks import JSONLTrajectorySink, TrajectorySink

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TrajectoryRecorderConfig:
    """Recording-specific policy independent of run identity and sink location."""

    mode: TelemetryMode = TelemetryMode.LIGHT
    model_tag: str | None = None
    provider: str = "ollama"
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class TrajectoryRecord:
    """Description of one telemetry event before recorder-managed metadata is added."""

    event_type: TrajectoryEventType
    component: str
    span_id: UUID | None = None
    parent_span_id: UUID | None = None
    model_tag: str | None = None
    provider: str | None = None
    step_index: int | None = None
    tool_name: str | None = None
    tool_args: Mapping[str, Any] | None = None
    tool_result_summary: Any | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_ms: float | None = None
    payload: Any | None = None
    error: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class TrajectoryErrorRecord:
    """Description of a runtime error before recorder-managed metadata is added."""

    component: str
    message: str
    step_index: int | None = None
    span_id: UUID | None = None
    parent_span_id: UUID | None = None
    error_type: str | None = None


@dataclass(frozen=True, slots=True)
class _SpanContext:
    """Internal causal metadata for one active logical operation span."""

    span_id: UUID
    parent_span_id: UUID | None


class TrajectoryRecorder:
    """Best-effort trajectory recorder that never propagates sink failures to the runtime."""

    def __init__(
        self,
        run_context: RunContext,
        sink: TrajectorySink,
        config: TrajectoryRecorderConfig | None = None,
    ) -> None:
        """Initialize a recorder for one run, sink, and recording policy."""
        self.sink = sink
        self.run_context = run_context
        self.run_id = run_context.run_id
        self.session_id = run_context.session_id
        recorder_config = config or TrajectoryRecorderConfig()
        self.mode = recorder_config.mode
        self.model_tag = recorder_config.model_tag
        self.provider = recorder_config.provider
        self.enabled = recorder_config.enabled
        self._sequence = 0
        self._closed = False
        self._spans: dict[UUID, _SpanContext] = {}

    @classmethod
    def from_settings(
        cls,
        run_context: RunContext,
        *,
        mode: TelemetryMode = TelemetryMode.LIGHT,
        model_tag: str | None = None,
    ) -> TrajectoryRecorder:
        """Create the default Step 2.1 JSONL recorder from ProjectSettings."""
        sink = JSONLTrajectorySink(
            settings.telemetry_log_dir,
            max_log_files=settings.telemetry_max_log_files,
            max_total_size=settings.telemetry_max_total_size,
        )
        config = TrajectoryRecorderConfig(
            mode=mode,
            model_tag=model_tag,
            provider="ollama",
            enabled=settings.telemetry_level.upper() != "OFF",
        )
        return cls(run_context, sink, config)

    @property
    def sequence(self) -> int:
        """Return the most recently assigned sequence number."""
        return self._sequence

    def record(self, record: TrajectoryRecord) -> TrajectoryEvent | None:
        """Create and persist one described event, swallowing telemetry failures."""
        if not self.enabled or self._closed:
            return None

        self._sequence += 1
        sanitized_payload = redact_value(record.payload)
        sanitized_args = redact_value(dict(record.tool_args)) if record.tool_args is not None else None
        sanitized_result = redact_value(record.tool_result_summary)
        sanitized_error = redact_value(dict(record.error)) if record.error is not None else None

        effective_span_id = record.span_id or uuid4()
        event = TrajectoryEvent(
            run_id=self.run_id,
            session_id=self.session_id,
            sequence=self._sequence,
            timestamp=datetime.now(UTC),
            event_type=record.event_type,
            component=record.component,
            mode=self.mode,
            span_id=effective_span_id,
            parent_span_id=record.parent_span_id,
            model_tag=record.model_tag or self.model_tag,
            provider=record.provider or self.provider,
            step_index=record.step_index,
            tool_name=record.tool_name,
            tool_args=sanitized_args,
            tool_result_summary=sanitized_result,
            prompt_tokens=record.prompt_tokens,
            completion_tokens=record.completion_tokens,
            latency_ms=record.latency_ms,
            payload=sanitized_payload,
            payload_hash=self._hash_payload(sanitized_payload),
            error=sanitized_error,
        )

        try:
            self.sink.record(event)
        except Exception:
            logger.exception("Trajectory telemetry sink failed; continuing without affecting agent execution.")
        return event

    def flush(self) -> None:
        """Best-effort flush of the configured sink."""
        if not self.enabled or self._closed:
            return
        try:
            self.sink.flush()
        except Exception:
            logger.exception("Trajectory telemetry flush failed; continuing without affecting agent execution.")

    def close(self) -> None:
        """Best-effort sink close; repeated calls are harmless."""
        if self._closed:
            return
        try:
            self.sink.close()
        except Exception:
            logger.exception("Trajectory telemetry close failed; continuing without affecting agent execution.")
        finally:
            self._closed = True

    def start_span(self, *, parent_span_id: UUID | None = None) -> UUID:
        """Create a logical operation span with an explicit causal parent."""
        span_id = uuid4()
        self._spans[span_id] = _SpanContext(
            span_id=span_id,
            parent_span_id=parent_span_id,
        )
        return span_id

    def end_span(self, span_id: UUID) -> None:
        """Mark a logical operation span inactive without affecting event ordering."""
        self._spans.pop(span_id, None)

    def get_span_parent(self, span_id: UUID) -> UUID | None:
        """Return the explicit causal parent for a known span."""
        span = self._spans.get(span_id)
        return span.parent_span_id if span is not None else None

    def record_error(self, error: TrajectoryErrorRecord) -> TrajectoryEvent | None:
        """Record a sanitized runtime error event."""
        return self.record(
            TrajectoryRecord(
                event_type=TrajectoryEventType.ERROR,
                component=error.component,
                step_index=error.step_index,
                span_id=error.span_id,
                parent_span_id=error.parent_span_id,
                error={
                    "type": error.error_type or "RuntimeError",
                    "message": sanitize_exception_message(error.message),
                },
            )
        )

    @staticmethod
    def _hash_payload(payload: Any) -> str | None:
        """Hash a retained payload using canonical JSON serialization."""
        if payload is None:
            return None
        try:
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
        except (TypeError, ValueError):
            return None
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
