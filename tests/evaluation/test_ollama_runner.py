"""Mocked checks for optional real-local-Ollama Golden-Suite execution."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import BaseModel

from src.core.telemetry import RunContext, TrajectoryEvent, TrajectoryEventType, TrajectoryRecorder
from src.evaluation.catalog import build_deterministic_requests
from src.evaluation.models import ComponentKind, ComponentOutcome, ComponentResult
from src.evaluation.ollama_runner import (
    NondeterministicOutcomePolicy,
    OllamaEvaluationConfig,
    OllamaEvaluationResult,
    run_real_local_ollama_suite,
)
from src.evaluation.reporting import CaseEvaluationResult, CaseOutcome
from src.evaluation.runner import DeterministicCaseRequest
from src.llm.client import LLMClient, LLMGenerateResult
from src.schema.config import SchemaConfig

EXECUTED_AT = datetime(2026, 8, 31, 20, 0, tzinfo=UTC)


class RecordingSink:
    """Retain one empirical trajectory in memory."""

    def __init__(self) -> None:
        """Initialize an empty event collection."""
        self.events: list[TrajectoryEvent] = []
        self.closed = False

    def record(self, event: TrajectoryEvent) -> None:
        """Retain one event."""
        self.events.append(event)

    def flush(self) -> None:
        """Accept a flush request."""

    def close(self) -> None:
        """Record trajectory closure."""
        self.closed = True


class RecordingFactory:
    """Create a fresh in-memory recorder for every empirical case trajectory."""

    def __init__(self) -> None:
        """Initialize an empty sink list."""
        self.sinks: list[RecordingSink] = []

    def __call__(self, run_context: RunContext, model_id: str) -> TrajectoryRecorder:
        """Return one caller-owned recorder for the supplied identity."""
        del model_id
        sink = RecordingSink()
        self.sinks.append(sink)
        return TrajectoryRecorder(run_context, sink)


class ScriptedLLMClient(LLMClient):
    """Supply bounded local-model responses without network access."""

    def __init__(
        self,
        responses: tuple[str | Exception, ...],
        *,
        ollama_version: str = "0.33.2",
    ) -> None:
        """Store scripted responses and observable call metadata."""
        self.responses = list(responses)
        self.ollama_version = ollama_version
        self.version_calls = 0
        self.generate_calls: list[dict[str, Any]] = []

    async def generate(
        self,
        prompt: list[dict[str, Any]] | str,
        model: str | None = None,
        temperature: float | None = None,
        response_model: type[BaseModel] | None = None,
        format: dict[str, Any] | str | None = None,  # noqa: A002
    ) -> LLMGenerateResult:
        """Return the next response and retain only test-observable request metadata."""
        del response_model
        self.generate_calls.append(
            {
                "prompt": prompt,
                "model": model,
                "temperature": temperature,
                "format": format,
            }
        )
        if not self.responses:
            raise AssertionError("No scripted local-model response remains.")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return LLMGenerateResult(text=response, prompt_tokens=11, completion_tokens=7)

    async def get_ollama_version(self) -> str | None:
        """Return one deterministic mocked server version."""
        self.version_calls += 1
        return self.ollama_version

    async def close(self) -> None:
        """Accept client closure without owning a network connection."""


def _request(case_id: str) -> DeterministicCaseRequest:
    """Return one canonical request by stable case identity."""
    return next(request for request in build_deterministic_requests() if request.case.case_id == case_id)


def _config(*, repetitions: int = 1) -> OllamaEvaluationConfig:
    """Build a bounded empirical configuration with legacy parser fallback."""
    return OllamaEvaluationConfig(
        endpoint="http://local-ollama.test",
        model_id="golden-model:test",
        temperature=0.25,
        max_steps=3,
        repetitions=repetitions,
        schema_config=SchemaConfig(
            strict_mode=True,
            additional_properties=False,
            use_native_constraint=False,
            fallback_to_prompt=False,
            max_validation_retries=0,
        ),
    )


def _component(result: CaseEvaluationResult, kind: ComponentKind) -> ComponentResult:
    """Return one case component by kind."""
    return next(component for component in result.components if component.kind is kind)


@pytest.mark.asyncio
async def test_empirical_runner_uses_production_orchestration_and_suppresses_private_reasoning() -> None:
    """A correct model-selected call executes fixtures while raw model content stays out of telemetry."""
    secret = "private-reasoning-must-not-persist"
    client = ScriptedLLMClient(
        (
            (
                f"<think>{secret}</think>"
                '{"name":"analyze_graham_number","parameters":'
                '{"ticker":"SYNTH","eps_basis":"three_year_average"}}'
            ),
            f"<think>{secret}</think>Finished.",
        )
    )
    factory = RecordingFactory()

    result = await run_real_local_ollama_suite(
        (_request("GRN-01"),),
        suite_id="empirical-test",
        suite_version="i-v1",
        fixture_set_version="fixtures-v1",
        llm_client=client,
        config=_config(),
        executed_at=EXECUTED_AT,
        recorder_factory=factory,
    )

    report = result.repetition_reports[0].report
    case = report.case_results[0]
    assert case.outcome is CaseOutcome.PASS
    assert _component(case, ComponentKind.STRATEGY_SELECTION).outcome is ComponentOutcome.PASS
    assert _component(case, ComponentKind.GRAHAM_METHOD_SELECTION).outcome is ComponentOutcome.PASS
    assert _component(case, ComponentKind.NUMERICAL_CORRECTNESS).outcome is ComponentOutcome.NOT_MEASURED
    assert case.trajectory_id is not None
    assert report.run_id is None
    assert client.version_calls == 1
    assert len(client.generate_calls) == 2
    first_prompt = client.generate_calls[0]["prompt"]
    assert isinstance(first_prompt, list)
    assert "analyze_graham_number" in str(first_prompt)
    assert "Analyze SYNTH with Graham Number" in str(first_prompt)

    assert len(factory.sinks) == 1
    events = factory.sinks[0].events
    assert any(event.event_type is TrajectoryEventType.TOOL_CALL for event in events)
    assert any(event.event_type is TrajectoryEventType.TOOL_RESULT for event in events)
    assert factory.sinks[0].closed is True
    assert secret not in "".join(event.model_dump_json() for event in events)
    prompt_event = next(event for event in events if event.event_type is TrajectoryEventType.PROMPT_SENT)
    response_event = next(event for event in events if event.event_type is TrajectoryEventType.LLM_RESPONSE)
    assert prompt_event.payload == {
        "format_constrained": False,
        "message_count": 2,
        "temperature": 0.25,
        "message_content_retained": False,
    }
    assert response_event.payload == {"response_content_retained": False}

    settings = {setting.name: setting.value for setting in result.model_configuration.settings}
    assert result.model_configuration.provider_id == "ollama"
    assert result.model_configuration.model_id == "golden-model:test"
    assert settings["endpoint"] == "http://local-ollama.test"
    assert settings["ollama_version"] == "0.33.2"
    assert settings["temperature"] == 0.25
    assert settings["requested_repetitions"] == 1
    assert len(str(settings["system_prompt_sha256"])) == 64
    assert len(str(settings["tool_schemas_sha256"])) == 64


@pytest.mark.asyncio
async def test_empirical_runner_reports_typed_reliability_failure_with_run_identity() -> None:
    """A circuit trip becomes inspectable evaluation evidence rather than an exception."""
    tool_call = '{"tool_name":"analyze_graham_number","tool_args":{"ticker":"SYNTH","eps_basis":"three_year_average"}}'
    client = ScriptedLLMClient((tool_call, tool_call, tool_call))
    factory = RecordingFactory()

    result = await run_real_local_ollama_suite(
        (_request("GRN-01"),),
        suite_id="empirical-test",
        suite_version="i-v1",
        fixture_set_version="fixtures-v1",
        llm_client=client,
        config=_config(),
        executed_at=EXECUTED_AT,
        recorder_factory=factory,
    )

    case = result.repetition_reports[0].report.case_results[0]
    execution = _component(case, ComponentKind.EXECUTION_STATUS)
    assert execution.outcome is ComponentOutcome.FAIL
    assert execution.failure_reason is not None
    assert "max_steps_exceeded" in execution.failure_reason
    run_id = factory.sinks[0].events[0].run_id
    assert str(run_id) in execution.failure_reason
    assert factory.sinks[0].closed is True


@pytest.mark.asyncio
async def test_empirical_runner_classifies_wrong_case_arguments_as_selection_failure() -> None:
    """Correct tool/method selection does not hide a wrong normalized argument choice."""
    client = ScriptedLLMClient(
        (
            ('{"tool_name":"analyze_graham_number","tool_args":{"ticker":"SYNTH","eps_basis":"ttm"}}'),
            "Finished.",
        )
    )

    result = await run_real_local_ollama_suite(
        (_request("GRN-01"),),
        suite_id="empirical-test",
        suite_version="i-v1",
        fixture_set_version="fixtures-v1",
        llm_client=client,
        config=_config(),
        executed_at=EXECUTED_AT,
        recorder_factory=RecordingFactory(),
    )

    case = result.repetition_reports[0].report.case_results[0]
    selection = _component(case, ComponentKind.STRATEGY_SELECTION)
    assert case.outcome is CaseOutcome.FAIL
    assert selection.outcome is ComponentOutcome.FAIL
    assert selection.failure_reason is not None
    assert "eps_basis" in selection.failure_reason
    assert _component(case, ComponentKind.GRAHAM_METHOD_SELECTION).outcome is ComponentOutcome.PASS
    assert _component(case, ComponentKind.EXECUTION_STATUS).outcome is ComponentOutcome.PASS


@pytest.mark.asyncio
async def test_empirical_repetitions_preserve_pass_and_failure_without_majority_vote() -> None:
    """Nondeterministic outcomes remain separate, ordered reports with unique trajectories."""
    client = ScriptedLLMClient(
        (
            ('{"tool_name":"analyze_graham_number","tool_args":{"ticker":"SYNTH","eps_basis":"three_year_average"}}'),
            "Finished.",
            (
                '{"tool_name":"analyze_graham_growth_value","tool_args":'
                '{"ticker":"SYNTH","eps_basis":"ttm","expected_growth":6.5,"current_aaa_yield":4.15}}'
            ),
            "Finished.",
        )
    )
    factory = RecordingFactory()

    result = await run_real_local_ollama_suite(
        (_request("GRN-01"),),
        suite_id="empirical-test",
        suite_version="i-v1",
        fixture_set_version="fixtures-v1",
        llm_client=client,
        config=_config(repetitions=2),
        executed_at=EXECUTED_AT,
        recorder_factory=factory,
    )

    assert result.outcome_policy is NondeterministicOutcomePolicy.PRESERVE_ALL_REPETITIONS
    assert tuple(item.repetition for item in result.repetition_reports) == (1, 2)
    assert tuple(item.report.case_results[0].outcome for item in result.repetition_reports) == (
        CaseOutcome.PASS,
        CaseOutcome.FAIL,
    )
    trajectory_ids = tuple(item.report.case_results[0].trajectory_id for item in result.repetition_reports)
    assert len(set(trajectory_ids)) == 2
    assert all(trajectory_id is not None for trajectory_id in trajectory_ids)
    assert client.version_calls == 1
    assert len(factory.sinks) == 2
    assert OllamaEvaluationResult.model_validate_json(result.model_dump_json()) == result


@pytest.mark.asyncio
async def test_empirical_runner_rejects_misreported_concrete_client_endpoint() -> None:
    """Recorded endpoint configuration must match the injected production client's endpoint."""
    client = LLMClient("http://actual-ollama.test", default_model="golden-model:test")
    try:
        with pytest.raises(ValueError, match="does not match client endpoint"):
            await run_real_local_ollama_suite(
                (_request("GRN-01"),),
                suite_id="empirical-test",
                suite_version="i-v1",
                fixture_set_version="fixtures-v1",
                llm_client=client,
                config=_config(),
                executed_at=EXECUTED_AT,
                recorder_factory=RecordingFactory(),
            )
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_empirical_runner_records_model_failure_as_execution_failure() -> None:
    """A local-model error becomes an explicit failed case and still closes telemetry."""
    client = ScriptedLLMClient((RuntimeError("mock local model unavailable"),))
    factory = RecordingFactory()

    result = await run_real_local_ollama_suite(
        (_request("GRN-01"),),
        suite_id="empirical-test",
        suite_version="i-v1",
        fixture_set_version="fixtures-v1",
        llm_client=client,
        config=_config(),
        executed_at=EXECUTED_AT,
        recorder_factory=factory,
    )

    case = result.repetition_reports[0].report.case_results[0]
    execution = _component(case, ComponentKind.EXECUTION_STATUS)
    assert case.outcome is CaseOutcome.FAIL
    assert execution.outcome is ComponentOutcome.FAIL
    assert execution.failure_reason is not None
    assert "mock local model unavailable" in execution.failure_reason
    assert factory.sinks[0].closed is True
