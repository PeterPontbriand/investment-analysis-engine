"""The action parameter error: its own names, and a caller's spelling of them."""

import pytest

from investment_analysis_engine.application.parameters import ActionParameterError
from investment_analysis_engine.core.operator_errors import InvalidParameterError


def test_the_message_and_parameters_use_the_actions_own_names() -> None:
    error = ActionParameterError("{name} must not be blank.", parameters=("name",))

    assert (str(error), error.parameters) == ("name must not be blank.", ("name",))
    assert error.reason_code is InvalidParameterError.reason_code


def test_named_fills_in_the_callers_names_in_message_and_parameters() -> None:
    error = ActionParameterError("{first} and {second} differ.", parameters=("first", "second"))

    spelled = error.named({"first": "NAME", "second": "--other", "unused": "IGNORED"})

    assert type(spelled) is InvalidParameterError
    assert (str(spelled), spelled.parameters) == ("NAME and --other differ.", ("NAME", "--other"))


def test_named_without_a_name_for_one_of_the_parameters_is_a_programming_error() -> None:
    error = ActionParameterError("{name} must not be blank.", parameters=("name",))

    with pytest.raises(KeyError):
        error.named({"other": "OTHER"})
