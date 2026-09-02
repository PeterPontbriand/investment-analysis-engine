"""Execution-boundary tests for the FCF and earnings-growth strategy."""

from __future__ import annotations

import json
from dataclasses import replace

from src.analysis.fcf_earnings_growth import (
    FCFEarningsGrowthAnalyzer,
    FCFEarningsGrowthPolicy,
    ForwardPolicy,
    ProductionAnnualGrowthSeriesResolver,
)
from src.analysis.fcf_earnings_growth.models import Classification, MetricStatus, ReasonCode
from src.data.financial.production import ProductionFinancialFactsProvider
from src.data.sec_edgar import SEC_PROVIDER_ID
from src.evaluation.fixtures.fcf_earnings_growth import (
    FixtureAnnualFinancialFactsProvider,
    annual_series,
)
from src.reporting.fcf_earnings_growth import render_fcf_earnings_growth
from src.reporting.presentation import PresentationMode
from tests.analysis.fcf_earnings_growth.test_fcf_earnings_growth_input_resolver import NOW


def _analyzer() -> FCFEarningsGrowthAnalyzer:
    facts = tuple(
        replace(
            fact,
            provider_id=SEC_PROVIDER_ID,
            provider_fact_id=f"fy-{fact.fiscal_year}:{fact.field_name.value}",
        )
        for fact in annual_series(range(2020, 2026))
    )
    provider = ProductionFinancialFactsProvider(sec_edgar=FixtureAnnualFinancialFactsProvider(facts))
    resolver = ProductionAnnualGrowthSeriesResolver(provider, clock=lambda: NOW)
    return FCFEarningsGrowthAnalyzer(resolver)


def test_analyzer_composes_approved_history_into_canonical_result() -> None:
    result = _analyzer().run_analysis(
        ticker="acme",
        policy=FCFEarningsGrowthPolicy(),
        currency="USD",
        as_of=None,
        provider_id=SEC_PROVIDER_ID,
        effective_as_of=NOW,
    )

    assert result.ticker == "ACME"
    assert result.classification is Classification.PASS
    assert result.selected_horizon_years == 5
    assert result.selected_observation_count == 6
    assert result.fcf_cagr.status is MetricStatus.OK
    assert result.eps_cagr.status is MetricStatus.OK
    assert result.fcf_yield.status is MetricStatus.UNAVAILABLE
    assert result.fcf_yield.reason_code is ReasonCode.MARKET_CAP_UNAVAILABLE
    assert result.market_capitalization is None


def test_hard_gate_is_indeterminate_when_unapproved_consensus_is_unavailable() -> None:
    result = _analyzer().run_analysis(
        ticker="ACME",
        policy=FCFEarningsGrowthPolicy(forward_policy=ForwardPolicy.HARD_GATE),
        currency="USD",
        as_of=None,
        provider_id=SEC_PROVIDER_ID,
        effective_as_of=NOW,
    )

    assert result.classification is Classification.INDETERMINATE
    assert result.classification_reason_code is ReasonCode.CONSENSUS_UNAVAILABLE


def test_presenter_modes_share_result_and_json_has_null_not_nan() -> None:
    result = _analyzer().run_analysis(
        ticker="ACME",
        policy=FCFEarningsGrowthPolicy(),
        currency="USD",
        as_of=None,
        provider_id=SEC_PROVIDER_ID,
        effective_as_of=NOW,
    )

    concise = render_fcf_earnings_growth(result, PresentationMode.CONCISE)
    details = render_fcf_earnings_growth(result, PresentationMode.DETAILS)
    diagnostics = render_fcf_earnings_growth(result, PresentationMode.DIAGNOSTICS)
    document = render_fcf_earnings_growth(result, PresentationMode.JSON)
    payload = json.loads(document)

    expected_lines = ["ACME — Free Cash Flow & Earnings Growth", "Screen: PASS", "Period: FY2020–FY2025"]
    positions = [concise.index(line) for line in expected_lines]
    assert positions == sorted(positions)
    assert "Free cash flow CAGR:" in concise
    assert "FCF per diluted share CAGR:" in concise
    assert "Classification basis: Total company free cash flow" in concise
    assert "Diluted EPS CAGR:" in concise
    assert "Limitation:" in concise
    assert "Details" in details
    assert "derivation: operating_cash_flow - normalized_capital_expenditures" in details
    assert "derivation: free_cash_flow / weighted_average_diluted_shares" in details
    assert "Diagnostics" in diagnostics
    assert "provider/success" in diagnostics
    assert payload["schema_version"] == 4
    assert payload["result_schema_version"] == 3
    assert payload["security_identity"]["instrument_name"] is None
    assert payload["strategy_id"] == "fcf_earnings_growth"
    assert payload["market_capitalization"] is None
    assert payload["fcf_yield"]["value"] is None
    assert payload["fcf_per_share_cagr"]["status"] == "ok"
    assert "NaN" not in document
