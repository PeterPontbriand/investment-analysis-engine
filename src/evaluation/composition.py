"""Deterministic fixture composition for production analysis-tool dispatch.

This module is strategy-neutral. It builds the cross-strategy fixture context for a case, asks the evaluation
tier for each declared strategy's dependency class and fixture requirement, and binds the production handlers.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from src.core.strategy_errors import require
from src.evaluation.fixture_context import (
    profile_resolver,
    require_fixture_evidence,
)
from src.evaluation.models import Case
from src.evaluation.strategy_fixtures import (
    EVALUATION_STRATEGIES,
    EvaluationStrategy,
    build_case_context,
    evaluation_by_tool,
)
from src.orchestrator.analysis_tool_arguments import AnalysisToolArguments
from src.orchestrator.analysis_tools import register_analysis_tools
from src.orchestrator.dispatcher import AsyncToolDispatcher
from src.orchestrator.tool_names import ToolName
from src.orchestrator.tool_runtime import ToolRuntime
from src.orchestrator.types import ToolCallRequest, ToolCallResult
from src.strategy_wiring import STRATEGIES, StrategyDescriptor, bind_handlers, build_indexes, tool_for_arguments


@dataclass(frozen=True)
class FixtureDependencies:
    """Fixture-backed dependency instances, one per declared tool, and the shared runtime."""

    dependencies: Mapping[ToolName, object]
    runtime: ToolRuntime


def compose_fixture_dependencies(
    case: Case,
    *,
    clock_at: datetime,
    descriptors: tuple[StrategyDescriptor, ...] = STRATEGIES,
    tier: tuple[EvaluationStrategy, ...] = EVALUATION_STRATEGIES,
) -> FixtureDependencies:
    """Build every declared strategy's tool dependencies from a supplied case's fixtures.

    Args:
        case: Typed case containing only explicitly selected fixture identifiers.
        clock_at: Fixed timezone-aware execution time for every clocked resolver.
        descriptors: The declared strategies; the production ones unless a caller supplies another tuple.
        tier: The evaluation tier; the declared one unless a caller supplies another.

    Returns:
        One fixture-backed dependency instance per declared tool, with the shared runtime.

    Raises:
        FixtureCompositionError: If identifiers conflict, are unsupported, or the
            supplied clock is ambiguous.
        UndeclaredStrategyError: If a declared tool has no evaluation-tier entry.
    """
    entries = evaluation_by_tool(descriptors, tier)
    context = build_case_context(case, clock_at=clock_at, descriptors=descriptors, tier=tier)
    dependencies = {descriptor.tool: entries[descriptor.tool].compose(context) for descriptor in descriptors}
    runtime = ToolRuntime(clock=lambda: clock_at, profile_resolver=profile_resolver(context))
    return FixtureDependencies(dependencies=MappingProxyType(dependencies), runtime=runtime)


def compose_fixture_dispatcher(
    case: Case,
    *,
    clock_at: datetime,
    descriptors: tuple[StrategyDescriptor, ...] = STRATEGIES,
    tier: tuple[EvaluationStrategy, ...] = EVALUATION_STRATEGIES,
) -> AsyncToolDispatcher:
    """Register every declared production handler with fixture-backed dependencies."""
    fixtures = compose_fixture_dependencies(case, clock_at=clock_at, descriptors=descriptors, tier=tier)
    dispatcher = AsyncToolDispatcher()
    register_analysis_tools(dispatcher, bind_handlers(descriptors, fixtures.dependencies, fixtures.runtime))
    return dispatcher


async def dispatch_fixture_case(
    case: Case,
    arguments: AnalysisToolArguments,
    *,
    clock_at: datetime,
    descriptors: tuple[StrategyDescriptor, ...] = STRATEGIES,
    tier: tuple[EvaluationStrategy, ...] = EVALUATION_STRATEGIES,
) -> ToolCallResult:
    """Execute one typed production-tool call for a supplied case without an LLM."""
    tool_name = tool_for_arguments(arguments, build_indexes(descriptors).by_arguments)
    entry = require(evaluation_by_tool(descriptors, tier), tool_name, what="evaluation tier entry for tool")
    require_fixture_evidence(case, entry.requirement, ticker=arguments.ticker)
    dispatcher = compose_fixture_dispatcher(case, clock_at=clock_at, descriptors=descriptors, tier=tier)
    request = ToolCallRequest(
        call_id=f"golden:{case.case_id}:{tool_name.value}",
        tool_name=tool_name.value,
        arguments=arguments.model_dump(mode="python"),
    )
    return await dispatcher.dispatch(request)
