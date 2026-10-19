"""The CLI tier fails closed: a missing entry or key is an error naming it, never a default strategy.

The tests make no network, provider or LLM call; the refresh executors are never run against a provider.
"""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType
from typing import cast
from unittest.mock import MagicMock

import pytest
import typer.main

from investment_analysis_engine.cli_composition import momentum_settings
from investment_analysis_engine.cli_strategy_wiring import (
    CLI_BUILDERS,
    CLI_REFRESHERS,
    CLI_STRATEGIES,
    CliComposition,
    build_selection_for,
    builders_by_alias,
    cli_entries,
    pair_cli,
    refresh_executor_for,
    refreshers_by_key,
)
from investment_analysis_engine.cli_watchlist_flags import WatchlistFlags
from investment_analysis_engine.cli_workspace import watchlist_app
from investment_analysis_engine.core.strategy_errors import UndeclaredStrategyError
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.strategies.fcf_growth.selection import FCFGrowthSelection
from investment_analysis_engine.strategies.graham_growth.selection import GrahamGrowthSelection
from investment_analysis_engine.strategies.graham_number.selection import GrahamNumberSelection
from investment_analysis_engine.strategies.momentum.cli import refresh as refresh_momentum
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.strategy_wiring import (
    FCF_GROWTH,
    GRAHAM_GROWTH,
    GRAHAM_NUMBER,
    MOMENTUM,
    MOMENTUM_BEHAVIOR,
    STRATEGIES,
)

_FLAGS = WatchlistFlags(
    short_window=5,
    long_window=20,
    rsi_period=14,
    as_of=None,
    data_provider=None,
    no_cache=False,
    eps=None,
    eps_basis=None,
    bvps=None,
    current_price=None,
    expected_growth=6.0,
    aaa_yield=4.4,
    growth_years=None,
    forward_policy="display-only",
    classification_basis="total-fcf",
    currency="USD",
)
_WITHOUT_FCF = tuple(entry for entry in CLI_STRATEGIES if entry.behavior is not FCF_GROWTH.behavior)


@pytest.mark.parametrize("command", ["create", "add-selection"])
def test_the_watchlist_momentum_options_default_to_the_configured_values(command: str) -> None:
    """The window and RSI options default to the settings file, so a selection built from them carries it."""
    configured = momentum_settings()
    group = typer.main.get_group(watchlist_app)
    defaults = {parameter.name: parameter.default for parameter in group.commands[command].params}
    assert defaults["short_window"] == configured.short_window
    assert defaults["long_window"] == configured.long_window
    assert defaults["rsi_period"] == configured.rsi_period
    flags = replace(
        _FLAGS,
        short_window=defaults["short_window"],
        long_window=defaults["long_window"],
        rsi_period=defaults["rsi_period"],
    )
    assert build_selection_for(MOMENTUM.alias, flags) == MomentumSelection(
        short_window=configured.short_window, long_window=configured.long_window, rsi_period=configured.rsi_period
    )


def test_every_declared_strategy_has_a_builder_and_a_refresh_executor() -> None:
    """The production tier covers every descriptor, in declaration order."""
    assert tuple(CLI_BUILDERS) == tuple(item.alias for item in STRATEGIES)
    assert tuple(CLI_REFRESHERS) == tuple((item.analysis_id, item.method_id) for item in STRATEGIES)
    assert [descriptor for descriptor, _ in cli_entries(STRATEGIES)] == list(STRATEGIES)


def test_the_builders_return_the_selection_class_of_their_own_strategy() -> None:
    """Each alias builds exactly its strategy's selection class."""
    expected = {
        MOMENTUM.alias: MomentumSelection,
        GRAHAM_NUMBER.alias: GrahamNumberSelection,
        GRAHAM_GROWTH.alias: GrahamGrowthSelection,
        FCF_GROWTH.alias: FCFGrowthSelection,
    }
    for alias, selection_type in expected.items():
        assert type(build_selection_for(alias, _FLAGS)) is selection_type


def test_a_missing_cli_tier_entry_fails_closed_for_the_selection_builder() -> None:
    """A strategy with no entry is reported by identity; the other strategies are not a fallback."""
    with pytest.raises(UndeclaredStrategyError, match=r"CLI tier has no entry for strategy .*reported_fcf_eps_cagr"):
        builders_by_alias(STRATEGIES, _WITHOUT_FCF)
    without_builder = {alias: builder for alias, builder in CLI_BUILDERS.items() if alias != FCF_GROWTH.alias}
    with pytest.raises(UndeclaredStrategyError, match="selection builder alias 'fcf-growth'"):
        build_selection_for(FCF_GROWTH.alias, _FLAGS, MappingProxyType(without_builder))
    with pytest.raises(UndeclaredStrategyError, match="selection builder alias 'undeclared'"):
        build_selection_for("undeclared", _FLAGS)


def test_a_missing_cli_tier_entry_fails_closed_for_the_refresh_executor() -> None:
    """A selection of a strategy with no entry is reported by its identifiers, never run as another strategy."""
    with pytest.raises(UndeclaredStrategyError, match=r"CLI tier has no entry for strategy .*reported_fcf_eps_cagr"):
        refreshers_by_key(STRATEGIES, _WITHOUT_FCF)
    without_executor = {key: value for key, value in CLI_REFRESHERS.items() if key[1] != FCF_GROWTH.method_id}
    with pytest.raises(UndeclaredStrategyError, match=r"refresh executor .*reported_fcf_eps_cagr"):
        refresh_executor_for(FCFGrowthSelection(), MappingProxyType(without_executor))


def test_an_entry_serving_no_descriptor_and_a_duplicate_entry_are_rejected() -> None:
    """The tier is checked against the descriptors in both directions."""
    stray = replace(CLI_STRATEGIES[0], behavior=object())
    with pytest.raises(UndeclaredStrategyError, match="CLI tier entry for bundle"):
        cli_entries(STRATEGIES, (stray, *CLI_STRATEGIES))
    with pytest.raises(ValueError, match="Duplicate CLI tier entry"):
        cli_entries(STRATEGIES, (*CLI_STRATEGIES, CLI_STRATEGIES[0]))


def test_an_entry_rejects_another_strategys_selection() -> None:
    """A refresh executor runs for no other strategy's selection, and a builder returns only its own."""
    momentum = CLI_STRATEGIES[0]
    cache = MagicMock(spec=InstrumentProfileResolver)
    with pytest.raises(UndeclaredStrategyError, match="selection type"):
        momentum.refresh("AAPL", GrahamNumberSelection(), profile_cache=cache)
    cache.resolve.assert_not_called()
    wrong = pair_cli(
        MOMENTUM_BEHAVIOR,
        CliComposition(
            build=lambda _flags: cast("MomentumSelection", GrahamNumberSelection()),
            refresh=refresh_momentum,
            command=momentum.command,
        ),
    )
    with pytest.raises(UndeclaredStrategyError, match="selection type"):
        wrong.build(_FLAGS)
