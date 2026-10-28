"""A bad strategy settings file stops every command at startup with one message and exit code 2."""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from investment_analysis_engine.config.component_settings import shipped_settings_path
from investment_analysis_engine.core.settings_error import ComponentSettingsError
from investment_analysis_engine.main import main
from investment_analysis_engine.strategies.momentum.settings import MomentumSettings

_MESSAGE = (
    f"Settings file {shipped_settings_path(MomentumSettings)} is invalid: short_window: Input should be greater than 0."
)


@pytest.mark.parametrize("arguments", [["ian", "--help"], ["ian", "momentum", "KO"]])
def test_a_loader_error_prints_the_message_and_exits_with_code_2(
    arguments: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Importing the commands defines them, and defining them loads every declared file, so a fresh import is needed.
    monkeypatch.delitem(sys.modules, "investment_analysis_engine.cli", raising=False)
    monkeypatch.setattr(sys, "argv", arguments)
    with (
        patch("investment_analysis_engine.utils.logger_util.setup_global_logging"),
        patch("investment_analysis_engine.utils.logger_util.teardown_global_logging"),
        patch(
            "investment_analysis_engine.cli_composition.load_component_settings",
            side_effect=ComponentSettingsError(_MESSAGE),
        ),
        pytest.raises(SystemExit) as exit_info,
    ):
        main()

    captured = capsys.readouterr()
    assert exit_info.value.code == 2
    assert captured.err == f"{_MESSAGE}\n"
    assert captured.out == ""
