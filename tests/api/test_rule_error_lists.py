"""A selection with several bad fields reports every error at once, in the API and on the command line."""

import json
import math
from datetime import UTC, date, datetime

import pytest
from typer.testing import CliRunner

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.parameters import ActionParameterError
from investment_analysis_engine.application.selections import build_selection
from investment_analysis_engine.cli import app
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.core.failure_codes import FailureReasonCode
from investment_analysis_engine.core.operator_errors import InvalidParameterError
from investment_analysis_engine.reporting.documents.failure import FailureEnvelope
from investment_analysis_engine.reporting.failure_envelope import failure_envelope, json_argument
from investment_analysis_engine.strategy_wiring import GRAHAM_GROWTH, GRAHAM_NUMBER, MOMENTUM
from tests.api._support import AUTH, client_for

runner = CliRunner()


def _rejection(fields: dict[str, object], settings: ProjectSettings) -> ActionParameterError:
    with pytest.raises(ActionParameterError) as caught:
        build_selection(ApplicationContext(settings=settings), GRAHAM_NUMBER.method_id, fields)
    return caught.value


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("text", "text"),
        (7, 7),
        (True, True),
        (None, None),
        (2.5, 2.5),
        (math.inf, "inf"),
        (-math.inf, "-inf"),
        (math.nan, "nan"),
        (date(2025, 12, 31), "2025-12-31"),
        (datetime(2025, 12, 31, 8, 30, tzinfo=UTC), "2025-12-31T08:30:00+00:00"),
        (("a", 1), "('a', 1)"),
    ],
)
def test_a_rule_argument_is_a_json_value(value: object, expected: object) -> None:
    converted = json_argument(value)

    assert converted == expected
    assert type(converted) is type(expected)
    json.dumps(converted, allow_nan=False, ensure_ascii=False)


def test_several_rejections_keep_every_rule_its_parameters_its_values_and_its_message(
    isolated_cli_settings: ProjectSettings,
) -> None:
    error = _rejection({"eps_override": math.inf, "bvps_override": math.nan}, isolated_cli_settings)

    envelope = failure_envelope(FailureReasonCode.INVALID_PARAMETER, str(error), cause=error)

    assert envelope.parameters == ("eps_override",)
    assert envelope.errors is not None
    assert [item.parameters for item in envelope.errors] == [("eps_override",), ("bvps_override",)]
    assert [item.rule for item in envelope.errors] == ["graham-number.override_not_finite"] * 2
    assert envelope.errors[0].message == envelope.reason
    assert envelope.errors[1].message == "Invalid bvps_override: Financial override must be a finite number."


def test_arguments_json_cannot_carry_are_text_in_the_document(isolated_cli_settings: ProjectSettings) -> None:
    del isolated_cli_settings
    error = ActionParameterError(
        "{value} on {day} is not allowed.",
        parameters=("value",),
        rule="test.not_allowed",
        arguments={"value": math.inf, "day": date(2025, 12, 31), "ratio": 0.5, "count": 3},
    )

    envelope = failure_envelope(FailureReasonCode.INVALID_PARAMETER, str(error), cause=error)

    assert envelope.errors is not None
    assert envelope.errors[0].arguments == {"value": "inf", "day": "2025-12-31", "ratio": 0.5, "count": 3}
    assert envelope.errors[0].message == "inf on 2025-12-31 is not allowed."
    json.dumps(envelope.model_dump(mode="json"), allow_nan=False, ensure_ascii=False)


def test_a_plain_invalid_parameter_error_has_no_error_list() -> None:
    plain = InvalidParameterError("limit must be an integer.", parameters=("limit",))

    envelope = failure_envelope(FailureReasonCode.INVALID_PARAMETER, str(plain), cause=plain)

    assert envelope.errors is None
    assert envelope.parameters == ("limit",)


def test_a_single_rule_rejection_lists_itself() -> None:
    error = ActionParameterError("{tickers} must not be empty.", parameters=("tickers",), rule="watchlist.blank_ticker")

    envelope = failure_envelope(FailureReasonCode.INVALID_PARAMETER, str(error), cause=error)

    assert envelope.errors is not None
    assert [(item.rule, item.parameters, item.arguments) for item in envelope.errors] == [
        ("watchlist.blank_ticker", ("tickers",), {})
    ]


def test_the_error_list_belongs_to_invalid_parameter_only() -> None:
    with pytest.raises(ValueError, match="errors is set only for invalid_parameter"):
        FailureEnvelope(status="error", reason_code=FailureReasonCode.EXECUTION_ERROR, reason="x", errors=())
    with pytest.raises(ValueError, match="errors is set only for invalid_parameter"):
        FailureEnvelope.model_validate(
            {
                "status": "error",
                "reason_code": "invalid_parameter",
                "reason": "x",
                "parameters": ["a"],
                "errors": [],
            }
        )


def test_the_api_lists_every_error_with_its_rule_and_message(isolated_cli_settings: ProjectSettings) -> None:
    body = {
        "ticker": "KO",
        "method_id": GRAHAM_NUMBER.method_id,
        "selection": {"eps_override": "x", "bvps_override": "y"},
    }
    with client_for(isolated_cli_settings) as client:
        response = client.post("/v1/analyses", json=body, headers=AUTH)

    failure = response.json()
    assert response.status_code == 400
    assert failure["parameters"] == ["selection.eps_override"]
    assert [item["parameters"] for item in failure["errors"]] == [
        ["selection.eps_override"],
        ["selection.bvps_override"],
    ]
    assert failure["reason"] == failure["errors"][0]["message"]
    assert failure["errors"][0]["message"] == "Invalid selection.eps_override: Input should be a valid number"
    assert failure["errors"][1]["rule"] == "pydantic.float_type"


def test_the_api_lists_a_rule_with_its_named_values(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        response = client.post(
            "/v1/analyses",
            json={
                "ticker": "KO",
                "method_id": MOMENTUM.method_id,
                "selection": {"short_window": 50, "long_window": 20},
            },
            headers=AUTH,
        )

    failure = response.json()
    assert response.status_code == 400
    assert [item["rule"] for item in failure["errors"]] == ["momentum.window_order"]
    assert failure["errors"][0]["parameters"] == ["selection.short_window", "selection.long_window"]
    assert failure["errors"][0]["arguments"] == {"short_window_value": 50, "long_window_value": 20}
    assert failure["parameters"] == failure["errors"][0]["parameters"]


@pytest.mark.usefixtures("isolated_cli_settings")
def test_the_command_line_message_and_exit_code_are_those_of_the_first_error_and_the_json_gains_errors() -> None:
    arguments = ["watchlist", "add-selection", "graham-number", "Core", "KO", "--eps", "inf", "--bvps", "nan"]
    assert runner.invoke(app, ["watchlist", "create", "Core"]).exit_code == 0

    text = runner.invoke(app, arguments)
    structured = runner.invoke(app, [*arguments, "--json"])

    assert text.exit_code == 1
    assert text.stderr.strip() == "Invalid --eps: Financial override must be a finite number."
    document = json.loads(structured.stdout)
    assert structured.exit_code == 1
    assert (document["reason"], document["parameters"]) == (text.stderr.strip(), ["--eps"])
    assert [item["parameters"] for item in document["errors"]] == [["--eps"], ["--bvps"]]
    assert document["errors"][1]["message"] == "Invalid --bvps: Financial override must be a finite number."
    assert document["schema_version"] == 13


# --- Pre-checks join the list (R2) ---------------------------------------------------------------------------------


def _graham_rejection(fields: dict[str, object], settings: ProjectSettings) -> ActionParameterError:
    with pytest.raises(ActionParameterError) as caught:
        build_selection(ApplicationContext(settings=settings), GRAHAM_NUMBER.method_id, fields)
    return caught.value


@pytest.mark.parametrize(
    ("fields", "rule", "parameters", "message"),
    [
        (
            {"analysis_id": "x"},
            "pydantic.extra_forbidden",
            ("analysis_id",),
            "Invalid analysis_id: Extra inputs are not permitted",
        ),
        ({"as_of": " "}, "selection.as_of_empty", ("as_of",), "as_of must be non-empty when supplied."),
        (
            {"as_of": "tomorrow"},
            "selection.as_of_syntax",
            ("as_of",),
            "as_of must be YYYY-MM-DD or a valid timezone-aware ISO-8601 timestamp.",
        ),
        (
            {"as_of": datetime(2025, 1, 15, 12)},  # noqa: DTZ001 - the case under test
            "selection.as_of_offset",
            ("as_of",),
            "Timestamp as_of values must include an explicit timezone offset.",
        ),
        ({"as_of": 5}, "selection.as_of_type", ("as_of",), "as_of must be a date, a timestamp or text."),
        (
            {"eps_override": "x"},
            "pydantic.float_type",
            ("eps_override",),
            "Invalid eps_override: Input should be a valid number",
        ),
    ],
)
def test_a_single_rejection_keeps_its_rule_parameters_and_message(
    fields: dict[str, object],
    rule: str,
    parameters: tuple[str, ...],
    message: str,
    isolated_cli_settings: ProjectSettings,
) -> None:
    error = _graham_rejection(fields, isolated_cli_settings)

    assert (error.rule, error.parameters, str(error)) == (rule, parameters, message)
    assert [item.rule for item in error.errors] == [rule]


@pytest.mark.usefixtures("isolated_cli_settings")
@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("", "--as-of must be non-empty when supplied."),
        ("tomorrow", "--as-of must be YYYY-MM-DD or a valid timezone-aware ISO-8601 timestamp."),
        ("2025-01-15T12:00:00", "Timestamp --as-of values must include an explicit timezone offset."),
    ],
)
def test_the_command_line_message_and_exit_code_for_a_bad_as_of_are_unchanged(value: str, message: str) -> None:
    assert runner.invoke(app, ["watchlist", "create", "Core"]).exit_code == 0

    result = runner.invoke(app, ["watchlist", "add-selection", "momentum", "Core", "KO", "--as-of", value])

    assert result.exit_code == 1
    assert result.stderr.strip() == message


def test_an_invalid_as_of_text_and_invalid_windows_are_listed_in_field_order(
    isolated_cli_settings: ProjectSettings,
) -> None:
    error = _graham_rejection(
        {"analysis_id": "x", "eps_override": "x", "bvps_override": "y", "as_of": "tomorrow"}, isolated_cli_settings
    )

    assert [item.action_parameters for item in error.errors] == [
        ("analysis_id",),
        ("eps_override",),
        ("bvps_override",),
        ("as_of",),
    ]
    assert [item.rule for item in error.errors][-1] == "selection.as_of_syntax"


def test_the_api_lists_an_invalid_as_of_text_with_invalid_windows_in_field_order(
    isolated_cli_settings: ProjectSettings,
) -> None:
    with client_for(isolated_cli_settings) as client:
        response = client.post(
            "/v1/analyses",
            json={
                "ticker": "KO",
                "method_id": GRAHAM_NUMBER.method_id,
                "selection": {"as_of": "tomorrow", "eps_override": "x", "bvps_override": "y"},
            },
            headers=AUTH,
        )

    failure = response.json()
    assert response.status_code == 400
    assert [item["parameters"] for item in failure["errors"]] == [
        ["selection.eps_override"],
        ["selection.bvps_override"],
        ["selection.as_of"],
    ]
    assert failure["errors"][-1]["rule"] == "selection.as_of_syntax"
    assert failure["parameters"] == ["selection.eps_override"]


@pytest.mark.parametrize(
    ("method_id", "selection", "parameter", "rule"),
    [
        (
            GRAHAM_NUMBER.method_id,
            {"quote_override": 0},
            "selection.quote_override",
            "graham-number.quote_override_not_positive",
        ),
        (
            GRAHAM_GROWTH.method_id,
            {"expected_growth": 5, "aaa_yield_override": 4.5, "quote_override": -3},
            "selection.quote_override",
            "graham-growth.quote_override_not_positive",
        ),
        (
            GRAHAM_GROWTH.method_id,
            {"expected_growth": 5, "aaa_yield_override": 0},
            "selection.aaa_yield_override",
            "graham-growth.aaa_yield_override_not_positive",
        ),
    ],
)
def test_the_api_refuses_a_zero_or_negative_price_or_yield_override_as_an_invalid_parameter(
    isolated_cli_settings: ProjectSettings, method_id: str, selection: dict[str, object], parameter: str, rule: str
) -> None:
    body = {"ticker": "KO", "method_id": method_id, "selection": selection}
    with client_for(isolated_cli_settings) as client:
        response = client.post("/v1/analyses", json=body, headers=AUTH)

    failure = response.json()
    assert response.status_code == 400
    assert failure["reason_code"] == "invalid_parameter"
    assert failure["parameters"] == [parameter]
    assert [item["rule"] for item in failure["errors"]] == [rule]
