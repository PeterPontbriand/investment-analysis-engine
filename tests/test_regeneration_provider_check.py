"""The stored-output regeneration entry points run outside pytest and must never send a real provider request.

``tests/conftest.py`` turns the automatic provider check off for the suite, but the entry points
``python -m tests._direct_command_output`` and ``python -m tests._strategy_document_output`` do not run under it. Each
switches the check off itself. The tests read the setting the probe is built from and never build an enabled probe,
because an enabled probe sends a real request.
"""

from pathlib import Path

import pytest

from investment_analysis_engine.config import settings
from tests import _direct_command_output, _strategy_document_output


def _switched_off_now() -> bool:
    """Return whether the setting every command builds its probe from has the check off."""
    return not settings.provider_check


@pytest.fixture(autouse=True)
def provider_check_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Leave the setting on, as a run outside pytest would find it, and restore it afterwards."""
    monkeypatch.setattr(settings, "provider_check", True)
    assert not _switched_off_now()


def test_the_direct_command_entry_point_runs_every_command_with_the_check_off(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: list[bool] = []

    def run_command(command: str, mode: str) -> _direct_command_output.CommandOutput:
        del command, mode
        seen.append(_switched_off_now())
        return _direct_command_output.CommandOutput(0, b"{}", b"")

    monkeypatch.setattr(_direct_command_output, "EXPECTED_DIRECTORY", tmp_path)
    monkeypatch.setattr(_direct_command_output, "cases", lambda: iter([("momentum", "json")]))
    monkeypatch.setattr(_direct_command_output, "run_command", run_command)

    _direct_command_output.regenerate()

    assert seen == [True]
    assert not _switched_off_now(), "The entry point restores the setting when it finishes."


def test_the_strategy_document_entry_point_runs_every_case_with_the_check_off(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: list[bool] = []

    def produce(stem: str) -> _direct_command_output.CommandOutput:
        del stem
        seen.append(_switched_off_now())
        return _direct_command_output.CommandOutput(0, b"{}", b"")

    monkeypatch.setattr(_strategy_document_output, "EXPECTED_DIRECTORY", tmp_path)
    monkeypatch.setattr(_strategy_document_output, "cases", lambda: iter(["case.direct"]))
    monkeypatch.setattr(_strategy_document_output, "produce", produce)
    monkeypatch.setattr(_strategy_document_output, "expected_exit_code", lambda _stem: 0)

    _strategy_document_output.regenerate()

    assert seen == [True]
    assert not _switched_off_now()
