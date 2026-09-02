"""Focused tests for pure Golden-Suite component evaluation."""

from datetime import UTC, datetime

import pytest

from src.evaluation.evaluator import (
    evaluate_behavior_constraints,
    evaluate_domain_outcomes,
    evaluate_execution_status,
    evaluate_fixture_status,
    evaluate_graham_method_selection,
    evaluate_numerical_correctness,
    evaluate_tool_selection,
)
from src.evaluation.models import (
    BehaviorConstraints,
    ComponentKind,
    ComponentOutcome,
    ComponentResult,
    DomainOutcomeExpectation,
    DomainOutcomeObservation,
    ExecutionMode,
    GrahamMethod,
    GrahamMethodConstraints,
    GrahamMethodObservation,
    NumericalExpectation,
    NumericalObservation,
    Observation,
    ToolCallObservation,
    ToolConstraints,
    ToolName,
)

OBSERVED_AT = datetime(2026, 8, 31, 15, 0, tzinfo=UTC)


def _observation(
    *,
    mode: ExecutionMode = ExecutionMode.REAL_LOCAL_OLLAMA,
    tools: tuple[ToolName, ...] = (),
    methods: tuple[GrahamMethod, ...] = (),
    numbers: tuple[tuple[str, float], ...] = (),
    domain_outcomes: tuple[tuple[str, str | bool | int | None], ...] = (),
) -> Observation:
    return Observation(
        execution_mode=mode,
        observed_at=OBSERVED_AT,
        tool_calls=tuple(ToolCallObservation(tool_name=tool) for tool in tools),
        graham_methods=tuple(GrahamMethodObservation(method=method) for method in methods),
        numerical_observations=tuple(
            NumericalObservation(field_path=field_path, value=value) for field_path, value in numbers
        ),
        domain_outcome_observations=tuple(
            DomainOutcomeObservation(field_path=field_path, value=value) for field_path, value in domain_outcomes
        ),
    )


def _pass_statuses() -> tuple[ComponentResult, ComponentResult]:
    return evaluate_fixture_status(), evaluate_execution_status()


def test_domain_outcomes_match_exact_status_reason_and_null_values() -> None:
    """Expected non-success native outcomes pass without becoming fixture failures."""
    expectations = (
        DomainOutcomeExpectation(field_path="result.status", expected_value="input_unavailable"),
        DomainOutcomeExpectation(field_path="result.reason_code", expected_value="non_contiguous_history"),
        DomainOutcomeExpectation(field_path="result.value", expected_value=None),
    )
    observation = _observation(
        mode=ExecutionMode.DETERMINISTIC_NO_LLM,
        domain_outcomes=(
            ("result.status", "input_unavailable"),
            ("result.reason_code", "non_contiguous_history"),
            ("result.value", None),
        ),
    )

    result = evaluate_domain_outcomes(expectations, observation)

    assert result.kind is ComponentKind.EXECUTION_STATUS
    assert result.outcome is ComponentOutcome.PASS
    assert result.evidence == "All 3 exact domain-outcome expectations matched."


@pytest.mark.parametrize(
    ("observed", "reason_fragment"),
    [
        ((("result.status", "ok"),), "observed 'ok', expected 'not_applicable'"),
        ((), "missing result.status"),
    ],
)
def test_domain_outcomes_detect_mismatch_and_missing_fields(
    observed: tuple[tuple[str, str], ...],
    reason_fragment: str,
) -> None:
    """A mutated or absent native outcome fails the execution-status component."""
    result = evaluate_domain_outcomes(
        (DomainOutcomeExpectation(field_path="result.status", expected_value="not_applicable"),),
        _observation(mode=ExecutionMode.DETERMINISTIC_NO_LLM, domain_outcomes=observed),
    )

    assert result.outcome is ComponentOutcome.FAIL
    assert result.failure_reason is not None
    assert reason_fragment in result.failure_reason


def test_domain_outcome_evaluation_preserves_infrastructure_execution_failure() -> None:
    """A dispatch exception remains distinct from a domain-outcome mismatch."""
    result = evaluate_domain_outcomes(
        (DomainOutcomeExpectation(field_path="result.status", expected_value="ok"),),
        _observation(mode=ExecutionMode.DETERMINISTIC_NO_LLM),
        execution_failure="Production dispatch raised RuntimeError.",
    )

    assert result.outcome is ComponentOutcome.FAIL
    assert result.failure_reason == "Production dispatch raised RuntimeError."


def _numerical(
    expectations: tuple[NumericalExpectation, ...],
    observation: Observation,
    *,
    fixture_status: ComponentResult | None = None,
    execution_status: ComponentResult | None = None,
) -> ComponentResult:
    passing_fixture, passing_execution = _pass_statuses()
    return evaluate_numerical_correctness(
        expectations,
        observation,
        fixture_status=fixture_status or passing_fixture,
        execution_status=execution_status or passing_execution,
    )


def test_deterministic_tool_selection_is_not_measured() -> None:
    constraints = ToolConstraints(
        permitted=(ToolName.ANALYZE_MOMENTUM,),
        required=(ToolName.ANALYZE_MOMENTUM,),
    )

    result = evaluate_tool_selection(
        constraints,
        _observation(mode=ExecutionMode.DETERMINISTIC_NO_LLM),
    )

    assert result.kind is ComponentKind.STRATEGY_SELECTION
    assert result.outcome is ComponentOutcome.NOT_MEASURED
    assert result.evidence is not None
    assert "does not measure" in result.evidence


def test_deterministic_graham_method_selection_is_not_measured_when_applicable() -> None:
    constraints = GrahamMethodConstraints(
        permitted=(GrahamMethod.GRAHAM_NUMBER,),
        required=(GrahamMethod.GRAHAM_NUMBER,),
    )

    result = evaluate_graham_method_selection(
        constraints,
        _observation(mode=ExecutionMode.DETERMINISTIC_NO_LLM),
    )

    assert result.outcome is ComponentOutcome.NOT_MEASURED


def test_graham_method_selection_is_not_applicable_without_constraints() -> None:
    result = evaluate_graham_method_selection(
        GrahamMethodConstraints(),
        _observation(mode=ExecutionMode.DETERMINISTIC_NO_LLM),
    )

    assert result.kind is ComponentKind.GRAHAM_METHOD_SELECTION
    assert result.outcome is ComponentOutcome.NOT_APPLICABLE


def test_tool_selection_is_not_applicable_without_constraints() -> None:
    result = evaluate_tool_selection(ToolConstraints(), _observation())

    assert result.kind is ComponentKind.STRATEGY_SELECTION
    assert result.outcome is ComponentOutcome.NOT_APPLICABLE


def test_tool_selection_accepts_one_legitimate_permitted_alternative() -> None:
    constraints = ToolConstraints(
        permitted=(
            ToolName.ANALYZE_MOMENTUM,
            ToolName.ANALYZE_FCF_EARNINGS_GROWTH,
        )
    )

    result = evaluate_tool_selection(
        constraints,
        _observation(tools=(ToolName.ANALYZE_FCF_EARNINGS_GROWTH,)),
    )

    assert result.outcome is ComponentOutcome.PASS


def test_permitted_tool_selection_requires_an_observed_call() -> None:
    result = evaluate_tool_selection(
        ToolConstraints(permitted=(ToolName.ANALYZE_MOMENTUM,)),
        _observation(),
    )

    assert result.outcome is ComponentOutcome.FAIL
    assert result.failure_reason == "No permitted selection was observed for tools."


def test_tool_selection_accepts_repeated_permitted_calls() -> None:
    constraints = ToolConstraints(permitted=(ToolName.ANALYZE_MOMENTUM,))

    result = evaluate_tool_selection(
        constraints,
        _observation(tools=(ToolName.ANALYZE_MOMENTUM, ToolName.ANALYZE_MOMENTUM)),
    )

    assert result.outcome is ComponentOutcome.PASS


def test_tool_selection_fails_when_required_tool_is_missing() -> None:
    constraints = ToolConstraints(
        permitted=(ToolName.ANALYZE_MOMENTUM,),
        required=(ToolName.ANALYZE_MOMENTUM,),
    )

    result = evaluate_tool_selection(constraints, _observation())

    assert result.outcome is ComponentOutcome.FAIL
    assert result.failure_reason is not None
    assert "Missing required tools" in result.failure_reason


def test_tool_selection_rejects_forbidden_tool() -> None:
    constraints = ToolConstraints(forbidden=(ToolName.ANALYZE_GRAHAM_GROWTH_VALUE,))

    result = evaluate_tool_selection(
        constraints,
        _observation(tools=(ToolName.ANALYZE_GRAHAM_GROWTH_VALUE,)),
    )

    assert result.outcome is ComponentOutcome.FAIL
    assert result.failure_reason is not None
    assert "forbidden tools" in result.failure_reason


def test_tool_selection_rejects_unpermitted_tool() -> None:
    constraints = ToolConstraints(permitted=(ToolName.ANALYZE_MOMENTUM,))

    result = evaluate_tool_selection(
        constraints,
        _observation(tools=(ToolName.ANALYZE_GRAHAM_NUMBER,)),
    )

    assert result.outcome is ComponentOutcome.FAIL
    assert result.failure_reason is not None
    assert "unpermitted tools" in result.failure_reason


def test_graham_method_failure_is_independent_of_correct_tool_selection() -> None:
    observation = _observation(
        tools=(ToolName.ANALYZE_GRAHAM_NUMBER,),
        methods=(GrahamMethod.GRAHAM_GROWTH_VALUE,),
    )
    tool_result = evaluate_tool_selection(
        ToolConstraints(
            permitted=(ToolName.ANALYZE_GRAHAM_NUMBER,),
            required=(ToolName.ANALYZE_GRAHAM_NUMBER,),
        ),
        observation,
    )
    method_result = evaluate_graham_method_selection(
        GrahamMethodConstraints(
            permitted=(GrahamMethod.GRAHAM_NUMBER,),
            required=(GrahamMethod.GRAHAM_NUMBER,),
        ),
        observation,
    )

    assert tool_result.outcome is ComponentOutcome.PASS
    assert method_result.outcome is ComponentOutcome.FAIL
    assert method_result.failure_reason is not None
    assert "Missing required Graham methods" in method_result.failure_reason


def test_behavior_constraints_accept_permitted_required_behavior() -> None:
    constraints = BehaviorConstraints(
        permitted=("retain_provenance", "use_fixture_data"),
        required=("use_fixture_data",),
    )

    result = evaluate_behavior_constraints(
        constraints,
        (" use_fixture_data ",),
        component_kind=ComponentKind.FIXTURE_STATUS,
    )

    assert result.kind is ComponentKind.FIXTURE_STATUS
    assert result.outcome is ComponentOutcome.PASS


@pytest.mark.parametrize(
    ("constraints", "observed", "reason_fragment"),
    [
        (BehaviorConstraints(forbidden=("live_fallback",)), ("live_fallback",), "forbidden behaviors"),
        (
            BehaviorConstraints(permitted=("retain_provenance",), required=("retain_provenance",)),
            (),
            "Missing required behaviors",
        ),
        (
            BehaviorConstraints(permitted=("use_fixture_data",)),
            ("invent_data",),
            "unpermitted behaviors",
        ),
    ],
)
def test_behavior_constraint_failures_are_classified_explicitly(
    constraints: BehaviorConstraints,
    observed: tuple[str, ...],
    reason_fragment: str,
) -> None:
    result = evaluate_behavior_constraints(
        constraints,
        observed,
        component_kind=ComponentKind.EXECUTION_STATUS,
    )

    assert result.kind is ComponentKind.EXECUTION_STATUS
    assert result.outcome is ComponentOutcome.FAIL
    assert result.failure_reason is not None
    assert reason_fragment in result.failure_reason


def test_behavior_constraints_reject_blank_observed_identifier_as_failure() -> None:
    result = evaluate_behavior_constraints(
        BehaviorConstraints(permitted=("use_fixture_data",)),
        (" ",),
        component_kind=ComponentKind.FIXTURE_STATUS,
    )

    assert result.outcome is ComponentOutcome.FAIL
    assert result.failure_reason == "Observed behavior identifiers must not be blank."


def test_behavior_component_is_not_applicable_without_constraints() -> None:
    result = evaluate_behavior_constraints(
        BehaviorConstraints(),
        (),
        component_kind=ComponentKind.EXECUTION_STATUS,
    )

    assert result.outcome is ComponentOutcome.NOT_APPLICABLE


def test_behavior_constraints_reject_unrelated_component_category() -> None:
    with pytest.raises(ValueError, match="fixture_status or execution_status"):
        evaluate_behavior_constraints(
            BehaviorConstraints(permitted=("use_fixture_data",)),
            ("use_fixture_data",),
            component_kind=ComponentKind.NUMERICAL_CORRECTNESS,
        )


@pytest.mark.parametrize(
    ("evaluator", "kind"),
    [
        (evaluate_fixture_status, ComponentKind.FIXTURE_STATUS),
        (evaluate_execution_status, ComponentKind.EXECUTION_STATUS),
    ],
)
def test_upstream_status_evaluators_separate_pass_and_failure(
    evaluator: object,
    kind: ComponentKind,
) -> None:
    assert callable(evaluator)
    passing = evaluator()
    failing = evaluator("provider fixture missing required EPS")

    assert passing == ComponentResult(kind=kind, outcome=ComponentOutcome.PASS, evidence=passing.evidence)
    assert failing.kind is kind
    assert failing.outcome is ComponentOutcome.FAIL
    assert failing.failure_reason == "provider fixture missing required EPS"


@pytest.mark.parametrize("evaluator", [evaluate_fixture_status, evaluate_execution_status])
def test_upstream_status_rejects_blank_failure_reason(evaluator: object) -> None:
    assert callable(evaluator)
    with pytest.raises(ValueError, match="failure_reason must not be blank"):
        evaluator(" ")


def test_numerical_absolute_tolerance_includes_boundary() -> None:
    expectation = NumericalExpectation(
        field_path="result.value",
        expected_value=100.0,
        absolute_tolerance=1.0,
    )

    result = _numerical((expectation,), _observation(numbers=(("result.value", 101.0),)))

    assert result.outcome is ComponentOutcome.PASS


def test_numerical_absolute_tolerance_rejects_just_outside_boundary() -> None:
    expectation = NumericalExpectation(
        field_path="result.value",
        expected_value=100.0,
        absolute_tolerance=1.0,
    )

    result = _numerical((expectation,), _observation(numbers=(("result.value", 101.0000001),)))

    assert result.outcome is ComponentOutcome.FAIL
    assert result.failure_reason is not None
    assert "exceeds tolerance" in result.failure_reason


def test_numerical_relative_tolerance_uses_expected_value_boundary() -> None:
    expectation = NumericalExpectation(
        field_path="result.value",
        expected_value=200.0,
        relative_tolerance=0.01,
    )

    passing = _numerical((expectation,), _observation(numbers=(("result.value", 202.0),)))
    failing = _numerical((expectation,), _observation(numbers=(("result.value", 202.000001),)))

    assert passing.outcome is ComponentOutcome.PASS
    assert failing.outcome is ComponentOutcome.FAIL


def test_numerical_comparison_uses_larger_configured_tolerance() -> None:
    expectation = NumericalExpectation(
        field_path="result.value",
        expected_value=100.0,
        absolute_tolerance=0.5,
        relative_tolerance=0.01,
    )

    result = _numerical((expectation,), _observation(numbers=(("result.value", 101.0),)))

    assert result.outcome is ComponentOutcome.PASS


def test_numerical_exact_tolerance_requires_exact_value() -> None:
    expectation = NumericalExpectation(
        field_path="result.value",
        expected_value=1.0,
        absolute_tolerance=0.0,
    )

    passing = _numerical((expectation,), _observation(numbers=(("result.value", 1.0),)))
    failing = _numerical((expectation,), _observation(numbers=(("result.value", 1.0000000001),)))

    assert passing.outcome is ComponentOutcome.PASS
    assert failing.outcome is ComponentOutcome.FAIL


def test_numerical_missing_expected_path_is_numerical_failure() -> None:
    expectation = NumericalExpectation(
        field_path="result.required",
        expected_value=1.0,
        absolute_tolerance=0.0,
    )

    result = _numerical((expectation,), _observation(numbers=(("result.other", 1.0),)))

    assert result.kind is ComponentKind.NUMERICAL_CORRECTNESS
    assert result.outcome is ComponentOutcome.FAIL
    assert result.failure_reason is not None
    assert "missing result.required" in result.failure_reason


def test_numerical_comparison_ignores_unaddressed_extra_observations() -> None:
    expectation = NumericalExpectation(
        field_path="result.required",
        expected_value=1.0,
        absolute_tolerance=0.0,
    )

    result = _numerical(
        (expectation,),
        _observation(numbers=(("result.required", 1.0), ("result.extra", 99.0))),
    )

    assert result.outcome is ComponentOutcome.PASS


def test_numerical_component_is_not_applicable_without_expectations() -> None:
    result = _numerical((), _observation())

    assert result.outcome is ComponentOutcome.NOT_APPLICABLE


def test_fixture_failure_is_not_reclassified_as_numerical_failure() -> None:
    fixture_status = evaluate_fixture_status("fixture lacks required annual facts")
    expectation = NumericalExpectation(
        field_path="result.value",
        expected_value=1.0,
        absolute_tolerance=0.0,
    )

    result = _numerical(
        (expectation,),
        _observation(),
        fixture_status=fixture_status,
    )

    assert fixture_status.outcome is ComponentOutcome.FAIL
    assert result.outcome is ComponentOutcome.NOT_APPLICABLE
    assert result.failure_reason is None
    assert result.evidence is not None
    assert "fixture_status failed" in result.evidence


def test_execution_failure_is_not_reclassified_as_numerical_failure() -> None:
    execution_status = evaluate_execution_status("strategy raised an unexpected error")
    expectation = NumericalExpectation(
        field_path="result.value",
        expected_value=1.0,
        absolute_tolerance=0.0,
    )

    result = _numerical(
        (expectation,),
        _observation(),
        execution_status=execution_status,
    )

    assert execution_status.outcome is ComponentOutcome.FAIL
    assert result.outcome is ComponentOutcome.NOT_APPLICABLE
    assert result.evidence is not None
    assert "execution_status failed" in result.evidence


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (
            ComponentResult(kind=ComponentKind.EXECUTION_STATUS, outcome=ComponentOutcome.PASS),
            "expected a fixture_status component result",
        ),
        (
            ComponentResult(
                kind=ComponentKind.FIXTURE_STATUS,
                outcome=ComponentOutcome.NOT_APPLICABLE,
                evidence="not applicable",
            ),
            "fixture_status must have a pass or fail outcome",
        ),
    ],
)
def test_numerical_evaluator_rejects_invalid_fixture_status(status: ComponentResult, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        evaluate_numerical_correctness(
            (),
            _observation(),
            fixture_status=status,
            execution_status=evaluate_execution_status(),
        )
