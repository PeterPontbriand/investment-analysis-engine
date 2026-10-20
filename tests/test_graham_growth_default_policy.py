"""Focused tests for investor-facing Graham Growth provider defaults."""

from unittest.mock import ANY, MagicMock, patch

from typer.testing import CliRunner

from investment_analysis_engine.cli import app
from investment_analysis_engine.strategies.graham_growth.calculation import GrahamGrowthInputResolver
from tests._cli_helpers import isolated_cli_database, normalize_cli_output  # noqa: F401

runner = CliRunner()


def _growth_args(*extra: str) -> list[str]:
    return [
        "graham-growth",
        "KO",
        "--expected-growth",
        "5",
        "--aaa-yield",
        "4.5",
        *extra,
    ]


def test_growth_default_routes_sec_three_year_average_and_yahoo_quote() -> None:
    with (
        patch(
            "investment_analysis_engine.strategies.graham_growth.cli.build_graham_resolver", return_value=MagicMock()
        ) as mock_build,
        patch(
            "investment_analysis_engine.strategies.graham_growth.cli._run_graham_growth", return_value=("ok", 0)
        ) as mock_run,
    ):
        result = runner.invoke(app, _growth_args())

    assert result.exit_code == 0
    assert result.output.strip() == "ok"
    mock_build.assert_called_once_with(resolver_type=GrahamGrowthInputResolver, cache=ANY, clock=ANY)
    assert mock_run.call_args.kwargs["selection"].eps_basis == "three_year_average"


def test_growth_rejects_ttm_with_sec_before_provider_access() -> None:
    result = runner.invoke(
        app,
        _growth_args("--eps-basis", "ttm"),
    )

    assert result.exit_code == 1
    normalized = normalize_cli_output(result.output)
    assert "Invalid --eps-basis: Input should be 'three_year_average' or 'fiscal_year'" in normalized
    assert "--eps-basis" in normalized
