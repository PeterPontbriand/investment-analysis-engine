"""Typed contracts for Golden-Suite cases, observations, and component results."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator


class ExecutionMode(StrEnum):
    """Supported Golden-Suite execution modes."""

    DETERMINISTIC_NO_LLM = "deterministic_no_llm"
    REAL_LOCAL_OLLAMA = "real_local_ollama"


class ToolName(StrEnum):
    """Approved production analysis-tool identifiers."""

    ANALYZE_MOMENTUM = "analyze_momentum"
    ANALYZE_GRAHAM_NUMBER = "analyze_graham_number"
    ANALYZE_GRAHAM_GROWTH_VALUE = "analyze_graham_growth_value"
    ANALYZE_FCF_EARNINGS_GROWTH = "analyze_fcf_earnings_growth"


class GrahamMethod(StrEnum):
    """Supported Graham valuation method identifiers."""

    GRAHAM_NUMBER = "graham_number"
    GRAHAM_GROWTH_VALUE = "graham_growth_value"


class ComponentKind(StrEnum):
    """Independently reported Golden-Suite evaluation components."""

    STRATEGY_SELECTION = "strategy_selection"
    GRAHAM_METHOD_SELECTION = "graham_method_selection"
    NUMERICAL_CORRECTNESS = "numerical_correctness"
    FIXTURE_STATUS = "fixture_status"
    EXECUTION_STATUS = "execution_status"


class ComponentOutcome(StrEnum):
    """Possible outcomes for an evaluated component."""

    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"
    NOT_MEASURED = "not_measured"


def _canonicalize[ConstraintValue: (ToolName, GrahamMethod, str)](
    values: tuple[ConstraintValue, ...],
) -> tuple[ConstraintValue, ...]:
    """Reject duplicate constraint values and return deterministic order."""
    if len(values) != len(set(values)):
        raise ValueError("constraint values must not contain duplicates")
    return tuple(sorted(values, key=str))


def _validate_relationships[ConstraintValue: (ToolName, GrahamMethod, str)](
    *,
    permitted: tuple[ConstraintValue, ...],
    required: tuple[ConstraintValue, ...],
    forbidden: tuple[ConstraintValue, ...],
) -> None:
    """Validate required, permitted, and forbidden set relationships."""
    permitted_values = set(permitted)
    required_values = set(required)
    forbidden_values = set(forbidden)
    if not required_values <= permitted_values:
        raise ValueError("required values must also be permitted")
    if forbidden_values & (permitted_values | required_values):
        raise ValueError("forbidden values must be disjoint from permitted and required values")


class ToolConstraints(BaseModel):
    """Immutable expected constraints on selected production tools."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    permitted: tuple[ToolName, ...] = ()
    required: tuple[ToolName, ...] = ()
    forbidden: tuple[ToolName, ...] = ()

    @field_validator("permitted", "required", "forbidden")
    @classmethod
    def canonicalize_values(cls, values: tuple[ToolName, ...]) -> tuple[ToolName, ...]:
        """Reject duplicates and canonicalize semantically unordered tools."""
        return _canonicalize(values)

    @model_validator(mode="after")
    def validate_relationships(self) -> ToolConstraints:
        """Enforce relationships between tool constraint collections."""
        _validate_relationships(permitted=self.permitted, required=self.required, forbidden=self.forbidden)
        return self


class GrahamMethodConstraints(BaseModel):
    """Immutable expected constraints on selected Graham methods."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    permitted: tuple[GrahamMethod, ...] = ()
    required: tuple[GrahamMethod, ...] = ()
    forbidden: tuple[GrahamMethod, ...] = ()

    @field_validator("permitted", "required", "forbidden")
    @classmethod
    def canonicalize_values(cls, values: tuple[GrahamMethod, ...]) -> tuple[GrahamMethod, ...]:
        """Reject duplicates and canonicalize semantically unordered methods."""
        return _canonicalize(values)

    @model_validator(mode="after")
    def validate_relationships(self) -> GrahamMethodConstraints:
        """Enforce relationships between Graham-method constraint collections."""
        _validate_relationships(permitted=self.permitted, required=self.required, forbidden=self.forbidden)
        return self


class BehaviorConstraints(BaseModel):
    """Immutable expected constraints on named execution behaviors."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    permitted: tuple[str, ...] = ()
    required: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()

    @field_validator("permitted", "required", "forbidden")
    @classmethod
    def validate_and_canonicalize_values(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Normalize, validate, and canonicalize behavior identifiers."""
        normalized = tuple(value.strip() for value in values)
        if any(not value for value in normalized):
            raise ValueError("behavior identifiers must not be blank")
        return _canonicalize(normalized)

    @model_validator(mode="after")
    def validate_relationships(self) -> BehaviorConstraints:
        """Enforce relationships between behavior constraint collections."""
        _validate_relationships(permitted=self.permitted, required=self.required, forbidden=self.forbidden)
        return self


FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
NonNegativeFiniteFloat = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class NumericalExpectation(BaseModel):
    """Immutable expected value and tolerances for one numerical field path."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field_path: str
    expected_value: FiniteFloat
    absolute_tolerance: NonNegativeFiniteFloat | None = None
    relative_tolerance: NonNegativeFiniteFloat | None = None

    @field_validator("field_path")
    @classmethod
    def validate_field_path(cls, value: str) -> str:
        """Return a normalized, nonblank numerical field path."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("field_path must not be blank")
        return normalized

    @model_validator(mode="after")
    def require_tolerance(self) -> NumericalExpectation:
        """Require at least one explicitly supplied comparison tolerance."""
        if self.absolute_tolerance is None and self.relative_tolerance is None:
            raise ValueError("at least one absolute or relative tolerance is required")
        return self


DomainScalar = StrictStr | StrictBool | StrictInt | None


class DomainOutcomeExpectation(BaseModel):
    """Immutable exact expectation for one nonnumerical native-result field."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field_path: str
    expected_value: DomainScalar

    @field_validator("field_path")
    @classmethod
    def validate_field_path(cls, value: str) -> str:
        """Return a normalized, nonblank native-result field path."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("field_path must not be blank")
        return normalized


class Expectation(BaseModel):
    """Immutable expected selection, behavior, and numerical evidence for one case."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_constraints: ToolConstraints = Field(default_factory=ToolConstraints)
    graham_method_constraints: GrahamMethodConstraints = Field(default_factory=GrahamMethodConstraints)
    behavior_constraints: BehaviorConstraints = Field(default_factory=BehaviorConstraints)
    numerical_expectations: tuple[NumericalExpectation, ...] = ()
    domain_outcome_expectations: tuple[DomainOutcomeExpectation, ...] = ()

    @field_validator("numerical_expectations")
    @classmethod
    def validate_numerical_paths(
        cls,
        values: tuple[NumericalExpectation, ...],
    ) -> tuple[NumericalExpectation, ...]:
        """Reject duplicate numerical paths and return deterministic path order."""
        field_paths = tuple(value.field_path for value in values)
        if len(field_paths) != len(set(field_paths)):
            raise ValueError("numerical expectation field paths must be unique")
        return tuple(sorted(values, key=lambda value: value.field_path))

    @field_validator("domain_outcome_expectations")
    @classmethod
    def validate_domain_outcome_paths(
        cls,
        values: tuple[DomainOutcomeExpectation, ...],
    ) -> tuple[DomainOutcomeExpectation, ...]:
        """Reject duplicate domain-outcome paths and return deterministic path order."""
        field_paths = tuple(value.field_path for value in values)
        if len(field_paths) != len(set(field_paths)):
            raise ValueError("domain-outcome expectation field paths must be unique")
        return tuple(sorted(values, key=lambda value: value.field_path))


class Case(BaseModel):
    """Immutable, mode-neutral definition of one Golden-Suite benchmark case."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    description: str
    task: str
    fixture_ids: tuple[str, ...]
    expectation: Expectation
    tags: tuple[str, ...] = ()

    @field_validator("case_id", "description", "task")
    @classmethod
    def validate_nonblank_text(cls, value: str) -> str:
        """Normalize and reject blank required case text."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("case text fields must not be blank")
        return normalized

    @field_validator("fixture_ids")
    @classmethod
    def validate_fixture_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Require unique nonblank fixture identifiers in deterministic order."""
        if not values:
            raise ValueError("at least one fixture identifier is required")
        return cls._canonicalize_identifiers(values, label="fixture identifiers")

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Return unique nonblank tags in deterministic order."""
        return cls._canonicalize_identifiers(values, label="tags")

    @staticmethod
    def _canonicalize_identifiers(values: tuple[str, ...], *, label: str) -> tuple[str, ...]:
        """Normalize and canonicalize one identifier collection."""
        normalized = tuple(value.strip() for value in values)
        if any(not value for value in normalized):
            raise ValueError(f"{label} must not contain blank values")
        if len(normalized) != len(set(normalized)):
            raise ValueError(f"{label} must not contain duplicates")
        return tuple(sorted(normalized))


class ToolCallObservation(BaseModel):
    """Raw observation of one selected production tool."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_name: ToolName


class GrahamMethodObservation(BaseModel):
    """Raw observation of one selected Graham method."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: GrahamMethod


class NumericalObservation(BaseModel):
    """Raw finite numerical observation addressed by result field path."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field_path: str
    value: FiniteFloat

    @field_validator("field_path")
    @classmethod
    def validate_field_path(cls, value: str) -> str:
        """Return a normalized, nonblank numerical field path."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("field_path must not be blank")
        return normalized


class DomainOutcomeObservation(BaseModel):
    """Raw exact nonnumerical observation addressed by native-result field path."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field_path: str
    value: DomainScalar

    @field_validator("field_path")
    @classmethod
    def validate_field_path(cls, value: str) -> str:
        """Return a normalized, nonblank native-result field path."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("field_path must not be blank")
        return normalized


class Observation(BaseModel):
    """Immutable raw evidence observed during one case execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_mode: ExecutionMode
    observed_at: datetime
    tool_calls: tuple[ToolCallObservation, ...] = ()
    graham_methods: tuple[GrahamMethodObservation, ...] = ()
    numerical_observations: tuple[NumericalObservation, ...] = ()
    domain_outcome_observations: tuple[DomainOutcomeObservation, ...] = ()

    @field_validator("observed_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        """Require an explicitly timezone-aware observation timestamp."""
        if value.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        return value

    @field_validator("numerical_observations")
    @classmethod
    def validate_numerical_paths(
        cls,
        values: tuple[NumericalObservation, ...],
    ) -> tuple[NumericalObservation, ...]:
        """Reject duplicate numerical paths and return deterministic path order."""
        field_paths = tuple(value.field_path for value in values)
        if len(field_paths) != len(set(field_paths)):
            raise ValueError("numerical observation field paths must be unique")
        return tuple(sorted(values, key=lambda value: value.field_path))

    @field_validator("domain_outcome_observations")
    @classmethod
    def validate_domain_outcome_paths(
        cls,
        values: tuple[DomainOutcomeObservation, ...],
    ) -> tuple[DomainOutcomeObservation, ...]:
        """Reject duplicate domain-outcome paths and return deterministic path order."""
        field_paths = tuple(value.field_path for value in values)
        if len(field_paths) != len(set(field_paths)):
            raise ValueError("domain-outcome observation field paths must be unique")
        return tuple(sorted(values, key=lambda value: value.field_path))

    @model_validator(mode="after")
    def reject_unmeasured_selection_evidence(self) -> Observation:
        """Prevent direct deterministic dispatch from masquerading as measured selection."""
        if self.execution_mode is ExecutionMode.DETERMINISTIC_NO_LLM and (self.tool_calls or self.graham_methods):
            raise ValueError("deterministic_no_llm observations must not contain selection evidence")
        return self


class ComponentResult(BaseModel):
    """Immutable evaluated outcome for one independently reported component."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: ComponentKind
    outcome: ComponentOutcome
    failure_reason: str | None = None
    evidence: str | None = None

    @field_validator("failure_reason", "evidence")
    @classmethod
    def validate_optional_explanation(cls, value: str | None) -> str | None:
        """Normalize supplied explanations and reject blank text."""
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("supplied explanations must not be blank")
        return normalized

    @model_validator(mode="after")
    def validate_outcome_explanations(self) -> ComponentResult:
        """Enforce the failure-reason and explanatory-evidence outcome matrix."""
        if self.outcome is ComponentOutcome.FAIL:
            if self.failure_reason is None:
                raise ValueError("fail outcomes require a failure reason")
        elif self.failure_reason is not None:
            raise ValueError("only fail outcomes may contain a failure reason")

        if self.outcome in (ComponentOutcome.NOT_APPLICABLE, ComponentOutcome.NOT_MEASURED) and self.evidence is None:
            raise ValueError("not_applicable and not_measured outcomes require explanatory evidence")
        return self
