"""The run context of an analysis-tool call: the clock is validated before the profile is resolved."""

from datetime import UTC, datetime

import pytest

from investment_analysis_engine.data.instrument_profile import InstrumentKind, InstrumentProfile
from investment_analysis_engine.evaluation.fixtures.instrument_profiles import fixture_instrument_profile
from investment_analysis_engine.orchestrator.analysis_tool_arguments import AnalysisToolArguments
from investment_analysis_engine.orchestrator.tool_runtime import ToolRuntime
from investment_analysis_engine.strategies._shared.tool import tool_context

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


def _profile(ticker: str) -> InstrumentProfile:
    return fixture_instrument_profile(ticker, kind=InstrumentKind.ETF, provider_value="ETF", instrument_name="Fund")


def test_the_context_carries_the_boundary_the_clock_the_cache_choice_and_the_profile() -> None:
    boundary = datetime(2026, 1, 2, tzinfo=UTC)
    resolved: list[str] = []
    profile = _profile("AAPL")

    def resolve(ticker: str) -> InstrumentProfile:
        resolved.append(ticker)
        return profile

    arguments = AnalysisToolArguments(ticker=" aapl ", as_of=boundary)

    context = tool_context(ToolRuntime(clock=lambda: NOW, profile_resolver=resolve), arguments, use_cache=False)

    assert (context.as_of, context.executed_at, context.use_cache) == (boundary, NOW, False)
    assert context.instrument_profile is profile
    assert resolved == ["AAPL"]


def test_no_resolver_gives_no_profile() -> None:
    context = tool_context(ToolRuntime(clock=lambda: NOW), AnalysisToolArguments(ticker="KO"), use_cache=True)

    assert context.instrument_profile is None
    assert context.as_of is None


def test_a_naive_clock_is_refused_before_any_profile_is_resolved() -> None:
    resolved: list[str] = []

    def resolve(ticker: str) -> InstrumentProfile:
        resolved.append(ticker)
        return _profile(ticker)

    runtime = ToolRuntime(clock=lambda: datetime(2026, 11, 1), profile_resolver=resolve)  # noqa: DTZ001

    with pytest.raises(ValueError, match="timezone-aware"):
        tool_context(runtime, AnalysisToolArguments(ticker="KO"), use_cache=True)

    assert resolved == []
