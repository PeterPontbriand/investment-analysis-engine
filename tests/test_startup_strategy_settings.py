"""A bad strategy settings file stops every command at startup with one message and exit code 2."""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from src.core.settings_error import StrategySettingsError
from src.main import main

_MESSAGE = "Settings file config/strategies/momentum.toml is invalid: short_window: Input should be greater than 0."


@pytest.mark.parametrize("arguments", [["ian", "--help"], ["ian", "momentum", "KO"]])
def test_a_loader_error_prints_the_message_and_exits_with_code_2(
    arguments: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Importing the commands defines them, and defining them loads every declared file, so a fresh import is needed.
    monkeypatch.delitem(sys.modules, "src.cli")
    monkeypatch.setattr(sys, "argv", arguments)
    with (
        patch("src.main.setup_global_logging"),
        patch("src.main.teardown_global_logging"),
        patch("src.cli_composition.load_strategy_settings", side_effect=StrategySettingsError(_MESSAGE)),
        pytest.raises(SystemExit) as exit_info,
    ):
        main()

    captured = capsys.readouterr()
    assert exit_info.value.code == 2
    assert captured.err == f"{_MESSAGE}\n"
    assert captured.out == ""
