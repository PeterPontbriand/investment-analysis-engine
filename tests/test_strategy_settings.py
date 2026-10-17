"""Every strategy that declares a settings model ships a valid settings.toml, and every shipped file has an owner."""

from __future__ import annotations

import tomllib
from collections.abc import Iterator
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from investment_analysis_engine.config import strategy_settings
from investment_analysis_engine.config.strategy_settings import (
    clear_strategy_settings_cache,
    load_strategy_settings,
    shipped_settings_path,
    user_settings_path,
)
from investment_analysis_engine.core.package_root import PACKAGE_ROOT
from investment_analysis_engine.core.settings_error import StrategySettingsError
from investment_analysis_engine.strategies.graham_growth.calculation import GrahamGrowthCalculationPolicy
from investment_analysis_engine.strategies.graham_growth.settings import GrahamGrowthSettings
from investment_analysis_engine.strategies.momentum.settings import MomentumSettings
from investment_analysis_engine.strategy_wiring import GRAHAM_GROWTH, MOMENTUM, STRATEGIES, StrategyDescriptor

STRATEGY_PACKAGES = PACKAGE_ROOT / "strategies"


@pytest.fixture(autouse=True)
def _isolated_cache() -> Iterator[None]:
    """Start and end every test with nothing cached."""
    clear_strategy_settings_cache()
    yield
    clear_strategy_settings_cache()


def settings_gaps(
    descriptors: tuple[StrategyDescriptor, ...], settings_folder: Path, strategy_packages: Path = STRATEGY_PACKAGES
) -> list[str]:
    """List every way the descriptors and the shipped files disagree with the settings convention.

    The settings are loaded for ``settings_folder``, which may hold the user's overrides.
    """
    gaps: list[str] = []
    owners = {shipped_settings_path(item.settings_type) for item in descriptors if item.settings_type is not None}
    for item in descriptors:
        model = item.settings_type
        if model is None:
            continue
        try:
            load_strategy_settings(item.alias, model, settings_folder)
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
        f"{path.parent.name}/{path.name} belongs to no strategy with a settings model"
        for path in sorted(strategy_packages.glob("*/settings.toml"))
        if path not in owners
    )
    return gaps


def test_the_shipped_files_and_the_declared_models_agree(tmp_path: Path) -> None:
    assert settings_gaps(STRATEGIES, tmp_path) == []


def test_the_two_configurable_strategies_declare_their_models() -> None:
    declared = {item.alias: item.settings_type for item in STRATEGIES}

    assert declared == {
        "momentum": MomentumSettings,
        "graham-number": None,
        "graham-growth": GrahamGrowthSettings,
        "fcf-growth": None,
    }


def test_a_declared_model_without_a_shipped_file_is_a_gap(tmp_path: Path) -> None:
    class Elsewhere(BaseModel):
        model_config = ConfigDict(extra="forbid", frozen=True)

    shipped = shipped_settings_path(Elsewhere)

    gaps = settings_gaps((replace(MOMENTUM, settings_type=Elsewhere),), tmp_path, tmp_path)

    assert gaps == [f"momentum: Settings file {shipped} is missing."]


def test_a_user_file_with_an_unknown_key_is_a_gap(tmp_path: Path) -> None:
    user = user_settings_path("graham-growth", tmp_path)
    user.parent.mkdir(parents=True)
    user.write_text("extra = 1\n", encoding="utf-8")

    gaps = settings_gaps((GRAHAM_GROWTH,), tmp_path, tmp_path)

    assert gaps == [f"graham-growth: Settings file {user} is invalid: extra: Extra inputs are not permitted."]


def test_a_shipped_file_without_an_owner_is_a_gap(tmp_path: Path) -> None:
    (tmp_path / "orphan").mkdir()
    (tmp_path / "orphan" / "settings.toml").write_text("a = 1\n", encoding="utf-8")

    assert settings_gaps((), tmp_path, tmp_path) == [
        "orphan/settings.toml belongs to no strategy with a settings model"
    ]


def test_a_model_with_a_default_that_is_not_frozen_or_closed_is_a_gap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Loose(BaseModel):
        model_config = ConfigDict(extra="ignore")

        value: int = 1

    shipped = tmp_path / "settings.toml"
    shipped.write_text("", encoding="utf-8")
    monkeypatch.setattr(strategy_settings, "shipped_settings_path", lambda _model: shipped)

    assert settings_gaps((replace(MOMENTUM, settings_type=Loose),), tmp_path / "user", tmp_path) == [
        "Loose is not frozen",
        "Loose does not forbid extra keys",
        "Loose.value has a default",
    ]


def test_graham_growth_settings_build_the_policy_with_the_files_values(tmp_path: Path) -> None:
    with shipped_settings_path(GrahamGrowthSettings).open("rb") as handle:
        values = tomllib.load(handle)

    policy = load_strategy_settings("graham-growth", GrahamGrowthSettings, tmp_path).to_policy()

    assert policy == GrahamGrowthCalculationPolicy(
        base_pe=values["base_pe"],
        growth_multiplier=values["growth_multiplier"],
        baseline_aaa_yield=values["baseline_aaa_yield"],
    )


def test_the_shipped_momentum_file_holds_the_documented_values(tmp_path: Path) -> None:
    assert load_strategy_settings("momentum", MomentumSettings, tmp_path) == MomentumSettings(
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
    user = user_settings_path("graham-growth", tmp_path)
    user.parent.mkdir(parents=True)
    user.write_text("".join(f"{name} = {item}\n" for name, item in values.items()), encoding="utf-8")

    with pytest.raises(StrategySettingsError) as error:
        load_strategy_settings("graham-growth", GrahamGrowthSettings, tmp_path)

    assert str(error.value) == f"Settings file {user} is invalid: {key}: {rule}."
