"""Each strategy's fixture composition and requirement, exercised through its own bound handler."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.data.quality import HistoricalDataQualityError
from src.evaluation.fixture_context import (
    FixtureCompositionError,
    FixtureContext,
    build_fixture_context,
    require_fixture_evidence,
)
from src.evaluation.fixture_ids import (
    GRAHAM_FACTS_FIXTURE_ID,
    KNOWN_ETF_PROFILE_FIXTURE_ID,
    MOMENTUM_BOUNDARY_FIXTURE_ID,
    MOMENTUM_SUCCESS_FIXTURE_ID,
)
from src.evaluation.fixtures.instrument_profiles import GOLDEN_ETF_TICKER
from src.evaluation.models import Case, Expectation
from src.orchestrator.tool_runtime import ToolRuntime
from src.strategies.momentum import evaluation as momentum_evaluation
from src.strategies.momentum.analyzer import MomentumRun
from src.strategy_wiring import MOMENTUM

EXECUTION_TIME = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def _case(*fixture_ids: str) -> Case:
    """Build a small supplied case."""
    return Case(
        case_id="strategy-evaluation",
        description="Synthetic strategy fixture case.",
        task="Compose the strategy's fixtures.",
        fixture_ids=fixture_ids,
        expectation=Expectation(),
    )


def _context(*fixture_ids: str) -> FixtureContext:
    """Build the cross-strategy context for a supplied case."""
    return build_fixture_context(_case(*fixture_ids), clock_at=EXECUTION_TIME)


def _runtime() -> ToolRuntime:
    """Build the shared runtime with the fixed clock."""
    return ToolRuntime(clock=lambda: EXECUTION_TIME)


def test_momentum_composes_the_selected_price_fixture() -> None:
    """Each price variant reaches the real Momentum handler with its own reviewed frame."""
    handler = MOMENTUM.behavior.bind_handler(
        momentum_evaluation.compose(_context(MOMENTUM_SUCCESS_FIXTURE_ID)), _runtime()
    )
    result = handler(ticker="MOM")
    assert isinstance(result, MomentumRun)
    assert result.metrics.current_price == 104.0

    handler = MOMENTUM.behavior.bind_handler(
        momentum_evaluation.compose(_context(MOMENTUM_BOUNDARY_FIXTURE_ID)), _runtime()
    )
    boundary = handler(ticker="MOM")
    assert isinstance(boundary, MomentumRun)
    assert boundary.metrics.current_price == 101.0


def test_momentum_without_a_price_fixture_has_explicitly_empty_history() -> None:
    """An unselected price variant is an empty frame, never default data."""
    handler = MOMENTUM.behavior.bind_handler(momentum_evaluation.compose(_context(GRAHAM_FACTS_FIXTURE_ID)), _runtime())
    with pytest.raises(HistoricalDataQualityError):
        handler(ticker="MOM")


def test_momentum_rejects_two_price_variants() -> None:
    """Conflicting price fixtures fail closed in Momentum's own composition."""
    with pytest.raises(FixtureCompositionError, match="Conflicting Momentum price fixture IDs"):
        momentum_evaluation.compose(_context(MOMENTUM_SUCCESS_FIXTURE_ID, MOMENTUM_BOUNDARY_FIXTURE_ID))


def test_momentum_requires_a_price_fixture_and_has_no_etf_exemption() -> None:
    """The requirement names the price capability and an ETF profile does not satisfy it."""
    requirement = momentum_evaluation.REQUIREMENT
    assert requirement.required_ids == {MOMENTUM_SUCCESS_FIXTURE_ID, MOMENTUM_BOUNDARY_FIXTURE_ID}
    assert requirement.etf_profile_exempt is False
    with pytest.raises(FixtureCompositionError, match="has no selected Momentum price fixture"):
        require_fixture_evidence(_case(KNOWN_ETF_PROFILE_FIXTURE_ID), requirement, ticker=GOLDEN_ETF_TICKER)
