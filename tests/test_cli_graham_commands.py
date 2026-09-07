"""Command migration, typed analyzer routing, and cleanup regressions."""

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from src.analysis.strategy.graham_growth.calculation import GrahamGrowthInputResolver
from src.analysis.strategy.graham_growth.config import GrahamGrowthConfig
from src.analysis.strategy.graham_number.calculation import GrahamNumberInputResolver
from src.analysis.strategy.graham_number.config import GrahamNumberConfig
from src.cli import app
from src.evaluation.fixtures.graham import NOW, PROVIDER_ID, SECURITY_ID, FixtureFinancialFactsProvider
from tests._cli_helpers import normalize_cli_output


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
    with patch("src.cli._build_graham_resolver") as build:
        result = CliRunner().invoke(app, arguments)
    assert result.exit_code == 2
    build.assert_not_called()


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
    with (
        patch("src.cli._build_graham_resolver") as build,
        patch("src.cli._run_" + command.replace("-", "_"), return_value=("ok", 0)) as run,
        patch("src.cli_support.SQLiteDatabase", side_effect=AssertionError("cache bypass")),
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
                "--eps-basis",
                " THREE_YEAR_AVERAGE ",
                "--as-of",
                "2025-12-31T12:00:00Z",
                "--no-cache",
                *(["-g", "5", "-y", "4.5"] if command == "graham-growth" else ["--bvps", "20"]),
            ],
        )
    assert result.exit_code == 0, result.output
    config = run.call_args.kwargs["config"]
    assert isinstance(config, GrahamGrowthConfig if command == "graham-growth" else GrahamNumberConfig)
    assert config.security_provider_id == "sec_edgar"
    assert config.quote_provider_id == "yfinance"
    assert config.eps_basis == "three_year_average"
    assert config.eps_override == 3.0
    assert config.quote_override == 20.0
    assert config.as_of == datetime(2025, 12, 31, 12, tzinfo=UTC)
    assert config.use_cache is False
    assert run.call_args.kwargs["ticker"] == "KO"
    build.assert_called_once()


@pytest.mark.parametrize("command", ["graham-number", "graham-growth"])
@pytest.mark.parametrize("mode", [[], ["--details"], ["--diagnostics"], ["--json"]])
def test_both_commands_execute_real_analyzers_with_fixture_evidence(command: str, mode: list[str]) -> None:
    resolver_type = GrahamGrowthInputResolver if command == "graham-growth" else GrahamNumberInputResolver
    resolver = resolver_type(FixtureFinancialFactsProvider(), clock=lambda: NOW)
    with (
        patch("src.cli._build_graham_resolver", return_value=resolver),
        patch("src.cli.YFinanceClient.resolve_security_identity", return_value=None),
        patch("src.cli.YFinanceClient.resolve_instrument_kind", return_value=None),
    ):
        result = CliRunner().invoke(app, [*_arguments(command), "--data-provider", PROVIDER_ID, "--no-cache", *mode])
    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    if mode == ["--json"]:
        payload = json.loads(result.stdout)
        assert payload["method"] == ("graham_number" if command == "graham-number" else "graham_growth_value")
    else:
        assert "Graham" in result.stdout


@pytest.mark.parametrize("command", ["graham-number", "graham-growth"])
@pytest.mark.parametrize(
    "error", [RuntimeError("private details"), typer.Exit(2), typer.BadParameter("invalid option")]
)
def test_command_exception_closes_cache_and_preserves_exit(command: str, error: Exception) -> None:
    database = MagicMock()
    with (
        patch("src.cli_support.SQLiteDatabase", return_value=database),
        patch("src.cli._build_graham_resolver", side_effect=error),
    ):
        result = CliRunner().invoke(app, _arguments(command))
    assert result.exit_code == (2 if isinstance(error, (typer.Exit, typer.BadParameter)) else 1)
    database.close.assert_called_once_with()
    assert "private details" not in result.output


@pytest.mark.parametrize("command", ["graham-number", "graham-growth"])
@pytest.mark.parametrize(
    "options", [["--eps-basis", "unknown"], ["--eps-basis", "ttm"], ["--details", "--json"], ["--as-of", "bad"]]
)
def test_usage_validation_precedes_resources(command: str, options: list[str]) -> None:
    with patch("src.cli_support.SQLiteDatabase") as database, patch("src.cli._build_graham_resolver") as build:
        result = CliRunner().invoke(app, [*_arguments(command), *options])
    assert result.exit_code == 2
    assert "input_value" not in result.output
    assert "validation error for" not in result.output
    database.assert_not_called()
    build.assert_not_called()


@pytest.mark.parametrize("command", ["graham-number", "graham-growth"])
@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
@pytest.mark.parametrize("option", ["--eps", "--current-price"])
def test_nonfinite_inputs_keep_typed_financial_outcomes(command: str, value: str, option: str) -> None:
    resolver_type = GrahamGrowthInputResolver if command == "graham-growth" else GrahamNumberInputResolver
    resolver = resolver_type(FixtureFinancialFactsProvider(), clock=lambda: NOW)
    with (
        patch("src.cli._build_graham_resolver", return_value=resolver),
        patch("src.cli.YFinanceClient.resolve_security_identity", return_value=None),
        patch("src.cli.YFinanceClient.resolve_instrument_kind", return_value=None),
    ):
        result = CliRunner().invoke(
            app,
            [
                *_arguments(command),
                "--data-provider",
                PROVIDER_ID,
                "--no-cache",
                "--json",
                f"{option}={value}",
            ],
        )
    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert payload["status"] == "invalid_input"
    assert payload["result"]["margin_of_safety_percent"] is None
    assert "NaN" not in result.stdout
    assert "Infinity" not in result.stdout


@pytest.mark.parametrize("command", ["graham-number", "graham-growth"])
def test_missing_ticker_names_the_invoking_command(command: str) -> None:
    arguments = _arguments(command)
    arguments.remove(SECURITY_ID)
    result = CliRunner().invoke(app, arguments)
    assert result.exit_code == 2
    assert f"financial-agents {command} TICKER" in normalize_cli_output(result.output)
