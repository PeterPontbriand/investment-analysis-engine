"""Focused tests for the Graham Number execution adapter, using fake dependencies only."""

import socket
from unittest.mock import patch

import pytest

from src.analysis.strategy.graham_number.analyzer import GrahamNumberAnalyzer
from src.analysis.strategy.graham_number.calculation import (
    GrahamNumberInputAssembly,
    GrahamNumberInputResolver,
    GrahamNumberResult,
)
from src.analysis.strategy.graham_number.config import GrahamNumberConfig
from src.analysis.strategy.graham_number.service import GrahamNumberAnalysis
from src.core.analysis_status import CalculationStatus
from src.data.instrument_profile import InstrumentKind, InstrumentProfile
from src.evaluation.fixtures.graham import NOW, SECURITY_ID, FixtureFinancialFactsProvider
from src.evaluation.fixtures.instrument_profiles import fixture_instrument_profile
from src.workspace.graham_number_execution import (
    GrahamNumberCapture,
    classify_graham_number_outcome,
    execute_graham_number,
)
from src.workspace.models import RunOutcome


def _resolver() -> GrahamNumberInputResolver:
    return GrahamNumberInputResolver(FixtureFinancialFactsProvider(), clock=lambda: NOW)


def _profile(ticker: str = SECURITY_ID) -> InstrumentProfile:
    return fixture_instrument_profile(ticker, kind=InstrumentKind.EQUITY, provider_value="EQUITY")


def _assembly(status: CalculationStatus) -> GrahamNumberInputAssembly:
    return GrahamNumberInputAssembly(status=status, reason=None if status is CalculationStatus.OK else "fixture reason")


def _result(status: CalculationStatus) -> GrahamNumberResult:
    if status is CalculationStatus.OK:
        return GrahamNumberResult(status=status, maximum_indicated_price=42.0)
    return GrahamNumberResult(status=status, reason="fixture reason")


def _analysis(
    assembly_status: CalculationStatus,
    result_status: CalculationStatus = CalculationStatus.OK,
    *,
    profile: InstrumentProfile | None = None,
) -> GrahamNumberAnalysis:
    return GrahamNumberAnalysis(
        ticker=SECURITY_ID,
        as_of=None,
        assembly=_assembly(assembly_status),
        result=_result(result_status),
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
def test_classify_graham_number_outcome_matches_the_frozen_mapping(
    assembly_status: CalculationStatus, result_status: CalculationStatus, expected: RunOutcome
) -> None:
    analysis = _analysis(assembly_status, result_status)
    assert classify_graham_number_outcome(analysis) == expected


def test_execute_graham_number_delegates_and_falls_back_to_the_composed_profile() -> None:
    resolver = _resolver()
    config = GrahamNumberConfig()
    composed = _profile()
    canned = _analysis(CalculationStatus.OK)
    captured: dict[str, object] = {}

    def fake_run_analysis(
        self: GrahamNumberAnalyzer, config: GrahamNumberConfig, ticker: str | None = None
    ) -> GrahamNumberAnalysis:
        captured["config"] = config
        captured["ticker"] = ticker
        captured["profile_supplied"] = self._instrument_profile
        return canned

    with (
        patch("src.workspace.graham_number_execution.compose_graham_profile", return_value=composed),
        patch.object(GrahamNumberAnalyzer, "run_analysis", fake_run_analysis),
    ):
        capture = execute_graham_number(resolver, SECURITY_ID, config, object())

    assert capture.analysis is canned
    assert capture.profile is composed
    assert capture.outcome is RunOutcome.COMPLETED
    assert captured == {"config": config, "ticker": SECURITY_ID, "profile_supplied": composed}


def test_execute_graham_number_prefers_the_analysis_own_profile() -> None:
    resolver = _resolver()
    config = GrahamNumberConfig()
    composed = _profile()
    refined = _profile("KO")
    canned = _analysis(CalculationStatus.OK, profile=refined)

    with (
        patch("src.workspace.graham_number_execution.compose_graham_profile", return_value=composed),
        patch.object(GrahamNumberAnalyzer, "run_analysis", return_value=canned),
    ):
        capture = execute_graham_number(resolver, SECURITY_ID, config, object())

    assert capture.profile is refined
    assert isinstance(capture, GrahamNumberCapture)


def test_no_network_access(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Graham Number execution adapter must not access the network.")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket.socket, "connect", reject_network)

    with patch("src.workspace.graham_number_execution.compose_graham_profile", return_value=_profile()):
        capture = execute_graham_number(_resolver(), SECURITY_ID, GrahamNumberConfig(), object())

    assert capture.analysis.ticker == SECURITY_ID
