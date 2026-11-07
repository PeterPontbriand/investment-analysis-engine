"""The application tier fails closed: a missing entry or key is an error naming it, never a default strategy.

The tests make no network, provider or LLM call; the run functions are never run against a provider.
"""

from dataclasses import replace
from types import MappingProxyType
from unittest.mock import MagicMock

import pytest

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.tier import (
    APPLICATION_RUNNERS,
    APPLICATION_STRATEGIES,
    analysis_runner_for,
    application_entries,
    runners_by_key,
)
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.core.clock import utc_now
from investment_analysis_engine.core.strategy_errors import UndeclaredStrategyError
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.strategies.fcf_growth.selection import FCFGrowthSelection
from investment_analysis_engine.strategies.graham_number.selection import GrahamNumberSelection
from investment_analysis_engine.strategy_wiring import FCF_GROWTH, MOMENTUM, STRATEGIES
from scripts import strategy_conformance as conformance

_CONTEXT = ApplicationContext(settings=ProjectSettings())
_WITHOUT_FCF = tuple(entry for entry in APPLICATION_STRATEGIES if entry.behavior is not FCF_GROWTH.behavior)


def test_every_declared_strategy_has_a_run_function() -> None:
    """The production tier covers every descriptor, in declaration order."""
    keys = tuple((item.analysis_id, item.method_id) for item in STRATEGIES)
    assert tuple(APPLICATION_RUNNERS) == keys
    assert [descriptor for descriptor, _ in application_entries(STRATEGIES)] == list(STRATEGIES)


def test_the_tier_is_a_closed_tuple_built_by_pairing() -> None:
    """The tier is a tuple of entries, each paired with exactly the core bundle of one descriptor."""
    assert isinstance(APPLICATION_STRATEGIES, tuple)
    assert [entry.behavior for entry in APPLICATION_STRATEGIES] == [item.behavior for item in STRATEGIES]


def test_a_missing_application_tier_entry_fails_closed_for_the_run_function() -> None:
    """A strategy with no entry is reported by identity; the other strategies are not a fallback."""
    pattern = r"application tier has no entry for strategy .*reported_fcf_eps_cagr"
    with pytest.raises(UndeclaredStrategyError, match=pattern):
        runners_by_key(STRATEGIES, _WITHOUT_FCF)
    without_runner = {key: value for key, value in APPLICATION_RUNNERS.items() if key[1] != FCF_GROWTH.method_id}
    with pytest.raises(UndeclaredStrategyError, match=r"analysis runner .*reported_fcf_eps_cagr"):
        analysis_runner_for(FCFGrowthSelection(), MappingProxyType(without_runner))


def test_an_entry_serving_no_descriptor_and_a_duplicate_entry_are_rejected() -> None:
    """The tier is checked against the descriptors in both directions."""
    stray = replace(APPLICATION_STRATEGIES[0], behavior=object())
    with pytest.raises(UndeclaredStrategyError, match="application tier entry for bundle"):
        application_entries(STRATEGIES, (stray, *APPLICATION_STRATEGIES))
    with pytest.raises(ValueError, match="Duplicate application tier entry"):
        application_entries(STRATEGIES, (*APPLICATION_STRATEGIES, APPLICATION_STRATEGIES[0]))


def test_an_entry_rejects_another_strategys_selection() -> None:
    """A run function runs for no other strategy's selection, whether for a direct analysis or a refresh job."""
    momentum = APPLICATION_STRATEGIES[0]
    assert momentum.behavior is MOMENTUM.behavior
    cache = MagicMock(spec=InstrumentProfileResolver)
    with pytest.raises(UndeclaredStrategyError, match="selection type"):
        momentum.run(_CONTEXT, "AAPL", GrahamNumberSelection(), executed_at=utc_now(), profile_cache=cache)
    cache.resolve.assert_not_called()


def test_the_conformance_checks_find_the_tier_closed_and_complete() -> None:
    """The tier has exactly the documented members, is a tuple, and serves every descriptor and no other."""
    assert conformance.application_tier_is_closed_gaps() == []
    assert conformance.application_tier_gaps(STRATEGIES) == []
    assert conformance.application_tier_gaps(STRATEGIES, _WITHOUT_FCF) == [
        f"strategy {conformance.label(FCF_GROWTH)} is not wired in: application tier"
    ]
    assert conformance.application_tier_is_closed_gaps([]) == ["APPLICATION_STRATEGIES is not a tuple"]
