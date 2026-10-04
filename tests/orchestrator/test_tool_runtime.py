"""The shared clock and profile resolver that every analysis-tool handler receives."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.data.instrument_profile import InstrumentKind, InstrumentProfile
from src.evaluation.fixtures.instrument_profiles import fixture_instrument_profile
from src.orchestrator.tool_runtime import ToolRuntime

NOW = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def _profile(ticker: str) -> InstrumentProfile:
    return fixture_instrument_profile(ticker, kind=InstrumentKind.ETF, provider_value="ETF", instrument_name="Fund")


def test_a_runtime_without_a_resolver_resolves_no_profile() -> None:
    """Profile evidence is optional; its absence is an explicit ``None``."""
    assert ToolRuntime(clock=lambda: NOW).resolve_profile("ANY") is None


def test_the_resolver_is_called_once_per_resolution_with_the_ticker() -> None:
    """The injected resolver receives the ticker exactly as given."""
    calls: list[str] = []

    def resolve(ticker: str) -> InstrumentProfile:
        calls.append(ticker)
        return _profile(ticker)

    runtime = ToolRuntime(clock=lambda: NOW, profile_resolver=resolve)
    profile = runtime.resolve_profile("FLSW")

    assert profile is not None
    assert profile.ticker == "FLSW"
    assert calls == ["FLSW"]


def test_a_timezone_aware_clock_value_is_returned_unchanged() -> None:
    """The execution timestamp is the injected clock's value."""
    assert ToolRuntime(clock=lambda: NOW).validated_clock_value() == NOW


def test_a_naive_clock_value_is_rejected() -> None:
    """An ambiguous execution timestamp never reaches an analyzer."""
    runtime = ToolRuntime(clock=lambda: datetime(2026, 3, 1, 12, 0))
    with pytest.raises(ValueError, match="Analysis tool clock must return a timezone-aware datetime."):
        runtime.validated_clock_value()
