"""With ``--save-run``, the database check precedes the strategy's own composition, for every strategy.

A strategy that needs a declared SEC identity used to report ``configuration_error`` when the identity was missing and
the database needed an upgrade, for some of the commands and options; the save step's database check now runs first for
all of them, so the command reports the database's own code. The step order is an approved output change of API.3a.
"""

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from investment_analysis_engine.cli import app
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.data.repositories import migrations, readiness
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.strategy_wiring import STRATEGIES
from tests._direct_command_output import _COMMANDS

_EXTRA_ARGUMENTS = {"graham-growth": ["--expected-growth", "5", "--aaa-yield", "4.5"]}


def _arguments(alias: str) -> list[str]:
    """Return the fixed command line of ``alias`` with the options it requires."""
    return [alias, _COMMANDS[alias][1], *_EXTRA_ARGUMENTS.get(alias, [])]


@pytest.mark.parametrize("output", [["--json"], []], ids=["json", "text"])
@pytest.mark.parametrize("cache", [[], ["--no-cache"]], ids=["cache", "no-cache"])
@pytest.mark.parametrize("alias", [item.alias for item in STRATEGIES])
def test_the_database_check_runs_before_the_strategy_composes_its_providers(
    alias: str, cache: list[str], output: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "older.sqlite3"
    selected = ProjectSettings(database_url=f"sqlite:///{path.as_posix()}", config_dir=tmp_path)
    selected.sec_user_agent = None
    database = SQLiteDatabase(selected)
    try:
        readiness.ensure_database_ready(database)
    finally:
        database.close()
    resources = migrations.migration_resources()
    monkeypatch.setattr(
        readiness,
        "migration_resources",
        lambda: replace(resources, head="synthetic_head", ancestors=frozenset({resources.head})),
    )
    with patch("investment_analysis_engine.cli_support.settings", selected):
        result = CliRunner().invoke(app, [*_arguments(alias), "--save-run", *cache, *output])

    assert result.exit_code == 1, result.output
    if output:
        assert json.loads(result.stdout)["reason_code"] == "database_upgrade_required"
    else:
        assert "SEC EDGAR access is not configured" not in result.output
        assert "ian db upgrade" in result.stderr
