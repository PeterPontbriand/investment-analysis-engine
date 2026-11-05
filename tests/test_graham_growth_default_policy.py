"""Focused tests for investor-facing Graham Growth provider defaults."""

from unittest.mock import patch

import pytest
from pydantic import BaseModel
from typer.testing import CliRunner

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.application.analysis import AnalysisOutcome
from investment_analysis_engine.cli import app
from investment_analysis_engine.strategies.graham_growth.selection import GrahamGrowthSelection
from tests._cli_helpers import normalize_cli_output

pytestmark = pytest.mark.usefixtures("isolated_cli_settings")


class _Document(BaseModel):
    """A stand-in document."""


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
    outcome = AnalysisOutcome(
        document=_Document(), analysis_run_id=None, outcome=RunOutcome.COMPLETED, text_renderer=lambda _mode: "ok"
    )
    with patch(
        "investment_analysis_engine.strategies.graham_growth.cli.analyze_for_command", return_value=outcome
    ) as mock_run:
        result = runner.invoke(app, _growth_args())

    assert result.exit_code == 0
    assert result.output.strip() == "ok"
    selection = mock_run.call_args.args[1]
    assert isinstance(selection, GrahamGrowthSelection)
    assert selection.eps_basis == "three_year_average"


def test_growth_rejects_ttm_with_sec_before_provider_access() -> None:
    result = runner.invoke(
        app,
        _growth_args("--eps-basis", "ttm"),
    )

    assert result.exit_code == 1
    normalized = normalize_cli_output(result.output)
    assert "Invalid --eps-basis: Input should be 'three_year_average' or 'fiscal_year'" in normalized
    assert "--eps-basis" in normalized
