"""The ``runs list --json`` document as the command writes it: key order, the empty store, and ``has_more``."""

import json
from uuid import UUID

import pytest
from typer.testing import CliRunner

from investment_analysis_engine.cli import app
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.strategy_wiring import STRATEGIES
from investment_analysis_engine.workspace.repositories.analysis_runs import SQLiteAnalysisRunRepository
from investment_analysis_engine.workspace.runs import AnalysisRun
from investment_analysis_engine.workspace_documents.runs import RunsListDocument
from scripts.strategy_conformance import stored_runs

runner = CliRunner()


def _store_copies(settings: ProjectSettings, count: int) -> None:
    """Store ``count`` runs that differ only in their IDs, which are 1 to ``count``."""
    template = next(entry.run for entry in stored_runs(STRATEGIES) if isinstance(entry.run, AnalysisRun))
    database = SQLiteDatabase(settings)
    try:
        repository = SQLiteAnalysisRunRepository(database)
        for number in range(1, count + 1):
            repository.insert(template.model_copy(update={"analysis_run_id": UUID(int=number)}))
    finally:
        database.close()


@pytest.mark.usefixtures("isolated_cli_settings")
def test_an_empty_store_prints_a_version_one_page_with_no_items() -> None:
    result = runner.invoke(app, ["runs", "list", "--json"])

    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == '{"schema_version": 1, "has_more": false, "items": []}'


def test_the_command_reports_has_more_for_the_page_it_prints(isolated_cli_settings: ProjectSettings) -> None:
    _store_copies(isolated_cli_settings, 3)

    pages = {
        limit: json.loads(runner.invoke(app, ["runs", "list", "--limit", str(limit), "--json"]).stdout)
        for limit in (2, 3, 4)
    }

    assert [list(page) for page in pages.values()] == [["schema_version", "has_more", "items"]] * 3
    assert {limit: (len(page["items"]), page["has_more"]) for limit, page in pages.items()} == {
        2: (2, True),
        3: (3, False),
        4: (3, False),
    }
    assert RunsListDocument.model_validate(pages[2]).has_more is True


def test_the_text_output_does_not_mention_has_more(isolated_cli_settings: ProjectSettings) -> None:
    _store_copies(isolated_cli_settings, 2)

    result = runner.invoke(app, ["runs", "list", "--limit", "1"])

    assert result.exit_code == 0, result.output
    assert "has_more" not in result.output
    assert len(result.stdout.strip().splitlines()) == 1
