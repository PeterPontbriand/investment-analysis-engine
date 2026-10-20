"""CLI regression for non-positive Graham Growth Value comparison wording."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from investment_analysis_engine.cli import app
from investment_analysis_engine.evaluation.fixtures.graham import (
    SECURITY_ID,
)
from tests._sec_labeled_graham import sec_labeled_growth_resolver

pytestmark = pytest.mark.usefixtures("isolated_cli_settings", "stub_yahoo_identity_metadata")

runner = CliRunner()


def test_cli_growth_non_positive_value_explains_omitted_price_comparison() -> None:
    resolver = sec_labeled_growth_resolver()

    with patch("investment_analysis_engine.strategies.graham_growth.cli.build_graham_resolver", return_value=resolver):
        result = runner.invoke(
            app,
            [
                "graham-growth",
                SECURITY_ID,
                "--eps",
                "-1.5",
                "--expected-growth",
                "12.5",
                "--aaa-yield",
                "6.73",
            ],
        )

    assert result.exit_code == 0
    assert "Graham Growth Value: -" in result.output
    assert "Price comparison: unavailable (Graham growth value is non-positive)" in result.output
    assert "Warning: The Graham growth value is non-positive; percentage price comparison is omitted." in result.output
