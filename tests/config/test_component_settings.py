"""The strategy-settings loader: shipped defaults, a per-key user override, one message per kind of wrong file."""

from __future__ import annotations

import tomllib
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from investment_analysis_engine.config import component_settings
from investment_analysis_engine.config.component_settings import (
    clear_component_settings_cache,
    load_component_settings,
    shipped_settings_path,
    user_settings_path,
)
from investment_analysis_engine.core.settings_error import ComponentSettingsError
from investment_analysis_engine.strategies.momentum.settings import MomentumSettings

_SHIPPED_DEFAULTS = MomentumSettings(
    short_window=50, long_window=200, rsi_period=14, history_start_date=date(2021, 1, 1)
)
_VALID = """\
short_window = 50
long_window = 200
rsi_period = 14
history_start_date = "2021-01-01"
"""


@pytest.fixture(autouse=True)
def _isolated_cache() -> Iterator[None]:
    """Start and end every test with nothing cached."""
    clear_component_settings_cache()
    yield
    clear_component_settings_cache()


def _user_file(folder: Path) -> Path:
    return user_settings_path("momentum", folder)


def _write_user(folder: Path, text: str) -> Path:
    path = _user_file(folder)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _message(folder: Path) -> str:
    """Return the message of the error that loading Momentum's settings raises."""
    with pytest.raises(ComponentSettingsError) as error:
        load_component_settings("momentum", MomentumSettings, folder)
    return str(error.value)


def _use_shipped_file(monkeypatch: pytest.MonkeyPatch, folder: Path, text: str | None) -> Path:
    """Replace the shipped file with ``text`` in ``folder`` (no file at all when None) and return its path."""
    path = folder / "shipped" / "settings.toml"
    if text is not None:
        path.parent.mkdir(parents=True)
        path.write_text(text, encoding="utf-8")
    monkeypatch.setattr(component_settings, "shipped_settings_path", lambda _model: path)
    return path


def test_the_shipped_file_sits_beside_the_module_that_defines_the_model() -> None:
    path = shipped_settings_path(MomentumSettings)

    assert path.name == "settings.toml"
    assert path.parent.name == "momentum"
    assert path.is_file()


def test_the_user_file_is_in_the_strategies_folder_of_the_settings_folder(tmp_path: Path) -> None:
    assert user_settings_path("graham-growth", tmp_path) == tmp_path / "strategies" / "graham-growth.toml"


def test_without_a_user_file_the_shipped_defaults_load(tmp_path: Path) -> None:
    assert load_component_settings("momentum", MomentumSettings, tmp_path) == _SHIPPED_DEFAULTS


def test_a_user_file_may_hold_any_subset_of_the_keys(tmp_path: Path) -> None:
    _write_user(tmp_path, "rsi_period = 21\n")

    assert load_component_settings("momentum", MomentumSettings, tmp_path) == _SHIPPED_DEFAULTS.model_copy(
        update={"rsi_period": 21}
    )


def test_an_empty_user_file_changes_nothing(tmp_path: Path) -> None:
    _write_user(tmp_path, "")

    assert load_component_settings("momentum", MomentumSettings, tmp_path) == _SHIPPED_DEFAULTS


def test_the_error_is_a_value_error() -> None:
    assert issubclass(ComponentSettingsError, ValueError)


def test_a_missing_shipped_file_is_an_error_that_names_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shipped = _use_shipped_file(monkeypatch, tmp_path, None)

    assert _message(tmp_path) == f"Settings file {shipped} is missing."


def test_invalid_toml_in_the_user_file_names_that_file(tmp_path: Path) -> None:
    text = "short_window = \n"
    with pytest.raises(tomllib.TOMLDecodeError) as parser:
        tomllib.loads(text)
    user = _write_user(tmp_path, text)

    assert _message(tmp_path) == f"Settings file {user} is not valid TOML: {str(parser.value).rstrip('.')}."


def test_invalid_toml_in_the_shipped_file_names_that_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shipped = _use_shipped_file(monkeypatch, tmp_path, "short_window = \n")

    assert _message(tmp_path).startswith(f"Settings file {shipped} is not valid TOML: ")


def test_an_unknown_key_in_the_user_file_names_that_file(tmp_path: Path) -> None:
    user = _write_user(tmp_path, "medium_window = 100\n")

    assert _message(tmp_path) == f"Settings file {user} is invalid: medium_window: Extra inputs are not permitted."


def test_an_invalid_user_value_names_the_file_and_key_and_never_repeats_the_value(tmp_path: Path) -> None:
    user = _write_user(tmp_path, "short_window = -7\n")

    message = _message(tmp_path)

    assert message == f"Settings file {user} is invalid: short_window: Input should be greater than 0."


def test_a_rule_that_spans_keys_names_the_user_file_and_no_key(tmp_path: Path) -> None:
    user = _write_user(tmp_path, "short_window = 300\n")

    assert _message(tmp_path) == f"Settings file {user} is invalid: short_window must be smaller than long_window."


def test_an_invalid_value_that_comes_from_the_shipped_file_names_the_shipped_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shipped = _use_shipped_file(monkeypatch, tmp_path, _VALID.replace("rsi_period = 14", "rsi_period = -1"))
    _write_user(tmp_path, "short_window = 40\n")

    assert _message(tmp_path) == f"Settings file {shipped} is invalid: rsi_period: Input should be greater than 0."


def test_a_key_in_neither_file_is_reported_against_the_shipped_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shipped = _use_shipped_file(monkeypatch, tmp_path, _VALID.replace("rsi_period = 14\n", ""))

    assert _message(tmp_path) == f"Settings file {shipped} is invalid: rsi_period: Field required."


def test_a_file_is_read_once_per_process_until_the_cache_is_cleared(tmp_path: Path) -> None:
    _write_user(tmp_path, "rsi_period = 20\n")
    first = load_component_settings("momentum", MomentumSettings, tmp_path)
    _write_user(tmp_path, "rsi_period = 21\n")

    assert load_component_settings("momentum", MomentumSettings, tmp_path) is first
    assert first.rsi_period == 20

    clear_component_settings_cache()
    reloaded = load_component_settings("momentum", MomentumSettings, tmp_path)
    assert reloaded is not first
    assert reloaded.rsi_period == 21


def test_the_cache_is_per_settings_folder(tmp_path: Path) -> None:
    other = tmp_path / "other"
    _write_user(other, "rsi_period = 30\n")

    assert load_component_settings("momentum", MomentumSettings, tmp_path).rsi_period == 14
    assert load_component_settings("momentum", MomentumSettings, other).rsi_period == 30


def test_a_failed_load_is_not_cached(tmp_path: Path) -> None:
    user = _write_user(tmp_path, "rsi_period = -3\n")
    assert _message(tmp_path).startswith(f"Settings file {user} is invalid")

    user.write_text("rsi_period = 22\n", encoding="utf-8")

    assert load_component_settings("momentum", MomentumSettings, tmp_path).rsi_period == 22
