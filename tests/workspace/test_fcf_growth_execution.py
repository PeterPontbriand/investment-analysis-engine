"""Focused tests for the FCF/Earnings Growth execution adapter, using fake dependencies only."""

import socket
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from src.analysis.strategy.fcf_earnings_growth.analyzer import FCFEarningsGrowthAnalyzer
from src.analysis.strategy.fcf_earnings_growth.input_resolver import ProductionAnnualGrowthSeriesResolver
from src.analysis.strategy.fcf_earnings_growth.models import (
    Classification,
    FCFEarningsGrowthPolicy,
    FCFEarningsGrowthResult,
    ForwardEvidence,
    ForwardEvidenceStatus,
    TrendClassification,
)
from src.core.analysis_status import CalculationStatus
from src.core.metric_result import MetricResult, MetricStatus, ReasonCode
from src.data.instrument_profile import InstrumentKind
from src.data.sec_edgar import SEC_PROVIDER_ID
from src.evaluation.fixtures.fcf_earnings_growth import FixtureAnnualFinancialFactsProvider, annual_series
from src.evaluation.fixtures.instrument_profiles import (
    GOLDEN_ETF_TICKER,
    fixture_instrument_profile,
    fixture_known_etf_profile,
)
from src.workspace.fcf_growth_execution import FCFGrowthCapture, classify_fcf_growth_outcome, execute_fcf_growth
from src.workspace.models import RunOutcome

NOW = datetime(2026, 9, 18, 12, tzinfo=UTC)


def _resolver() -> ProductionAnnualGrowthSeriesResolver:
    facts = tuple(replace(fact, provider_id=SEC_PROVIDER_ID) for fact in annual_series(range(2020, 2026)))
    return ProductionAnnualGrowthSeriesResolver(FixtureAnnualFinancialFactsProvider(facts), clock=lambda: NOW)


def _ok_result() -> FCFEarningsGrowthResult:
    """A real, fully computed result from the fixture provider chain."""
    return FCFEarningsGrowthAnalyzer(_resolver()).run_analysis(
        ticker="ACME",
        policy=FCFEarningsGrowthPolicy(),
        currency="USD",
        as_of=None,
        provider_id=SEC_PROVIDER_ID,
        use_cache=True,
        effective_as_of=NOW,
        instrument_profile=None,
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


def test_classify_fcf_growth_outcome_ok_completes() -> None:
    assert classify_fcf_growth_outcome(_ok_result()) == RunOutcome.COMPLETED


def test_classify_fcf_growth_outcome_not_applicable() -> None:
    assert classify_fcf_growth_outcome(_not_applicable_result()) == RunOutcome.NOT_APPLICABLE


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (CalculationStatus.INPUT_UNAVAILABLE, RunOutcome.UNAVAILABLE),
        (CalculationStatus.INVALID_INPUT, RunOutcome.FAILED),
        (CalculationStatus.PROVIDER_ERROR, RunOutcome.FAILED),
    ],
)
def test_classify_fcf_growth_outcome_non_ok_statuses(status: CalculationStatus, expected: RunOutcome) -> None:
    assert classify_fcf_growth_outcome(_non_ok_result(status)) == expected


def test_execute_fcf_growth_delegates_with_the_composed_profile() -> None:
    resolver = _resolver()
    policy = FCFEarningsGrowthPolicy()
    composed = fixture_instrument_profile("ACME", kind=InstrumentKind.EQUITY, provider_value="EQUITY")
    canned = _ok_result()
    captured: dict[str, object] = {}

    def fake_run_analysis(  # noqa: PLR0913
        self: FCFEarningsGrowthAnalyzer,
        *,
        ticker: str,
        policy: FCFEarningsGrowthPolicy,
        currency: str,
        as_of: datetime | None,
        provider_id: str,
        use_cache: bool = True,
        effective_as_of: datetime | None = None,
        instrument_profile: object | None = None,
    ) -> FCFEarningsGrowthResult:
        del self
        captured.update(
            ticker=ticker,
            policy=policy,
            currency=currency,
            as_of=as_of,
            provider_id=provider_id,
            use_cache=use_cache,
            effective_as_of=effective_as_of,
            instrument_profile=instrument_profile,
        )
        return canned

    with (
        patch("src.workspace.fcf_growth_execution.compose_graham_profile", return_value=composed),
        patch.object(FCFEarningsGrowthAnalyzer, "run_analysis", fake_run_analysis),
    ):
        capture = execute_fcf_growth(
            resolver,
            "ACME",
            policy=policy,
            currency="USD",
            as_of=None,
            provider_id=SEC_PROVIDER_ID,
            use_cache=True,
            effective_as_of=NOW,
            provider=object(),
        )

    assert capture.result is canned
    assert capture.profile is composed
    assert capture.outcome is RunOutcome.COMPLETED
    assert captured == {
        "ticker": "ACME",
        "policy": policy,
        "currency": "USD",
        "as_of": None,
        "provider_id": SEC_PROVIDER_ID,
        "use_cache": True,
        "effective_as_of": NOW,
        "instrument_profile": composed,
    }


def test_known_etf_profile_is_not_applicable_through_the_real_analyzer() -> None:
    """The analyzer's own ETF short-circuit is exercised for real, not mocked away."""
    resolver = _resolver()
    etf_profile = fixture_known_etf_profile()

    with patch("src.workspace.fcf_growth_execution.compose_graham_profile", return_value=etf_profile):
        capture = execute_fcf_growth(
            resolver,
            GOLDEN_ETF_TICKER,
            policy=FCFEarningsGrowthPolicy(),
            currency="USD",
            as_of=None,
            provider_id=SEC_PROVIDER_ID,
            use_cache=True,
            effective_as_of=NOW,
            provider=object(),
        )

    assert capture.result.execution_status is CalculationStatus.NOT_APPLICABLE
    assert capture.outcome is RunOutcome.NOT_APPLICABLE


def test_partial_forward_evidence_is_preserved_unmodified() -> None:
    """Optional/partial metrics inside a completed result are not stripped or altered."""
    resolver = _resolver()

    with patch(
        "src.workspace.fcf_growth_execution.compose_graham_profile",
        return_value=fixture_instrument_profile("ACME", kind=InstrumentKind.EQUITY, provider_value="EQUITY"),
    ):
        capture = execute_fcf_growth(
            resolver,
            "ACME",
            policy=FCFEarningsGrowthPolicy(),
            currency="USD",
            as_of=None,
            provider_id=SEC_PROVIDER_ID,
            use_cache=True,
            effective_as_of=NOW,
            provider=object(),
        )

    assert capture.result.forward_evidence.status is ForwardEvidenceStatus.UNAVAILABLE
    assert capture.result.annual_observations


def test_no_network_access(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("FCF Growth execution adapter must not access the network.")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket.socket, "connect", reject_network)

    with patch(
        "src.workspace.fcf_growth_execution.compose_graham_profile",
        return_value=fixture_instrument_profile("ACME", kind=InstrumentKind.EQUITY, provider_value="EQUITY"),
    ):
        capture = execute_fcf_growth(
            _resolver(),
            "ACME",
            policy=FCFEarningsGrowthPolicy(),
            currency="USD",
            as_of=None,
            provider_id=SEC_PROVIDER_ID,
            use_cache=True,
            effective_as_of=NOW,
            provider=object(),
        )

    assert isinstance(capture, FCFGrowthCapture)
