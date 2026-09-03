# src/orchestrator/loop.py
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field, replace
from typing import Any, Literal
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from src.config import settings
from src.core.telemetry import (
    RunContext,
    TelemetryMode,
    TrajectoryErrorRecord,
    TrajectoryEventType,
    TrajectoryRecord,
    TrajectoryRecorder,
)
from src.core.telemetry.run_context import get_current_run_context
from src.llm.client import LLMClient
from src.orchestrator.context import MessageContext
from src.orchestrator.dispatcher import AsyncToolDispatcher
from src.orchestrator.reliability import (
    CircuitBreaker,
    CircuitSnapshot,
    MonotonicClock,
    ReliabilityFailure,
    ReliabilityLimitReachedError,
    ReliabilityLimits,
    ReliabilityTripReason,
)
from src.orchestrator.types import AgentStepResult, ChatMessage, Role, ToolCallRequest, ToolCallResult
from src.schema.config import SchemaConfig
from src.schema.constraint import (
    build_schema_constraint,
    detect_ollama_schema_support,
    format_schema_for_ollama,
)
from src.schema.models import ToolCallResponse
from src.schema.validator import build_retry_messages, validate_response
from src.tools.parser import ToolParser


class OrchestratorConfig(BaseModel):
    """Configuration for the AgentOrchestrator."""

    model_config = ConfigDict(extra="forbid")

    reliability_limits: ReliabilityLimits = Field(default_factory=lambda: settings.reliability_limits)
    max_steps: int = Field(default=10, ge=1, le=50, exclude=True)
    model_selection: str = "qwen2.5-coder:latest"
    temperature: float = 0.0
    mode: Literal["light", "full"] = "light"
    schema_config: SchemaConfig = Field(default_factory=lambda: settings.schema_config)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_limits(cls, value: Any) -> Any:
        """Normalize supported legacy limit inputs into one reliability policy."""
        if not isinstance(value, dict):
            return value

        normalized = dict(value)
        legacy_max_steps = normalized.get("max_steps")
        raw_limits = normalized.get("reliability_limits")
        limits = settings.reliability_limits if raw_limits is None else ReliabilityLimits.model_validate(raw_limits)
        if legacy_max_steps is None:
            normalized["max_steps"] = limits.max_steps
            migrated_limits = limits
        else:
            migrated_limits = ReliabilityLimits.model_validate({**limits.model_dump(), "max_steps": legacy_max_steps})
            if raw_limits is not None and limits.max_steps != migrated_limits.max_steps:
                raise ValueError("max_steps conflicts with reliability_limits.max_steps")

        raw_schema_config = normalized.get("schema_config")
        schema_config = settings.schema_config if raw_schema_config is None else raw_schema_config
        if not isinstance(schema_config, SchemaConfig):
            schema_config = TypeAdapter(SchemaConfig).validate_python(schema_config)

        if raw_schema_config is not None and raw_limits is None:
            migrated_limits = ReliabilityLimits.model_validate(
                {
                    **migrated_limits.model_dump(),
                    "max_transient_retries": schema_config.max_validation_retries,
                    "max_consecutive_schema_violations": schema_config.max_validation_retries + 1,
                }
            )
        elif (
            raw_schema_config is not None
            and schema_config.max_validation_retries != migrated_limits.max_schema_validation_retries
        ):
            raise ValueError(
                "schema_config.max_validation_retries conflicts with "
                "reliability_limits.max_consecutive_schema_violations"
            )
        else:
            schema_config = replace(
                schema_config,
                max_validation_retries=migrated_limits.max_schema_validation_retries,
            )

        normalized["reliability_limits"] = migrated_limits
        normalized["schema_config"] = schema_config
        return normalized


@dataclass
class OrchestratorOptions:
    """Grouped options for orchestrator initialisation."""

    config: OrchestratorConfig = field(default_factory=OrchestratorConfig)
    recorder: TrajectoryRecorder | None = None
    run_context: RunContext | None = None
    clock: MonotonicClock | None = None


@dataclass(frozen=True, slots=True)
class _RecoveryAttemptTelemetry:
    """Sanitized metadata emitted immediately before a retry."""

    step: int
    span_id: UUID
    parent_span_id: UUID
    category: str
    retry_number: int
    maximum: int


class AgentOrchestrator:
    """Orchestrates the LLM, tool dispatcher, parser, and observational telemetry."""

    def __init__(
        self,
        llm_client: LLMClient,
        dispatcher: AsyncToolDispatcher,
        parser: ToolParser,
        options: OrchestratorOptions | None = None,
    ) -> None:
        """Initialize the orchestrator with explicit execution identity."""
        self.llm_client = llm_client
        self.dispatcher = dispatcher
        self.parser = parser
        self.options = options or OrchestratorOptions()
        self.config = self.options.config

        # Resolve run_context and recorder
        self.run_context = self.options.run_context
        if self.run_context is None and self.options.recorder is not None:
            self.run_context = self.options.recorder.run_context
        if self.run_context is None:
            self.run_context = get_current_run_context() or RunContext.new()

        # Ensure recorder is always set
        if self.options.recorder is not None:
            self.recorder = self.options.recorder
        else:
            self.recorder = TrajectoryRecorder.from_settings(
                self.run_context,
                mode=TelemetryMode(self.config.mode),
                model_tag=self.config.model_selection,
            )

        if self.recorder.run_context != self.run_context:
            raise ValueError("Orchestrator run_context must match the recorder run_context.")

        # Step 2.2 – Native schema capability (lazy-resolved, cached per-instance)
        # True=supported, False=unsupported, None=unknown/unresolved
        self._schema_capability: bool | None = None
        self._capability_resolved: bool = False
        self._circuit: CircuitBreaker | None = None
        self.last_reliability_failure: ReliabilityFailure | None = None

    @property
    def reliability_snapshot(self) -> CircuitSnapshot | None:
        """Return the current request-scoped circuit state when a run has started."""
        return self._circuit.snapshot if self._circuit is not None else None

    @staticmethod
    def _schema_instruction_message(schema_dict: dict[str, Any]) -> dict[str, Any]:
        """Build a system-role message carrying explicit JSON-schema instructions.

        Used only in the ``prompt`` enforcement mode, where the native Ollama
        ``format`` constraint is unavailable. The message instructs the model
        to emit a single JSON object that exactly matches the schema, and it
        is persisted across retries because ``build_retry_messages`` copies
        the original message list verbatim.

        Args:
            schema_dict: JSON Schema (dict) the model must emit.

        Returns:
            A single Ollama-shaped message dict with ``role="system"``.
        """
        body = (
            "You must respond with a single JSON object that exactly matches "
            "the following JSON Schema. Do not include any text, markdown, "
            "comments, or explanation outside the JSON object.\n\n"
            "Schema:\n"
            f"{json.dumps(schema_dict, indent=2)}"
        )
        return {"role": "system", "content": body}

    @staticmethod
    def _inject_schema_instruction(
        messages: list[dict[str, Any]],
        schema_dict: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Return a copy of ``messages`` with a schema instruction inserted.

        The instruction is inserted immediately after the existing system
        message (if any) so that the caller's system prompt keeps priority,
        or at the front otherwise. No other message is modified.

        Args:
            messages: The original Ollama-shaped message list.
            schema_dict: JSON Schema the model must emit.

        Returns:
            New list of message dicts (the input is not mutated).
        """
        instruction = AgentOrchestrator._schema_instruction_message(schema_dict)
        out = list(messages)
        if out and out[0].get("role") == "system":
            out.insert(1, instruction)
        else:
            out.insert(0, instruction)
        return out

    async def run_stream(self, prompt: str, context: MessageContext) -> AsyncGenerator[AgentStepResult, None]:
        """Run the orchestration loop while recording an ordered causal trajectory."""
        run_started = False
        terminal_status = "aborted"
        final_step = 0
        started_at = time.perf_counter()
        run_span_id = self.recorder.start_span()
        active_step_span_id: UUID | None = None
        self._circuit = CircuitBreaker(self.config.reliability_limits, self.options.clock)
        self.last_reliability_failure = None

        try:
            self._record_run_start(run_span_id, prompt)
            run_started = True
            context.add_message(ChatMessage(role=Role.USER, content=prompt))

            for step in range(1, self.config.max_steps + 1):
                self._circuit.begin_step(step)
                final_step = step
                step_span_id = self.recorder.start_span(parent_span_id=run_span_id)
                active_step_span_id = step_span_id
                self._record_step_start(step, step_span_id, run_span_id)

                tool_requests, assistant_msg = await self._execute_llm_step(
                    step,
                    step_span_id,
                    context,
                )
                self._circuit.check_deadlines()

                if not tool_requests:
                    terminal_status = "completed"
                    self._record_step_end(step, step_span_id, run_span_id, {"status": "completed", "tool_count": 0})
                    self.recorder.end_span(step_span_id)
                    active_step_span_id = None
                    yield AgentStepResult(step_number=step, message=assistant_msg, is_terminal=True)
                    return

                tool_results = await self._execute_tools(step, tool_requests, step_span_id, context)
                self._circuit.check_deadlines()
                self._record_step_end(
                    step,
                    step_span_id,
                    run_span_id,
                    {"status": "continued", "tool_count": len(tool_requests)},
                )
                self.recorder.end_span(step_span_id)
                active_step_span_id = None

                yield AgentStepResult(
                    step_number=step,
                    message=assistant_msg,
                    executed_tools=tool_results,
                    is_terminal=False,
                )

            self._circuit.trip(
                ReliabilityTripReason.MAX_STEPS_EXCEEDED,
                configured_limit=self.config.max_steps,
                observed_value=self.config.max_steps + 1,
            )
        except ReliabilityLimitReachedError as exc:
            terminal_status = exc.reason.value
            yield self._handle_reliability_trip(
                exc,
                final_step=final_step,
                active_step_span_id=active_step_span_id,
                run_span_id=run_span_id,
            )
        except Exception:
            terminal_status = "failed"
            raise
        finally:
            if active_step_span_id is not None:
                self.recorder.end_span(active_step_span_id)
            if run_started:
                self._record_run_end(run_span_id, final_step, started_at, terminal_status)
            self.recorder.end_span(run_span_id)
            self.recorder.flush()
            self.recorder.close()

    async def _execute_llm_step(
        self,
        step: int,
        step_span_id: UUID,
        context: MessageContext,
    ) -> tuple[list[ToolCallRequest], ChatMessage]:
        """Execute one planning request and close its logical span exactly once."""
        request_span_id = self.recorder.start_span(parent_span_id=step_span_id)
        try:
            return await self._handle_llm_response(step, step_span_id, request_span_id, context)
        finally:
            self.recorder.end_span(request_span_id)

    def _build_reliability_failure(
        self,
        exc: ReliabilityLimitReachedError,
        final_step: int,
    ) -> ReliabilityFailure:
        """Build the sanitized terminal reliability outcome for one circuit trip."""
        message = f"{exc.reason.value}: reliability limit reached (run_id={self.recorder.run_id})."
        return ReliabilityFailure(
            reason=exc.reason,
            message=message,
            run_id=self.recorder.run_id,
            final_step=final_step or None,
            configured_limit=exc.configured_limit,
            observed_value=exc.observed_value,
            recent_events=self.recorder.recent_events(),
            cancellation_confirmed=exc.cancellation_confirmed,
        )

    def _handle_reliability_trip(
        self,
        exc: ReliabilityLimitReachedError,
        *,
        final_step: int,
        active_step_span_id: UUID | None,
        run_span_id: UUID,
    ) -> AgentStepResult:
        """Record and return the typed terminal view of a reliability trip."""
        failure = self._build_reliability_failure(exc, final_step)
        self.last_reliability_failure = failure
        self.recorder.record_error(
            TrajectoryErrorRecord(
                component="circuit_breaker",
                message=failure.message,
                step_index=final_step or None,
                span_id=active_step_span_id or run_span_id,
                parent_span_id=run_span_id if active_step_span_id is not None else None,
                error_type=exc.reason.value,
            )
        )
        return AgentStepResult(
            step_number=final_step or 1,
            message=ChatMessage(role=Role.ASSISTANT, content=failure.message),
            is_terminal=True,
            failure=failure,
        )

    def _record_run_start(self, span_id: UUID, prompt: str) -> None:
        """Emit RUN_START event."""
        self.recorder.record(
            TrajectoryRecord(
                event_type=TrajectoryEventType.RUN_START,
                component="orchestrator",
                span_id=span_id,
                model_tag=self.config.model_selection,
                payload={
                    "prompt": prompt,
                    "max_steps": self.config.max_steps,
                    "temperature": self.config.temperature,
                },
            )
        )

    def _record_step_start(self, step: int, span_id: UUID, parent_span_id: UUID) -> None:
        """Emit STEP_START event."""
        self.recorder.record(
            TrajectoryRecord(
                event_type=TrajectoryEventType.STEP_START,
                component="orchestrator",
                span_id=span_id,
                parent_span_id=parent_span_id,
                step_index=step,
            )
        )

    def _record_step_end(self, step: int, span_id: UUID, parent_span_id: UUID, payload: dict[str, Any]) -> None:
        """Emit STEP_END event."""
        self.recorder.record(
            TrajectoryRecord(
                event_type=TrajectoryEventType.STEP_END,
                component="orchestrator",
                span_id=span_id,
                parent_span_id=parent_span_id,
                step_index=step,
                payload=payload,
            )
        )

    def _record_run_end(self, span_id: UUID, final_step: int, started_at: float, terminal_status: str) -> None:
        """Emit RUN_END event."""
        self.recorder.record(
            TrajectoryRecord(
                event_type=TrajectoryEventType.RUN_END,
                component="orchestrator",
                span_id=span_id,
                step_index=final_step or None,
                latency_ms=(time.perf_counter() - started_at) * 1000,
                payload={"status": terminal_status, "final_step": final_step},
            )
        )

    async def _resolve_schema_capability(self) -> bool:
        """Determine whether to send the native JSON Schema constraint.

        Resolution order:
          1. If ``use_native_constraint`` is False → never send (explicit opt-out).
          2. If ``SchemaConfig.ollama_version`` is set → classify that static value.
          3. Otherwise → query the configured remote Ollama endpoint once, cache result.

        Policy for unknown capability (version unresolvable):
          Do NOT send the native constraint.  This is the safe default:
          an unsupported ``format`` key may cause the server to reject the
          entire request, whereas omitting it preserves existing behavior.

        Returns:
            True if the native ``format`` kwarg should be included in the LLM request.
        """
        return (await self._resolve_enforcement_mode()) == "native"

    async def _resolve_enforcement_mode(self) -> str:
        """Resolve the schema-enforcement mode for the next LLM call.

        Deterministic decision policy:

        * ``use_native_constraint=False`` → ``"none"``.
          Legacy provider-compat path: no native constraint, no prompt
          fallback, no validation retry loop; the legacy parser is the
          immediate recovery mechanism. ``fallback_to_prompt`` is not
          consulted because it is scoped to the native-constraint branch.

        * ``use_native_constraint=True`` AND native capability confirmed
          (``True``) → ``"native"``. The Ollama ``format`` kwarg is sent
          and validation retries are enabled.

        * ``use_native_constraint=True`` AND native capability is
          ``False`` (known-unsupported) or ``None`` (unknown):
            - if ``fallback_to_prompt=True`` → ``"prompt"``. Explicit
              JSON-schema instructions are injected into the prompt and the
              existing Pydantic validation/retry loop is used.
            - if ``fallback_to_prompt=False`` → ``"none"``. Native
              enforcement is not pretended; the safe existing
              provider-compat behaviour (no ``format``, no prompt
              injection, no retry loop, parser as recovery) is preserved.

        Capability resolution order (idempotent, cached per instance):
          1. Static ``SchemaConfig.ollama_version`` override if set.
          2. Otherwise a single remote query via
             ``LLMClient.get_ollama_version``.

        Returns:
            One of ``"native"``, ``"prompt"``, or ``"none"``.
        """
        cfg = self.config.schema_config
        if not cfg.use_native_constraint:
            return "none"

        if self._capability_resolved:
            capability = self._schema_capability
        else:
            if cfg.ollama_version is not None:
                capability = detect_ollama_schema_support(cfg.ollama_version)
            else:
                capability = detect_ollama_schema_support(await self.llm_client.get_ollama_version())
            self._schema_capability = capability
            self._capability_resolved = True

        if capability is True:
            return "native"
        if cfg.fallback_to_prompt:
            return "prompt"
        return "none"

    async def _build_generate_kwargs(self, prompt_payload: Any) -> dict[str, Any]:
        """Build the kwargs for an LLM generate call, including schema constraints.

        The native ``format`` kwarg is included only when the resolved
        enforcement mode is ``"native"`` (i.e. ``use_native_constraint`` is
        enabled AND Ollama native schema capability is confirmed).

        In ``"prompt"`` and ``"none"`` modes the ``format`` key is omitted so
        the server is not asked to constrain decoding with a key it may not
        understand. Prompt-level schema instructions (when applicable) are
        injected separately into the message payload by
        :meth:`_handle_llm_response`.
        """
        kwargs: dict[str, Any] = {
            "prompt": prompt_payload,
            "model": self.config.model_selection,
            "temperature": self.config.temperature,
        }
        if (await self._resolve_enforcement_mode()) == "native":
            schema_params = format_schema_for_ollama(
                ToolCallResponse,
                strict=self.config.schema_config.strict_mode,
                additional_properties=self.config.schema_config.additional_properties,
            )
            kwargs.update(schema_params)
        return kwargs

    async def _call_llm(
        self,
        step: int,
        prompt_payload: Any,
        step_span_id: UUID,
        request_span_id: UUID,
    ) -> str:
        """Call the LLM with bounded retries for classified transport failures."""
        while True:
            try:
                response = await self._call_llm_once(step, prompt_payload, step_span_id, request_span_id)
            except ReliabilityLimitReachedError:
                raise
            except Exception as exc:
                if not self._is_transient_llm_error(exc):
                    raise
                circuit = self._require_circuit()
                retry_number = circuit.authorize_transient_retry()
                self._record_recovery_attempt(
                    _RecoveryAttemptTelemetry(
                        step=step,
                        span_id=request_span_id,
                        parent_span_id=step_span_id,
                        category="llm_transport",
                        retry_number=retry_number,
                        maximum=circuit.limits.max_transient_retries,
                    )
                )
                continue
            self._require_circuit().reset_transient_retries()
            return response

    async def _call_llm_once(
        self,
        step: int,
        prompt_payload: Any,
        step_span_id: UUID,
        request_span_id: UUID,
    ) -> str:
        """Perform one timeout-bounded LLM call with telemetry."""
        request_started = time.perf_counter()
        generate_kwargs = await self._build_generate_kwargs(prompt_payload)
        circuit = self._require_circuit()
        budget = circuit.timeout_budget(ReliabilityTripReason.LLM_TIMEOUT)

        self.recorder.record(
            TrajectoryRecord(
                event_type=TrajectoryEventType.PROMPT_SENT,
                component="llm",
                span_id=request_span_id,
                parent_span_id=step_span_id,
                model_tag=self.config.model_selection,
                step_index=step,
                payload={
                    "messages": prompt_payload,
                    "temperature": self.config.temperature,
                    "format_constrained": "format" in generate_kwargs,
                },
            )
        )

        try:
            try:
                async with asyncio.timeout(budget.seconds):
                    result = await self.llm_client.generate(**generate_kwargs)
            except TimeoutError:
                circuit.trip_timeout(budget, cancellation_confirmed=True)
        except ReliabilityLimitReachedError:
            raise
        except Exception as exc:
            self.recorder.record_error(
                TrajectoryErrorRecord(
                    component="llm",
                    message=str(exc),
                    step_index=step,
                    span_id=request_span_id,
                    parent_span_id=step_span_id,
                    error_type=type(exc).__name__,
                )
            )
            raise
        latency_ms = (time.perf_counter() - request_started) * 1000
        self.recorder.record(
            TrajectoryRecord(
                event_type=TrajectoryEventType.LLM_RESPONSE,
                component="llm",
                span_id=request_span_id,
                parent_span_id=step_span_id,
                model_tag=self.config.model_selection,
                step_index=step,
                latency_ms=latency_ms,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                payload={"response": result.text},
            )
        )
        return result.text

    @staticmethod
    def _is_transient_llm_error(exc: Exception) -> bool:
        """Classify the bounded transport failures eligible for retry."""
        if isinstance(exc, httpx.TimeoutException):
            return False
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            return status == 429 or status >= 500
        return isinstance(exc, httpx.TransportError)

    def _require_circuit(self) -> CircuitBreaker:
        """Return the active request-scoped circuit."""
        if self._circuit is None:
            raise RuntimeError("Reliability circuit is not active.")
        return self._circuit

    def _record_recovery_attempt(self, attempt: _RecoveryAttemptTelemetry) -> None:
        """Emit sanitized telemetry immediately before an actual retry."""
        self.recorder.record(
            TrajectoryRecord(
                event_type=TrajectoryEventType.RECOVERY_ATTEMPTED,
                component="orchestrator",
                span_id=attempt.span_id,
                parent_span_id=attempt.parent_span_id,
                step_index=attempt.step,
                payload={
                    "failure_category": attempt.category,
                    "retry_number": attempt.retry_number,
                    "maximum_retries": attempt.maximum,
                },
            )
        )

    async def _handle_llm_response(
        self,
        step: int,
        step_span_id: UUID,
        request_span_id: UUID,
        context: MessageContext,
    ) -> tuple[list[ToolCallRequest], ChatMessage]:
        """Parse LLM response with schema validation and bounded retry on violation.

        Step 2.2: When the LLM is called with a native schema constraint and
        the response fails Pydantic validation, the failure is treated as a
        recoverable schema violation.  The orchestrator builds a retry prompt
        via ``build_retry_messages``, re-issues the LLM call, and repeats up
        to ``SchemaConfig.max_validation_retries`` times.

        Only after the retry budget is exhausted (or when native constraint
        is disabled) does the response fall through to the legacy
        ``self.parser.parse`` as a gated provider-compatibility fallback.
        """
        strict = self.config.schema_config.strict_mode
        mode = await self._resolve_enforcement_mode()
        max_retries = self.config.schema_config.max_validation_retries if mode in ("native", "prompt") else 0

        # --- initial attempt ------------------------------------------------
        payload = context.to_ollama_payload()
        if mode == "prompt":
            schema_dict = build_schema_constraint(
                ToolCallResponse,
                strict=strict,
                additional_properties=self.config.schema_config.additional_properties,
            ).schema_dict
            payload = self._inject_schema_instruction(payload, schema_dict)
        raw = await self._call_llm(step, payload, step_span_id, request_span_id)
        val = validate_response(raw, ToolCallResponse, strict=strict)
        circuit = self._require_circuit()
        if mode in ("native", "prompt"):
            if val.valid:
                circuit.reset_schema_violations()
            else:
                circuit.record_schema_violation()

        # --- bounded retry loop ---------------------------------------------
        attempts = 0
        while not val.valid and attempts < max_retries:
            self.recorder.record_error(
                TrajectoryErrorRecord(
                    component="schema_validator",
                    message=val.error_summary(),
                    step_index=step,
                    span_id=request_span_id,
                    parent_span_id=step_span_id,
                    error_type=val.error_type.value if val.error_type else "SchemaValidationError",
                )
            )
            retry_messages = build_retry_messages(payload, val, assistant_content=raw)
            delta = retry_messages[len(payload) :]
            context.append_raw_dicts(delta)
            payload = retry_messages
            self._record_recovery_attempt(
                _RecoveryAttemptTelemetry(
                    step=step,
                    span_id=request_span_id,
                    parent_span_id=step_span_id,
                    category="schema_validation",
                    retry_number=attempts + 1,
                    maximum=max_retries,
                )
            )
            raw = await self._call_llm(step, payload, step_span_id, request_span_id)
            val = validate_response(raw, ToolCallResponse, strict=strict)
            attempts += 1
            if val.valid:
                circuit.reset_schema_violations()
            else:
                circuit.record_schema_violation()

        # Record final validation failure when the retry loop never ran (max_retries=0)
        if not val.valid and attempts == 0:
            self.recorder.record_error(
                TrajectoryErrorRecord(
                    component="schema_validator",
                    message=val.error_summary(),
                    step_index=step,
                    span_id=request_span_id,
                    parent_span_id=step_span_id,
                    error_type=val.error_type.value if val.error_type else "SchemaValidationError",
                )
            )

        # --- resolve tool requests -------------------------------------------
        tool_requests: list[ToolCallRequest] = []
        if val.valid and isinstance(val.data, ToolCallResponse):
            tool_requests.append(
                ToolCallRequest(
                    tool_name=val.data.tool_name,
                    arguments=val.data.tool_args,
                )
            )
        else:
            # Gated fallback: legacy parser as a provider-compatibility last
            # resort.  Reached only when:
            #   * use_native_constraint is False (provider-compat path), OR
            #   * the retry budget is exhausted on the native-constraint path.
            try:
                parsed = self.parser.parse(raw)
                tool_requests.append(
                    ToolCallRequest(
                        tool_name=parsed.tool_name,
                        arguments=parsed.arguments,
                    )
                )
            except Exception as exc:
                self.recorder.record_error(
                    TrajectoryErrorRecord(
                        component="tool_parser",
                        message=str(exc),
                        step_index=step,
                        span_id=request_span_id,
                        parent_span_id=step_span_id,
                        error_type=type(exc).__name__,
                    )
                )

        assistant_msg = ChatMessage(
            role=Role.ASSISTANT,
            content=raw,
            tool_calls=tool_requests if tool_requests else None,
        )
        context.add_message(assistant_msg)
        return tool_requests, assistant_msg

    async def _execute_tools(
        self,
        step: int,
        tool_requests: list[ToolCallRequest],
        step_span_id: UUID,
        context: MessageContext,
    ) -> list[ToolCallResult]:
        """Dispatch and record all tool calls in this step."""
        results: list[ToolCallResult] = []
        for request in tool_requests:
            results.append(await self._execute_one_tool(step, request, step_span_id, context))
        return results

    async def _execute_one_tool(
        self,
        step: int,
        request: ToolCallRequest,
        step_span_id: UUID,
        context: MessageContext,
    ) -> ToolCallResult:
        """Execute one timeout-bounded tool call and close its span exactly once."""
        tool_span_id = self.recorder.start_span(parent_span_id=step_span_id)
        try:
            self.recorder.record(
                TrajectoryRecord(
                    event_type=TrajectoryEventType.TOOL_CALL,
                    component="orchestrator",
                    span_id=tool_span_id,
                    parent_span_id=step_span_id,
                    step_index=step,
                    tool_name=request.tool_name,
                    tool_args=request.arguments,
                    payload={"call_id": request.call_id},
                )
            )

            tool_started = time.perf_counter()
            circuit = self._require_circuit()
            budget = circuit.timeout_budget(ReliabilityTripReason.TOOL_TIMEOUT)
            try:
                async with asyncio.timeout(budget.seconds):
                    response = await self.dispatcher.dispatch(request)
            except TimeoutError:
                circuit.trip_timeout(
                    budget,
                    cancellation_confirmed=self.dispatcher.cancellation_is_cooperative(request.tool_name),
                )
            tool_latency_ms = (time.perf_counter() - tool_started) * 1000

            tool_msg_content = str(response.result) if response.success else f"Error: {response.error_message}"
            context.add_message(
                ChatMessage(
                    role=Role.TOOL,
                    name=response.tool_name,
                    content=tool_msg_content,
                    tool_call_id=response.call_id,
                )
            )

            if response.success:
                self.recorder.record(
                    TrajectoryRecord(
                        event_type=TrajectoryEventType.TOOL_RESULT,
                        component="tool_dispatcher",
                        span_id=tool_span_id,
                        parent_span_id=step_span_id,
                        step_index=step,
                        tool_name=response.tool_name,
                        latency_ms=tool_latency_ms,
                        tool_result_summary={"success": True, "result": response.result},
                        payload={"call_id": response.call_id},
                    )
                )
            else:
                self.recorder.record_error(
                    TrajectoryErrorRecord(
                        component="tool_dispatcher",
                        message=response.error_message or "Tool execution failed.",
                        step_index=step,
                        span_id=tool_span_id,
                        parent_span_id=step_span_id,
                        error_type="ToolExecutionError",
                    )
                )
                self.recorder.record(
                    TrajectoryRecord(
                        event_type=TrajectoryEventType.TOOL_RESULT,
                        component="tool_dispatcher",
                        span_id=tool_span_id,
                        parent_span_id=step_span_id,
                        step_index=step,
                        tool_name=response.tool_name,
                        latency_ms=tool_latency_ms,
                        tool_result_summary={"success": False, "error": response.error_message},
                        payload={"call_id": response.call_id},
                    )
                )
            return response
        finally:
            self.recorder.end_span(tool_span_id)
