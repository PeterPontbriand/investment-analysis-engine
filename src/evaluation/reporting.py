"""Immutable aggregation and machine-readable reporting for evaluated cases."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from src.evaluation.models import (
    ComponentKind,
    ComponentOutcome,
    ComponentResult,
    ExecutionMode,
)

FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
Rate = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]
SettingValue = StrictStr | StrictBool | StrictInt | FiniteFloat | None


def _normalize_text(value: str, *, label: str) -> str:
    """Normalize one required nonblank text field."""
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} must not be blank")
    return normalized


def _normalize_optional_text(value: str | None, *, label: str) -> str | None:
    """Normalize one optional nonblank text field."""
    if value is None:
        return None
    return _normalize_text(value, label=label)


class CaseOutcome(StrEnum):
    """Aggregate outcome for one requested benchmark case."""

    PASS = "pass"
    FAIL = "fail"
    SKIPPED = "skipped"


class ModelSetting(BaseModel):
    """One deterministic, finite model-configuration setting."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    value: SettingValue

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Normalize and reject a blank setting name."""
        return _normalize_text(value, label="model setting name")


class ModelConfiguration(BaseModel):
    """Explicit provider, model, and settings for empirical execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_id: str
    model_id: str
    settings: tuple[ModelSetting, ...] = ()

    @field_validator("provider_id", "model_id")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        """Normalize and reject blank model configuration identifiers."""
        return _normalize_text(value, label="model configuration identifier")

    @field_validator("settings")
    @classmethod
    def validate_settings(cls, values: tuple[ModelSetting, ...]) -> tuple[ModelSetting, ...]:
        """Reject duplicate names and return deterministic setting order."""
        names = tuple(value.name for value in values)
        if len(names) != len(set(names)):
            raise ValueError("model setting names must be unique")
        return tuple(sorted(values, key=lambda value: value.name))


class CaseEvaluationResult(BaseModel):
    """Auditable component results and aggregate outcome for one case."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    outcome: CaseOutcome
    components: tuple[ComponentResult, ...]
    failure_reasons: tuple[str, ...] = ()
    skip_reason: str | None = None
    trajectory_id: str | None = None

    @field_validator("case_id")
    @classmethod
    def validate_case_id(cls, value: str) -> str:
        """Normalize and reject a blank case identifier."""
        return _normalize_text(value, label="case_id")

    @field_validator("trajectory_id")
    @classmethod
    def validate_trajectory_id(cls, value: str | None) -> str | None:
        """Normalize an optional trajectory identifier."""
        return _normalize_optional_text(value, label="trajectory_id")

    @field_validator("components")
    @classmethod
    def validate_components(cls, values: tuple[ComponentResult, ...]) -> tuple[ComponentResult, ...]:
        """Require unique component kinds and return deterministic order."""
        kinds = tuple(value.kind for value in values)
        if len(kinds) != len(set(kinds)):
            raise ValueError("case component kinds must be unique")
        return tuple(sorted(values, key=lambda value: value.kind.value))

    @field_validator("failure_reasons")
    @classmethod
    def validate_failure_reasons(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Normalize, reject duplicate reasons, and return deterministic order."""
        normalized = tuple(_normalize_text(value, label="failure reason") for value in values)
        if len(normalized) != len(set(normalized)):
            raise ValueError("case failure reasons must be unique")
        return tuple(sorted(normalized))

    @field_validator("skip_reason")
    @classmethod
    def validate_skip_reason(cls, value: str | None) -> str | None:
        """Normalize an optional skip reason."""
        return _normalize_optional_text(value, label="skip_reason")

    @model_validator(mode="after")
    def validate_outcome_state(self) -> CaseEvaluationResult:
        """Enforce coherent pass, fail, and skipped case states."""
        if self.outcome is CaseOutcome.SKIPPED:
            if self.skip_reason is None:
                raise ValueError("skipped cases require a skip_reason")
            if self.components or self.failure_reasons:
                raise ValueError("skipped cases must not contain component results or failure reasons")
            return self
        if self.skip_reason is not None:
            raise ValueError("executed cases must not contain a skip_reason")
        if not self.components:
            raise ValueError("executed cases require component results")
        if self.outcome is CaseOutcome.FAIL:
            if not self.failure_reasons:
                raise ValueError("failed cases require failure reasons")
        elif self.failure_reasons:
            raise ValueError("passing cases must not contain failure reasons")
        return self


class ComponentMetric(BaseModel):
    """Counts and measured/applicable pass rate for one component kind."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: ComponentKind
    total_observations: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    not_applicable: int = Field(ge=0)
    not_measured: int = Field(ge=0)
    measured_applicable: int = Field(ge=0)
    pass_rate: Rate | None

    @model_validator(mode="after")
    def validate_counts(self) -> ComponentMetric:
        """Enforce count and denominator invariants."""
        if self.total_observations != self.passed + self.failed + self.not_applicable + self.not_measured:
            raise ValueError("component outcome counts must sum to total_observations")
        expected_denominator = self.passed + self.failed
        if self.measured_applicable != expected_denominator:
            raise ValueError("measured_applicable must equal passed plus failed")
        expected_rate = None if expected_denominator == 0 else self.passed / expected_denominator
        if self.pass_rate != expected_rate:
            raise ValueError("component pass_rate must equal passed divided by measured_applicable")
        return self


class EvaluationReport(BaseModel):
    """Deterministic machine-readable report for already-evaluated cases."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    suite_id: str
    suite_version: str
    fixture_set_version: str
    execution_mode: ExecutionMode
    executed_at: datetime
    required_component_kinds: tuple[ComponentKind, ...]
    model_configuration: ModelConfiguration | None = None
    run_id: str | None = None
    total_cases: int = Field(ge=0)
    executed_cases: int = Field(ge=0)
    passed_cases: int = Field(ge=0)
    failed_cases: int = Field(ge=0)
    skipped_cases: int = Field(ge=0)
    overall_pass_rate: Rate | None
    component_metrics: tuple[ComponentMetric, ...]
    case_results: tuple[CaseEvaluationResult, ...]

    @field_validator("suite_id", "suite_version", "fixture_set_version")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        """Normalize required report identifiers and versions."""
        return _normalize_text(value, label="report identifier or version")

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str | None) -> str | None:
        """Normalize an optional run identifier."""
        return _normalize_optional_text(value, label="run_id")

    @field_validator("executed_at")
    @classmethod
    def validate_executed_at(cls, value: datetime) -> datetime:
        """Require a timezone-aware execution timestamp."""
        if value.utcoffset() is None:
            raise ValueError("executed_at must be timezone-aware")
        return value

    @field_validator("required_component_kinds")
    @classmethod
    def validate_required_component_kinds(
        cls,
        values: tuple[ComponentKind, ...],
    ) -> tuple[ComponentKind, ...]:
        """Require unique explicit criteria in deterministic order."""
        if not values:
            raise ValueError("at least one required component kind is required")
        if len(values) != len(set(values)):
            raise ValueError("required component kinds must be unique")
        return tuple(sorted(values, key=lambda value: value.value))

    @field_validator("component_metrics")
    @classmethod
    def validate_component_metrics(cls, values: tuple[ComponentMetric, ...]) -> tuple[ComponentMetric, ...]:
        """Require exactly one metric for every component kind."""
        kinds = tuple(value.kind for value in values)
        if len(kinds) != len(set(kinds)):
            raise ValueError("component metric kinds must be unique")
        if set(kinds) != set(ComponentKind):
            raise ValueError("component metrics must include every component kind")
        return tuple(sorted(values, key=lambda value: value.kind.value))

    @field_validator("case_results")
    @classmethod
    def validate_case_results(
        cls,
        values: tuple[CaseEvaluationResult, ...],
    ) -> tuple[CaseEvaluationResult, ...]:
        """Reject duplicate case IDs and return deterministic order."""
        case_ids = tuple(value.case_id for value in values)
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("case result IDs must be unique")
        return tuple(sorted(values, key=lambda value: value.case_id))

    @model_validator(mode="after")
    def validate_report_invariants(self) -> EvaluationReport:  # noqa: PLR0912
        """Enforce mode, case, aggregate, and failure-reason invariants."""
        if self.execution_mode is ExecutionMode.DETERMINISTIC_NO_LLM:
            if self.model_configuration is not None:
                raise ValueError("deterministic_no_llm reports must not contain model_configuration")
            selection_kinds = {
                ComponentKind.STRATEGY_SELECTION,
                ComponentKind.GRAHAM_METHOD_SELECTION,
            }
            if selection_kinds & set(self.required_component_kinds):
                raise ValueError("deterministic_no_llm reports must not require unmeasured selection components")
        elif self.model_configuration is None:
            raise ValueError("real_local_ollama reports require model_configuration")

        expected_total = len(self.case_results)
        expected_passed = sum(case.outcome is CaseOutcome.PASS for case in self.case_results)
        expected_failed = sum(case.outcome is CaseOutcome.FAIL for case in self.case_results)
        expected_skipped = sum(case.outcome is CaseOutcome.SKIPPED for case in self.case_results)
        expected_executed = expected_passed + expected_failed
        expected_rate = None if expected_executed == 0 else expected_passed / expected_executed
        if self.total_cases != expected_total:
            raise ValueError("total_cases must equal the number of case results")
        if self.executed_cases != expected_executed:
            raise ValueError("executed_cases must equal passed_cases plus failed_cases")
        if (self.passed_cases, self.failed_cases, self.skipped_cases) != (
            expected_passed,
            expected_failed,
            expected_skipped,
        ):
            raise ValueError("case outcome counts do not match case results")
        if self.overall_pass_rate != expected_rate:
            raise ValueError("overall_pass_rate must equal passed cases divided by executed cases")

        expected_metrics = tuple(_component_metric(kind, self.case_results) for kind in ComponentKind)
        if self.component_metrics != tuple(sorted(expected_metrics, key=lambda value: value.kind.value)):
            raise ValueError("component metrics do not match case component results")

        required = set(self.required_component_kinds)
        for case in self.case_results:
            if case.outcome is CaseOutcome.SKIPPED:
                continue
            by_kind = {component.kind: component for component in case.components}
            if self.execution_mode is ExecutionMode.DETERMINISTIC_NO_LLM:
                for kind in (ComponentKind.STRATEGY_SELECTION, ComponentKind.GRAHAM_METHOD_SELECTION):
                    selection = by_kind.get(kind)
                    if selection is not None and selection.outcome not in (
                        ComponentOutcome.NOT_APPLICABLE,
                        ComponentOutcome.NOT_MEASURED,
                    ):
                        raise ValueError("deterministic_no_llm selection components must not be scored as pass or fail")
            missing = required - set(by_kind)
            if missing:
                names = ", ".join(sorted(value.value for value in missing))
                raise ValueError(f"executed case {case.case_id!r} lacks required components: {names}")
            expected_reasons = _required_failure_reasons(case.components, self.required_component_kinds)
            expected_outcome = CaseOutcome.FAIL if expected_reasons else CaseOutcome.PASS
            if case.outcome is not expected_outcome or case.failure_reasons != expected_reasons:
                raise ValueError(f"case {case.case_id!r} outcome does not match required component results")
        return self


def _required_failure_reasons(
    components: tuple[ComponentResult, ...],
    required_component_kinds: tuple[ComponentKind, ...],
) -> tuple[str, ...]:
    """Return canonical failure reasons for required failing components."""
    required = set(required_component_kinds)
    reasons = (
        f"{component.kind.value}: {component.failure_reason}"
        for component in components
        if component.kind in required and component.outcome is ComponentOutcome.FAIL
    )
    return tuple(sorted(reasons))


def build_case_result(
    *,
    case_id: str,
    components: tuple[ComponentResult, ...],
    required_component_kinds: tuple[ComponentKind, ...],
    skip_reason: str | None = None,
    trajectory_id: str | None = None,
) -> CaseEvaluationResult:
    """Aggregate supplied components for one case without executing it."""
    if skip_reason is not None:
        return CaseEvaluationResult(
            case_id=case_id,
            outcome=CaseOutcome.SKIPPED,
            components=components,
            skip_reason=skip_reason,
            trajectory_id=trajectory_id,
        )
    by_kind = {component.kind: component for component in components}
    missing = set(required_component_kinds) - set(by_kind)
    if missing:
        names = ", ".join(sorted(value.value for value in missing))
        raise ValueError(f"executed case lacks required components: {names}")
    failure_reasons = _required_failure_reasons(components, required_component_kinds)
    return CaseEvaluationResult(
        case_id=case_id,
        outcome=CaseOutcome.FAIL if failure_reasons else CaseOutcome.PASS,
        components=components,
        failure_reasons=failure_reasons,
        trajectory_id=trajectory_id,
    )


def _component_metric(kind: ComponentKind, cases: tuple[CaseEvaluationResult, ...]) -> ComponentMetric:
    """Aggregate one component kind across executed cases where it is present."""
    outcomes = tuple(
        component.outcome
        for case in cases
        if case.outcome is not CaseOutcome.SKIPPED
        for component in case.components
        if component.kind is kind
    )
    passed = outcomes.count(ComponentOutcome.PASS)
    failed = outcomes.count(ComponentOutcome.FAIL)
    not_applicable = outcomes.count(ComponentOutcome.NOT_APPLICABLE)
    not_measured = outcomes.count(ComponentOutcome.NOT_MEASURED)
    denominator = passed + failed
    return ComponentMetric(
        kind=kind,
        total_observations=len(outcomes),
        passed=passed,
        failed=failed,
        not_applicable=not_applicable,
        not_measured=not_measured,
        measured_applicable=denominator,
        pass_rate=None if denominator == 0 else passed / denominator,
    )


def build_evaluation_report(  # noqa: PLR0913
    *,
    suite_id: str,
    suite_version: str,
    fixture_set_version: str,
    execution_mode: ExecutionMode,
    executed_at: datetime,
    required_component_kinds: tuple[ComponentKind, ...],
    case_results: tuple[CaseEvaluationResult, ...],
    model_configuration: ModelConfiguration | None = None,
    run_id: str | None = None,
) -> EvaluationReport:
    """Aggregate supplied case results into a deterministic report."""
    passed = sum(case.outcome is CaseOutcome.PASS for case in case_results)
    failed = sum(case.outcome is CaseOutcome.FAIL for case in case_results)
    skipped = sum(case.outcome is CaseOutcome.SKIPPED for case in case_results)
    executed = passed + failed
    return EvaluationReport(
        suite_id=suite_id,
        suite_version=suite_version,
        fixture_set_version=fixture_set_version,
        execution_mode=execution_mode,
        executed_at=executed_at,
        required_component_kinds=required_component_kinds,
        model_configuration=model_configuration,
        run_id=run_id,
        total_cases=len(case_results),
        executed_cases=executed,
        passed_cases=passed,
        failed_cases=failed,
        skipped_cases=skipped,
        overall_pass_rate=None if executed == 0 else passed / executed,
        component_metrics=tuple(_component_metric(kind, case_results) for kind in ComponentKind),
        case_results=case_results,
    )
