"""Focused tests for the Graham Growth execution adapter, using fake dependencies only."""

import socket
from unittest.mock import patch

import pytest

from src.analysis.strategy.graham_growth.analyzer import GrahamGrowthAnalyzer
from src.analysis.strategy.graham_growth.calculation import (
    GrahamGrowthCalculationPolicy,
    GrahamGrowthInputResolver,
    GrahamGrowthValueResult,
    GrowthValueInputAssembly,
)
from src.analysis.strategy.graham_growth.config import GrahamGrowthConfig
from src.analysis.strategy.graham_growth.service import GrahamGrowthAnalysis
from src.core.analysis_status import CalculationStatus
from src.data.instrument_profile import InstrumentKind, InstrumentProfile
from src.evaluation.fixtures.graham import NOW, SECURITY_ID, FixtureFinancialFactsProvider
from src.evaluation.fixtures.instrument_profiles import fixture_instrument_profile
from src.workspace.graham_growth_execution import (
    GrahamGrowthCapture,
    classify_graham_growth_outcome,
    execute_graham_growth,
)
from src.workspace.models import RunOutcome

_POLICY = GrahamGrowthCalculationPolicy(base_pe=8.5, growth_multiplier=2.0, baseline_aaa_yield=4.4)


def _resolver() -> GrahamGrowthInputResolver:
    return GrahamGrowthInputResolver(FixtureFinancialFactsProvider(), clock=lambda: NOW)


def _profile(ticker: str = SECURITY_ID) -> InstrumentProfile:
    return fixture_instrument_profile(ticker, kind=InstrumentKind.EQUITY, provider_value="EQUITY")


def _assembly(status: CalculationStatus) -> GrowthValueInputAssembly:
    return GrowthValueInputAssembly(status=status, reason=None if status is CalculationStatus.OK else "fixture reason")


def _result(status: CalculationStatus, *, growth_value: float = 42.0) -> GrahamGrowthValueResult:
    if status is CalculationStatus.OK:
        return GrahamGrowthValueResult(status=status, growth_value=growth_value)
    return GrahamGrowthValueResult(status=status, reason="fixture reason")


def _analysis(
    assembly_status: CalculationStatus,
    result_status: CalculationStatus = CalculationStatus.OK,
    *,
    growth_value: float = 42.0,
    profile: InstrumentProfile | None = None,
) -> GrahamGrowthAnalysis:
    return GrahamGrowthAnalysis(
        ticker=SECURITY_ID,
        as_of=None,
        assembly=_assembly(assembly_status),
        result=_result(result_status, growth_value=growth_value),
        policy=_POLICY,
        margin_of_safety_percent=None,
        instrument_profile=profile,
    )


@pytest.mark.parametrize(
    ("assembly_status", "result_status", "expected"),
    [
        (CalculationStatus.OK, CalculationStatus.OK, RunOutcome.COMPLETED),
        (CalculationStatus.OK, CalculationStatus.INVALID_INPUT, RunOutcome.FAILED),
        (CalculationStatus.NOT_APPLICABLE, CalculationStatus.OK, RunOutcome.NOT_APPLICABLE),
        (CalculationStatus.INPUT_UNAVAILABLE, CalculationStatus.OK, RunOutcome.UNAVAILABLE),
        (CalculationStatus.INVALID_INPUT, CalculationStatus.OK, RunOutcome.FAILED),
        (CalculationStatus.PROVIDER_ERROR, CalculationStatus.OK, RunOutcome.FAILED),
    ],
)
def test_classify_graham_growth_outcome_matches_the_frozen_mapping(
    assembly_status: CalculationStatus, result_status: CalculationStatus, expected: RunOutcome
) -> None:
    analysis = _analysis(assembly_status, result_status)
    assert classify_graham_growth_outcome(analysis) == expected


def test_nonpositive_growth_value_is_a_completed_calculation_not_a_failure() -> None:
    """A nonpositive growth value is a valid financial signal, not an execution failure."""
    analysis = _analysis(CalculationStatus.OK, CalculationStatus.OK, growth_value=-3.5)
    assert classify_graham_growth_outcome(analysis) == RunOutcome.COMPLETED


def test_execute_graham_growth_delegates_and_falls_back_to_the_composed_profile() -> None:
    resolver = _resolver()
    config = GrahamGrowthConfig(expected_growth=5.0, aaa_yield_override=4.4)
    composed = _profile()
    canned = _analysis(CalculationStatus.OK)
    captured: dict[str, object] = {}

    def fake_run_analysis(
        self: GrahamGrowthAnalyzer, config: GrahamGrowthConfig, ticker: str | None = None
    ) -> GrahamGrowthAnalysis:
        captured["config"] = config
        captured["ticker"] = ticker
        captured["profile_supplied"] = self._instrument_profile
        captured["policy_supplied"] = self._policy
        return canned

    with (
        patch("src.workspace.graham_growth_execution.compose_graham_profile", return_value=composed),
        patch.object(GrahamGrowthAnalyzer, "run_analysis", fake_run_analysis),
    ):
        capture = execute_graham_growth(resolver, SECURITY_ID, config, _POLICY, object())

    assert capture.analysis is canned
    assert capture.profile is composed
    assert capture.outcome is RunOutcome.COMPLETED
    assert captured == {
        "config": config,
        "ticker": SECURITY_ID,
        "profile_supplied": composed,
        "policy_supplied": _POLICY,
    }


def test_execute_graham_growth_prefers_the_analysis_own_profile() -> None:
    resolver = _resolver()
    config = GrahamGrowthConfig(expected_growth=5.0, aaa_yield_override=4.4)
    composed = _profile()
    refined = _profile("KO")
    canned = _analysis(CalculationStatus.OK, profile=refined)

    with (
        patch("src.workspace.graham_growth_execution.compose_graham_profile", return_value=composed),
        patch.object(GrahamGrowthAnalyzer, "run_analysis", return_value=canned),
    ):
        capture = execute_graham_growth(resolver, SECURITY_ID, config, _POLICY, object())

    assert capture.profile is refined
    assert isinstance(capture, GrahamGrowthCapture)


def test_captured_analysis_retains_the_effective_policy() -> None:
    resolver = _resolver()
    config = GrahamGrowthConfig(expected_growth=5.0, aaa_yield_override=4.4)

    with patch("src.workspace.graham_growth_execution.compose_graham_profile", return_value=_profile()):
        capture = execute_graham_growth(resolver, SECURITY_ID, config, _POLICY, object())

    assert capture.analysis.policy == _POLICY


def test_no_network_access(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Graham Growth execution adapter must not access the network.")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket.socket, "connect", reject_network)

    config = GrahamGrowthConfig(expected_growth=5.0, aaa_yield_override=4.4)
    with patch("src.workspace.graham_growth_execution.compose_graham_profile", return_value=_profile()):
        capture = execute_graham_growth(_resolver(), SECURITY_ID, config, _POLICY, object())

    assert capture.analysis.ticker == SECURITY_ID
