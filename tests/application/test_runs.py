"""The Analysis Run read operations: list, replay in every mode for every strategy, and compare."""

import logging
from collections.abc import Callable
from functools import cache
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import update
from typer.testing import CliRunner

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.runs import (
    compare_refresh_runs,
    list_runs,
    replay_run_document,
    replay_run_text,
)
from investment_analysis_engine.cli import app
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.data.repositories.readiness import DatabaseReadinessError
from investment_analysis_engine.data.repositories.schema import analysis_runs
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.reporting.documents.strategy_document import strategy_document_json
from investment_analysis_engine.reporting.presentation import PresentationMode
from investment_analysis_engine.reporting.replay_inputs import TextPresentationMode
from investment_analysis_engine.strategy_wiring import STRATEGIES
from investment_analysis_engine.workspace.codecs import InvalidStoredRunError
from investment_analysis_engine.workspace.repositories.analysis_runs import SQLiteAnalysisRunRepository
from investment_analysis_engine.workspace.runs import AnalysisRun, AnalysisRunNotFoundError, RunQuery
from investment_analysis_engine.workspace_documents.runs_compare import (
    DuplicateRefreshRunsError,
    no_runs_message,
)
from scripts.strategy_conformance import stored_runs
from tests._runs_compare_refresh import GROWTH, LONG_AVERAGE, MOMENTUM, refresh
from tests.application._unready_database import unready_database_url

runner = CliRunner()

_TEXT_MODES: tuple[tuple[TextPresentationMode, list[str]], ...] = (
    (PresentationMode.CONCISE, []),
    (PresentationMode.DETAILS, ["--details"]),
    (PresentationMode.DIAGNOSTICS, ["--diagnostics"]),
)


@cache
def _runs_by_alias() -> dict[str, AnalysisRun]:
    """Return one stored run per declared strategy, executed from its golden fixture."""
    runs: dict[str, AnalysisRun] = {}
    for entry in stored_runs(STRATEGIES):
        assert isinstance(entry.run, AnalysisRun)
        runs[entry.descriptor.alias] = entry.run
    return runs


def _store(settings: ProjectSettings, run: AnalysisRun) -> None:
    database = SQLiteDatabase(settings)
    try:
        SQLiteAnalysisRunRepository(database).insert(run)
    finally:
        database.close()


def _context(settings: ProjectSettings) -> ApplicationContext:
    return ApplicationContext(settings=settings)


def _unreadable_message(run_id: UUID) -> str:
    return f"Analysis Run {run_id} could not be read: its stored record is malformed or does not match its summary."


@pytest.mark.usefixtures("isolated_cli_settings")
def test_an_empty_store_lists_no_runs(isolated_cli_settings: ProjectSettings) -> None:
    assert list_runs(_context(isolated_cli_settings), RunQuery()) == ()


def test_the_list_returns_the_stored_summaries_and_applies_the_query(isolated_cli_settings: ProjectSettings) -> None:
    runs = _runs_by_alias()
    for run in runs.values():
        _store(isolated_cli_settings, run)

    everything = list_runs(_context(isolated_cli_settings), RunQuery())
    one = next(iter(runs.values()))
    filtered = list_runs(_context(isolated_cli_settings), RunQuery(method_id=one.method_id, limit=1))

    assert {item.analysis_run_id for item in everything} == {run.analysis_run_id for run in runs.values()}
    assert [item.analysis_run_id for item in filtered] == [one.analysis_run_id]


@pytest.mark.parametrize("alias", [descriptor.alias for descriptor in STRATEGIES])
def test_a_stored_run_replays_in_every_mode_as_the_command_prints_it(
    alias: str, isolated_cli_settings: ProjectSettings
) -> None:
    descriptor = next(item for item in STRATEGIES if item.alias == alias)
    run = _runs_by_alias()[alias]
    _store(isolated_cli_settings, run)
    context = _context(isolated_cli_settings)
    run_id = str(run.analysis_run_id)

    for mode, flags in _TEXT_MODES:
        shown = runner.invoke(app, ["runs", "show", run_id, *flags])
        assert shown.exit_code == 0, shown.output
        assert replay_run_text(context, run.analysis_run_id, mode) == shown.stdout.rstrip("\n")

    document = replay_run_document(context, run.analysis_run_id)
    assert isinstance(document, descriptor.json_envelope)
    shown_json = runner.invoke(app, ["runs", "show", run_id, "--json"])
    assert shown_json.exit_code == 0, shown_json.output
    assert strategy_document_json(document) == shown_json.stdout.rstrip("\n")


def test_a_missing_run_raises_the_not_found_error_for_both_projections(isolated_cli_settings: ProjectSettings) -> None:
    missing = uuid4()
    context = _context(isolated_cli_settings)
    message = f"No Analysis Run with ID {missing} exists."

    with pytest.raises(AnalysisRunNotFoundError) as text_error:
        replay_run_text(context, missing, PresentationMode.CONCISE)
    with pytest.raises(AnalysisRunNotFoundError) as document_error:
        replay_run_document(context, missing)

    assert str(text_error.value) == str(document_error.value) == message


def test_a_malformed_stored_record_is_logged_and_raised_as_the_sanitized_error(
    isolated_cli_settings: ProjectSettings, caplog: pytest.LogCaptureFixture
) -> None:
    run = next(iter(_runs_by_alias().values()))
    _store(isolated_cli_settings, run)
    database = SQLiteDatabase(isolated_cli_settings)
    try:
        with database.transaction() as connection:
            connection.execute(
                update(analysis_runs)
                .where(analysis_runs.c.analysis_run_id == str(run.analysis_run_id))
                .values(envelope_json='{"requested_config": {}}')
            )
    finally:
        database.close()

    for operation in (
        lambda: replay_run_text(_context(isolated_cli_settings), run.analysis_run_id, PresentationMode.CONCISE),
        lambda: replay_run_document(_context(isolated_cli_settings), run.analysis_run_id),
    ):
        caplog.clear()
        with (
            caplog.at_level(logging.ERROR, logger="investment_analysis_engine.application.runs"),
            pytest.raises(InvalidStoredRunError) as caught,
        ):
            operation()
        assert str(caught.value) == _unreadable_message(run.analysis_run_id)
        assert "validation error" not in str(caught.value)
        assert any(
            record.name == "investment_analysis_engine.application.runs"
            and record.exc_info is not None
            and "validation error" in str(record.exc_info[1])
            for record in caplog.records
        )


@pytest.mark.usefixtures("stub_yahoo_identity_metadata")
def test_the_compare_table_is_the_refreshs_document(isolated_cli_settings: ProjectSettings) -> None:
    refresh_id = refresh(isolated_cli_settings, entries=[("SYNTH", MOMENTUM)])

    document = compare_refresh_runs(_context(isolated_cli_settings), refresh_id)

    assert document.refresh_id == refresh_id
    assert [row.ticker for row in document.rows] == ["SYNTH"]


def test_a_refresh_with_no_runs_raises_the_not_found_error_with_the_shared_message(
    isolated_cli_settings: ProjectSettings,
) -> None:
    unknown = uuid4()
    with pytest.raises(AnalysisRunNotFoundError) as caught:
        compare_refresh_runs(_context(isolated_cli_settings), unknown)
    assert str(caught.value) == no_runs_message(unknown)


@pytest.mark.usefixtures("stub_yahoo_identity_metadata")
def test_two_runs_of_one_ticker_and_strategy_raise_the_duplicate_error(isolated_cli_settings: ProjectSettings) -> None:
    refresh_id = refresh(
        isolated_cli_settings,
        entries=[("SYNTH", MOMENTUM), ("SYNTH", LONG_AVERAGE), ("ERROR", GROWTH), ("ERROR", GROWTH)],
    )
    with pytest.raises(DuplicateRefreshRunsError, match="SYNTH momentum"):
        compare_refresh_runs(_context(isolated_cli_settings), refresh_id)


@pytest.mark.parametrize(
    "operation",
    [
        lambda context: list_runs(context, RunQuery()),
        lambda context: replay_run_text(context, uuid4(), PresentationMode.CONCISE),
        lambda context: replay_run_document(context, uuid4()),
        lambda context: compare_refresh_runs(context, uuid4()),
    ],
    ids=["list", "text", "document", "compare"],
)
def test_an_unready_database_is_a_readiness_error(
    operation: Callable[[ApplicationContext], object], tmp_path: Path
) -> None:
    context = _context(ProjectSettings(database_url=unready_database_url(tmp_path)))
    with pytest.raises(DatabaseReadinessError):
        operation(context)
