"""Contract tests for Step 2.6 reliability models and configuration."""

from __future__ import annotations

from dataclasses import dataclass
from math import inf, nan
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.config import ProjectSettings
from src.core.telemetry import TrajectoryEventType
from src.orchestrator.loop import OrchestratorConfig
from src.orchestrator.reliability import (
    CircuitBreaker,
    CircuitSnapshot,
    CircuitState,
    RecentEventSummary,
    ReliabilityFailure,
    ReliabilityLimitReachedError,
    ReliabilityLimits,
    ReliabilityTripReason,
    SystemMonotonicClock,
)
from src.schema.config import SchemaConfig


@dataclass
class FakeClock:
    """Deterministic monotonic clock for contract tests."""

    value: float = 100.0

    def now(self) -> float:
        """Return the controlled time."""
        return self.value

    def advance(self, seconds: float) -> None:
        """Advance controlled time."""
        self.value += seconds


def test_reliability_limits_have_approved_defaults() -> None:
    """The typed defaults match the approved Slice A contract."""
    limits = ReliabilityLimits()

    assert limits == ReliabilityLimits(
        max_steps=10,
        max_transient_retries=3,
        max_consecutive_schema_violations=4,
        overall_timeout_seconds=300.0,
        step_timeout_seconds=180.0,
        llm_call_timeout_seconds=120.0,
        tool_call_timeout_seconds=60.0,
        recent_diagnostic_events=5,
    )


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("max_steps", 0),
        ("max_steps", 51),
        ("max_transient_retries", -1),
        ("max_consecutive_schema_violations", 0),
        ("overall_timeout_seconds", 0),
        ("step_timeout_seconds", -1),
        ("llm_call_timeout_seconds", inf),
        ("tool_call_timeout_seconds", nan),
        ("recent_diagnostic_events", 0),
        ("max_consecutive_schema_violations", 5),
    ],
)
def test_reliability_limits_reject_invalid_values(field_name: str, invalid_value: int | float) -> None:
    """Invalid bounds and non-finite timeouts fail closed."""
    with pytest.raises(ValidationError):
        ReliabilityLimits.model_validate({field_name: invalid_value})


def test_reliability_limits_are_frozen_and_forbid_unknown_fields() -> None:
    """Run policy cannot drift after validation or accept misspelled settings."""
    limits = ReliabilityLimits()

    with pytest.raises(ValidationError):
        limits.max_steps = 4
    with pytest.raises(ValidationError):
        ReliabilityLimits.model_validate({"max_step": 4})


def test_project_settings_accept_typed_reliability_overrides() -> None:
    """Settings provide the single application-level reliability namespace."""
    project_settings = ProjectSettings.model_validate(
        {"reliability_limits": {"max_steps": 7, "tool_call_timeout_seconds": 12.5}}
    )

    assert project_settings.reliability_limits.max_steps == 7
    assert project_settings.reliability_limits.tool_call_timeout_seconds == 12.5


def test_project_settings_reads_nested_reliability_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reliability limits remain configurable without code changes."""
    monkeypatch.setenv("reliability_limits__max_steps", "8")

    project_settings = ProjectSettings()

    assert project_settings.reliability_limits.max_steps == 8


def test_orchestrator_config_uses_explicit_reliability_limits() -> None:
    """A per-run typed override is the authoritative effective policy."""
    limits = ReliabilityLimits(max_steps=6)
    config = OrchestratorConfig(reliability_limits=limits)

    assert config.reliability_limits is limits
    assert config.max_steps == 6


def test_orchestrator_config_migrates_legacy_max_steps() -> None:
    """The existing construction path normalizes into the typed policy."""
    config = OrchestratorConfig(max_steps=3)

    assert config.max_steps == 3
    assert config.reliability_limits.max_steps == 3
    assert "max_steps" not in config.model_dump()


def test_orchestrator_config_validates_legacy_max_steps_during_migration() -> None:
    """Compatibility normalization cannot bypass the typed limit bounds."""
    with pytest.raises(ValidationError):
        OrchestratorConfig(max_steps=51)


def test_orchestrator_config_rejects_conflicting_max_steps() -> None:
    """Legacy and typed inputs cannot create two authoritative values."""
    with pytest.raises(ValidationError, match="max_steps conflicts"):
        OrchestratorConfig(
            max_steps=3,
            reliability_limits=ReliabilityLimits(max_steps=4),
        )


def test_orchestrator_config_migrates_legacy_schema_retries() -> None:
    """The existing schema retry input normalizes into the typed policy."""
    config = OrchestratorConfig(schema_config=SchemaConfig(max_validation_retries=2))

    assert config.schema_config.max_validation_retries == 2
    assert config.reliability_limits.max_transient_retries == 2
    assert config.reliability_limits.max_consecutive_schema_violations == 3


def test_orchestrator_config_migrates_mapping_schema_config() -> None:
    """Pydantic mapping construction remains supported during migration."""
    config = OrchestratorConfig.model_validate({"schema_config": {"max_validation_retries": 2}})

    assert config.schema_config.max_validation_retries == 2
    assert config.reliability_limits.max_consecutive_schema_violations == 3


def test_orchestrator_config_uses_reliability_schema_limit() -> None:
    """A typed policy updates the compatibility schema retry view."""
    config = OrchestratorConfig(
        reliability_limits=ReliabilityLimits(
            max_transient_retries=3,
            max_consecutive_schema_violations=2,
        )
    )

    assert config.schema_config.max_validation_retries == 1


def test_orchestrator_config_rejects_conflicting_schema_retry_inputs() -> None:
    """Typed and legacy schema inputs cannot disagree."""
    with pytest.raises(ValidationError, match="schema_config.max_validation_retries conflicts"):
        OrchestratorConfig(
            reliability_limits=ReliabilityLimits(),
            schema_config=SchemaConfig(max_validation_retries=2),
        )


def test_reliability_failure_serializes_stable_sanitized_contract() -> None:
    """Terminal failures carry identifiers and metadata without raw payloads."""
    run_id = uuid4()
    event = RecentEventSummary(
        sequence=8,
        event_type=TrajectoryEventType.LLM_RESPONSE,
        component="llm",
        step_index=2,
    )
    failure = ReliabilityFailure(
        reason=ReliabilityTripReason.LLM_TIMEOUT,
        message="LLM call exceeded its configured timeout.",
        run_id=run_id,
        final_step=2,
        configured_limit=120.0,
        observed_value=120.1,
        recent_events=(event,),
        cancellation_confirmed=True,
    )

    restored = ReliabilityFailure.model_validate_json(failure.model_dump_json())

    assert restored == failure
    assert restored.run_id == run_id
    assert set(type(restored.recent_events[0]).model_fields) == {
        "sequence",
        "event_type",
        "component",
        "step_index",
    }


def test_circuit_snapshot_defaults_closed_and_is_frozen() -> None:
    """A new observable circuit state is closed with zero counters."""
    snapshot = CircuitSnapshot()

    assert snapshot.state is CircuitState.CLOSED
    assert snapshot.trip_reason is None
    assert snapshot.transient_retries == 0
    assert snapshot.consecutive_schema_violations == 0
    with pytest.raises(ValidationError):
        snapshot.state = CircuitState.TRIPPED


@pytest.mark.parametrize(
    "snapshot",
    [
        {"state": CircuitState.TRIPPED},
        {
            "state": CircuitState.CLOSED,
            "trip_reason": ReliabilityTripReason.MAX_STEPS_EXCEEDED,
        },
    ],
)
def test_circuit_snapshot_rejects_inconsistent_trip_reason(snapshot: dict[str, object]) -> None:
    """Observable circuit state cannot disagree with its terminal reason."""
    with pytest.raises(ValidationError):
        CircuitSnapshot.model_validate(snapshot)


def test_system_monotonic_clock_returns_monotonic_value() -> None:
    """The production clock implements the injectable monotonic-clock seam."""
    clock = SystemMonotonicClock()

    assert clock.now() <= clock.now()


def test_circuit_selects_earliest_deadline() -> None:
    """The step deadline wins when it precedes the operation and run deadlines."""
    clock = FakeClock()
    circuit = CircuitBreaker(
        ReliabilityLimits(
            overall_timeout_seconds=30,
            step_timeout_seconds=5,
            llm_call_timeout_seconds=10,
        ),
        clock,
    )
    circuit.begin_step(1)

    budget = circuit.timeout_budget(ReliabilityTripReason.LLM_TIMEOUT)

    assert budget.seconds == 5
    assert budget.reason is ReliabilityTripReason.STEP_TIMEOUT


def test_circuit_trips_overall_deadline_before_new_step() -> None:
    """No new planning step starts after the overall deadline."""
    clock = FakeClock()
    circuit = CircuitBreaker(ReliabilityLimits(overall_timeout_seconds=2), clock)
    clock.advance(2)

    with pytest.raises(ReliabilityLimitReachedError) as raised:
        circuit.begin_step(1)

    assert raised.value.reason is ReliabilityTripReason.OVERALL_TIMEOUT
    assert circuit.snapshot.trip_reason is ReliabilityTripReason.OVERALL_TIMEOUT


def test_circuit_transient_retry_limit_and_success_reset() -> None:
    """Retries are per operation and reset only after success."""
    circuit = CircuitBreaker(
        ReliabilityLimits(
            max_transient_retries=1,
            max_consecutive_schema_violations=2,
        ),
        FakeClock(),
    )

    assert circuit.authorize_transient_retry() == 1
    circuit.reset_transient_retries()
    assert circuit.authorize_transient_retry() == 1
    with pytest.raises(ReliabilityLimitReachedError) as raised:
        circuit.authorize_transient_retry()

    assert raised.value.reason is ReliabilityTripReason.TRANSIENT_RETRY_LIMIT


def test_circuit_schema_counter_resets_only_after_valid_response() -> None:
    """Consecutive schema violations reset through the explicit valid-response path."""
    circuit = CircuitBreaker(
        ReliabilityLimits(
            max_transient_retries=2,
            max_consecutive_schema_violations=2,
        ),
        FakeClock(),
    )

    assert circuit.record_schema_violation() == 1
    circuit.reset_schema_violations()
    assert circuit.record_schema_violation() == 1
    with pytest.raises(ReliabilityLimitReachedError) as raised:
        circuit.record_schema_violation()

    assert raised.value.reason is ReliabilityTripReason.SCHEMA_VIOLATION_LIMIT
