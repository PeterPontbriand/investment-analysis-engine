"""Focused tests for investor-facing Graham Growth provider defaults."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli import GrahamCliMethod, app
from src.data.financial.providers import MASSIVE_PROVIDER_ID, SEC_PROVIDER_ID, YFINANCE_PROVIDER_ID
from tests._cli_helpers import normalize_cli_output

runner = CliRunner()


def _growth_args(*extra: str) -> list[str]:
    return [
        "graham",
        "KO",
        "--method",
        "growth",
        "--expected-growth",
        "5",
        "--aaa-yield",
        "4.5",
        *extra,
    ]


def test_growth_default_routes_sec_three_year_average_and_yahoo_quote() -> None:
    with (
        patch("src.cli._build_graham_resolver", return_value=MagicMock()) as mock_build,
        patch("src.cli._run_graham_growth", return_value=("ok", 0)) as mock_run,
    ):
        result = runner.invoke(app, _growth_args())

    assert result.exit_code == 0
    assert result.output.strip() == "ok"
    mock_build.assert_called_once_with(method=GrahamCliMethod.GROWTH, data_provider=SEC_PROVIDER_ID)
    assert mock_run.call_args.kwargs["security_provider_id"] == SEC_PROVIDER_ID
    assert mock_run.call_args.kwargs["quote_provider_id"] == YFINANCE_PROVIDER_ID
    assert mock_run.call_args.kwargs["eps_basis"] == "three_year_average"


def test_growth_explicit_massive_routes_ttm_and_massive_quote() -> None:
    with (
        patch("src.cli._build_graham_resolver", return_value=MagicMock()) as mock_build,
        patch("src.cli._run_graham_growth", return_value=("ok", 0)) as mock_run,
    ):
        result = runner.invoke(app, _growth_args("--data-provider", "massive"))

    assert result.exit_code == 0
    mock_build.assert_called_once_with(method=GrahamCliMethod.GROWTH, data_provider=MASSIVE_PROVIDER_ID)
    assert mock_run.call_args.kwargs["security_provider_id"] == MASSIVE_PROVIDER_ID
    assert mock_run.call_args.kwargs["quote_provider_id"] == MASSIVE_PROVIDER_ID
    assert mock_run.call_args.kwargs["eps_basis"] == "ttm"


def test_growth_rejects_ttm_with_sec_before_provider_access() -> None:
    result = runner.invoke(
        app,
        _growth_args("--data-provider", "sec_edgar", "--eps-basis", "ttm"),
    )

    assert result.exit_code == 2
    normalized = normalize_cli_output(result.output)
    assert "SEC EDGAR Growth analysis supports --eps-basis three_year_average only" in normalized
    assert "use --data-provider massive for TTM EPS" in normalized


def test_growth_rejects_three_year_average_with_massive_before_provider_access() -> None:
    result = runner.invoke(
        app,
        _growth_args("--data-provider", "massive", "--eps-basis", "three_year_average"),
    )

    assert result.exit_code == 2
    normalized = normalize_cli_output(result.output)
    assert "Massive Growth analysis supports --eps-basis ttm only" in normalized
    assert "use --data-provider sec_edgar for three-year-average EPS" in normalized
