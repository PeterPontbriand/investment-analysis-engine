"""The CLI tier fails closed: a missing entry or key is an error naming it, never a default strategy.

The tests make no network, provider or LLM call.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
import typer.main
from typer.core import TyperGroup
from typer.testing import CliRunner

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.selections import build_selection
from investment_analysis_engine.cli import app
from investment_analysis_engine.cli_strategy_wiring import CLI_STRATEGIES, cli_entries
from investment_analysis_engine.cli_support import selection_from_options
from investment_analysis_engine.cli_workspace import watchlist_app
from investment_analysis_engine.config import ProjectSettings, settings
from investment_analysis_engine.config.component_settings import clear_component_settings_cache, load_component_settings
from investment_analysis_engine.core.strategy_errors import UndeclaredStrategyError
from investment_analysis_engine.strategies.fcf_growth.selection import FCFGrowthSelection
from investment_analysis_engine.strategies.graham_growth.selection import GrahamGrowthSelection
from investment_analysis_engine.strategies.graham_number.selection import GrahamNumberSelection
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.strategies.momentum.settings import MomentumSettings
from investment_analysis_engine.strategies.piotroski.selection import PiotroskiSelection
from investment_analysis_engine.strategy_wiring import (
    FCF_GROWTH,
    GRAHAM_GROWTH,
    GRAHAM_NUMBER,
    MOMENTUM,
    PIOTROSKI,
    STRATEGIES,
    StrategyDescriptor,
)
from tests._cli_helpers import normalize_cli_output

runner = CliRunner()

_WITHOUT_FCF = tuple(entry for entry in CLI_STRATEGIES if entry.behavior is not FCF_GROWTH.behavior)


def test_every_declared_strategy_has_an_entry_in_declaration_order() -> None:
    """The production tier covers every descriptor, in declaration order."""
    assert [descriptor for descriptor, _ in cli_entries(STRATEGIES)] == list(STRATEGIES)


def test_each_entrys_option_table_builds_exactly_its_strategys_selection() -> None:
    """The table of each strategy builds its own selection class from option values."""
    values: dict[StrategyDescriptor, dict[str, object]] = {
        MOMENTUM: {"short_window": 5, "long_window": 20, "rsi_period": 14, "as_of": None, "no_cache": False},
        GRAHAM_NUMBER: {"as_of": None, "no_cache": False, "eps": None, "bvps": None, "current_price": None},
        GRAHAM_GROWTH: {
            "as_of": None,
            "no_cache": False,
            "eps": None,
            "eps_basis": None,
            "expected_growth": 6.0,
            "aaa_yield": 4.4,
            "current_price": None,
        },
        FCF_GROWTH: {
            "growth_years": None,
            "forward_policy": "display-only",
            "classification_basis": "total-fcf",
            "as_of": None,
            "currency": "USD",
            "no_cache": False,
        },
        PIOTROSKI: {"as_of": None, "no_cache": False},
    }
    expected = {
        MOMENTUM: MomentumSelection,
        GRAHAM_NUMBER: GrahamNumberSelection,
        GRAHAM_GROWTH: GrahamGrowthSelection,
        FCF_GROWTH: FCFGrowthSelection,
        PIOTROSKI: PiotroskiSelection,
    }
    for descriptor, entry in cli_entries(STRATEGIES):
        if descriptor not in values:
            continue  # a strategy added since is covered by the option-table conformance check
        built = selection_from_options(descriptor.method_id, entry.selection_options, values[descriptor])
        assert type(built) is expected[descriptor]


def test_a_missing_cli_tier_entry_fails_closed() -> None:
    """A strategy with no entry is reported by identity; the other strategies are not a fallback."""
    with pytest.raises(UndeclaredStrategyError, match=r"CLI tier has no entry for strategy .*reported_fcf_eps_cagr"):
        cli_entries(STRATEGIES, _WITHOUT_FCF)


def test_an_entry_serving_no_descriptor_and_a_duplicate_entry_are_rejected() -> None:
    """The tier is checked against the descriptors in both directions."""
    stray = replace(CLI_STRATEGIES[0], behavior=object())
    with pytest.raises(UndeclaredStrategyError, match="CLI tier entry for bundle"):
        cli_entries(STRATEGIES, (stray, *CLI_STRATEGIES))
    with pytest.raises(ValueError, match="Duplicate CLI tier entry"):
        cli_entries(STRATEGIES, (*CLI_STRATEGIES, CLI_STRATEGIES[0]))


def test_add_selection_is_a_command_group_with_one_command_per_declared_strategy() -> None:
    """The group holds each alias, in declaration order, each summarized from its descriptor's label."""
    group = typer.main.get_group(watchlist_app)
    add_selection = group.commands["add-selection"]
    assert isinstance(add_selection, TyperGroup)
    assert list(add_selection.commands) == [item.alias for item in STRATEGIES]
    for item in STRATEGIES:
        assert add_selection.commands[item.alias].help is not None
        assert add_selection.commands[item.alias].get_short_help_str(200) == (
            f"Add one {item.label} entry per ticker to an existing watchlist."
        )


@pytest.mark.parametrize("command", [["momentum"], ["watchlist", "add-selection", "momentum"]])
def test_the_momentum_window_options_default_to_the_settings_and_show_the_value_in_effect(command: list[str]) -> None:
    """The options are omitted by default and their help shows the value in effect."""
    shipped = load_component_settings("momentum", MomentumSettings, settings.config_dir)
    result = runner.invoke(app, [*command, "--help"], env={"COLUMNS": "200"})
    assert result.exit_code == 0, result.output
    text = normalize_cli_output(result.output)
    for value in (shipped.short_window, shipped.long_window, shipped.rsi_period):
        assert f"[default: (from settings: {value})]" in text


def test_an_omitted_momentum_window_is_filled_from_the_settings_when_the_selection_is_built(tmp_path: Path) -> None:
    """The user's settings file is read when a selection is built, not when the command line is imported."""
    folder = tmp_path / "config"
    (folder / "strategies").mkdir(parents=True)
    (folder / "strategies" / "momentum.toml").write_text("short_window = 7\nlong_window = 90\n", encoding="utf-8")
    clear_component_settings_cache()
    try:
        built = build_selection(ApplicationContext(settings=ProjectSettings(config_dir=folder)), MOMENTUM.method_id, {})
    finally:
        clear_component_settings_cache()
    assert isinstance(built, MomentumSelection)
    assert (built.short_window, built.long_window, built.rsi_period) == (
        7,
        90,
        14,
    )
