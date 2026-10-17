"""Focused tests for the Graham Number execution adapter, using fake dependencies only."""

import socket
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.data.instrument_profile import InstrumentKind, InstrumentProfile
from investment_analysis_engine.evaluation.fixtures.graham import NOW, SECURITY_ID, FixtureFinancialFactsProvider
from investment_analysis_engine.evaluation.fixtures.instrument_profiles import fixture_instrument_profile
from investment_analysis_engine.strategies.graham_number.analyzer import GrahamNumberAnalyzer
from investment_analysis_engine.strategies.graham_number.calculation import (
    GrahamNumberInputAssembly,
    GrahamNumberInputResolver,
    GrahamNumberResult,
)
from investment_analysis_engine.strategies.graham_number.config import GrahamNumberConfig
from investment_analysis_engine.strategies.graham_number.execution import (
    GrahamNumberCapture,
    classify_graham_number_outcome,
    execute_graham_number,
)
from investment_analysis_engine.strategies.graham_number.service import GrahamNumberAnalysis


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
        effective_as_of=NOW,
        assembly=_assembly(assembly_status),
        result=_result(result_status),
        margin_of_safety_percent=None,
        instrument_profile=profile,
    )


@pytest.mark.parametrize(
    ("assembly_status", "result_status", "expected"),
    [
        (CalculationStatus.OK, CalculationStatus.OK, RunOutcome.COMPLETED),
        (CalculationStatus.OK, CalculationStatus.NOT_APPLICABLE, RunOutcome.NOT_APPLICABLE),
        (CalculationStatus.OK, CalculationStatus.INVALID_INPUT, RunOutcome.FAILED),
        # The service never builds these two (the calculation returns ok, not_applicable or invalid_input); a result
        # that is neither is a defect, and a failed run is the outcome that surfaces it.
        (CalculationStatus.OK, CalculationStatus.INPUT_UNAVAILABLE, RunOutcome.FAILED),
        (CalculationStatus.OK, CalculationStatus.PROVIDER_ERROR, RunOutcome.FAILED),
        (CalculationStatus.NOT_APPLICABLE, CalculationStatus.OK, RunOutcome.NOT_APPLICABLE),
        (CalculationStatus.NOT_APPLICABLE, CalculationStatus.NOT_APPLICABLE, RunOutcome.NOT_APPLICABLE),
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
        self: GrahamNumberAnalyzer, ticker: str, config: GrahamNumberConfig, context: AnalysisContext
    ) -> GrahamNumberAnalysis:
        del self
        captured["config"] = config
        captured["ticker"] = ticker
        captured["profile_supplied"] = context.instrument_profile
        return canned

    with (
        patch(
            "investment_analysis_engine.strategies.graham_number.execution.compose_graham_profile",
            return_value=composed,
        ),
        patch.object(GrahamNumberAnalyzer, "run_analysis", fake_run_analysis),
    ):
        capture = execute_graham_number(
            resolver, SECURITY_ID, config, object(), as_of=None, executed_at=NOW, use_cache=True
        )

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
        patch(
            "investment_analysis_engine.strategies.graham_number.execution.compose_graham_profile",
            return_value=composed,
        ),
        patch.object(GrahamNumberAnalyzer, "run_analysis", return_value=canned),
    ):
        capture = execute_graham_number(
            resolver, SECURITY_ID, config, object(), as_of=None, executed_at=NOW, use_cache=True
        )

    assert capture.profile is refined
    assert isinstance(capture, GrahamNumberCapture)


def test_no_network_access(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Graham Number execution adapter must not access the network.")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket.socket, "connect", reject_network)

    with patch(
        "investment_analysis_engine.strategies.graham_number.execution.compose_graham_profile", return_value=_profile()
    ):
        capture = execute_graham_number(
            _resolver(),
            SECURITY_ID,
            GrahamNumberConfig(),
            object(),
            as_of=None,
            executed_at=datetime.now(UTC),
            use_cache=True,
        )

    assert capture.analysis.ticker == SECURITY_ID
