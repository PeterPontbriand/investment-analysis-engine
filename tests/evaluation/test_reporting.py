"""Focused tests for Golden-Suite case aggregation and report serialization."""

import json
from datetime import UTC, datetime
from math import inf, nan

import pytest
from pydantic import ValidationError

from src.evaluation.models import (
    ComponentKind,
    ComponentOutcome,
    ComponentResult,
    ExecutionMode,
)
from src.evaluation.reporting import (
    CaseEvaluationResult,
    CaseOutcome,
    ComponentMetric,
    EvaluationReport,
    ModelConfiguration,
    ModelSetting,
    build_case_result,
    build_evaluation_report,
)

EXECUTED_AT = datetime(2026, 8, 31, 16, 0, tzinfo=UTC)
DETERMINISTIC_REQUIRED = (
    ComponentKind.FIXTURE_STATUS,
    ComponentKind.EXECUTION_STATUS,
    ComponentKind.NUMERICAL_CORRECTNESS,
)


def _component(
    kind: ComponentKind,
    outcome: ComponentOutcome,
    *,
    reason: str | None = None,
) -> ComponentResult:
    evidence = (
        f"{kind.value} is {outcome.value}."
        if outcome in (ComponentOutcome.NOT_APPLICABLE, ComponentOutcome.NOT_MEASURED)
        else None
    )
    return ComponentResult(
        kind=kind,
        outcome=outcome,
        failure_reason=reason,
        evidence=evidence,
    )


def _deterministic_components(
    numerical_outcome: ComponentOutcome = ComponentOutcome.PASS,
) -> tuple[ComponentResult, ...]:
    numerical_reason = "observed value exceeded tolerance" if numerical_outcome is ComponentOutcome.FAIL else None
    return (
        _component(ComponentKind.STRATEGY_SELECTION, ComponentOutcome.NOT_MEASURED),
        _component(ComponentKind.GRAHAM_METHOD_SELECTION, ComponentOutcome.NOT_APPLICABLE),
        _component(ComponentKind.NUMERICAL_CORRECTNESS, numerical_outcome, reason=numerical_reason),
        _component(ComponentKind.FIXTURE_STATUS, ComponentOutcome.PASS),
        _component(ComponentKind.EXECUTION_STATUS, ComponentOutcome.PASS),
    )


def _case(
    case_id: str,
    numerical_outcome: ComponentOutcome = ComponentOutcome.PASS,
) -> CaseEvaluationResult:
    return build_case_result(
        case_id=case_id,
        components=_deterministic_components(numerical_outcome),
        required_component_kinds=DETERMINISTIC_REQUIRED,
        trajectory_id=f"trajectory-{case_id}",
    )


def _report(
    case_results: tuple[CaseEvaluationResult, ...],
) -> EvaluationReport:
    return build_evaluation_report(
        suite_id="step-2.5-golden",
        suite_version="1",
        fixture_set_version="step-2.5-b2-v1",
        execution_mode=ExecutionMode.DETERMINISTIC_NO_LLM,
        executed_at=EXECUTED_AT,
        required_component_kinds=DETERMINISTIC_REQUIRED,
        case_results=case_results,
        run_id="run-001",
    )


def _metric(report: EvaluationReport, kind: ComponentKind) -> ComponentMetric:
    return next(metric for metric in report.component_metrics if metric.kind is kind)


def test_case_aggregation_fails_only_when_required_component_fails() -> None:
    passing = _case("passing")
    failing = _case("failing", ComponentOutcome.FAIL)

    assert passing.outcome is CaseOutcome.PASS
    assert passing.failure_reasons == ()
    assert failing.outcome is CaseOutcome.FAIL
    assert failing.failure_reasons == ("numerical_correctness: observed value exceeded tolerance",)


def test_nonrequired_component_failure_remains_distinct_from_overall_case() -> None:
    result = build_case_result(
        case_id="selection-not-required",
        components=(
            _component(
                ComponentKind.STRATEGY_SELECTION,
                ComponentOutcome.FAIL,
                reason="wrong strategy",
            ),
            _component(ComponentKind.NUMERICAL_CORRECTNESS, ComponentOutcome.PASS),
        ),
        required_component_kinds=(ComponentKind.NUMERICAL_CORRECTNESS,),
    )

    assert result.outcome is CaseOutcome.PASS
    assert result.failure_reasons == ()
    assert (
        next(component for component in result.components if component.kind is ComponentKind.STRATEGY_SELECTION).outcome
        is ComponentOutcome.FAIL
    )


def test_case_aggregation_rejects_missing_required_component() -> None:
    with pytest.raises(ValueError, match="lacks required components: numerical_correctness"):
        build_case_result(
            case_id="missing-numerical",
            components=(_component(ComponentKind.FIXTURE_STATUS, ComponentOutcome.PASS),),
            required_component_kinds=(ComponentKind.NUMERICAL_CORRECTNESS,),
        )


def test_mixed_report_uses_executed_case_denominator_and_preserves_skips() -> None:
    skipped = build_case_result(
        case_id="skipped",
        components=(),
        required_component_kinds=DETERMINISTIC_REQUIRED,
        skip_reason="fixture intentionally unavailable on this platform",
    )
    report = _report((_case("pass"), _case("fail", ComponentOutcome.FAIL), skipped))

    assert report.total_cases == 3
    assert report.executed_cases == 2
    assert report.passed_cases == 1
    assert report.failed_cases == 1
    assert report.skipped_cases == 1
    assert report.overall_pass_rate == 0.5


def test_component_denominators_exclude_not_measured_and_not_applicable() -> None:
    report = _report((_case("pass"), _case("fail", ComponentOutcome.FAIL)))
    strategy = _metric(report, ComponentKind.STRATEGY_SELECTION)
    graham = _metric(report, ComponentKind.GRAHAM_METHOD_SELECTION)
    numerical = _metric(report, ComponentKind.NUMERICAL_CORRECTNESS)
    fixture = _metric(report, ComponentKind.FIXTURE_STATUS)

    assert (strategy.not_measured, strategy.measured_applicable, strategy.pass_rate) == (2, 0, None)
    assert (graham.not_applicable, graham.measured_applicable, graham.pass_rate) == (2, 0, None)
    assert (numerical.passed, numerical.failed, numerical.measured_applicable, numerical.pass_rate) == (1, 1, 2, 0.5)
    assert (fixture.passed, fixture.failed, fixture.pass_rate) == (2, 0, 1.0)


def test_fixture_and_execution_failures_remain_separate_categories() -> None:
    case = build_case_result(
        case_id="upstream-failures",
        components=(
            _component(ComponentKind.STRATEGY_SELECTION, ComponentOutcome.NOT_MEASURED),
            _component(ComponentKind.GRAHAM_METHOD_SELECTION, ComponentOutcome.NOT_APPLICABLE),
            _component(ComponentKind.NUMERICAL_CORRECTNESS, ComponentOutcome.NOT_APPLICABLE),
            _component(
                ComponentKind.FIXTURE_STATUS,
                ComponentOutcome.FAIL,
                reason="required fixture fact missing",
            ),
            _component(
                ComponentKind.EXECUTION_STATUS,
                ComponentOutcome.FAIL,
                reason="strategy execution aborted",
            ),
        ),
        required_component_kinds=DETERMINISTIC_REQUIRED,
    )
    report = _report((case,))

    assert case.outcome is CaseOutcome.FAIL
    assert case.failure_reasons == (
        "execution_status: strategy execution aborted",
        "fixture_status: required fixture fact missing",
    )
    assert (
        _metric(report, ComponentKind.FIXTURE_STATUS).failed,
        _metric(report, ComponentKind.EXECUTION_STATUS).failed,
    ) == (
        1,
        1,
    )
    assert _metric(report, ComponentKind.NUMERICAL_CORRECTNESS).not_applicable == 1


def test_zero_executed_case_and_component_denominators_serialize_as_null() -> None:
    skipped = build_case_result(
        case_id="skipped",
        components=(),
        required_component_kinds=DETERMINISTIC_REQUIRED,
        skip_reason="not executed",
    )
    report = _report((skipped,))

    assert report.executed_cases == 0
    assert report.overall_pass_rate is None
    assert all(metric.measured_applicable == 0 and metric.pass_rate is None for metric in report.component_metrics)
    payload = json.loads(report.model_dump_json())
    assert payload["overall_pass_rate"] is None


def test_report_canonicalizes_case_component_metric_and_required_order() -> None:
    report = build_evaluation_report(
        suite_id="suite",
        suite_version="1",
        fixture_set_version="fixtures-1",
        execution_mode=ExecutionMode.DETERMINISTIC_NO_LLM,
        executed_at=EXECUTED_AT,
        required_component_kinds=tuple(reversed(DETERMINISTIC_REQUIRED)),
        case_results=(_case("z-case"), _case("a-case")),
    )

    assert tuple(case.case_id for case in report.case_results) == ("a-case", "z-case")
    assert tuple(metric.kind.value for metric in report.component_metrics) == tuple(
        sorted(kind.value for kind in ComponentKind)
    )
    assert report.required_component_kinds == tuple(sorted(DETERMINISTIC_REQUIRED, key=lambda kind: kind.value))
    assert tuple(component.kind.value for component in report.case_results[0].components) == tuple(
        sorted(kind.value for kind in ComponentKind)
    )


def test_semantically_reordered_inputs_serialize_identically() -> None:
    first = _report((_case("z-case"), _case("a-case")))
    second = _report((_case("a-case"), _case("z-case")))

    assert first.model_dump_json() == second.model_dump_json()


def test_real_model_configuration_is_typed_canonical_and_round_trips() -> None:
    required = (ComponentKind.STRATEGY_SELECTION,)
    case = build_case_result(
        case_id="empirical",
        components=(_component(ComponentKind.STRATEGY_SELECTION, ComponentOutcome.PASS),),
        required_component_kinds=required,
        trajectory_id="trajectory-empirical",
    )
    configuration = ModelConfiguration(
        provider_id="ollama",
        model_id="local-model",
        settings=(
            ModelSetting(name="temperature", value=0.0),
            ModelSetting(name="seed", value=42),
            ModelSetting(name="stream", value=False),
        ),
    )
    report = build_evaluation_report(
        suite_id="suite",
        suite_version="1",
        fixture_set_version="fixtures-1",
        execution_mode=ExecutionMode.REAL_LOCAL_OLLAMA,
        executed_at=EXECUTED_AT,
        required_component_kinds=required,
        case_results=(case,),
        model_configuration=configuration,
        run_id="empirical-run",
    )
    serialized = report.model_dump_json()

    assert report.model_configuration is not None
    assert tuple(setting.name for setting in report.model_configuration.settings) == (
        "seed",
        "stream",
        "temperature",
    )
    assert EvaluationReport.model_validate_json(serialized) == report
    assert EvaluationReport.model_validate_json(serialized).model_dump_json() == serialized
    assert "NaN" not in serialized
    assert "Infinity" not in serialized


@pytest.mark.parametrize("value", [inf, -inf, nan])
def test_model_settings_reject_nonfinite_numbers(value: float) -> None:
    with pytest.raises(ValidationError):
        ModelSetting(name="temperature", value=value)


@pytest.mark.parametrize("value", [inf, -inf, nan])
def test_report_rejects_nonfinite_aggregate_rate(value: float) -> None:
    payload = _report((_case("pass"),)).model_dump(mode="python")
    payload["overall_pass_rate"] = value

    with pytest.raises(ValidationError):
        EvaluationReport.model_validate(payload)


def test_deterministic_report_rejects_model_configuration() -> None:
    with pytest.raises(ValidationError, match="must not contain model_configuration"):
        build_evaluation_report(
            suite_id="suite",
            suite_version="1",
            fixture_set_version="fixtures-1",
            execution_mode=ExecutionMode.DETERMINISTIC_NO_LLM,
            executed_at=EXECUTED_AT,
            required_component_kinds=DETERMINISTIC_REQUIRED,
            case_results=(_case("pass"),),
            model_configuration=ModelConfiguration(provider_id="ollama", model_id="model"),
        )


def test_real_model_report_requires_configuration() -> None:
    case = build_case_result(
        case_id="empirical",
        components=(_component(ComponentKind.STRATEGY_SELECTION, ComponentOutcome.PASS),),
        required_component_kinds=(ComponentKind.STRATEGY_SELECTION,),
    )

    with pytest.raises(ValidationError, match="require model_configuration"):
        build_evaluation_report(
            suite_id="suite",
            suite_version="1",
            fixture_set_version="fixtures-1",
            execution_mode=ExecutionMode.REAL_LOCAL_OLLAMA,
            executed_at=EXECUTED_AT,
            required_component_kinds=(ComponentKind.STRATEGY_SELECTION,),
            case_results=(case,),
        )


def test_deterministic_report_rejects_fabricated_selection_pass() -> None:
    case = build_case_result(
        case_id="fabricated-selection",
        components=(
            _component(ComponentKind.STRATEGY_SELECTION, ComponentOutcome.PASS),
            _component(ComponentKind.FIXTURE_STATUS, ComponentOutcome.PASS),
        ),
        required_component_kinds=(ComponentKind.FIXTURE_STATUS,),
    )

    with pytest.raises(ValidationError, match="must not be scored as pass or fail"):
        build_evaluation_report(
            suite_id="suite",
            suite_version="1",
            fixture_set_version="fixtures-1",
            execution_mode=ExecutionMode.DETERMINISTIC_NO_LLM,
            executed_at=EXECUTED_AT,
            required_component_kinds=(ComponentKind.FIXTURE_STATUS,),
            case_results=(case,),
        )


def test_deterministic_report_rejects_selection_as_required_criterion() -> None:
    case = build_case_result(
        case_id="unmeasured-selection",
        components=(_component(ComponentKind.STRATEGY_SELECTION, ComponentOutcome.NOT_MEASURED),),
        required_component_kinds=(ComponentKind.STRATEGY_SELECTION,),
    )

    with pytest.raises(ValidationError, match="must not require unmeasured selection"):
        build_evaluation_report(
            suite_id="suite",
            suite_version="1",
            fixture_set_version="fixtures-1",
            execution_mode=ExecutionMode.DETERMINISTIC_NO_LLM,
            executed_at=EXECUTED_AT,
            required_component_kinds=(ComponentKind.STRATEGY_SELECTION,),
            case_results=(case,),
        )


def test_report_rejects_naive_execution_timestamp() -> None:
    with pytest.raises(ValidationError, match="executed_at must be timezone-aware"):
        build_evaluation_report(
            suite_id="suite",
            suite_version="1",
            fixture_set_version="fixtures-1",
            execution_mode=ExecutionMode.DETERMINISTIC_NO_LLM,
            executed_at=datetime(2026, 8, 31, 16, 0),
            required_component_kinds=DETERMINISTIC_REQUIRED,
            case_results=(_case("pass"),),
        )


def test_report_rejects_tampered_case_counts_and_component_metrics() -> None:
    report = _report((_case("pass"),))
    count_payload = report.model_dump(mode="python")
    count_payload["passed_cases"] = 0
    metric_payload = report.model_dump(mode="python")
    metric_payload["component_metrics"][0]["passed"] = 0
    metric_payload["component_metrics"][0]["failed"] = 1
    metric_payload["component_metrics"][0]["pass_rate"] = 0.0

    with pytest.raises(ValidationError, match="case outcome counts"):
        EvaluationReport.model_validate(count_payload)
    with pytest.raises(ValidationError, match="component metrics do not match"):
        EvaluationReport.model_validate(metric_payload)


def test_case_result_rejects_duplicate_component_kinds() -> None:
    with pytest.raises(ValidationError, match="component kinds must be unique"):
        CaseEvaluationResult(
            case_id="duplicate",
            outcome=CaseOutcome.PASS,
            components=(
                _component(ComponentKind.FIXTURE_STATUS, ComponentOutcome.PASS),
                _component(ComponentKind.FIXTURE_STATUS, ComponentOutcome.PASS),
            ),
        )


def test_skipped_case_requires_reason_and_forbids_components() -> None:
    with pytest.raises(ValidationError, match="require a skip_reason"):
        CaseEvaluationResult(case_id="skipped", outcome=CaseOutcome.SKIPPED, components=())
    with pytest.raises(ValidationError, match="must not contain component results"):
        build_case_result(
            case_id="skipped",
            components=(_component(ComponentKind.FIXTURE_STATUS, ComponentOutcome.PASS),),
            required_component_kinds=DETERMINISTIC_REQUIRED,
            skip_reason="not executed",
        )


def test_model_configuration_rejects_duplicate_setting_names() -> None:
    with pytest.raises(ValidationError, match="setting names must be unique"):
        ModelConfiguration(
            provider_id="ollama",
            model_id="model",
            settings=(
                ModelSetting(name="seed", value=1),
                ModelSetting(name=" seed ", value=2),
            ),
        )
