"""T22: every strategy's direct command, run with ``--save-run``, stores exactly one run its codec accepts.

The per-alias setup is the fixture arguments and providers of ``tests/_direct_command_output.py``, which is
hand-written test data keyed by alias; a descriptor with no entry fails with ``no save-run fixture for alias``.
Each command runs for real against a temporary, migrated database.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import ExitStack
from pathlib import Path

import pytest
from alembic.config import Config
from typer.testing import CliRunner

from alembic import command
from scripts import strategy_conformance as conformance
from src.cli import app
from src.config import ProjectSettings
from src.config import settings as real_settings
from src.data.repositories.analysis_runs import SQLiteAnalysisRunRepository
from src.data.repositories.sqlite import SQLiteDatabase
from src.data.sec_edgar import SEC_PROVIDER_ID
from src.evaluation.fixtures.graham import PROVIDER_ID
from src.strategy_wiring import STRATEGIES
from src.workspace.runs import AnalysisRun, RunQuery
from tests._direct_command_output import _COMMANDS, enter_fixture_providers

_REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


def _stored_runs(directory: Path, monkeypatch: pytest.MonkeyPatch, alias: str) -> Callable[[], Sequence[AnalysisRun]]:
    """Return a function that runs ``alias`` with ``--save-run`` and reads back what its database holds."""

    def run() -> Sequence[AnalysisRun]:
        directory.mkdir()
        url = f"sqlite:///{(directory / 'save_run.sqlite3').as_posix()}"
        config = Config(str(_REPOSITORY_ROOT / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
        command.upgrade(config, "head")
        isolated = ProjectSettings(**(real_settings.model_dump() | {"database_url": url}))
        monkeypatch.setattr("src.cli_run_support.settings", isolated)
        monkeypatch.setattr("src.strategies.momentum.cli.settings", isolated)
        # A saved run's selection admits only the providers the CLI supports, so the fixture provider's id is
        # replaced by SEC EDGAR, and the fixture facts are relabeled to agree with it.
        arguments = [SEC_PROVIDER_ID if argument == PROVIDER_ID else argument for argument in _COMMANDS[alias]]
        with ExitStack() as stack:
            enter_fixture_providers(stack, alias, sec_labeled=True)
            result = CliRunner().invoke(app, [*arguments, "--save-run"])
        assert result.exit_code == 0, result.output
        repository = SQLiteAnalysisRunRepository(SQLiteDatabase(isolated))
        runs = (repository.get(summary.analysis_run_id) for summary in repository.list(RunQuery()))
        return tuple(item for item in runs if item is not None)

    return run


def test_t22_every_direct_command_saves_one_run_under_its_descriptors_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each alias's real command stores one run whose key equals the descriptor's and which decodes."""
    stored = {
        item.alias: _stored_runs(tmp_path / item.alias, monkeypatch, item.alias)
        for item in STRATEGIES
        if item.alias in _COMMANDS
    }
    assert conformance.save_run_gaps(STRATEGIES, stored) == []


def test_t22_names_an_alias_with_no_fixture() -> None:
    """A descriptor whose alias has no entry fails, naming the alias."""
    assert conformance.save_run_gaps(STRATEGIES, {}) == [
        f"no save-run fixture for alias {item.alias!r}" for item in STRATEGIES
    ]


def test_t22_reports_a_command_that_stores_no_run_and_a_run_under_another_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An alias that stores nothing, and one that stores another strategy's run, are both reported."""
    first, second = STRATEGIES[0], STRATEGIES[1]
    gaps = conformance.save_run_gaps(
        (first, second),
        {first.alias: lambda: (), second.alias: _stored_runs(tmp_path / "second", monkeypatch, second.alias)},
    )
    assert gaps == [f"alias {first.alias!r} stored no run"]
    gaps = conformance.save_run_gaps(
        (first,), {first.alias: _stored_runs(tmp_path / "other", monkeypatch, second.alias)}
    )
    assert len(gaps) == 1
    assert gaps[0].startswith(f"alias {first.alias!r} stored a run keyed ")
