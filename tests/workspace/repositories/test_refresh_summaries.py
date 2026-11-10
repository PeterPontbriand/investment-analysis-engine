"""Verify the grouped, filtered and paged refresh summaries read from the stored run columns alone."""

from uuid import UUID

import pytest
from sqlalchemy import select, update

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.data.repositories.schema import analysis_runs
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.workspace.repositories.analysis_runs import SQLiteAnalysisRunRepository
from investment_analysis_engine.workspace.runs import RefreshQuery
from tests._refresh_runs import CORE_ID, VALUE_ID, at, refresh_run

REFRESH_A = UUID("aaaaaaaa-0000-4000-8000-000000000001")
REFRESH_B = UUID("aaaaaaaa-0000-4000-8000-000000000002")
REFRESH_C = UUID("aaaaaaaa-0000-4000-8000-000000000003")
REFRESH_D = UUID("aaaaaaaa-0000-4000-8000-000000000004")


@pytest.fixture
def repository(migrated_database: SQLiteDatabase) -> SQLiteAnalysisRunRepository:
    return SQLiteAnalysisRunRepository(migrated_database)


def _store_refreshes(repository: SQLiteAnalysisRunRepository) -> None:
    core = (CORE_ID, "Core")
    for position, (minute, status) in enumerate(
        ((0, RunOutcome.COMPLETED), (1, RunOutcome.COMPLETED), (2, RunOutcome.FAILED))
    ):
        repository.insert(refresh_run(REFRESH_A, position, at(minute), watchlist=core, status=status))
    repository.insert(refresh_run(REFRESH_B, 0, at(10), watchlist=(CORE_ID, "Core before rename")))
    repository.insert(refresh_run(REFRESH_B, 1, at(11), watchlist=(CORE_ID, "Core before rename")))
    repository.insert(refresh_run(REFRESH_C, 0, at(20), status=RunOutcome.UNAVAILABLE))
    repository.insert(
        refresh_run(REFRESH_D, 0, at(20), watchlist=(VALUE_ID, "Value"), status=RunOutcome.NOT_APPLICABLE)
    )
    repository.insert(refresh_run(None, 0, at(30)))


def test_a_refresh_is_summarized_from_its_stored_runs(repository: SQLiteAnalysisRunRepository) -> None:
    _store_refreshes(repository)

    page = repository.list_refreshes(RefreshQuery())
    by_id = {item.refresh_id: item for item in page.summaries}

    first = by_id[REFRESH_A]
    assert (first.watchlist_id, first.watchlist_name, first.run_count) == (CORE_ID, "Core", 3)
    assert (first.first_completed_at, first.last_completed_at) == (at(0), at(2))
    assert dict(first.outcome_counts) == {
        RunOutcome.COMPLETED: 2,
        RunOutcome.UNAVAILABLE: 0,
        RunOutcome.NOT_APPLICABLE: 0,
        RunOutcome.FAILED: 1,
    }
    assert by_id[REFRESH_B].watchlist_name == "Core before rename"
    entries = by_id[REFRESH_C]
    assert (entries.watchlist_id, entries.watchlist_name, entries.run_count) == (None, None, 1)
    assert entries.outcome_counts[RunOutcome.UNAVAILABLE] == 1
    assert len(by_id) == 4
    assert not page.has_more


def test_refreshes_order_newest_first_then_by_refresh_id_descending(repository: SQLiteAnalysisRunRepository) -> None:
    _store_refreshes(repository)

    ordered = [item.refresh_id for item in repository.list_refreshes(RefreshQuery()).summaries]

    assert ordered == [REFRESH_D, REFRESH_C, REFRESH_B, REFRESH_A]


def test_the_watchlist_filter_keeps_only_that_watchlists_refreshes(repository: SQLiteAnalysisRunRepository) -> None:
    _store_refreshes(repository)

    core = repository.list_refreshes(RefreshQuery(watchlist_id=CORE_ID))
    value = repository.list_refreshes(RefreshQuery(watchlist_id=VALUE_ID))
    deleted = repository.list_refreshes(RefreshQuery(watchlist_id=UUID(int=7)))

    assert [item.refresh_id for item in core.summaries] == [REFRESH_B, REFRESH_A]
    assert [item.run_count for item in core.summaries] == [2, 3]
    assert [item.refresh_id for item in value.summaries] == [REFRESH_D]
    assert deleted.summaries == ()
    assert not deleted.has_more


def test_a_refresh_with_an_unreadable_run_still_counts_every_stored_run(
    repository: SQLiteAnalysisRunRepository, migrated_database: SQLiteDatabase
) -> None:
    _store_refreshes(repository)
    with migrated_database.transaction() as connection:
        connection.execute(
            update(analysis_runs)
            .where(analysis_runs.c.refresh_id == str(REFRESH_A), analysis_runs.c.batch_position == 1)
            .values(watchlist_id=None, watchlist_name=None, envelope_json="{}")
        )

    summary = next(
        item
        for item in repository.list_refreshes(RefreshQuery(watchlist_id=CORE_ID)).summaries
        if item.refresh_id == REFRESH_A
    )

    assert (summary.run_count, summary.watchlist_name) == (3, "Core")


def test_refreshes_page_with_has_more_and_no_total(repository: SQLiteAnalysisRunRepository) -> None:
    _store_refreshes(repository)

    first = repository.list_refreshes(RefreshQuery(limit=3))
    second = repository.list_refreshes(RefreshQuery(limit=3, offset=3))
    beyond = repository.list_refreshes(RefreshQuery(limit=3, offset=4))

    assert ([item.refresh_id for item in first.summaries], first.has_more) == ([REFRESH_D, REFRESH_C, REFRESH_B], True)
    assert ([item.refresh_id for item in second.summaries], second.has_more) == ([REFRESH_A], False)
    assert (beyond.summaries, beyond.has_more) == ((), False)


def test_an_empty_store_lists_no_refreshes(repository: SQLiteAnalysisRunRepository) -> None:
    page = repository.list_refreshes(RefreshQuery())

    assert (page.summaries, page.has_more) == ((), False)


def test_insert_copies_the_envelopes_watchlist_into_the_summary_columns(
    repository: SQLiteAnalysisRunRepository, migrated_database: SQLiteDatabase
) -> None:
    named = refresh_run(REFRESH_A, 0, at(0), watchlist=(CORE_ID, "Core"))
    unnamed = refresh_run(REFRESH_C, 0, at(1))
    repository.insert(named)
    repository.insert(unnamed)

    with migrated_database.read() as connection:
        rows = {
            row["analysis_run_id"]: (row["watchlist_id"], row["watchlist_name"])
            for row in connection.execute(
                select(analysis_runs.c.analysis_run_id, analysis_runs.c.watchlist_id, analysis_runs.c.watchlist_name)
            )
            .mappings()
            .all()
        }

    assert rows == {str(named.analysis_run_id): (str(CORE_ID), "Core"), str(unnamed.analysis_run_id): (None, None)}
    assert repository.get(named.analysis_run_id) == named
