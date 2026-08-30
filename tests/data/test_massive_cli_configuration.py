"""CLI configuration tests for Massive-backed Graham analysis."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.data.massive.financial_facts import MassiveFinancialFactsAdapter

runner = CliRunner()


def test_massive_adapter_remains_constructible_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Preserve the provider contract: missing credentials do not break construction."""
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)

    adapter = MassiveFinancialFactsAdapter()

    assert adapter.is_configured is False


def test_cli_explicit_massive_missing_api_key_is_clean_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Report missing Massive access before misclassifying it as unavailable financial data."""
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)

    result = runner.invoke(
        app,
        [
            "graham",
            "KO",
            "--method",
            "growth",
            "--data-provider",
            "massive",
            "--expected-growth",
            "5",
            "--aaa-yield",
            "4.5",
        ],
    )

    assert result.exit_code == 1
    assert "Unable to start Graham analysis: Massive access is not configured." in result.output
    assert "Set MASSIVE_API_KEY and retry." in result.output
    assert "required financial data is unavailable" not in result.output
    assert "Traceback" not in result.output
