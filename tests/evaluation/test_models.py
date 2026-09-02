from collections.abc import Callable
from datetime import UTC, datetime
from math import inf, nan

import pytest
from pydantic import BaseModel, ValidationError

from src import evaluation
from src.evaluation.models import (
    BehaviorConstraints,
    Case,
    ComponentKind,
    ComponentOutcome,
    ComponentResult,
    DomainOutcomeExpectation,
    DomainOutcomeObservation,
    ExecutionMode,
    Expectation,
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


@pytest.mark.parametrize(
    ("enum_type", "expected_values"),
    [
        (ExecutionMode, ["deterministic_no_llm", "real_local_ollama"]),
        (
            ToolName,
            [
                "analyze_momentum",
                "analyze_graham_number",
                "analyze_graham_growth_value",
                "analyze_fcf_earnings_growth",
            ],
        ),
        (GrahamMethod, ["graham_number", "graham_growth_value"]),
        (
            ComponentKind,
            [
                "strategy_selection",
                "graham_method_selection",
                "numerical_correctness",
                "fixture_status",
                "execution_status",
            ],
        ),
        (ComponentOutcome, ["pass", "fail", "not_applicable", "not_measured"]),
    ],
)
def test_string_enum_values(enum_type: type[object], expected_values: list[str]) -> None:
    assert [str(member) for member in enum_type] == expected_values  # type: ignore[attr-defined]


def test_tool_constraints_are_canonical_and_accept_required_permitted_values() -> None:
    constraints = ToolConstraints(
        permitted=(ToolName.ANALYZE_MOMENTUM, ToolName.ANALYZE_FCF_EARNINGS_GROWTH),
        required=(ToolName.ANALYZE_MOMENTUM,),
        forbidden=(ToolName.ANALYZE_GRAHAM_NUMBER, ToolName.ANALYZE_GRAHAM_GROWTH_VALUE),
    )

    assert constraints.permitted == (
        ToolName.ANALYZE_FCF_EARNINGS_GROWTH,
        ToolName.ANALYZE_MOMENTUM,
    )
    assert constraints.required == (ToolName.ANALYZE_MOMENTUM,)
    assert constraints.forbidden == (
        ToolName.ANALYZE_GRAHAM_GROWTH_VALUE,
        ToolName.ANALYZE_GRAHAM_NUMBER,
    )


def test_graham_method_constraints_are_canonical() -> None:
    constraints = GrahamMethodConstraints(
        permitted=(GrahamMethod.GRAHAM_NUMBER, GrahamMethod.GRAHAM_GROWTH_VALUE),
        required=(GrahamMethod.GRAHAM_NUMBER,),
    )

    assert constraints.permitted == (
        GrahamMethod.GRAHAM_GROWTH_VALUE,
        GrahamMethod.GRAHAM_NUMBER,
    )


def test_behavior_constraints_normalize_and_canonicalize_identifiers() -> None:
    constraints = BehaviorConstraints(
        permitted=(" use_fixture_data ", "retain_provenance"),
        required=("retain_provenance",),
        forbidden=("live_network_access",),
    )

    assert constraints.permitted == ("retain_provenance", "use_fixture_data")
    assert constraints.required == ("retain_provenance",)
    assert constraints.forbidden == ("live_network_access",)


@pytest.mark.parametrize(
    ("model", "field_name", "value"),
    [
        (ToolConstraints(permitted=(ToolName.ANALYZE_MOMENTUM,)), "permitted", ()),
        (GrahamMethodConstraints(permitted=(GrahamMethod.GRAHAM_NUMBER,)), "permitted", ()),
        (BehaviorConstraints(permitted=("retain_provenance",)), "permitted", ()),
        (
            NumericalExpectation(field_path="result.value", expected_value=1.0, absolute_tolerance=0.0),
            "field_path",
            "other.value",
        ),
    ],
)
def test_leaf_models_are_frozen(model: BaseModel, field_name: str, value: object) -> None:
    with pytest.raises(ValidationError, match="frozen"):
        setattr(model, field_name, value)


@pytest.mark.parametrize(
    "model",
    [
        ToolConstraints(
            permitted=(ToolName.ANALYZE_MOMENTUM, ToolName.ANALYZE_GRAHAM_NUMBER),
            required=(ToolName.ANALYZE_MOMENTUM,),
        ),
        GrahamMethodConstraints(
            permitted=(GrahamMethod.GRAHAM_NUMBER, GrahamMethod.GRAHAM_GROWTH_VALUE),
            forbidden=(),
        ),
        BehaviorConstraints(
            permitted=("retain_provenance", "use_fixture_data"),
            required=("retain_provenance",),
        ),
        NumericalExpectation(
            field_path="result.maximum_indicated_price",
            expected_value=42.5,
            absolute_tolerance=0.01,
            relative_tolerance=0.001,
        ),
    ],
)
def test_leaf_models_have_deterministic_json_round_trips(model: BaseModel) -> None:
    serialized = model.model_dump_json()

    assert type(model).model_validate_json(serialized) == model
    assert type(model).model_validate_json(serialized).model_dump_json() == serialized


@pytest.mark.parametrize(
    "factory",
    [
        lambda: ToolConstraints(
            permitted=(ToolName.ANALYZE_MOMENTUM, ToolName.ANALYZE_MOMENTUM),
        ),
        lambda: GrahamMethodConstraints(
            forbidden=(GrahamMethod.GRAHAM_NUMBER, GrahamMethod.GRAHAM_NUMBER),
        ),
        lambda: BehaviorConstraints(required=("retain_provenance", " retain_provenance ")),
    ],
)
def test_constraint_models_reject_duplicates(factory: Callable[[], BaseModel]) -> None:
    with pytest.raises(ValidationError, match="duplicates"):
        factory()


@pytest.mark.parametrize(
    "factory",
    [
        lambda: ToolConstraints(required=(ToolName.ANALYZE_MOMENTUM,)),
        lambda: GrahamMethodConstraints(required=(GrahamMethod.GRAHAM_NUMBER,)),
        lambda: BehaviorConstraints(required=("retain_provenance",)),
    ],
)
def test_constraint_models_reject_required_values_that_are_not_permitted(
    factory: Callable[[], BaseModel],
) -> None:
    with pytest.raises(ValidationError, match="required values must also be permitted"):
        factory()


@pytest.mark.parametrize(
    "factory",
    [
        lambda: ToolConstraints(
            permitted=(ToolName.ANALYZE_MOMENTUM,),
            forbidden=(ToolName.ANALYZE_MOMENTUM,),
        ),
        lambda: GrahamMethodConstraints(
            permitted=(GrahamMethod.GRAHAM_NUMBER,),
            required=(GrahamMethod.GRAHAM_NUMBER,),
            forbidden=(GrahamMethod.GRAHAM_NUMBER,),
        ),
        lambda: BehaviorConstraints(
            permitted=("retain_provenance",),
            forbidden=("retain_provenance",),
        ),
    ],
)
def test_constraint_models_reject_forbidden_overlaps(factory: Callable[[], BaseModel]) -> None:
    with pytest.raises(ValidationError, match="forbidden values must be disjoint"):
        factory()


@pytest.mark.parametrize("value", ["", " ", "\t"])
def test_behavior_constraints_reject_blank_identifiers(value: str) -> None:
    with pytest.raises(ValidationError, match="must not be blank"):
        BehaviorConstraints(permitted=(value,))


def test_numerical_expectation_accepts_zero_as_exact_match_tolerance() -> None:
    expectation = NumericalExpectation(
        field_path=" result.margin_of_safety ",
        expected_value=0.0,
        absolute_tolerance=0.0,
    )

    assert expectation.field_path == "result.margin_of_safety"
    assert expectation.absolute_tolerance == 0.0
    assert expectation.relative_tolerance is None


def test_domain_outcome_expectation_normalizes_path_and_accepts_explicit_null() -> None:
    expectation = DomainOutcomeExpectation(field_path=" result.status ", expected_value=None)

    assert expectation.field_path == "result.status"
    assert expectation.expected_value is None


def test_domain_outcome_expectation_rejects_nonscalar_value() -> None:
    with pytest.raises(ValidationError):
        DomainOutcomeExpectation.model_validate({"field_path": "result.status", "expected_value": 1.5})


@pytest.mark.parametrize("field_path", ["", " ", "\n"])
def test_numerical_expectation_rejects_blank_field_paths(field_path: str) -> None:
    with pytest.raises(ValidationError, match="field_path must not be blank"):
        NumericalExpectation(field_path=field_path, expected_value=1.0, absolute_tolerance=0.0)


def test_numerical_expectation_requires_at_least_one_tolerance() -> None:
    with pytest.raises(ValidationError, match="at least one absolute or relative tolerance is required"):
        NumericalExpectation(field_path="result.value", expected_value=1.0)


@pytest.mark.parametrize("tolerance", [-0.01, inf, -inf, nan])
@pytest.mark.parametrize("field_name", ["absolute_tolerance", "relative_tolerance"])
def test_numerical_expectation_rejects_invalid_tolerances(field_name: str, tolerance: float) -> None:
    values: dict[str, object] = {
        "field_path": "result.value",
        "expected_value": 1.0,
        field_name: tolerance,
    }

    with pytest.raises(ValidationError):
        NumericalExpectation.model_validate(values)


@pytest.mark.parametrize("expected_value", [inf, -inf, nan])
def test_numerical_expectation_rejects_non_finite_expected_values(expected_value: float) -> None:
    with pytest.raises(ValidationError):
        NumericalExpectation(
            field_path="result.value",
            expected_value=expected_value,
            absolute_tolerance=0.0,
        )


def test_expectation_composes_constraints_and_canonical_numerical_paths() -> None:
    expectation = Expectation(
        tool_constraints=ToolConstraints(permitted=(ToolName.ANALYZE_MOMENTUM,)),
        behavior_constraints=BehaviorConstraints(permitted=("use_fixture_data",)),
        numerical_expectations=(
            NumericalExpectation(field_path="result.z_score", expected_value=2.0, absolute_tolerance=0.01),
            NumericalExpectation(field_path="result.alpha", expected_value=1.0, relative_tolerance=0.001),
        ),
    )

    assert tuple(item.field_path for item in expectation.numerical_expectations) == (
        "result.alpha",
        "result.z_score",
    )
    assert expectation.graham_method_constraints == GrahamMethodConstraints()


def test_expectation_rejects_duplicate_numerical_paths() -> None:
    with pytest.raises(ValidationError, match="numerical expectation field paths must be unique"):
        Expectation(
            numerical_expectations=(
                NumericalExpectation(field_path="result.value", expected_value=1.0, absolute_tolerance=0.0),
                NumericalExpectation(field_path=" result.value ", expected_value=2.0, absolute_tolerance=0.0),
            )
        )


def test_expectation_canonicalizes_and_rejects_duplicate_domain_outcome_paths() -> None:
    expectation = Expectation(
        domain_outcome_expectations=(
            DomainOutcomeExpectation(field_path="result.status", expected_value="ok"),
            DomainOutcomeExpectation(field_path="assembly.status", expected_value="ok"),
        )
    )
    assert tuple(item.field_path for item in expectation.domain_outcome_expectations) == (
        "assembly.status",
        "result.status",
    )

    with pytest.raises(ValidationError, match="domain-outcome expectation field paths must be unique"):
        Expectation(
            domain_outcome_expectations=(
                DomainOutcomeExpectation(field_path="result.status", expected_value="ok"),
                DomainOutcomeExpectation(field_path=" result.status ", expected_value="input_unavailable"),
            )
        )


def test_case_is_mode_neutral_and_canonicalizes_fixture_ids_and_tags() -> None:
    case = Case(
        case_id=" momentum_success ",
        description=" A deterministic Momentum success case. ",
        task=" Analyze fixture-backed momentum. ",
        fixture_ids=("prices_daily", " instrument_profile "),
        expectation=Expectation(),
        tags=("success", "momentum"),
    )

    assert case.case_id == "momentum_success"
    assert case.description == "A deterministic Momentum success case."
    assert case.task == "Analyze fixture-backed momentum."
    assert case.fixture_ids == ("instrument_profile", "prices_daily")
    assert case.tags == ("momentum", "success")
    assert "execution_mode" not in Case.model_fields


@pytest.mark.parametrize("field_name", ["case_id", "description", "task"])
def test_case_rejects_blank_required_text(field_name: str) -> None:
    values: dict[str, object] = {
        "case_id": "case_id",
        "description": "description",
        "task": "task",
        "fixture_ids": ["fixture"],
        "expectation": {},
    }
    values[field_name] = " "

    with pytest.raises(ValidationError, match="case text fields must not be blank"):
        Case.model_validate(values)


@pytest.mark.parametrize(
    ("fixture_ids", "message"),
    [
        ([], "at least one fixture identifier is required"),
        (["fixture", " fixture "], "fixture identifiers must not contain duplicates"),
        (["fixture", " "], "fixture identifiers must not contain blank values"),
    ],
)
def test_case_rejects_invalid_fixture_ids(fixture_ids: list[str], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Case(
            case_id="case_id",
            description="description",
            task="task",
            fixture_ids=tuple(fixture_ids),
            expectation=Expectation(),
        )


@pytest.mark.parametrize(
    ("tags", "message"),
    [
        (["tag", " tag "], "tags must not contain duplicates"),
        (["tag", " "], "tags must not contain blank values"),
    ],
)
def test_case_rejects_invalid_tags(tags: list[str], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Case(
            case_id="case_id",
            description="description",
            task="task",
            fixture_ids=("fixture",),
            expectation=Expectation(),
            tags=tuple(tags),
        )


def test_observation_preserves_ordered_and_repeated_selection_evidence() -> None:
    observation = Observation(
        execution_mode=ExecutionMode.REAL_LOCAL_OLLAMA,
        observed_at=datetime(2026, 8, 31, 12, 0, tzinfo=UTC),
        tool_calls=(
            ToolCallObservation(tool_name=ToolName.ANALYZE_MOMENTUM),
            ToolCallObservation(tool_name=ToolName.ANALYZE_GRAHAM_NUMBER),
            ToolCallObservation(tool_name=ToolName.ANALYZE_MOMENTUM),
        ),
        graham_methods=(
            GrahamMethodObservation(method=GrahamMethod.GRAHAM_NUMBER),
            GrahamMethodObservation(method=GrahamMethod.GRAHAM_GROWTH_VALUE),
            GrahamMethodObservation(method=GrahamMethod.GRAHAM_NUMBER),
        ),
    )

    assert tuple(call.tool_name for call in observation.tool_calls) == (
        ToolName.ANALYZE_MOMENTUM,
        ToolName.ANALYZE_GRAHAM_NUMBER,
        ToolName.ANALYZE_MOMENTUM,
    )
    assert tuple(item.method for item in observation.graham_methods) == (
        GrahamMethod.GRAHAM_NUMBER,
        GrahamMethod.GRAHAM_GROWTH_VALUE,
        GrahamMethod.GRAHAM_NUMBER,
    )


def test_observation_canonicalizes_unique_numerical_paths() -> None:
    observation = Observation(
        execution_mode=ExecutionMode.DETERMINISTIC_NO_LLM,
        observed_at=datetime(2026, 8, 31, 12, 0, tzinfo=UTC),
        numerical_observations=(
            NumericalObservation(field_path="result.z_score", value=2.0),
            NumericalObservation(field_path="result.alpha", value=1.0),
        ),
    )

    assert tuple(item.field_path for item in observation.numerical_observations) == (
        "result.alpha",
        "result.z_score",
    )


def test_observation_rejects_duplicate_numerical_paths() -> None:
    with pytest.raises(ValidationError, match="numerical observation field paths must be unique"):
        Observation(
            execution_mode=ExecutionMode.DETERMINISTIC_NO_LLM,
            observed_at=datetime(2026, 8, 31, 12, 0, tzinfo=UTC),
            numerical_observations=(
                NumericalObservation(field_path="result.value", value=1.0),
                NumericalObservation(field_path=" result.value ", value=2.0),
            ),
        )


def test_observation_preserves_explicit_null_and_rejects_duplicate_domain_paths() -> None:
    observation = Observation(
        execution_mode=ExecutionMode.DETERMINISTIC_NO_LLM,
        observed_at=datetime(2026, 8, 31, 12, 0, tzinfo=UTC),
        domain_outcome_observations=(DomainOutcomeObservation(field_path="result.value", value=None),),
    )
    assert observation.domain_outcome_observations[0].value is None

    with pytest.raises(ValidationError, match="domain-outcome observation field paths must be unique"):
        Observation(
            execution_mode=ExecutionMode.DETERMINISTIC_NO_LLM,
            observed_at=datetime(2026, 8, 31, 12, 0, tzinfo=UTC),
            domain_outcome_observations=(
                DomainOutcomeObservation(field_path="result.status", value="ok"),
                DomainOutcomeObservation(field_path=" result.status ", value="input_unavailable"),
            ),
        )


@pytest.mark.parametrize("value", [inf, -inf, nan])
def test_numerical_observation_rejects_non_finite_values(value: float) -> None:
    with pytest.raises(ValidationError):
        NumericalObservation(field_path="result.value", value=value)


@pytest.mark.parametrize("field_path", ["", " ", "\t"])
def test_numerical_observation_rejects_blank_paths(field_path: str) -> None:
    with pytest.raises(ValidationError, match="field_path must not be blank"):
        NumericalObservation(field_path=field_path, value=1.0)


def test_observation_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError, match="observed_at must be timezone-aware"):
        Observation(
            execution_mode=ExecutionMode.DETERMINISTIC_NO_LLM,
            observed_at=datetime(2026, 8, 31, 12, 0),
        )


@pytest.mark.parametrize(
    "selection_evidence",
    [
        {"tool_calls": [{"tool_name": ToolName.ANALYZE_MOMENTUM}]},
        {"graham_methods": [{"method": GrahamMethod.GRAHAM_NUMBER}]},
    ],
)
def test_deterministic_observation_rejects_selection_evidence(
    selection_evidence: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "execution_mode": ExecutionMode.DETERMINISTIC_NO_LLM,
        "observed_at": datetime(2026, 8, 31, 12, 0, tzinfo=UTC),
        **selection_evidence,
    }

    with pytest.raises(ValidationError, match="must not contain selection evidence"):
        Observation.model_validate(values)


@pytest.mark.parametrize(
    "result",
    [
        ComponentResult(kind=ComponentKind.NUMERICAL_CORRECTNESS, outcome=ComponentOutcome.PASS),
        ComponentResult(
            kind=ComponentKind.EXECUTION_STATUS,
            outcome=ComponentOutcome.FAIL,
            failure_reason=" execution failed ",
        ),
        ComponentResult(
            kind=ComponentKind.GRAHAM_METHOD_SELECTION,
            outcome=ComponentOutcome.NOT_APPLICABLE,
            evidence=" not a Graham case ",
        ),
        ComponentResult(
            kind=ComponentKind.STRATEGY_SELECTION,
            outcome=ComponentOutcome.NOT_MEASURED,
            evidence=" deterministic execution has no LLM selection evidence ",
        ),
    ],
)
def test_component_result_accepts_valid_outcome_matrix(result: ComponentResult) -> None:
    if result.failure_reason is not None:
        assert result.failure_reason == result.failure_reason.strip()
    if result.evidence is not None:
        assert result.evidence == result.evidence.strip()


@pytest.mark.parametrize("failure_reason", [None, "", " "])
def test_component_result_fail_requires_nonblank_failure_reason(failure_reason: str | None) -> None:
    with pytest.raises(ValidationError):
        ComponentResult(
            kind=ComponentKind.EXECUTION_STATUS,
            outcome=ComponentOutcome.FAIL,
            failure_reason=failure_reason,
        )


@pytest.mark.parametrize(
    "outcome",
    [ComponentOutcome.PASS, ComponentOutcome.NOT_APPLICABLE, ComponentOutcome.NOT_MEASURED],
)
def test_component_result_non_fail_outcomes_forbid_failure_reason(outcome: ComponentOutcome) -> None:
    values: dict[str, object] = {
        "kind": ComponentKind.EXECUTION_STATUS,
        "outcome": outcome,
        "failure_reason": "unexpected reason",
    }
    if outcome in (ComponentOutcome.NOT_APPLICABLE, ComponentOutcome.NOT_MEASURED):
        values["evidence"] = "explanation"

    with pytest.raises(ValidationError, match="only fail outcomes may contain a failure reason"):
        ComponentResult.model_validate(values)


@pytest.mark.parametrize("outcome", [ComponentOutcome.NOT_APPLICABLE, ComponentOutcome.NOT_MEASURED])
@pytest.mark.parametrize("evidence", [None, "", " "])
def test_component_result_unmeasured_outcomes_require_nonblank_evidence(
    outcome: ComponentOutcome,
    evidence: str | None,
) -> None:
    with pytest.raises(ValidationError):
        ComponentResult(
            kind=ComponentKind.STRATEGY_SELECTION,
            outcome=outcome,
            evidence=evidence,
        )


@pytest.mark.parametrize(
    ("model", "field_name", "value"),
    [
        (Expectation(), "numerical_expectations", ()),
        (
            Case(
                case_id="case_id",
                description="description",
                task="task",
                fixture_ids=("fixture",),
                expectation=Expectation(),
            ),
            "case_id",
            "other_case",
        ),
        (ToolCallObservation(tool_name=ToolName.ANALYZE_MOMENTUM), "tool_name", ToolName.ANALYZE_GRAHAM_NUMBER),
        (
            GrahamMethodObservation(method=GrahamMethod.GRAHAM_NUMBER),
            "method",
            GrahamMethod.GRAHAM_GROWTH_VALUE,
        ),
        (NumericalObservation(field_path="result.value", value=1.0), "value", 2.0),
        (
            Observation(
                execution_mode=ExecutionMode.DETERMINISTIC_NO_LLM,
                observed_at=datetime(2026, 8, 31, 12, 0, tzinfo=UTC),
            ),
            "execution_mode",
            ExecutionMode.REAL_LOCAL_OLLAMA,
        ),
        (
            ComponentResult(kind=ComponentKind.NUMERICAL_CORRECTNESS, outcome=ComponentOutcome.PASS),
            "outcome",
            ComponentOutcome.FAIL,
        ),
    ],
)
def test_composed_models_are_frozen(model: BaseModel, field_name: str, value: object) -> None:
    with pytest.raises(ValidationError, match="frozen"):
        setattr(model, field_name, value)


def test_composed_contract_has_deterministic_json_round_trip() -> None:
    case = Case(
        case_id="graham_number_success",
        description="A deterministic Graham Number case.",
        task="Calculate the Graham Number.",
        fixture_ids=("graham_facts", "instrument_profile"),
        expectation=Expectation(
            tool_constraints=ToolConstraints(
                permitted=(ToolName.ANALYZE_GRAHAM_NUMBER,),
                required=(ToolName.ANALYZE_GRAHAM_NUMBER,),
            ),
            numerical_expectations=(
                NumericalExpectation(
                    field_path="result.maximum_indicated_price",
                    expected_value=42.5,
                    absolute_tolerance=0.01,
                ),
            ),
        ),
        tags=("success", "graham"),
    )
    serialized = case.model_dump_json()

    assert Case.model_validate_json(serialized) == case
    assert Case.model_validate_json(serialized).model_dump_json() == serialized


def test_public_evaluation_exports_are_deliberate() -> None:
    assert evaluation.__all__ == [
        "BehaviorConstraints",
        "Case",
        "ComponentKind",
        "ComponentOutcome",
        "ComponentResult",
        "DomainOutcomeExpectation",
        "DomainOutcomeObservation",
        "ExecutionMode",
        "Expectation",
        "GrahamMethod",
        "GrahamMethodConstraints",
        "GrahamMethodObservation",
        "NumericalExpectation",
        "NumericalObservation",
        "Observation",
        "ToolCallObservation",
        "ToolConstraints",
        "ToolName",
    ]
