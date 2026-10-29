"""Focused tests for the FCF/Earnings Growth execution adapter, using fake dependencies only."""

import socket
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.metric_result import MetricResult, MetricStatus, ReasonCode
from investment_analysis_engine.data.instrument_profile import InstrumentKind
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from investment_analysis_engine.evaluation.fixtures.fcf_earnings_growth import (
    FixtureAnnualFinancialFactsProvider,
    annual_series,
)
from investment_analysis_engine.evaluation.fixtures.instrument_profiles import (
    GOLDEN_ETF_TICKER,
    fixture_instrument_profile,
    fixture_known_etf_profile,
)
from investment_analysis_engine.strategies.fcf_growth.analyzer import FCFEarningsGrowthAnalyzer
from investment_analysis_engine.strategies.fcf_growth.execution import (
    FCFGrowthCapture,
    execute_fcf_growth,
    from_fcf_growth_capture,
)
from investment_analysis_engine.strategies.fcf_growth.input_resolver import ProductionAnnualGrowthSeriesResolver
from investment_analysis_engine.strategies.fcf_growth.models import (
    FCFEarningsGrowthConfig,
    FCFEarningsGrowthPolicy,
    FCFEarningsGrowthResult,
    ForwardEvidence,
)
from investment_analysis_engine.strategies.fcf_growth.vocabulary import (
    Classification,
    ForwardEvidenceStatus,
    TrendClassification,
)
from tests._fcf_market_data import fcf_market_data

NOW = datetime(2026, 9, 18, 12, tzinfo=UTC)


def _resolver() -> ProductionAnnualGrowthSeriesResolver:
    facts = tuple(replace(fact, provider_id=SEC_PROVIDER_ID) for fact in annual_series(range(2020, 2026)))
    return ProductionAnnualGrowthSeriesResolver(FixtureAnnualFinancialFactsProvider(facts), clock=lambda: NOW)


def _ok_result() -> FCFEarningsGrowthResult:
    """A real, fully computed result from the fixture provider chain."""
    return FCFEarningsGrowthAnalyzer(_resolver(), fcf_market_data()).run_analysis(
        "ACME",
        FCFEarningsGrowthConfig(policy=FCFEarningsGrowthPolicy(), currency="USD"),
        AnalysisContext(as_of=None, executed_at=NOW, use_cache=True),
    )


def _non_ok_result(status: CalculationStatus) -> FCFEarningsGrowthResult:
    """Minimal valid result for a non-OK, non-not_applicable execution status."""
    unavailable = MetricResult.failure(MetricStatus.UNAVAILABLE, ReasonCode.CONSENSUS_UNAVAILABLE, "fixture reason")
    return FCFEarningsGrowthResult(
        ticker="ACME",
        effective_as_of=NOW,
        policy=FCFEarningsGrowthPolicy(),
        execution_status=status,
        classification=Classification.INDETERMINATE,
        classification_reason_code=ReasonCode.CONSENSUS_UNAVAILABLE,
        classification_reason="fixture reason",
        fcf_cagr=unavailable,
        fcf_per_share_cagr=unavailable,
        eps_cagr=unavailable,
        trend_classification=TrendClassification.INSUFFICIENT_OR_NONMEANINGFUL_GROWTH,
        fcf_yield=unavailable,
        forward_evidence=ForwardEvidence(
            status=ForwardEvidenceStatus.UNAVAILABLE,
            latest_actual_eps=None,
            fy1_consensus_eps=None,
            fy2_consensus_eps=None,
            actual_to_fy1_growth=unavailable,
            fy1_to_fy2_growth=unavailable,
            confirms_positive_growth=None,
        ),
    )


def _not_applicable_result() -> FCFEarningsGrowthResult:
    """Minimal valid result for execution_status=not_applicable (the ETF shape)."""
    not_applicable = MetricResult.failure(
        MetricStatus.NOT_APPLICABLE, ReasonCode.INSTRUMENT_KIND_NOT_APPLICABLE, "fixture reason"
    )
    return FCFEarningsGrowthResult(
        ticker="ACME",
        effective_as_of=NOW,
        policy=FCFEarningsGrowthPolicy(),
        execution_status=CalculationStatus.NOT_APPLICABLE,
        classification=Classification.INDETERMINATE,
        classification_reason_code=ReasonCode.INSTRUMENT_KIND_NOT_APPLICABLE,
        classification_reason="fixture reason",
        fcf_cagr=not_applicable,
        fcf_per_share_cagr=not_applicable,
        eps_cagr=not_applicable,
        trend_classification=TrendClassification.INSUFFICIENT_OR_NONMEANINGFUL_GROWTH,
        fcf_yield=not_applicable,
        forward_evidence=ForwardEvidence(
            status=ForwardEvidenceStatus.UNAVAILABLE,
            latest_actual_eps=None,
            fy1_consensus_eps=None,
            fy2_consensus_eps=None,
            actual_to_fy1_growth=not_applicable,
            fy1_to_fy2_growth=not_applicable,
            confirms_positive_growth=None,
        ),
    )


def _outcome_of(result: FCFEarningsGrowthResult) -> RunOutcome:
    profile = fixture_instrument_profile("ACME", kind=InstrumentKind.EQUITY, provider_value="EQUITY")
    return from_fcf_growth_capture(FCFGrowthCapture(result, profile)).outcome


def test_fcf_growth_outcome_ok_completes() -> None:
    assert _outcome_of(_ok_result()) is RunOutcome.COMPLETED


def test_fcf_growth_outcome_not_applicable() -> None:
    assert _outcome_of(_not_applicable_result()) is RunOutcome.NOT_APPLICABLE


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (CalculationStatus.INPUT_UNAVAILABLE, RunOutcome.UNAVAILABLE),
        (CalculationStatus.INVALID_INPUT, RunOutcome.FAILED),
        (CalculationStatus.PROVIDER_ERROR, RunOutcome.FAILED),
    ],
)
def test_fcf_growth_outcome_non_ok_statuses(status: CalculationStatus, expected: RunOutcome) -> None:
    assert _outcome_of(_non_ok_result(status)) is expected


def test_execute_fcf_growth_delegates_with_the_composed_profile() -> None:
    resolver = _resolver()
    policy = FCFEarningsGrowthPolicy()
    composed = fixture_instrument_profile("ACME", kind=InstrumentKind.EQUITY, provider_value="EQUITY")
    canned = _ok_result()
    captured: dict[str, object] = {}

    def fake_run_analysis(
        self: FCFEarningsGrowthAnalyzer, ticker: str, config: FCFEarningsGrowthConfig, context: AnalysisContext
    ) -> FCFEarningsGrowthResult:
        del self
        captured.update(ticker=ticker, config=config, context=context)
        return canned

    with (
        patch(
            "investment_analysis_engine.strategies.fcf_growth.execution.compose_graham_profile", return_value=composed
        ),
        patch.object(FCFEarningsGrowthAnalyzer, "run_analysis", fake_run_analysis),
    ):
        capture = execute_fcf_growth(
            resolver,
            "ACME",
            config=FCFEarningsGrowthConfig(policy=policy, currency="USD"),
            as_of=None,
            executed_at=NOW,
            use_cache=True,
            provider=object(),
            market_data=fcf_market_data(),
        )

    assert capture.result is canned
    assert capture.profile is composed
    assert from_fcf_growth_capture(capture).outcome is RunOutcome.COMPLETED
    assert captured == {
        "ticker": "ACME",
        "config": FCFEarningsGrowthConfig(policy=policy, currency="USD"),
        "context": AnalysisContext(as_of=None, executed_at=NOW, use_cache=True, instrument_profile=composed),
    }


def test_known_etf_profile_is_not_applicable_through_the_real_analyzer() -> None:
    """The analyzer's own ETF short-circuit is exercised for real, not mocked away."""
    resolver = _resolver()
    etf_profile = fixture_known_etf_profile()

    with patch(
        "investment_analysis_engine.strategies.fcf_growth.execution.compose_graham_profile", return_value=etf_profile
    ):
        capture = execute_fcf_growth(
            resolver,
            GOLDEN_ETF_TICKER,
            config=FCFEarningsGrowthConfig(policy=FCFEarningsGrowthPolicy(), currency="USD"),
            as_of=None,
            executed_at=NOW,
            use_cache=True,
            provider=object(),
            market_data=fcf_market_data(),
        )

    assert capture.result.execution_status is CalculationStatus.NOT_APPLICABLE
    assert from_fcf_growth_capture(capture).outcome is RunOutcome.NOT_APPLICABLE


def test_partial_forward_evidence_is_preserved_unmodified() -> None:
    """Optional/partial metrics inside a completed result are not stripped or altered."""
    resolver = _resolver()

    with patch(
        "investment_analysis_engine.strategies.fcf_growth.execution.compose_graham_profile",
        return_value=fixture_instrument_profile("ACME", kind=InstrumentKind.EQUITY, provider_value="EQUITY"),
    ):
        capture = execute_fcf_growth(
            resolver,
            "ACME",
            config=FCFEarningsGrowthConfig(policy=FCFEarningsGrowthPolicy(), currency="USD"),
            as_of=None,
            executed_at=NOW,
            use_cache=True,
            provider=object(),
            market_data=fcf_market_data(),
        )

    assert capture.result.forward_evidence.status is ForwardEvidenceStatus.UNAVAILABLE
    assert capture.result.annual_observations


def test_no_network_access(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("FCF Growth execution adapter must not access the network.")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket.socket, "connect", reject_network)

    with patch(
        "investment_analysis_engine.strategies.fcf_growth.execution.compose_graham_profile",
        return_value=fixture_instrument_profile("ACME", kind=InstrumentKind.EQUITY, provider_value="EQUITY"),
    ):
        capture = execute_fcf_growth(
            _resolver(),
            "ACME",
            config=FCFEarningsGrowthConfig(policy=FCFEarningsGrowthPolicy(), currency="USD"),
            as_of=None,
            executed_at=NOW,
            use_cache=True,
            provider=object(),
            market_data=fcf_market_data(),
        )

    assert isinstance(capture, FCFGrowthCapture)
