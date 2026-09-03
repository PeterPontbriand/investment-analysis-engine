"""Optional empirical Golden-Suite execution through the real local-Ollama orchestration path."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Final
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from src.core.telemetry import (
    RunContext,
    TelemetryMode,
    TrajectoryEvent,
    TrajectoryEventType,
    TrajectoryRecord,
    TrajectoryRecorder,
    TrajectoryRecorderConfig,
)
from src.evaluation.catalog import (
    DETERMINISTIC_FIXTURE_SET_VERSION,
    DETERMINISTIC_SUITE_ID,
    DETERMINISTIC_SUITE_VERSION,
    build_deterministic_requests,
)
from src.evaluation.composition import AnalysisToolArguments, FixtureCompositionError, compose_fixture_dispatcher
from src.evaluation.evaluator import (
    evaluate_execution_status,
    evaluate_fixture_status,
    evaluate_graham_method_selection,
    evaluate_tool_selection,
)
from src.evaluation.models import (
    ComponentKind,
    ComponentOutcome,
    ComponentResult,
    ExecutionMode,
    GrahamMethod,
    GrahamMethodObservation,
    Observation,
    ToolCallObservation,
    ToolName,
)
from src.evaluation.reporting import (
    CaseEvaluationResult,
    EvaluationReport,
    ModelConfiguration,
    ModelSetting,
    build_case_result,
    build_evaluation_report,
)
from src.evaluation.runner import DeterministicCaseRequest
from src.llm.client import LLMClient
from src.orchestrator.analysis_tools import (
    ANALYSIS_TOOL_ARGUMENT_MODELS,
    FCFEarningsGrowthToolArguments,
    GrahamGrowthValueToolArguments,
    GrahamNumberToolArguments,
    MomentumToolArguments,
)
from src.orchestrator.context import MessageContext
from src.orchestrator.loop import AgentOrchestrator, OrchestratorConfig, OrchestratorOptions
from src.orchestrator.prompts import SystemPromptBuilder
from src.orchestrator.types import AgentStepResult, ToolCallRequest, ToolCallResult
from src.schema.config import SchemaConfig
from src.tools.parser import ToolParser
from src.tools.schema_generator import ToolRegistry

FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]

OLLAMA_REQUIRED_COMPONENT_KINDS: Final = (
    ComponentKind.STRATEGY_SELECTION,
    ComponentKind.GRAHAM_METHOD_SELECTION,
    ComponentKind.FIXTURE_STATUS,
    ComponentKind.EXECUTION_STATUS,
)

_TOOL_DESCRIPTIONS: Final = {
    ToolName.ANALYZE_MOMENTUM.value: "Analyze historical price momentum with structured SMA and RSI metrics.",
    ToolName.ANALYZE_GRAHAM_NUMBER.value: "Calculate the Graham Number company-level valuation ceiling.",
    ToolName.ANALYZE_GRAHAM_GROWTH_VALUE.value: "Calculate the explicit Graham growth-value method.",
    ToolName.ANALYZE_FCF_EARNINGS_GROWTH.value: "Analyze company free-cash-flow and diluted-EPS growth.",
}

type RecorderFactory = Callable[[RunContext, str], TrajectoryRecorder]


class NondeterministicOutcomePolicy(StrEnum):
    """Supported treatment of repeated empirical outcomes."""

    PRESERVE_ALL_REPETITIONS = "preserve_all_repetitions"


class OllamaEvaluationConfig(BaseModel):
    """Explicit model, endpoint, sampling, schema, and repetition configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    endpoint: str
    model_id: str
    temperature: FiniteFloat = 0.0
    max_steps: int = Field(default=10, ge=1, le=50)
    repetitions: int = Field(default=1, ge=1, le=100)
    schema_config: SchemaConfig = Field(default_factory=SchemaConfig)
    outcome_policy: NondeterministicOutcomePolicy = NondeterministicOutcomePolicy.PRESERVE_ALL_REPETITIONS

    @field_validator("endpoint", "model_id")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        """Normalize required configuration identifiers."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("Ollama endpoint and model_id must not be blank")
        return normalized


class OllamaRepetitionReport(BaseModel):
    """One unmodified empirical report for one requested repetition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    repetition: int = Field(ge=1)
    report: EvaluationReport

    @model_validator(mode="after")
    def validate_empirical_report(self) -> OllamaRepetitionReport:
        """Require the real-local-Ollama report mode."""
        if self.report.execution_mode is not ExecutionMode.REAL_LOCAL_OLLAMA:
            raise ValueError("repetition reports must use real_local_ollama mode")
        return self


class OllamaEvaluationResult(BaseModel):
    """Machine-readable empirical result preserving every repetition independently."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    suite_id: str
    suite_version: str
    fixture_set_version: str
    executed_at: datetime
    session_id: str
    model_configuration: ModelConfiguration
    outcome_policy: NondeterministicOutcomePolicy
    requested_repetitions: int = Field(ge=1)
    repetition_reports: tuple[OllamaRepetitionReport, ...]

    @field_validator("suite_id", "suite_version", "fixture_set_version", "session_id")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        """Normalize required result identifiers."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("empirical result identifiers must not be blank")
        return normalized

    @field_validator("executed_at")
    @classmethod
    def validate_executed_at(cls, value: datetime) -> datetime:
        """Require an unambiguous evaluation timestamp."""
        if value.utcoffset() is None:
            raise ValueError("executed_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_repetitions(self) -> OllamaEvaluationResult:
        """Require exact ordered repetitions with consistent report metadata."""
        if len(self.repetition_reports) != self.requested_repetitions:
            raise ValueError("repetition report count must equal requested_repetitions")
        expected_numbers = tuple(range(1, self.requested_repetitions + 1))
        if tuple(item.repetition for item in self.repetition_reports) != expected_numbers:
            raise ValueError("repetition reports must be complete and ordered")
        for item in self.repetition_reports:
            report = item.report
            if (
                report.suite_id != self.suite_id
                or report.suite_version != self.suite_version
                or report.fixture_set_version != self.fixture_set_version
                or report.executed_at != self.executed_at
                or report.model_configuration != self.model_configuration
            ):
                raise ValueError("repetition report metadata must match the empirical result")
        return self


class _PrivateReasoningSafeRecorder(TrajectoryRecorder):
    """Retain observable execution evidence without persisting model-response content."""

    def record(self, record: TrajectoryRecord) -> TrajectoryEvent | None:
        """Suppress response and retry-message bodies before ordinary redaction/persistence."""
        if record.event_type is TrajectoryEventType.PROMPT_SENT:
            payload = record.payload if isinstance(record.payload, dict) else {}
            messages = payload.get("messages")
            safe_payload = {
                "format_constrained": payload.get("format_constrained"),
                "message_count": len(messages) if isinstance(messages, list) else None,
                "temperature": payload.get("temperature"),
                "message_content_retained": False,
            }
            record = replace(record, payload=safe_payload)
        elif record.event_type is TrajectoryEventType.LLM_RESPONSE:
            record = replace(record, payload={"response_content_retained": False})
        return super().record(record)


async def run_minimum_real_local_ollama_suite(
    *,
    llm_client: LLMClient,
    config: OllamaEvaluationConfig,
    executed_at: datetime,
    recorder_factory: RecorderFactory | None = None,
) -> OllamaEvaluationResult:
    """Run the reviewed fifteen-case catalog through the empirical orchestration path."""
    return await run_real_local_ollama_suite(
        build_deterministic_requests(),
        suite_id=DETERMINISTIC_SUITE_ID,
        suite_version=DETERMINISTIC_SUITE_VERSION,
        fixture_set_version=DETERMINISTIC_FIXTURE_SET_VERSION,
        llm_client=llm_client,
        config=config,
        executed_at=executed_at,
        recorder_factory=recorder_factory,
    )


async def run_real_local_ollama_suite(  # noqa: PLR0913
    requests: tuple[DeterministicCaseRequest, ...],
    *,
    suite_id: str,
    suite_version: str,
    fixture_set_version: str,
    llm_client: LLMClient,
    config: OllamaEvaluationConfig,
    executed_at: datetime,
    recorder_factory: RecorderFactory | None = None,
) -> OllamaEvaluationResult:
    """Execute supplied cases empirically while preserving each repetition as observed."""
    _validate_run_inputs(requests, executed_at=executed_at)
    _validate_client_endpoint(llm_client, configured_endpoint=config.endpoint)
    ollama_version = await llm_client.get_ollama_version()
    tool_schemas_json = _tool_schemas_json()
    system_prompt = SystemPromptBuilder(tool_schemas_json=tool_schemas_json).build()
    effective_schema_config = replace(
        config.schema_config,
        ollama_version=ollama_version or config.schema_config.ollama_version,
    )
    model_configuration = _model_configuration(
        config,
        ollama_version=ollama_version,
        system_prompt=system_prompt,
        tool_schemas_json=tool_schemas_json,
    )
    session_id = uuid4()
    factory = recorder_factory or _default_recorder_factory
    repetition_reports: list[OllamaRepetitionReport] = []

    for repetition in range(1, config.repetitions + 1):
        case_results = []
        for request in requests:
            run_context = RunContext.new(session_id=session_id)
            recorder = _private_reasoning_safe_recorder(factory(run_context, config.model_id))
            case_results.append(
                await _run_case(
                    request,
                    llm_client=llm_client,
                    config=config,
                    schema_config=effective_schema_config,
                    executed_at=executed_at,
                    system_prompt=system_prompt,
                    recorder=recorder,
                )
            )
        report = build_evaluation_report(
            suite_id=suite_id,
            suite_version=suite_version,
            fixture_set_version=fixture_set_version,
            execution_mode=ExecutionMode.REAL_LOCAL_OLLAMA,
            executed_at=executed_at,
            required_component_kinds=OLLAMA_REQUIRED_COMPONENT_KINDS,
            case_results=tuple(case_results),
            model_configuration=model_configuration,
        )
        repetition_reports.append(OllamaRepetitionReport(repetition=repetition, report=report))

    return OllamaEvaluationResult(
        suite_id=suite_id,
        suite_version=suite_version,
        fixture_set_version=fixture_set_version,
        executed_at=executed_at,
        session_id=str(session_id),
        model_configuration=model_configuration,
        outcome_policy=config.outcome_policy,
        requested_repetitions=config.repetitions,
        repetition_reports=tuple(repetition_reports),
    )


async def _run_case(  # noqa: PLR0913
    request: DeterministicCaseRequest,
    *,
    llm_client: LLMClient,
    config: OllamaEvaluationConfig,
    schema_config: SchemaConfig,
    executed_at: datetime,
    system_prompt: str,
    recorder: TrajectoryRecorder,
) -> CaseEvaluationResult:
    """Execute and score one empirical case through the production orchestrator."""
    fixture_failure: str | None = None
    execution_failure: str | None = None
    steps: list[AgentStepResult] = []
    try:
        dispatcher = compose_fixture_dispatcher(request.case, clock_at=executed_at)
    except FixtureCompositionError as exc:
        fixture_failure = str(exc)
        recorder.flush()
        recorder.close()
    else:
        context = MessageContext()
        context.set_system_prompt(system_prompt)
        orchestrator = AgentOrchestrator(
            llm_client,
            dispatcher,
            _tool_parser(),
            OrchestratorOptions(
                config=OrchestratorConfig(
                    max_steps=config.max_steps,
                    model_selection=config.model_id,
                    temperature=config.temperature,
                    mode="full",
                    schema_config=schema_config,
                ),
                recorder=recorder,
                run_context=recorder.run_context,
            ),
        )
        try:
            async for step in orchestrator.run_stream(request.case.task, context):
                steps.append(step)
        except Exception as exc:
            execution_failure = f"Orchestration raised {type(exc).__name__}: {exc}"

    tool_requests = tuple(tool_request for step in steps for tool_request in (step.message.tool_calls or ()))
    tool_results = tuple(result for step in steps for result in step.executed_tools)
    if execution_failure is None:
        execution_failure = _tool_execution_failure(tool_results) or _terminal_failure(steps)

    observation = _selection_observation(tool_requests, observed_at=executed_at)
    selection = _evaluate_tool_and_argument_selection(request, tool_requests, observation)
    method_selection = evaluate_graham_method_selection(
        request.case.expectation.graham_method_constraints,
        observation,
    )
    components = (
        selection,
        method_selection,
        ComponentResult(
            kind=ComponentKind.NUMERICAL_CORRECTNESS,
            outcome=ComponentOutcome.NOT_MEASURED,
            evidence=(
                "Empirical mode measures model selection; deterministic numerical correctness is reported separately."
            ),
        ),
        evaluate_fixture_status(fixture_failure),
        evaluate_execution_status(execution_failure),
    )
    return build_case_result(
        case_id=request.case.case_id,
        components=components,
        required_component_kinds=OLLAMA_REQUIRED_COMPONENT_KINDS,
        trajectory_id=str(recorder.run_id),
    )


def _selection_observation(
    tool_requests: tuple[ToolCallRequest, ...],
    *,
    observed_at: datetime,
) -> Observation:
    """Build typed selection evidence from observable parsed tool requests only."""
    recognized = tuple(
        ToolCallObservation(tool_name=ToolName(request.tool_name))
        for request in tool_requests
        if request.tool_name in ToolName._value2member_map_
    )
    methods = tuple(
        GrahamMethodObservation(method=method)
        for request in tool_requests
        if (method := _graham_method(request.tool_name)) is not None
    )
    return Observation(
        execution_mode=ExecutionMode.REAL_LOCAL_OLLAMA,
        observed_at=observed_at,
        tool_calls=recognized,
        graham_methods=methods,
    )


def _evaluate_tool_and_argument_selection(
    request: DeterministicCaseRequest,
    tool_requests: tuple[ToolCallRequest, ...],
    observation: Observation,
) -> ComponentResult:
    """Evaluate tool identity plus strict, case-corresponding normalized arguments."""
    base = evaluate_tool_selection(request.case.expectation.tool_constraints, observation)
    unknown_tools = tuple(
        item.tool_name for item in tool_requests if item.tool_name not in ANALYSIS_TOOL_ARGUMENT_MODELS
    )
    if unknown_tools:
        return ComponentResult(
            kind=ComponentKind.STRATEGY_SELECTION,
            outcome=ComponentOutcome.FAIL,
            failure_reason="Observed unregistered tools: " + ", ".join(sorted(set(unknown_tools))) + ".",
            evidence=base.evidence,
        )
    if base.outcome is not ComponentOutcome.PASS:
        return base

    expected_tool = _tool_name(request.arguments).value
    failures: list[str] = []
    matching_calls = tuple(item for item in tool_requests if item.tool_name == expected_tool)
    for index, item in enumerate(matching_calls, start=1):
        argument_model = ANALYSIS_TOOL_ARGUMENT_MODELS[item.tool_name]
        try:
            observed_arguments = argument_model.model_validate(item.arguments)
        except ValidationError as exc:
            failures.append(
                f"call {index} arguments failed {argument_model.__name__} validation: {exc.error_count()} error(s)"
            )
            continue
        differences = _argument_differences(request.arguments, observed_arguments)
        if differences:
            failures.append(f"call {index} differs at {', '.join(differences)}")
    if failures:
        return ComponentResult(
            kind=ComponentKind.STRATEGY_SELECTION,
            outcome=ComponentOutcome.FAIL,
            failure_reason="Tool arguments did not match the reviewed case contract: " + "; ".join(failures) + ".",
            evidence=base.evidence,
        )
    return ComponentResult(
        kind=ComponentKind.STRATEGY_SELECTION,
        outcome=ComponentOutcome.PASS,
        evidence=(base.evidence or "")
        + f" {len(matching_calls)} matching call(s) used the reviewed normalized arguments.",
    )


def _argument_differences(expected: BaseModel, observed: BaseModel) -> tuple[str, ...]:
    """Return names of normalized argument fields that differ."""
    expected_values = expected.model_dump(mode="python")
    observed_values = observed.model_dump(mode="python")
    names = set(expected_values) | set(observed_values)
    return tuple(sorted(name for name in names if expected_values.get(name) != observed_values.get(name)))


def _tool_execution_failure(results: tuple[ToolCallResult, ...]) -> str | None:
    """Return one observable production-dispatch failure summary, if any."""
    failures = tuple(
        f"{result.tool_name}: {result.error_message or 'tool execution failed'}"
        for result in results
        if not result.success
    )
    return None if not failures else "Production tool execution failed: " + "; ".join(failures) + "."


def _terminal_failure(steps: list[AgentStepResult]) -> str | None:
    """Return a typed terminal reliability diagnostic without inspecting model prose."""
    if not steps:
        return None
    failure = steps[-1].failure
    return None if failure is None else failure.message


def _graham_method(tool_name: str) -> GrahamMethod | None:
    """Map observable production-tool identity to a Graham method."""
    if tool_name == ToolName.ANALYZE_GRAHAM_NUMBER.value:
        return GrahamMethod.GRAHAM_NUMBER
    if tool_name == ToolName.ANALYZE_GRAHAM_GROWTH_VALUE.value:
        return GrahamMethod.GRAHAM_GROWTH_VALUE
    return None


def _tool_name(arguments: AnalysisToolArguments) -> ToolName:
    """Return the production tool represented by one strict argument model."""
    if isinstance(arguments, MomentumToolArguments):
        return ToolName.ANALYZE_MOMENTUM
    if isinstance(arguments, GrahamNumberToolArguments):
        return ToolName.ANALYZE_GRAHAM_NUMBER
    if isinstance(arguments, GrahamGrowthValueToolArguments):
        return ToolName.ANALYZE_GRAHAM_GROWTH_VALUE
    if isinstance(arguments, FCFEarningsGrowthToolArguments):
        return ToolName.ANALYZE_FCF_EARNINGS_GROWTH
    raise TypeError(f"Unsupported analysis-tool argument model: {type(arguments).__name__}.")


def _tool_schemas_json() -> str:
    """Serialize the four existing production argument contracts for the model prompt."""
    tools = tuple(
        {
            "name": name,
            "description": _TOOL_DESCRIPTIONS[name],
            "parameters": argument_model.model_json_schema(),
        }
        for name, argument_model in ANALYSIS_TOOL_ARGUMENT_MODELS.items()
    )
    return json.dumps({"tools": tools}, sort_keys=True, separators=(",", ":"))


def _tool_parser() -> ToolParser:
    """Build the production parser's approved-name registry without duplicating argument schemas."""
    registry = ToolRegistry()

    def parser_placeholder() -> None:
        """Placeholder used only to register an approved model-visible tool name."""

    for name in ANALYSIS_TOOL_ARGUMENT_MODELS:
        registry.register(parser_placeholder, name=name, description=_TOOL_DESCRIPTIONS[name])
    return ToolParser(registry)


def _model_configuration(
    config: OllamaEvaluationConfig,
    *,
    ollama_version: str | None,
    system_prompt: str,
    tool_schemas_json: str,
) -> ModelConfiguration:
    """Record only applied and observable empirical model/runtime configuration."""
    schema = config.schema_config
    settings = (
        ModelSetting(name="endpoint", value=config.endpoint),
        ModelSetting(name="ollama_version", value=ollama_version),
        ModelSetting(name="temperature", value=config.temperature),
        ModelSetting(name="max_steps", value=config.max_steps),
        ModelSetting(name="requested_repetitions", value=config.repetitions),
        ModelSetting(name="schema_strict_mode", value=schema.strict_mode),
        ModelSetting(name="schema_additional_properties", value=schema.additional_properties),
        ModelSetting(name="schema_use_native_constraint", value=schema.use_native_constraint),
        ModelSetting(name="schema_fallback_to_prompt", value=schema.fallback_to_prompt),
        ModelSetting(name="schema_max_validation_retries", value=schema.max_validation_retries),
        ModelSetting(name="schema_version_override", value=schema.ollama_version),
        ModelSetting(name="system_prompt_sha256", value=_sha256(system_prompt)),
        ModelSetting(name="tool_schemas_sha256", value=_sha256(tool_schemas_json)),
    )
    return ModelConfiguration(provider_id="ollama", model_id=config.model_id, settings=settings)


def _sha256(value: str) -> str:
    """Return a stable content identity without retaining prompt bodies in the result."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _private_reasoning_safe_recorder(recorder: TrajectoryRecorder) -> TrajectoryRecorder:
    """Adopt a fresh recorder's sink while enforcing empirical content suppression."""
    return _PrivateReasoningSafeRecorder(
        recorder.run_context,
        recorder.sink,
        TrajectoryRecorderConfig(
            mode=recorder.mode,
            model_tag=recorder.model_tag,
            provider=recorder.provider,
            enabled=recorder.enabled,
        ),
    )


def _default_recorder_factory(run_context: RunContext, model_id: str) -> TrajectoryRecorder:
    """Create the existing local JSONL trajectory recorder for an explicit empirical run."""
    return TrajectoryRecorder.from_settings(run_context, mode=TelemetryMode.FULL, model_tag=model_id)


def _validate_run_inputs(requests: tuple[DeterministicCaseRequest, ...], *, executed_at: datetime) -> None:
    """Reject ambiguous timestamps and duplicate case identities before any model call."""
    if executed_at.utcoffset() is None:
        raise ValueError("executed_at must be timezone-aware")
    case_ids = tuple(request.case.case_id for request in requests)
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("empirical case identifiers must be unique")


def _validate_client_endpoint(llm_client: LLMClient, *, configured_endpoint: str) -> None:
    """Prevent a concrete production client from being reported under a different endpoint."""
    client = getattr(llm_client, "client", None)
    base_url = getattr(client, "base_url", None)
    if base_url is None:
        return
    actual = str(base_url).rstrip("/")
    expected = configured_endpoint.rstrip("/")
    if actual != expected:
        raise ValueError(f"Configured Ollama endpoint {expected!r} does not match client endpoint {actual!r}.")


__all__ = [
    "NondeterministicOutcomePolicy",
    "OLLAMA_REQUIRED_COMPONENT_KINDS",
    "OllamaEvaluationConfig",
    "OllamaEvaluationResult",
    "OllamaRepetitionReport",
    "run_minimum_real_local_ollama_suite",
    "run_real_local_ollama_suite",
]
