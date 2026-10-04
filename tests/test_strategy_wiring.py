"""The composition root: descriptors, indexes, exact-type guards and handler binding."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from types import MappingProxyType

import pytest

from src.core.strategy_errors import UndeclaredStrategyError
from src.evaluation.catalog import build_deterministic_requests
from src.evaluation.composition import compose_fixture_dependencies, dispatch_fixture_case
from src.evaluation.runner import DeterministicCaseRequest
from src.orchestrator.tool_names import ToolName
from src.orchestrator.tool_runtime import ToolRuntime
from src.strategies.fcf_growth.models import METHOD_ID, STRATEGY_ID, FCFEarningsGrowthResult
from src.strategies.fcf_growth.tool import FCFEarningsGrowthToolDependencies, FCFEarningsGrowthToolHandler
from src.strategies.graham_growth.service import GrahamGrowthAnalysis
from src.strategies.graham_number.service import GrahamNumberAnalysis
from src.strategies.momentum.analyzer import MomentumRun
from src.strategies.momentum.tool import MomentumToolArguments, MomentumToolDependencies
from src.strategy_wiring import (
    BY_ARGUMENTS,
    BY_KEY,
    BY_METHOD_ID,
    BY_RESULT_TYPE,
    BY_TOOL,
    FCF_GROWTH,
    GRAHAM_GROWTH,
    GRAHAM_NUMBER,
    MOMENTUM,
    STRATEGIES,
    bind_handlers,
    build_indexes,
    tool_for_arguments,
)

EXECUTED_AT = datetime(2026, 8, 31, 18, 30, tzinfo=UTC)


class _SubclassedMomentumArguments(MomentumToolArguments):
    """A subclass of a declared arguments model, which must not route as its parent."""


def test_the_declared_identifiers_are_the_existing_ones() -> None:
    """Identity, tool names and descriptions are unchanged from the declarations they replace."""
    assert [(d.analysis_id, d.method_id, d.tool.value) for d in STRATEGIES] == [
        ("momentum", "sma_crossover", "analyze_momentum"),
        ("graham_number", "graham_number", "analyze_graham_number"),
        ("graham_growth_value", "graham_growth_value", "analyze_graham_growth_value"),
        ("fcf_earnings_growth", "reported_fcf_eps_cagr", "analyze_fcf_earnings_growth"),
    ]
    assert [d.tool_description for d in STRATEGIES] == [
        "Analyze historical price momentum with structured SMA and RSI metrics.",
        "Calculate the Graham Number company-level valuation ceiling.",
        "Calculate the explicit Graham growth-value method.",
        "Analyze company free-cash-flow and diluted-EPS growth.",
    ]


def test_the_fcf_descriptor_references_its_existing_identity_constants() -> None:
    """FCF's identity is declared once, in its models module."""
    assert FCF_GROWTH.analysis_id is STRATEGY_ID
    assert FCF_GROWTH.method_id is METHOD_ID


def test_every_index_is_read_only_and_in_declaration_order() -> None:
    """The indexes are read-only mappings that iterate in the order the strategies are declared."""
    for index in (BY_KEY, BY_METHOD_ID, BY_TOOL, BY_ARGUMENTS, BY_RESULT_TYPE):
        assert isinstance(index, MappingProxyType)
        assert list(index.values()) == list(STRATEGIES)
    assert list(BY_TOOL) == list(ToolName)
    with pytest.raises(TypeError):
        BY_TOOL[ToolName.ANALYZE_MOMENTUM] = GRAHAM_NUMBER  # type: ignore[index]


def test_lookups_find_each_strategy_by_each_key() -> None:
    """Every key reaches the same descriptor."""
    for descriptor in STRATEGIES:
        assert BY_KEY[(descriptor.analysis_id, descriptor.method_id)] is descriptor
        assert BY_METHOD_ID[descriptor.method_id] is descriptor
        assert BY_TOOL[descriptor.tool] is descriptor
        assert BY_ARGUMENTS[descriptor.tool_arguments] is descriptor
        assert BY_RESULT_TYPE[descriptor.behavior.result_type] is descriptor


def test_tool_for_arguments_routes_by_exact_type() -> None:
    """A subclass of a declared model is not silently routed as its parent."""
    assert tool_for_arguments(MomentumToolArguments(ticker="MOM")) is ToolName.ANALYZE_MOMENTUM
    with pytest.raises(UndeclaredStrategyError, match="_SubclassedMomentumArguments"):
        tool_for_arguments(_SubclassedMomentumArguments(ticker="MOM"))


def test_build_indexes_is_a_pure_function_of_its_tuple() -> None:
    """A modified copy builds its own indexes and leaves the declared ones untouched."""
    subset = build_indexes(STRATEGIES[:2])
    assert list(subset.by_tool) == [ToolName.ANALYZE_MOMENTUM, ToolName.ANALYZE_GRAHAM_NUMBER]
    assert len(BY_TOOL) == 4
    assert build_indexes(()).by_key == {}


def test_a_repeated_key_raises_naming_the_rule_and_both_descriptors() -> None:
    """The builder fails at once on a repeated key, as the import-time build does."""
    with pytest.raises(ValueError, match=r"Duplicate tool .*declared by \('momentum', 'sma_crossover'\) and"):
        build_indexes((MOMENTUM, replace(GRAHAM_NUMBER, tool=MOMENTUM.tool)))


def test_native_status_comes_from_each_strategys_own_function() -> None:
    """Momentum declares no result-level status; the others return their own status value."""
    seen: dict[type, str | None] = {}
    for request in build_deterministic_requests():
        result = _dispatch(request)
        status = BY_RESULT_TYPE[type(result)].behavior.native_status_of(result)
        if isinstance(result, MomentumRun):
            assert status is None
        elif isinstance(result, (GrahamNumberAnalysis, GrahamGrowthAnalysis)):
            assert status == result.result.status.value
        else:
            assert isinstance(result, FCFEarningsGrowthResult)
            assert status == result.execution_status.value
        seen[type(result)] = status
    assert set(seen) == {MomentumRun, GrahamNumberAnalysis, GrahamGrowthAnalysis, FCFEarningsGrowthResult}


def test_a_behavior_rejects_another_strategys_object() -> None:
    """Every bundle method guards by exact type."""
    request = next(item for item in build_deterministic_requests() if item.case.case_id == "MOM-01")
    momentum_result = _dispatch(request)
    with pytest.raises(UndeclaredStrategyError, match="MomentumRun"):
        FCF_GROWTH.behavior.native_status_of(momentum_result)
    with pytest.raises(UndeclaredStrategyError, match="MomentumToolDependencies"):
        FCF_GROWTH.behavior.bind_handler(
            MomentumToolDependencies(analyzer=None),  # type: ignore[arg-type]
            ToolRuntime(clock=lambda: EXECUTED_AT),
        )


def test_bind_handlers_returns_one_handler_per_declared_tool_in_order() -> None:
    """Handlers are bound from each strategy's own dependency class and the shared runtime."""
    fixtures = compose_fixture_dependencies(build_deterministic_requests()[0].case, clock_at=EXECUTED_AT)
    handlers = bind_handlers(STRATEGIES, fixtures.dependencies, fixtures.runtime)
    assert list(handlers) == list(ToolName)
    assert isinstance(handlers, MappingProxyType)
    assert isinstance(handlers[ToolName.ANALYZE_FCF_EARNINGS_GROWTH], FCFEarningsGrowthToolHandler)
    assert isinstance(fixtures.dependencies[ToolName.ANALYZE_FCF_EARNINGS_GROWTH], FCFEarningsGrowthToolDependencies)


def test_bind_handlers_fails_closed_in_both_directions() -> None:
    """A descriptor tool with no dependencies, and dependencies for no descriptor tool, are both rejected."""
    fixtures = compose_fixture_dependencies(build_deterministic_requests()[0].case, clock_at=EXECUTED_AT)
    without_fcf = {tool: value for tool, value in fixtures.dependencies.items() if tool is not FCF_GROWTH.tool}
    with pytest.raises(UndeclaredStrategyError, match="tool dependencies .*ANALYZE_FCF_EARNINGS_GROWTH"):
        bind_handlers(STRATEGIES, without_fcf, fixtures.runtime)
    with pytest.raises(UndeclaredStrategyError, match="ANALYZE_MOMENTUM"):
        bind_handlers(STRATEGIES[1:], fixtures.dependencies, fixtures.runtime)
    swapped = {**fixtures.dependencies, MOMENTUM.tool: fixtures.dependencies[GRAHAM_GROWTH.tool]}
    with pytest.raises(UndeclaredStrategyError, match="GrahamGrowthToolDependencies"):
        bind_handlers(STRATEGIES, swapped, fixtures.runtime)


def _dispatch(request: DeterministicCaseRequest) -> object:
    """Dispatch one catalog request through the fixture composition and return its native result."""
    outcome = asyncio.run(dispatch_fixture_case(request.case, request.arguments, clock_at=EXECUTED_AT))
    assert outcome.success is True
    assert outcome.result is not None
    return outcome.result
