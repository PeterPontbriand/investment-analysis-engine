"""Direct CLI tests for FCF and earnings growth."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.data.financial.production import ProductionFinancialFactsProvider
from src.data.instrument_profile import InstrumentKind, InstrumentProfile
from src.data.sec_edgar import SEC_PROVIDER_ID
from src.evaluation.fixtures.fcf_earnings_growth import (
    FixtureAnnualFinancialFactsProvider,
    annual_series,
)
from src.evaluation.fixtures.instrument_profiles import fixture_instrument_profile
from tests._cli_helpers import normalize_cli_output

runner = CliRunner()


@pytest.fixture(autouse=True)
def disable_live_instrument_profile_resolution() -> Iterator[None]:
    """Keep direct FCF CLI tests independent from current provider metadata."""

    def unknown_profile(ticker: str, **_arguments: object) -> InstrumentProfile:
        return InstrumentProfile(ticker=ticker, identity=None, kind_evidence=None, diagnostics=())

    with patch("src.cli._compose_analysis_profile", side_effect=unknown_profile):
        yield


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


def test_cli_fcf_growth_known_etf_is_successful_not_applicable_without_fact_resolution() -> None:
    provider = _provider()
    profile = fixture_instrument_profile(
        "FLSW",
        kind=InstrumentKind.ETF,
        provider_value="ETF",
        instrument_name="Franklin FTSE Switzerland ETF",
    )
    with (
        patch("src.cli._build_sec_production_provider", return_value=provider),
        patch("src.cli._compose_analysis_profile", return_value=profile),
        patch.object(provider, "fetch_facts", wraps=provider.fetch_facts) as fetch_facts,
    ):
        result = runner.invoke(app, ["fcf-growth", "FLSW", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["execution_status"] == "not_applicable"
    assert payload["classification"] == "indeterminate"
    assert payload["classification_reason_code"] == "instrument_kind_not_applicable"
    assert payload["security_identity"]["instrument_name"] == "Franklin FTSE Switzerland ETF"
    assert payload["instrument_kind"]["kind"] == "etf"
    assert payload["annual_observations"] == []
    fetch_facts.assert_not_called()


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
