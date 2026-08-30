"""Direct CLI tests for FCF and earnings growth."""

from __future__ import annotations

import json
from dataclasses import replace
from unittest.mock import patch

from typer.testing import CliRunner

from src.cli import app
from src.data.financial.production import ProductionFinancialFactsProvider
from src.data.sec_edgar import SEC_PROVIDER_ID
from tests._cli_helpers import normalize_cli_output
from tests.analysis.fcf_earnings_growth.fixture_financial_facts_provider import (
    FixtureAnnualFinancialFactsProvider,
    annual_series,
)

runner = CliRunner()


def _provider() -> ProductionFinancialFactsProvider:
    facts = tuple(
        replace(
            fact,
            provider_id=SEC_PROVIDER_ID,
            provider_fact_id=f"fy-{fact.fiscal_year}:{fact.field_name.value}",
        )
        for fact in annual_series(range(2020, 2026))
    )
    return ProductionFinancialFactsProvider(sec_edgar=FixtureAnnualFinancialFactsProvider(facts))


def test_cli_fcf_growth_runs_concise_and_json_from_same_typed_path() -> None:
    with patch("src.cli._build_sec_production_provider", side_effect=[_provider(), _provider()]):
        concise = runner.invoke(app, ["fcf-growth", "acme"])
        json_result = runner.invoke(app, ["fcf-growth", "ACME", "--json"])

    assert concise.exit_code == 0
    assert "ACME — Free Cash Flow & Earnings Growth" in concise.output
    assert "Screen: PASS" in concise.output
    payload = json.loads(json_result.output)
    assert payload["ticker"] == "ACME"
    assert payload["classification"] == "pass"


def test_cli_fcf_growth_selects_per_share_classification_basis() -> None:
    with patch("src.cli._build_sec_production_provider", return_value=_provider()):
        result = runner.invoke(
            app,
            ["fcf-growth", "ACME", "--classification-basis", "fcf-per-share", "--json"],
        )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["policy"]["classification_basis"] == "fcf_per_share"
    assert payload["fcf_cagr"]["status"] == "ok"
    assert payload["fcf_per_share_cagr"]["status"] == "ok"


def test_cli_fcf_growth_rejects_invalid_classification_basis() -> None:
    result = runner.invoke(app, ["fcf-growth", "ACME", "--classification-basis", "per-company"])
    assert result.exit_code == 2
    assert "--classification-basis must be total-fcf or fcf-per-share" in normalize_cli_output(result.output)


def test_cli_fcf_growth_rejects_invalid_horizon_before_provider_setup() -> None:
    result = runner.invoke(app, ["fcf-growth", "ACME", "--growth-years", "2"])

    assert result.exit_code == 2
    assert "--growth-years must be 3, 4, or 5" in normalize_cli_output(result.output)


def test_cli_fcf_growth_modes_are_mutually_exclusive() -> None:
    result = runner.invoke(app, ["fcf-growth", "ACME", "--details", "--json"])

    assert result.exit_code == 2
    assert "Choose only one" in result.output


def test_cli_fcf_growth_accepts_hyphenated_forward_policy() -> None:
    with patch("src.cli._build_sec_production_provider", return_value=_provider()):
        result = runner.invoke(app, ["fcf-growth", "ACME", "--forward-policy", "hard-gate", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["policy"]["forward_policy"] == "hard_gate"
    assert payload["classification"] == "indeterminate"


def test_cli_fcf_growth_rejects_unapproved_provider_without_network_work() -> None:
    with patch("src.cli._build_sec_production_provider", return_value=_provider()):
        result = runner.invoke(app, ["fcf-growth", "ACME", "--data-provider", "massive"])

    assert result.exit_code == 1
    assert "INDETERMINATE" in result.output
    assert "does not have approved" in result.output
