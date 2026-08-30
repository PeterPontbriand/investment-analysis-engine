"""Cross-strategy presentation regression tests for Slice F-1 identity."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime

from src.analysis.fcf_earnings_growth import (
    FCFEarningsGrowthAnalyzer,
    FCFEarningsGrowthPolicy,
    ProductionAnnualGrowthSeriesResolver,
)
from src.analysis.fcf_earnings_growth.models import FCFEarningsGrowthResult
from src.analysis.graham_value.input_resolver import GrahamNumberInputAssembly, GrowthValueInputAssembly
from src.analysis.graham_value.models import GrahamGrowthValueResult, GrahamNumberResult
from src.analysis.momentum.momentum_analyzer import MomentumConfig, MomentumMetrics
from src.core.analysis_status import CalculationStatus
from src.core.constants import TrendStatus
from src.data.financial.production import ProductionFinancialFactsProvider
from src.data.financial.provenance import ResolvedInput, SourceKind
from src.data.sec_edgar import SEC_PROVIDER_ID
from src.data.security_identity import (
    SecurityIdentity,
    SecurityIdentityRequest,
    SecurityIdentityResolution,
    resolve_security_identity,
)
from src.reporting.fcf_earnings_growth import render_fcf_earnings_growth
from src.reporting.graham import (
    GrahamGrowthPresentation,
    GrahamNumberPresentation,
    render_graham_growth,
    render_graham_number,
)
from src.reporting.momentum import MomentumPresentation, render_momentum
from src.reporting.presentation import PresentationMode
from tests.analysis.fcf_earnings_growth.fixture_financial_facts_provider import (
    FixtureAnnualFinancialFactsProvider,
    annual_series,
)

NOW = datetime(2026, 8, 29, 20, 0, tzinfo=UTC)


class _IdentityProvider:
    """Return one deterministic identity or raise a configured failure."""

    def __init__(self, identity: SecurityIdentity | None, *, fails: bool = False) -> None:
        self._identity = identity
        self._fails = fails

    def resolve_security_identity(self, _request: SecurityIdentityRequest) -> SecurityIdentity | None:
        if self._fails:
            raise RuntimeError("simulated failure")
        return self._identity


def _resolution(ticker: str, name: str | None) -> SecurityIdentityResolution:
    identity = SecurityIdentity(
        ticker=ticker,
        instrument_name=name,
        provider_id="fixture_identity",
        resolved_at=NOW,
    )
    return resolve_security_identity(
        _IdentityProvider(identity),
        SecurityIdentityRequest(ticker, "fixture_identity"),
    )


def _input(field_name: str, value: float, units: str) -> ResolvedInput:
    return ResolvedInput(
        field_name=field_name,
        value=value,
        source_kind=SourceKind.OVERRIDE,
        resolved_at=NOW,
        units=units,
    )


def _momentum(identity: SecurityIdentityResolution, *, ticker: str = "ACME") -> MomentumPresentation:
    return MomentumPresentation(
        metrics=MomentumMetrics(
            ticker=ticker,
            status=TrendStatus.BULLISH,
            current_price=10.0,
            short_sma_val=9.0,
            long_sma_val=8.0,
            crossover_signal=1.0,
            timestamp=NOW,
        ),
        config=MomentumConfig(short_window=20, long_window=50),
        identity_resolution=identity,
    )


def _graham_number(identity: SecurityIdentityResolution) -> GrahamNumberPresentation:
    return GrahamNumberPresentation(
        ticker="ACME",
        assembly=GrahamNumberInputAssembly(
            status=CalculationStatus.OK,
            eps=_input("eps", 2.0, "currency_per_share"),
            bvps=_input("bvps", 10.0, "currency_per_share"),
        ),
        result=GrahamNumberResult(status=CalculationStatus.OK, maximum_indicated_price=21.213203435596427),
        identity_resolution=identity,
    )


def _graham_growth(identity: SecurityIdentityResolution) -> GrahamGrowthPresentation:
    return GrahamGrowthPresentation(
        ticker="ACME",
        assembly=GrowthValueInputAssembly(
            status=CalculationStatus.OK,
            eps=_input("eps", 2.0, "currency_per_share"),
            expected_growth=_input("expected_growth", 5.0, "percentage_points"),
            current_aaa_yield=_input("current_aaa_yield", 4.4, "percentage_points"),
        ),
        result=GrahamGrowthValueResult(status=CalculationStatus.OK, growth_value=37.0),
        base_pe=8.5,
        growth_multiplier=2.0,
        baseline_aaa_yield=4.4,
        identity_resolution=identity,
    )


def _fcf_result() -> FCFEarningsGrowthResult:
    facts = tuple(
        replace(fact, provider_id=SEC_PROVIDER_ID, provider_fact_id=f"id:{index}")
        for index, fact in enumerate(annual_series(range(2020, 2026)))
    )
    provider = ProductionFinancialFactsProvider(sec_edgar=FixtureAnnualFinancialFactsProvider(facts))
    analyzer = FCFEarningsGrowthAnalyzer(ProductionAnnualGrowthSeriesResolver(provider, clock=lambda: NOW))
    return analyzer.run_analysis(
        ticker="ACME",
        policy=FCFEarningsGrowthPolicy(),
        currency="USD",
        as_of=None,
        provider_id=SEC_PROVIDER_ID,
        effective_as_of=NOW,
    )


def test_available_name_uses_shared_heading_in_every_text_mode_and_strategy() -> None:
    identity = _resolution("ACME", "Acme Holdings, Inc.")
    expected = "Acme Holdings, Inc. (ACME) —"
    fcf_result = _fcf_result()

    for mode in (PresentationMode.CONCISE, PresentationMode.DETAILS, PresentationMode.DIAGNOSTICS):
        assert expected in render_momentum(_momentum(identity), mode)
        assert expected in render_graham_number(_graham_number(identity), mode)
        assert expected in render_graham_growth(_graham_growth(identity), mode)
        assert expected in render_fcf_earnings_growth(fcf_result, mode, identity)


def test_json_contracts_expose_same_snapshot_and_deliberate_versions() -> None:
    identity = _resolution("ACME", "Acme Holdings, Inc.")
    fcf_result = _fcf_result()

    documents = (
        json.loads(render_momentum(_momentum(identity), PresentationMode.JSON)),
        json.loads(render_graham_number(_graham_number(identity), PresentationMode.JSON)),
        json.loads(render_graham_growth(_graham_growth(identity), PresentationMode.JSON)),
        json.loads(render_fcf_earnings_growth(fcf_result, PresentationMode.JSON, identity)),
    )

    assert [document["schema_version"] for document in documents] == [2, 2, 2, 3]
    for document in documents:
        snapshot = document["security_identity"]
        assert snapshot["ticker"] == "ACME"
        assert snapshot["instrument_name"] == "Acme Holdings, Inc."
        assert snapshot["listing_venue"] is None
        assert snapshot["issuer_identifier"] is None
        assert snapshot["instrument_identifier"] is None
        assert snapshot["provider_id"] == "fixture_identity"
        assert snapshot["resolved_at"] == NOW.isoformat()


def test_unavailable_name_falls_back_to_ticker_for_every_strategy() -> None:
    identity = _resolution("ACME", None)
    fcf_result = _fcf_result()

    assert render_momentum(_momentum(identity)).startswith("ACME — Momentum")
    assert render_graham_number(_graham_number(identity)).startswith("ACME — Graham Number")
    assert render_graham_growth(_graham_growth(identity)).startswith("ACME — Graham Growth Value")
    assert render_fcf_earnings_growth(fcf_result, PresentationMode.CONCISE, identity).startswith(
        "ACME — Free Cash Flow & Earnings Growth"
    )


def test_non_company_instrument_name_is_used_by_momentum_heading() -> None:
    identity = _resolution("BTC-USD", "Bitcoin USD")

    rendered = render_momentum(_momentum(identity, ticker="BTC-USD"))

    assert rendered.startswith("Bitcoin USD (BTC-USD) — Momentum")


def test_lookup_failure_is_diagnostic_only_and_preserves_success_semantics() -> None:
    failure = resolve_security_identity(
        _IdentityProvider(None, fails=True),
        SecurityIdentityRequest("ACME", "fixture_identity"),
    )
    momentum = _momentum(failure)
    number = _graham_number(failure)
    growth = _graham_growth(failure)
    fcf_result = _fcf_result()

    momentum_payload = json.loads(render_momentum(momentum, PresentationMode.JSON))
    number_payload = json.loads(render_graham_number(number, PresentationMode.JSON))
    growth_payload = json.loads(render_graham_growth(growth, PresentationMode.JSON))
    fcf_payload = json.loads(render_fcf_earnings_growth(fcf_result, PresentationMode.JSON, failure))
    baseline_number_payload = json.loads(
        render_graham_number(_graham_number(_resolution("ACME", None)), PresentationMode.JSON)
    )

    assert momentum_payload["status"] == "BULLISH"
    assert number_payload["status"] == "ok"
    assert growth_payload["status"] == "ok"
    assert fcf_payload["execution_status"] == "ok"
    assert fcf_payload["classification"] == "pass"
    assert momentum_payload["warnings"] == []
    assert number_payload["warnings"] == baseline_number_payload["warnings"]
    assert momentum_payload["security_identity"]["instrument_name"] is None
    assert number_payload["security_identity"]["instrument_name"] is None
    assert growth_payload["security_identity"]["instrument_name"] is None
    assert fcf_payload["security_identity"]["instrument_name"] is None
    assert "provider_error" in render_momentum(momentum, PresentationMode.DIAGNOSTICS)
    assert "provider_error" in render_graham_number(number, PresentationMode.DIAGNOSTICS)
    assert "provider_error" in render_graham_growth(growth, PresentationMode.DIAGNOSTICS)
    assert "provider_error" in render_fcf_earnings_growth(
        fcf_result,
        PresentationMode.DIAGNOSTICS,
        failure,
    )
