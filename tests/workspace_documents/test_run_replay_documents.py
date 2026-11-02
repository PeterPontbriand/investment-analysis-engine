"""The replay's document projection of every strategy's stored run, and the generic replay's two paths."""

from functools import cache

import pytest
from typer.testing import CliRunner

from investment_analysis_engine.cli import app
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.reporting.documents.strategy_document import strategy_document_json
from investment_analysis_engine.reporting.replay_inputs import ReplayOptions, UnsupportedProjectionError
from investment_analysis_engine.strategy_wiring import DOCUMENTS_BY_KEY, EVIDENCE_BY_KEY, REPLAYS_BY_KEY, STRATEGIES
from investment_analysis_engine.workspace.repositories.analysis_runs import SQLiteAnalysisRunRepository
from investment_analysis_engine.workspace.runs import AnalysisRun
from investment_analysis_engine.workspace_documents.run_replay import project_run, project_run_document
from scripts.strategy_conformance import stored_runs

runner = CliRunner()


@cache
def _runs_by_alias() -> dict[str, AnalysisRun]:
    """Return one stored run per declared strategy, executed from its golden fixture."""
    runs: dict[str, AnalysisRun] = {}
    for entry in stored_runs(STRATEGIES):
        assert isinstance(entry.run, AnalysisRun)
        runs[entry.descriptor.alias] = entry.run
    return runs


def _any_run() -> AnalysisRun:
    return next(iter(_runs_by_alias().values()))


@pytest.mark.parametrize("alias", [descriptor.alias for descriptor in STRATEGIES])
@pytest.mark.usefixtures("isolated_cli_settings")
def test_a_stored_runs_document_is_its_strategys_document_and_serializes_to_runs_show_json(
    alias: str, isolated_cli_settings: ProjectSettings
) -> None:
    """The document is the strategy's document type; serialized, it is the ``runs show --json`` output."""
    descriptor = next(item for item in STRATEGIES if item.alias == alias)
    run = _runs_by_alias()[alias]
    database = SQLiteDatabase(isolated_cli_settings)
    try:
        SQLiteAnalysisRunRepository(database).insert(run)
    finally:
        database.close()

    document = project_run_document(run, codecs=EVIDENCE_BY_KEY, documents=DOCUMENTS_BY_KEY)

    assert isinstance(document, descriptor.json_envelope)
    shown = runner.invoke(app, ["runs", "show", str(run.analysis_run_id), "--json"])
    assert shown.exit_code == 0, shown.output
    assert strategy_document_json(document) == shown.output.rstrip("\n")


def test_the_text_path_projects_text_and_defaults_to_the_concise_mode() -> None:
    run = _any_run()
    concise = project_run(run, ReplayOptions(), codecs=EVIDENCE_BY_KEY, replays=REPLAYS_BY_KEY)
    assert concise
    assert not concise.lstrip().startswith("{")
    assert concise == project_run(run, codecs=EVIDENCE_BY_KEY, replays=REPLAYS_BY_KEY)


def test_the_document_path_rejects_an_unsupported_projection_version() -> None:
    run = _any_run().model_copy(update={"projection_version": 2})
    with pytest.raises(UnsupportedProjectionError, match="projection version"):
        project_run_document(run, codecs=EVIDENCE_BY_KEY, documents=DOCUMENTS_BY_KEY)


def test_the_text_path_rejects_an_unsupported_projection_version() -> None:
    run = _any_run().model_copy(update={"projection_version": 2})
    with pytest.raises(UnsupportedProjectionError, match="projection version"):
        project_run(run, codecs=EVIDENCE_BY_KEY, replays=REPLAYS_BY_KEY)


def test_the_document_path_rejects_an_undeclared_method() -> None:
    run = _any_run().model_copy(update={"analysis_id": "example_undeclared", "method_id": "example_method"})
    with pytest.raises(UnsupportedProjectionError, match="No v1 replay"):
        project_run_document(run, codecs=EVIDENCE_BY_KEY, documents=DOCUMENTS_BY_KEY)


def test_the_text_path_rejects_an_undeclared_method() -> None:
    run = _any_run().model_copy(update={"analysis_id": "example_undeclared", "method_id": "example_method"})
    with pytest.raises(UnsupportedProjectionError, match="No v1 replay"):
        project_run(run, codecs=EVIDENCE_BY_KEY, replays=REPLAYS_BY_KEY)


def test_each_path_uses_only_its_own_projector_mapping() -> None:
    """A method declared for text only has no document, and a method declared for documents only has no text."""
    run = _any_run()
    key = (run.analysis_id, run.method_id)
    without_document = {other: value for other, value in DOCUMENTS_BY_KEY.items() if other != key}
    without_text = {other: value for other, value in REPLAYS_BY_KEY.items() if other != key}
    with pytest.raises(UnsupportedProjectionError):
        project_run_document(run, codecs=EVIDENCE_BY_KEY, documents=without_document)
    assert project_run(run, codecs=EVIDENCE_BY_KEY, replays=REPLAYS_BY_KEY)
    with pytest.raises(UnsupportedProjectionError):
        project_run(run, codecs=EVIDENCE_BY_KEY, replays=without_text)
    assert project_run_document(run, codecs=EVIDENCE_BY_KEY, documents=DOCUMENTS_BY_KEY)
