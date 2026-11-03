"""An unexpected exception while ``runs show`` replays a stored run is one fixed failure, in text and in JSON."""

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from investment_analysis_engine.cli import app
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.strategy_wiring import STRATEGIES
from investment_analysis_engine.workspace.repositories.analysis_runs import SQLiteAnalysisRunRepository
from investment_analysis_engine.workspace.runs import AnalysisRun
from scripts.strategy_conformance import stored_runs

runner = CliRunner()

_MESSAGE = "runs show failed unexpectedly."


def test_an_unexpected_replay_exception_is_the_fixed_execution_error_with_its_traceback_in_the_log(
    isolated_cli_settings: ProjectSettings, caplog: pytest.LogCaptureFixture
) -> None:
    run = stored_runs(STRATEGIES)[0].run
    assert isinstance(run, AnalysisRun)
    database = SQLiteDatabase(isolated_cli_settings)
    try:
        SQLiteAnalysisRunRepository(database).insert(run)
    finally:
        database.close()
    error = RuntimeError("replay detail that must stay out of the output")
    run_id = str(run.analysis_run_id)

    with (
        patch("investment_analysis_engine.application.runs.project_run", side_effect=error),
        patch("investment_analysis_engine.application.runs.project_run_document", side_effect=error),
    ):
        text = runner.invoke(app, ["runs", "show", run_id])
        as_json = runner.invoke(app, ["runs", "show", run_id, "--json"])

    assert (text.exit_code, text.stdout, text.stderr.strip()) == (1, "", _MESSAGE)
    assert (as_json.exit_code, as_json.stderr) == (1, "")
    envelope = json.loads(as_json.stdout)
    assert (envelope["reason_code"], envelope["reason"]) == ("execution_error", _MESSAGE)
    assert "replay detail" not in text.stderr + as_json.stdout
    assert any(record.exc_info and record.exc_info[1] is error for record in caplog.records)
