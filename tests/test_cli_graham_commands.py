"""Command migration, typed analyzer routing, and cleanup regressions."""

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from src.cli import app
from src.core.operator_errors import InvalidParameterError
from src.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from src.evaluation.fixtures.graham import SECURITY_ID
from src.strategies.graham_growth import cli as graham_growth_cli
from src.strategies.graham_growth.selection import GrahamGrowthSelection
from src.strategies.graham_number import cli as graham_number_cli
from src.strategies.graham_number.selection import GrahamNumberSelection
from tests._cli_helpers import normalize_cli_output
from tests._sec_labeled_graham import sec_labeled_growth_resolver, sec_labeled_number_resolver

_STRATEGY_CLI = {"graham-number": graham_number_cli, "graham-growth": graham_growth_cli}


def _arguments(command: str) -> list[str]:
    return [command, SECURITY_ID, *(["-g", "5", "-y", "4.5"] if command == "graham-growth" else [])]


@pytest.mark.parametrize(
    "arguments",
    [
        ["graham", "KO"],
        ["graham-number", "KO", "--method", "number"],
        ["graham-number", "KO", "-m", "number"],
        ["graham-growth", "KO", "--method", "growth"],
        ["graham-number", "KO", "--aaa-yield", "4.5"],
    ],
)
def test_removed_commands_and_options_fail_before_composition(arguments: list[str]) -> None:
    with (
        patch("src.strategies.graham_number.cli.build_graham_resolver") as build_number,
        patch("src.strategies.graham_growth.cli.build_graham_resolver") as build_growth,
    ):
        result = CliRunner().invoke(app, arguments)
    assert result.exit_code == 2
    build_number.assert_not_called()
    build_growth.assert_not_called()


@pytest.mark.parametrize("command", ["graham-number", "graham-growth"])
def test_help_exposes_only_applicable_options(command: str) -> None:
    result = CliRunner().invoke(app, [command, "--help"])
    assert result.exit_code == 0
    output = normalize_cli_output(result.output)
    assert "--method" not in output
    assert "--quote-provider" not in output
    assert ("--bvps" in output) == (command == "graham-number")
    assert ("--expected-growth" in output) == (command == "graham-growth")
    assert ("--aaa-yield" in output) == (command == "graham-growth")


@pytest.mark.parametrize("command", ["graham-number", "graham-growth"])
def test_aliases_and_normalized_config_reach_execution(command: str) -> None:
    module = _STRATEGY_CLI[command]
    with (
        patch.object(module, "build_graham_resolver") as build,
        patch.object(module, f"_run_{command.replace('-', '_')}", return_value=("ok", 0)) as run,
        patch("src.cli_support.ensure_database_ready", side_effect=AssertionError("cache bypass")),
    ):
        result = CliRunner().invoke(
            app,
            [
                command,
                "-t",
                " ko ",
                "-e",
                "3",
                "-p",
                "20",
                "--data-provider",
                " SEC_EDGAR ",
                "--as-of",
                "2025-12-31T12:00:00Z",
                "--no-cache",
                *(
                    ["-g", "5", "-y", "4.5", "--eps-basis", " THREE_YEAR_AVERAGE "]
                    if command == "graham-growth"
                    else ["--bvps", "20"]
                ),
            ],
        )
    assert result.exit_code == 0, result.output
    selection = run.call_args.kwargs["selection"]
    assert isinstance(selection, GrahamGrowthSelection if command == "graham-growth" else GrahamNumberSelection)
    assert selection.security_provider_id == "sec_edgar"
    assert selection.quote_provider_id == "yfinance"
    if isinstance(selection, GrahamGrowthSelection):
        assert selection.eps_basis == "three_year_average"
    assert selection.eps_override == 3.0
    assert selection.quote_override == 20.0
    assert selection.as_of == datetime(2025, 12, 31, 12, tzinfo=UTC)
    assert selection.use_cache is False
    assert run.call_args.kwargs["ticker"] == "KO"
    build.assert_called_once()


@pytest.mark.parametrize("command", ["graham-number", "graham-growth"])
@pytest.mark.parametrize("mode", [[], ["--details"], ["--diagnostics"], ["--json"]])
def test_both_commands_execute_real_analyzers_with_fixture_evidence(command: str, mode: list[str]) -> None:
    resolver = sec_labeled_growth_resolver() if command == "graham-growth" else sec_labeled_number_resolver()
    with (
        patch(f"src.strategies.{command.replace('-', '_')}.cli.build_graham_resolver", return_value=resolver),
        patch("src.data.yfinance.client.YFinanceClient.resolve_security_identity", return_value=None),
        patch("src.data.yfinance.client.YFinanceClient.resolve_instrument_kind", return_value=None),
    ):
        result = CliRunner().invoke(
            app, [*_arguments(command), "--data-provider", SEC_PROVIDER_ID, "--no-cache", *mode]
        )
    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    if mode == ["--json"]:
        payload = json.loads(result.stdout)
        assert payload["method"] == ("graham_number" if command == "graham-number" else "graham_growth_value")
    else:
        assert "Graham" in result.stdout


@pytest.mark.parametrize("command", ["graham-number", "graham-growth"])
@pytest.mark.parametrize(
    "error",
    [RuntimeError("private details"), typer.Exit(2), InvalidParameterError("invalid option", parameters=("--option",))],
)
def test_command_exception_closes_cache_and_preserves_exit(command: str, error: Exception) -> None:
    database = MagicMock()
    with (
        patch("src.cli_support.SQLiteDatabase", return_value=database),
        patch("src.cli_support.ensure_database_ready"),
        patch(f"src.strategies.{command.replace('-', '_')}.cli.build_graham_resolver", side_effect=error),
    ):
        result = CliRunner().invoke(app, _arguments(command))
    assert result.exit_code == (2 if isinstance(error, typer.Exit) else 1)
    database.close.assert_called_once_with()
    assert "private details" not in result.output


@pytest.mark.parametrize("command", ["graham-number", "graham-growth"])
@pytest.mark.parametrize("options", [["--details", "--json"], ["--as-of", "bad"]])
def test_usage_validation_precedes_resources(command: str, options: list[str]) -> None:
    with (
        patch("src.cli_support.SQLiteDatabase") as database,
        patch(f"src.strategies.{command.replace('-', '_')}.cli.build_graham_resolver") as build,
    ):
        result = CliRunner().invoke(app, [*_arguments(command), *options])
    _assert_usage_error_without_resources(result.exit_code, result.output, database, build)


@pytest.mark.parametrize("options", [["--eps-basis", "unknown"], ["--eps-basis", "ttm"]])
def test_graham_growth_basis_validation_precedes_resources(options: list[str]) -> None:
    with (
        patch("src.cli_support.SQLiteDatabase") as database,
        patch("src.strategies.graham_growth.cli.build_graham_resolver") as build,
    ):
        result = CliRunner().invoke(app, [*_arguments("graham-growth"), *options])
    _assert_usage_error_without_resources(result.exit_code, result.output, database, build)


def _assert_usage_error_without_resources(exit_code: int, output: str, database: MagicMock, build: MagicMock) -> None:
    assert exit_code == 1
    assert "input_value" not in output
    assert "validation error for" not in output
    assert "errors.pydantic.dev" not in output
    database.assert_not_called()
    build.assert_not_called()


@pytest.mark.parametrize("basis", ["three_year_average", "ttm"])
def test_graham_number_has_no_eps_basis_option(basis: str) -> None:
    with (
        patch("src.cli_support.SQLiteDatabase") as database,
        patch("src.strategies.graham_number.cli.build_graham_resolver") as build,
    ):
        result = CliRunner().invoke(app, [*_arguments("graham-number"), "--eps-basis", basis])
    assert result.exit_code == 2
    assert "No such option: --eps-basis" in normalize_cli_output(result.output)
    database.assert_not_called()
    build.assert_not_called()
