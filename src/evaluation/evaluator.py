"""Pure component evaluators for Golden-Suite observations."""

from __future__ import annotations

from src.evaluation.models import (
    BehaviorConstraints,
    ComponentKind,
    ComponentOutcome,
    ComponentResult,
    DomainOutcomeExpectation,
    ExecutionMode,
    GrahamMethod,
    GrahamMethodConstraints,
    NumericalExpectation,
    Observation,
    ToolConstraints,
    ToolName,
)

type ConstraintValue = ToolName | GrahamMethod | str


def _display(values: set[ConstraintValue]) -> str:
    """Return deterministic human-readable constraint evidence."""
    return ", ".join(sorted(str(value) for value in values)) or "none"


def _evaluate_constraints(  # noqa: PLR0913
    *,
    kind: ComponentKind,
    label: str,
    observed: tuple[ConstraintValue, ...],
    permitted: tuple[ConstraintValue, ...],
    required: tuple[ConstraintValue, ...],
    forbidden: tuple[ConstraintValue, ...],
) -> ComponentResult:
    """Evaluate one required/permitted/forbidden constraint set."""
    observed_values = set(observed)
    permitted_values = set(permitted)
    required_values = set(required)
    forbidden_values = set(forbidden)
    evidence = f"Observed {label}: {_display(observed_values)}."

    forbidden_observed = observed_values & forbidden_values
    if forbidden_observed:
        return ComponentResult(
            kind=kind,
            outcome=ComponentOutcome.FAIL,
            failure_reason=f"Observed forbidden {label}: {_display(forbidden_observed)}.",
            evidence=evidence,
        )

    missing_required = required_values - observed_values
    if missing_required:
        return ComponentResult(
            kind=kind,
            outcome=ComponentOutcome.FAIL,
            failure_reason=f"Missing required {label}: {_display(missing_required)}.",
            evidence=evidence,
        )

    unpermitted_observed = observed_values - permitted_values if permitted_values else set()
    if unpermitted_observed:
        return ComponentResult(
            kind=kind,
            outcome=ComponentOutcome.FAIL,
            failure_reason=f"Observed unpermitted {label}: {_display(unpermitted_observed)}.",
            evidence=evidence,
        )

    if permitted_values and not observed_values:
        return ComponentResult(
            kind=kind,
            outcome=ComponentOutcome.FAIL,
            failure_reason=f"No permitted selection was observed for {label}.",
            evidence=evidence,
        )

    return ComponentResult(kind=kind, outcome=ComponentOutcome.PASS, evidence=evidence)


def evaluate_tool_selection(constraints: ToolConstraints, observation: Observation) -> ComponentResult:
    """Evaluate observed production-tool selection independently of results."""
    if not (constraints.permitted or constraints.required or constraints.forbidden):
        return ComponentResult(
            kind=ComponentKind.STRATEGY_SELECTION,
            outcome=ComponentOutcome.NOT_APPLICABLE,
            evidence="This case defines no tool-selection constraints.",
        )
    if observation.execution_mode is ExecutionMode.DETERMINISTIC_NO_LLM:
        return ComponentResult(
            kind=ComponentKind.STRATEGY_SELECTION,
            outcome=ComponentOutcome.NOT_MEASURED,
            evidence="Deterministic/no-LLM execution does not measure model tool selection.",
        )
    return _evaluate_constraints(
        kind=ComponentKind.STRATEGY_SELECTION,
        label="tools",
        observed=tuple(call.tool_name for call in observation.tool_calls),
        permitted=constraints.permitted,
        required=constraints.required,
        forbidden=constraints.forbidden,
    )


def evaluate_graham_method_selection(
    constraints: GrahamMethodConstraints,
    observation: Observation,
) -> ComponentResult:
    """Evaluate Graham-method selection separately from broad tool selection."""
    if not (constraints.permitted or constraints.required or constraints.forbidden):
        return ComponentResult(
            kind=ComponentKind.GRAHAM_METHOD_SELECTION,
            outcome=ComponentOutcome.NOT_APPLICABLE,
            evidence="This case defines no Graham-method constraints.",
        )
    if observation.execution_mode is ExecutionMode.DETERMINISTIC_NO_LLM:
        return ComponentResult(
            kind=ComponentKind.GRAHAM_METHOD_SELECTION,
            outcome=ComponentOutcome.NOT_MEASURED,
            evidence="Deterministic/no-LLM execution does not measure model Graham-method selection.",
        )
    return _evaluate_constraints(
        kind=ComponentKind.GRAHAM_METHOD_SELECTION,
        label="Graham methods",
        observed=tuple(item.method for item in observation.graham_methods),
        permitted=constraints.permitted,
        required=constraints.required,
        forbidden=constraints.forbidden,
    )


def evaluate_behavior_constraints(
    constraints: BehaviorConstraints,
    observed_behaviors: tuple[str, ...],
    *,
    component_kind: ComponentKind,
) -> ComponentResult:
    """Evaluate named behaviors under a fixture or execution failure category."""
    if component_kind not in (ComponentKind.FIXTURE_STATUS, ComponentKind.EXECUTION_STATUS):
        raise ValueError("behavior constraints must be classified as fixture_status or execution_status")
    if not (constraints.permitted or constraints.required or constraints.forbidden):
        return ComponentResult(
            kind=component_kind,
            outcome=ComponentOutcome.NOT_APPLICABLE,
            evidence="This case defines no named behavior constraints.",
        )
    normalized = tuple(value.strip() for value in observed_behaviors)
    if any(not value for value in normalized):
        return ComponentResult(
            kind=component_kind,
            outcome=ComponentOutcome.FAIL,
            failure_reason="Observed behavior identifiers must not be blank.",
            evidence="Observed behaviors contained a blank identifier.",
        )
    return _evaluate_constraints(
        kind=component_kind,
        label="behaviors",
        observed=normalized,
        permitted=constraints.permitted,
        required=constraints.required,
        forbidden=constraints.forbidden,
    )


def _evaluate_status(kind: ComponentKind, failure_reason: str | None) -> ComponentResult:
    """Build one pass/fail upstream status component."""
    label = "Fixture/data" if kind is ComponentKind.FIXTURE_STATUS else "Execution"
    if failure_reason is None:
        return ComponentResult(
            kind=kind,
            outcome=ComponentOutcome.PASS,
            evidence=f"{label} evaluation completed without a reported failure.",
        )
    normalized = failure_reason.strip()
    if not normalized:
        raise ValueError("failure_reason must not be blank")
    return ComponentResult(
        kind=kind,
        outcome=ComponentOutcome.FAIL,
        failure_reason=normalized,
    )


def evaluate_fixture_status(failure_reason: str | None = None) -> ComponentResult:
    """Classify fixture and input-data readiness separately from execution."""
    return _evaluate_status(ComponentKind.FIXTURE_STATUS, failure_reason)


def evaluate_execution_status(failure_reason: str | None = None) -> ComponentResult:
    """Classify non-fixture execution readiness separately from numerical output."""
    return _evaluate_status(ComponentKind.EXECUTION_STATUS, failure_reason)


def evaluate_domain_outcomes(
    expectations: tuple[DomainOutcomeExpectation, ...],
    observation: Observation,
    *,
    execution_failure: str | None = None,
) -> ComponentResult:
    """Evaluate exact native-result outcomes without treating them as infrastructure failures."""
    if execution_failure is not None:
        return evaluate_execution_status(execution_failure)
    if not expectations:
        return ComponentResult(
            kind=ComponentKind.EXECUTION_STATUS,
            outcome=ComponentOutcome.PASS,
            evidence="Execution completed; this case defines no exact domain-outcome expectations.",
        )

    observed_by_path = {item.field_path: item.value for item in observation.domain_outcome_observations}
    failures: list[str] = []
    for expectation in expectations:
        if expectation.field_path not in observed_by_path:
            failures.append(f"missing {expectation.field_path}")
            continue
        observed = observed_by_path[expectation.field_path]
        if observed != expectation.expected_value:
            failures.append(f"{expectation.field_path}: observed {observed!r}, expected {expectation.expected_value!r}")
    if failures:
        return ComponentResult(
            kind=ComponentKind.EXECUTION_STATUS,
            outcome=ComponentOutcome.FAIL,
            failure_reason="Domain-outcome comparison failed: " + "; ".join(failures) + ".",
        )
    return ComponentResult(
        kind=ComponentKind.EXECUTION_STATUS,
        outcome=ComponentOutcome.PASS,
        evidence=f"All {len(expectations)} exact domain-outcome expectations matched.",
    )


def _require_upstream_status(result: ComponentResult, kind: ComponentKind) -> None:
    """Validate a status component supplied to numerical evaluation."""
    if result.kind is not kind:
        raise ValueError(f"expected a {kind.value} component result")
    if result.outcome not in (ComponentOutcome.PASS, ComponentOutcome.FAIL):
        raise ValueError(f"{kind.value} must have a pass or fail outcome")


def _allowed_difference(expectation: NumericalExpectation) -> float:
    """Return the larger configured absolute or expected-value-relative tolerance."""
    absolute = expectation.absolute_tolerance or 0.0
    relative = (expectation.relative_tolerance or 0.0) * abs(expectation.expected_value)
    return max(absolute, relative)


def evaluate_numerical_correctness(
    expectations: tuple[NumericalExpectation, ...],
    observation: Observation,
    *,
    fixture_status: ComponentResult,
    execution_status: ComponentResult,
) -> ComponentResult:
    """Compare field-addressed values without relabeling upstream failures."""
    _require_upstream_status(fixture_status, ComponentKind.FIXTURE_STATUS)
    _require_upstream_status(execution_status, ComponentKind.EXECUTION_STATUS)
    if not expectations:
        return ComponentResult(
            kind=ComponentKind.NUMERICAL_CORRECTNESS,
            outcome=ComponentOutcome.NOT_APPLICABLE,
            evidence="This case defines no numerical expectations.",
        )
    for status in (fixture_status, execution_status):
        if status.outcome is ComponentOutcome.FAIL:
            return ComponentResult(
                kind=ComponentKind.NUMERICAL_CORRECTNESS,
                outcome=ComponentOutcome.NOT_APPLICABLE,
                evidence=(
                    f"Numerical correctness was not evaluated because {status.kind.value} failed: "
                    f"{status.failure_reason}."
                ),
            )

    observed_by_path = {item.field_path: item.value for item in observation.numerical_observations}
    failures: list[str] = []
    for expectation in expectations:
        observed = observed_by_path.get(expectation.field_path)
        if observed is None:
            failures.append(f"missing {expectation.field_path}")
            continue
        difference = abs(observed - expectation.expected_value)
        allowed = _allowed_difference(expectation)
        if difference > allowed:
            failures.append(
                f"{expectation.field_path}: observed {observed!r}, expected {expectation.expected_value!r}, "
                f"difference {difference!r} exceeds tolerance {allowed!r}"
            )
    if failures:
        return ComponentResult(
            kind=ComponentKind.NUMERICAL_CORRECTNESS,
            outcome=ComponentOutcome.FAIL,
            failure_reason="Numerical comparison failed: " + "; ".join(failures) + ".",
        )
    return ComponentResult(
        kind=ComponentKind.NUMERICAL_CORRECTNESS,
        outcome=ComponentOutcome.PASS,
        evidence=f"All {len(expectations)} numerical expectations matched within tolerance.",
    )
