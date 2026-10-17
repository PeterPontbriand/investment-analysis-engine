"""The strategy-settings loader: one cached read per file, and one message for each way a file can be wrong."""

from __future__ import annotations

import tomllib
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from investment_analysis_engine.config.strategy_settings import clear_strategy_settings_cache, load_strategy_settings
from investment_analysis_engine.core.settings_error import StrategySettingsError
from investment_analysis_engine.strategies.momentum.settings import MomentumSettings

_VALID = """\
short_window = 50
long_window = 200
rsi_period = 14
history_start_date = "2021-01-01"
"""
_FILE = "config/strategies/momentum.toml"


@pytest.fixture(autouse=True)
def _isolated_cache() -> Iterator[None]:
    """Start and end every test with nothing cached."""
    clear_strategy_settings_cache()
    yield
    clear_strategy_settings_cache()


def _load(directory: Path, text: str | None) -> MomentumSettings:
    """Write ``text`` as the Momentum file in ``directory`` (nothing when None) and load it."""
    if text is not None:
        (directory / "momentum.toml").write_text(text, encoding="utf-8")
    return load_strategy_settings("momentum", MomentumSettings, directory)


def _message(directory: Path, text: str | None) -> str:
    """Return the message of the error that loading ``text`` raises."""
    with pytest.raises(StrategySettingsError) as error:
        _load(directory, text)
    return str(error.value)


def test_a_valid_file_loads_into_the_model(tmp_path: Path) -> None:
    assert _load(tmp_path, _VALID) == MomentumSettings(
        short_window=50, long_window=200, rsi_period=14, history_start_date=date(2021, 1, 1)
    )


def test_the_error_is_a_value_error() -> None:
    assert issubclass(StrategySettingsError, ValueError)


def test_a_missing_file(tmp_path: Path) -> None:
    assert _message(tmp_path, None) == f"Settings file {_FILE} is missing."


def test_invalid_toml(tmp_path: Path) -> None:
    text = "short_window = \n"
    with pytest.raises(tomllib.TOMLDecodeError) as parser:
        tomllib.loads(text)

    assert _message(tmp_path, text) == f"Settings file {_FILE} is not valid TOML: {str(parser.value).rstrip('.')}."


def test_an_unknown_key(tmp_path: Path) -> None:
    message = _message(tmp_path, _VALID + "medium_window = 100\n")

    assert message == f"Settings file {_FILE} is invalid: medium_window: Extra inputs are not permitted."


def test_a_missing_key(tmp_path: Path) -> None:
    message = _message(tmp_path, _VALID.replace("rsi_period = 14\n", ""))

    assert message == f"Settings file {_FILE} is invalid: rsi_period: Field required."


def test_an_invalid_value_names_the_key_and_never_repeats_the_value(tmp_path: Path) -> None:
    message = _message(tmp_path, _VALID.replace("short_window = 50", "short_window = -7"))

    assert message == f"Settings file {_FILE} is invalid: short_window: Input should be greater than 0."
    assert "-7" not in message


def test_a_rule_that_spans_keys_names_no_key(tmp_path: Path) -> None:
    message = _message(tmp_path, _VALID.replace("short_window = 50", "short_window = 300"))

    assert message == f"Settings file {_FILE} is invalid: short_window must be smaller than long_window."


def test_a_file_is_read_once_per_process_until_the_cache_is_cleared(tmp_path: Path) -> None:
    first = _load(tmp_path, _VALID)
    (tmp_path / "momentum.toml").write_text(_VALID.replace("rsi_period = 14", "rsi_period = 21"), encoding="utf-8")

    assert load_strategy_settings("momentum", MomentumSettings, tmp_path) is first
    assert first.rsi_period == 14

    clear_strategy_settings_cache()
    reloaded = load_strategy_settings("momentum", MomentumSettings, tmp_path)
    assert reloaded is not first
    assert reloaded.rsi_period == 21


def test_a_failed_load_is_not_cached(tmp_path: Path) -> None:
    assert _message(tmp_path, None) == f"Settings file {_FILE} is missing."

    assert _load(tmp_path, _VALID).short_window == 50
