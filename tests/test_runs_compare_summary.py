"""The runs comparison carries its refresh's summary, the same one the refreshes list gives for that refresh."""

from uuid import UUID, uuid4

import pytest
from typer.testing import CliRunner

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.runs import compare_refresh_runs, list_refreshes
from investment_analysis_engine.cli import app
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.workspace.repositories.analysis_runs import SQLiteAnalysisRunRepository
from investment_analysis_engine.workspace.runs import AnalysisRun, RefreshQuery
from investment_analysis_engine.workspace_documents.refreshes import build_refreshes_list_document
from investment_analysis_engine.workspace_documents.runs_compare import RunsCompareDocument
from tests._refresh_runs import CORE_ID, at, refresh_run
from tests._runs_compare_refresh import alter_row, as_version_3, refresh, run_ids

pytestmark = pytest.mark.usefixtures("isolated_cli_settings", "stub_yahoo_identity_metadata")

runner = CliRunner()

_SUMMARY_FIELDS = (
    "watchlist_id",
    "watchlist_name",
    "first_completed_at",
    "last_completed_at",
    "run_count",
    "outcome_counts",
)


def _insert(settings: ProjectSettings, runs: list[AnalysisRun]) -> None:
    database = SQLiteDatabase(settings)
    try:
        repository = SQLiteAnalysisRunRepository(database)
        for run in runs:
            repository.insert(run)
    finally:
        database.close()


def _run(
    refresh_id: UUID,
    position: int,
    minute: int,
    *,
    watchlist: tuple[UUID, str] | None = None,
    outcome: RunOutcome = RunOutcome.COMPLETED,
) -> AnalysisRun:
    """Return a stored run of its own ticker, so a refresh holds no two runs of one ticker and strategy."""
    run = refresh_run(refresh_id, position, at(minute), watchlist=watchlist, outcome=outcome)
    return run.model_copy(update={"ticker": f"T{position}", "method_version": 99})


def _list_item(settings: ProjectSettings, refresh_id: UUID) -> dict[str, object]:
    page = list_refreshes(ApplicationContext(settings=settings), RefreshQuery(limit=100))
    items = build_refreshes_list_document(page.summaries, has_more=page.has_more).model_dump(mode="json")["items"]
    (item,) = [item for item in items if item["refresh_id"] == str(refresh_id)]
    return dict(item)


def _assert_equals_the_list_item(settings: ProjectSettings, refresh_id: UUID) -> RunsCompareDocument:
    document = compare_refresh_runs(ApplicationContext(settings=settings), refresh_id)
    served = document.model_dump(mode="json")
    item = _list_item(settings, refresh_id)
    assert {name: served[name] for name in _SUMMARY_FIELDS} == {name: item[name] for name in _SUMMARY_FIELDS}
    return document


def test_a_watchlist_refreshs_comparison_equals_its_list_item(isolated_cli_settings: ProjectSettings) -> None:
    refresh_id = refresh(isolated_cli_settings)

    document = _assert_equals_the_list_item(isolated_cli_settings, refresh_id)

    assert document.watchlist_name == "Core"
    assert document.run_count == 11
    assert document.outcome_counts.model_dump() == {"completed": 5, "unavailable": 3, "not_applicable": 0, "failed": 3}


def test_a_refresh_of_a_list_of_entries_has_a_null_watchlist(isolated_cli_settings: ProjectSettings) -> None:
    refresh_id = uuid4()
    _insert(isolated_cli_settings, [_run(refresh_id, 0, 1), _run(refresh_id, 1, 2, outcome=RunOutcome.UNAVAILABLE)])

    document = _assert_equals_the_list_item(isolated_cli_settings, refresh_id)

    assert (document.watchlist_id, document.watchlist_name) == (None, None)
    assert document.run_count == 2


def test_a_refresh_stopped_partway_counts_the_runs_it_stored(isolated_cli_settings: ProjectSettings) -> None:
    refresh_id = uuid4()
    other = uuid4()
    _insert(
        isolated_cli_settings,
        [
            _run(refresh_id, 0, 1, watchlist=(CORE_ID, "Core")),
            _run(refresh_id, 1, 2, watchlist=(CORE_ID, "Core"), outcome=RunOutcome.FAILED),
            _run(other, 0, 9, watchlist=(CORE_ID, "Core")),
        ],
    )

    document = _assert_equals_the_list_item(isolated_cli_settings, refresh_id)

    assert (document.run_count, len(document.rows)) == (2, 2)
    assert document.outcome_counts.failed == 1
    assert document.last_completed_at.minute == 2


def test_the_watchlist_shows_when_no_runs_envelope_can_be_read(isolated_cli_settings: ProjectSettings) -> None:
    refresh_id = refresh(isolated_cli_settings)
    for run_id in run_ids(isolated_cli_settings, refresh_id).values():
        alter_row(
            isolated_cli_settings, run_id, {"method_version": 99}, lambda envelope: envelope.update(method_version=99)
        )

    document = _assert_equals_the_list_item(isolated_cli_settings, refresh_id)

    assert document.watchlist_name == "Core"
    assert all(
        entry.run is None or entry.run.headline_unavailable == "unsupported_version"
        for row in document.rows
        for entry in row.entries
    )


def test_a_version_3_run_compares_as_an_unsupported_version(isolated_cli_settings: ProjectSettings) -> None:
    refresh_id = refresh(isolated_cli_settings)

    for run_id in run_ids(isolated_cli_settings, refresh_id).values():
        alter_row(isolated_cli_settings, run_id, {"run_schema_version": 3}, as_version_3)

    document = compare_refresh_runs(ApplicationContext(settings=isolated_cli_settings), refresh_id)

    runs = [entry.run for row in document.rows for entry in row.entries if entry.run is not None]
    assert runs
    assert all(run.headline_unavailable == "unsupported_version" for run in runs)


def test_the_heading_names_the_last_completion_with_and_without_a_watchlist(
    isolated_cli_settings: ProjectSettings,
) -> None:
    named, entries = uuid4(), uuid4()
    _insert(
        isolated_cli_settings,
        [
            _run(named, 0, 1, watchlist=(CORE_ID, "Core")),
            _run(named, 1, 3, watchlist=(CORE_ID, "Core")),
            _run(entries, 0, 5),
        ],
    )

    first_named = runner.invoke(app, ["runs", "compare", str(named)]).stdout.splitlines()[0]
    first_entries = runner.invoke(app, ["runs", "compare", str(entries)]).stdout.splitlines()[0]

    assert (
        first_named
        == f'Refresh {named} · watchlist "Core" · completed 2026-11-01T10:03:00+00:00 · 2 tickers · 1 strategy'
    )
    assert first_entries == f"Refresh {entries} · completed 2026-11-01T10:05:00+00:00 · 1 ticker · 1 strategy"
