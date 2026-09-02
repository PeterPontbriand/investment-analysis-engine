"""Evaluator self-test using a controlled synthetic numerical mutation."""

from datetime import UTC, datetime

from src.evaluation.evaluator import (
    evaluate_execution_status,
    evaluate_fixture_status,
    evaluate_numerical_correctness,
)
from src.evaluation.models import (
    ComponentKind,
    ComponentOutcome,
    ExecutionMode,
    NumericalExpectation,
    NumericalObservation,
    Observation,
)

EXECUTED_AT = datetime(2026, 8, 31, 19, 0, tzinfo=UTC)
EXPECTED = NumericalExpectation(
    field_path="result.value",
    expected_value=104.0,
    absolute_tolerance=0.0,
)


def _observation(value: float) -> Observation:
    """Build one direct numerical observation for the self-test only."""
    return Observation(
        execution_mode=ExecutionMode.DETERMINISTIC_NO_LLM,
        observed_at=EXECUTED_AT,
        numerical_observations=(NumericalObservation(field_path="result.value", value=value),),
    )


def test_correct_observation_passes_and_controlled_mutation_fails_numerically() -> None:
    """A one-value mutation is detected without becoming a benchmark case."""
    fixture_status = evaluate_fixture_status()
    execution_status = evaluate_execution_status()

    correct = evaluate_numerical_correctness(
        (EXPECTED,),
        _observation(104.0),
        fixture_status=fixture_status,
        execution_status=execution_status,
    )
    mutated = evaluate_numerical_correctness(
        (EXPECTED,),
        _observation(105.0),
        fixture_status=fixture_status,
        execution_status=execution_status,
    )

    assert correct.kind is ComponentKind.NUMERICAL_CORRECTNESS
    assert correct.outcome is ComponentOutcome.PASS
    assert mutated.kind is ComponentKind.NUMERICAL_CORRECTNESS
    assert mutated.outcome is ComponentOutcome.FAIL
    assert mutated.failure_reason is not None
    assert "Numerical comparison failed" in mutated.failure_reason
    assert "exceeds tolerance" in mutated.failure_reason
    assert fixture_status.outcome is ComponentOutcome.PASS
    assert execution_status.outcome is ComponentOutcome.PASS
