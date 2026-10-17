"""Every strategy that declares a settings model has a valid shipped file, and every shipped file has an owner."""

from __future__ import annotations

import tomllib
from collections.abc import Iterator
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from investment_analysis_engine.config.strategy_settings import clear_strategy_settings_cache, load_strategy_settings
from investment_analysis_engine.core.settings_error import StrategySettingsError
from investment_analysis_engine.strategies.graham_growth.calculation import GrahamGrowthCalculationPolicy
from investment_analysis_engine.strategies.graham_growth.settings import GrahamGrowthSettings
from investment_analysis_engine.strategies.momentum.settings import MomentumSettings
from investment_analysis_engine.strategy_wiring import GRAHAM_GROWTH, MOMENTUM, STRATEGIES, StrategyDescriptor
from scripts.repository_root import REPOSITORY_ROOT

SHIPPED = REPOSITORY_ROOT / "config" / "strategies"


@pytest.fixture(autouse=True)
def _isolated_cache() -> Iterator[None]:
    """Start and end every test with nothing cached."""
    clear_strategy_settings_cache()
    yield
    clear_strategy_settings_cache()


def settings_gaps(descriptors: tuple[StrategyDescriptor, ...], directory: Path) -> list[str]:
    """List every way the descriptors and the files in ``directory`` disagree with the settings convention."""
    gaps: list[str] = []
    owners = {item.alias for item in descriptors if item.settings_type is not None}
    for item in descriptors:
        model = item.settings_type
        if model is None:
            continue
        try:
            load_strategy_settings(item.alias, model, directory)
        except StrategySettingsError as error:
            gaps.append(f"{item.alias}: {error}")
        if model.model_config.get("frozen") is not True:
            gaps.append(f"{model.__name__} is not frozen")
        if model.model_config.get("extra") != "forbid":
            gaps.append(f"{model.__name__} does not forbid extra keys")
        gaps.extend(
            f"{model.__name__}.{name} has a default"
            for name, field in model.model_fields.items()
            if not field.is_required()
        )
    gaps.extend(
        f"{path.name} belongs to no strategy with a settings model"
        for path in sorted(directory.glob("*.toml"))
        if path.stem not in owners
    )
    return gaps


def test_the_shipped_files_and_the_declared_models_agree() -> None:
    assert settings_gaps(STRATEGIES, SHIPPED) == []


def test_the_two_configurable_strategies_declare_their_models() -> None:
    declared = {item.alias: item.settings_type for item in STRATEGIES}

    assert declared == {
        "momentum": MomentumSettings,
        "graham-number": None,
        "graham-growth": GrahamGrowthSettings,
        "fcf-growth": None,
    }


def test_a_declared_model_without_a_file_is_a_gap(tmp_path: Path) -> None:
    gaps = settings_gaps((MOMENTUM,), tmp_path)

    assert gaps == ["momentum: Settings file config/strategies/momentum.toml is missing."]


def test_a_file_with_an_unknown_key_is_a_gap(tmp_path: Path) -> None:
    text = (SHIPPED / "graham-growth.toml").read_text(encoding="utf-8") + "extra = 1\n"
    (tmp_path / "graham-growth.toml").write_text(text, encoding="utf-8")

    gaps = settings_gaps((GRAHAM_GROWTH,), tmp_path)

    assert gaps == [
        "graham-growth: Settings file config/strategies/graham-growth.toml is invalid: "
        "extra: Extra inputs are not permitted."
    ]


def test_a_file_without_an_owner_is_a_gap(tmp_path: Path) -> None:
    (tmp_path / "orphan.toml").write_text("a = 1\n", encoding="utf-8")

    assert settings_gaps((), tmp_path) == ["orphan.toml belongs to no strategy with a settings model"]


def test_a_model_with_a_default_that_is_not_frozen_or_closed_is_a_gap(tmp_path: Path) -> None:
    class Loose(BaseModel):
        model_config = ConfigDict(extra="ignore")

        value: int = 1

    (tmp_path / "momentum.toml").write_text("", encoding="utf-8")

    assert settings_gaps((replace(MOMENTUM, settings_type=Loose),), tmp_path) == [
        "Loose is not frozen",
        "Loose does not forbid extra keys",
        "Loose.value has a default",
    ]


def test_graham_growth_settings_build_the_policy_with_the_files_values() -> None:
    with (SHIPPED / "graham-growth.toml").open("rb") as handle:
        values = tomllib.load(handle)

    policy = load_strategy_settings("graham-growth", GrahamGrowthSettings, SHIPPED).to_policy()

    assert policy == GrahamGrowthCalculationPolicy(
        base_pe=values["base_pe"],
        growth_multiplier=values["growth_multiplier"],
        baseline_aaa_yield=values["baseline_aaa_yield"],
    )


def test_the_shipped_momentum_file_holds_the_documented_values() -> None:
    assert load_strategy_settings("momentum", MomentumSettings, SHIPPED) == MomentumSettings(
        short_window=50, long_window=200, rsi_period=14, history_start_date=date(2021, 1, 1)
    )


@pytest.mark.parametrize(
    ("key", "value", "rule"),
    [
        ("base_pe", "0.0", "must be a finite number greater than zero"),
        ("growth_multiplier", "-1.0", "must be a finite number, zero or more"),
        ("baseline_aaa_yield", "nan", "must be a finite number greater than zero"),
    ],
)
def test_each_graham_growth_constant_has_its_own_rule(tmp_path: Path, key: str, value: str, rule: str) -> None:
    values = {"base_pe": "8.5", "growth_multiplier": "2.0", "baseline_aaa_yield": "4.4", key: value}
    (tmp_path / "graham-growth.toml").write_text(
        "".join(f"{name} = {item}\n" for name, item in values.items()), encoding="utf-8"
    )

    with pytest.raises(StrategySettingsError) as error:
        load_strategy_settings("graham-growth", GrahamGrowthSettings, tmp_path)

    assert str(error.value) == f"Settings file config/strategies/graham-growth.toml is invalid: {key}: {rule}."
