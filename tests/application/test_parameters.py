"""The action parameter error: its own names, and a caller's spelling of them."""

import pytest

from investment_analysis_engine.application.parameters import ActionParameterError
from investment_analysis_engine.core.operator_errors import InvalidParameterError


def test_the_message_and_parameters_use_the_actions_own_names() -> None:
    error = ActionParameterError("{name} must not be blank.", parameters=("name",), rule="demo.blank")

    assert (str(error), error.parameters) == ("name must not be blank.", ("name",))
    assert error.reason_code is InvalidParameterError.reason_code


def test_named_fills_in_the_callers_names_in_message_and_parameters() -> None:
    error = ActionParameterError("{first} and {second} differ.", parameters=("first", "second"), rule="demo.differ")

    spelled = error.named({"first": "NAME", "second": "--other", "unused": "IGNORED"})

    assert type(spelled) is InvalidParameterError
    assert (str(spelled), spelled.parameters) == ("NAME and --other differ.", ("NAME", "--other"))


def test_named_without_a_name_for_one_of_the_parameters_is_a_programming_error() -> None:
    error = ActionParameterError("{name} must not be blank.", parameters=("name",), rule="demo.blank")

    with pytest.raises(KeyError):
        error.named({"other": "OTHER"})


def test_the_rule_and_the_values_are_kept_beside_the_message() -> None:
    error = ActionParameterError(
        "{first} ({first_value}) must be below {second} ({second_value}).",
        parameters=("first", "second"),
        rule="demo.order",
        arguments={"first_value": 9, "second_value": 4},
    )

    assert str(error) == "first (9) must be below second (4)."
    assert (error.rule, error.arguments) == ("demo.order", {"first_value": 9, "second_value": 4})
    spelled = error.named({"first": "--a", "second": "--b"})
    assert (str(spelled), spelled.parameters) == ("--a (9) must be below --b (4).", ("--a", "--b"))


def test_a_nested_field_name_is_substituted_and_not_read_as_attribute_access() -> None:
    error = ActionParameterError(
        "Invalid {policy.historical_horizon}: {detail} {unrelated} {0}.",
        parameters=("policy.historical_horizon",),
        rule="pydantic.literal_error",
        arguments={"detail": "bad"},
    )

    assert str(error) == "Invalid policy.historical_horizon: bad {unrelated} {0}."
    spelled = error.named({"policy.historical_horizon": "--growth-years"})
    assert str(spelled) == "Invalid --growth-years: bad {unrelated} {0}."


def test_text_inserted_for_a_placeholder_is_not_substituted_again() -> None:
    error = ActionParameterError(
        "{name} got {value}.", parameters=("name",), rule="demo.once", arguments={"value": "{name} and {other}"}
    )

    assert str(error) == "name got {name} and {other}."
    assert str(error.named({"name": "--n"})) == "--n got {name} and {other}."


def test_a_placeholder_the_error_does_not_declare_stays_as_written() -> None:
    error = ActionParameterError("{name} and {undeclared}.", parameters=("name",), rule="demo.undeclared")

    assert str(error) == "name and {undeclared}."
