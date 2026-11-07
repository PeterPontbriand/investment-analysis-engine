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
from investment_analysis_engine.strategy_wiring import GRAHAM_NUMBER, MOMENTUM
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


def test_the_api_lists_every_error_with_its_values_and_a_non_finite_value_as_text(
    isolated_cli_settings: ProjectSettings,
) -> None:
    body = (
        b'{"ticker": "KO", "method_id": "%s", "selection": {"eps_override": Infinity, "bvps_override": NaN}}'
        % GRAHAM_NUMBER.method_id.encode()
    )
    with client_for(isolated_cli_settings) as client:
        response = client.post("/v1/analyses", content=body, headers={**AUTH, "Content-Type": "application/json"})

    failure = response.json()
    assert response.status_code == 400
    assert failure["parameters"] == ["selection.eps_override"]
    assert [item["parameters"] for item in failure["errors"]] == [
        ["selection.eps_override"],
        ["selection.bvps_override"],
    ]
    assert failure["reason"] == failure["errors"][0]["message"]
    assert (
        failure["errors"][0]["message"] == "Invalid selection.eps_override: Financial override must be a finite number."
    )
    assert failure["errors"][0]["rule"] == "graham-number.override_not_finite"


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
    assert document["schema_version"] == 12
