"""CLI regression for non-positive Graham Growth Value comparison wording."""

from unittest.mock import patch

from typer.testing import CliRunner

from src.analysis.graham_value.input_resolver import GrahamInputResolver
from src.cli import app
from tests.analysis.graham_value.fixture_valuation_provider import (
    NOW,
    PROVIDER_ID,
    SECURITY_ID,
    FixtureValuationProvider,
)

runner = CliRunner()


def test_cli_growth_non_positive_value_explains_omitted_price_comparison() -> None:
    resolver = GrahamInputResolver(FixtureValuationProvider(), clock=lambda: NOW)

    with patch("src.cli._build_graham_resolver", return_value=resolver):
        result = runner.invoke(
            app,
            [
                "graham",
                SECURITY_ID,
                "--method",
                "growth",
                "--data-provider",
                PROVIDER_ID,
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
