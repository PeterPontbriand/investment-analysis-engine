"""Focused tests for the run-envelope supporting value types."""

from datetime import UTC, date, datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from src.workspace.models import EffectiveBoundary, JsonValue, RunOutcome, StrictJsonMapping

_NON_PRIMITIVE_VALUES: list[object] = [datetime.now(UTC), b"bytes", {1, 2}, object()]


def test_run_outcome_is_terminal_only() -> None:
    assert {outcome.value for outcome in RunOutcome} == {
        "completed",
        "unavailable",
        "not_applicable",
        "failed",
        "cancelled",
    }
    assert not any("running" in outcome.name.lower() or "running" in outcome.value for outcome in RunOutcome)


def test_json_value_accepts_nested_primitives() -> None:
    adapter = TypeAdapter(StrictJsonMapping)
    payload = {"a": 1, "b": [1.5, None, True], "c": "text", "d": {"nested": -2}}
    assert adapter.validate_python(payload) == payload


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_json_value_rejects_non_finite_floats(bad_value: float) -> None:
    with pytest.raises(ValidationError, match="finite"):
        TypeAdapter(JsonValue).validate_python({"top": bad_value})


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf")])
def test_json_value_rejects_nested_non_finite_floats(bad_value: float) -> None:
    with pytest.raises(ValidationError, match="finite"):
        TypeAdapter(JsonValue).validate_python({"list": [1.0, {"deep": bad_value}]})


@pytest.mark.parametrize("bad_value", _NON_PRIMITIVE_VALUES)
def test_json_value_rejects_non_primitives(bad_value: object) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(JsonValue).validate_python({"value": bad_value})


@pytest.mark.parametrize("bad_key", [0, None, True, (1, 2)])
def test_json_value_rejects_non_string_object_keys(bad_key: object) -> None:
    with pytest.raises(ValidationError, match="keys must be strings"):
        TypeAdapter(JsonValue).validate_python({bad_key: "value"})


def test_effective_boundary_requires_end_on_or_after_start() -> None:
    with pytest.raises(ValidationError, match="on or after start"):
        EffectiveBoundary(start=date(2026, 1, 10), end=date(2026, 1, 5))

    assert EffectiveBoundary(start=date(2026, 1, 5), end=date(2026, 1, 5)).end == date(2026, 1, 5)
    assert EffectiveBoundary(end=date(2026, 1, 5)).start is None


def test_effective_boundary_is_frozen_and_strict() -> None:
    boundary = EffectiveBoundary(start=date(2026, 1, 1))
    with pytest.raises(ValidationError, match="frozen_instance"):
        boundary.start = date(2026, 1, 2)
    with pytest.raises(ValidationError, match="extra_forbidden"):
        EffectiveBoundary(start=date(2026, 1, 1), unexpected=1)  # type: ignore[call-arg]
