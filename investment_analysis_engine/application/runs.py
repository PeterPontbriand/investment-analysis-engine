"""The Analysis Run read operations: list, replay and compare."""

import logging
from uuid import UUID

from pydantic import BaseModel

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.database import open_database
from investment_analysis_engine.reporting.replay_inputs import ReplayOptions, TextPresentationMode
from investment_analysis_engine.strategy_wiring import (
    DOCUMENTS_BY_KEY,
    EVIDENCE_BY_KEY,
    REPLAYS_BY_KEY,
    STRATEGIES,
)
from investment_analysis_engine.workspace.codecs import InvalidStoredRunError
from investment_analysis_engine.workspace.repositories.analysis_runs import SQLiteAnalysisRunRepository
from investment_analysis_engine.workspace.runs import (
    AnalysisRun,
    AnalysisRunNotFoundError,
    AnalysisRunSummary,
    RunQuery,
)
from investment_analysis_engine.workspace_documents.run_replay import project_run, project_run_document
from investment_analysis_engine.workspace_documents.runs_compare import (
    CompareColumn,
    RunsCompareDocument,
    build_runs_compare,
    no_runs_message,
)

logger = logging.getLogger(__name__)


def _compare_columns() -> tuple[CompareColumn, ...]:
    """Return the declared strategies as table columns, in the order the strategies are declared."""
    return tuple(
        CompareColumn(
            analysis_id=descriptor.analysis_id,
            method_id=descriptor.method_id,
            alias=descriptor.alias,
            label=descriptor.label,
            codec=EVIDENCE_BY_KEY[(descriptor.analysis_id, descriptor.method_id)],
            headline=descriptor.behavior.headline_for,
        )
        for descriptor in STRATEGIES
    )


def _stored_run(context: ApplicationContext, run_id: UUID) -> AnalysisRun:
    """Read one stored run, closing the connection before the caller replays it.

    Raises:
        AnalysisRunNotFoundError: If no run has that ID.
        InvalidStoredRunError: If the stored record is malformed or does not match its summary.
    """
    with open_database(context) as database:
        repository = SQLiteAnalysisRunRepository(database)
        try:
            run = repository.get(run_id)
        except ValueError as exc:
            # The repository's documented contract: a malformed or internally inconsistent stored envelope raises
            # a plain ValueError from get(); its text is the validation library's, so it goes to the log.
            logger.exception("Analysis Run %s could not be read.", run_id)
            raise InvalidStoredRunError(
                f"Analysis Run {run_id} could not be read: "
                "its stored record is malformed or does not match its summary."
            ) from exc
    if run is None:
        raise AnalysisRunNotFoundError(f"No Analysis Run with ID {run_id} exists.")
    return run


def list_runs(context: ApplicationContext, query: RunQuery) -> tuple[AnalysisRunSummary, ...]:
    """Return the run summaries matching ``query``, most recently completed first."""
    with open_database(context) as database:
        return SQLiteAnalysisRunRepository(database).list(query)


def replay_run_text(context: ApplicationContext, run_id: UUID, mode: TextPresentationMode) -> str:
    """Replay one stored run as text in ``mode``, using only its own captured evidence.

    Raises:
        AnalysisRunNotFoundError: If no run has that ID.
        InvalidStoredRunError: If the stored record is malformed.
        UnsupportedRunVersionError: If the run was stored under a version this one cannot read.
        UnsupportedProjectionError: If the run's strategy declares no replay.
    """
    run = _stored_run(context, run_id)
    return project_run(run, ReplayOptions(mode=mode), codecs=EVIDENCE_BY_KEY, replays=REPLAYS_BY_KEY)


def replay_run_document(context: ApplicationContext, run_id: UUID) -> BaseModel:
    """Replay one stored run as its strategy's typed ``--json`` document, using only its own captured evidence.

    Raises:
        AnalysisRunNotFoundError: If no run has that ID.
        InvalidStoredRunError: If the stored record is malformed.
        UnsupportedRunVersionError: If the run was stored under a version this one cannot read.
        UnsupportedProjectionError: If the run's strategy declares no replay.
    """
    run = _stored_run(context, run_id)
    return project_run_document(run, codecs=EVIDENCE_BY_KEY, documents=DOCUMENTS_BY_KEY)


def compare_refresh_runs(context: ApplicationContext, refresh_id: UUID) -> RunsCompareDocument:
    """Return the runs of one refresh as a table, one row per ticker and one column group per strategy.

    Raises:
        AnalysisRunNotFoundError: If no run is stored for the refresh.
        DuplicateRefreshRunsError: If the refresh holds more than one run of a ticker and strategy.
        InvalidStoredRunError: If a run's evidence is invalid.
    """
    with open_database(context) as database:
        stored = SQLiteAnalysisRunRepository(database).list_refresh_runs(refresh_id)
    if not stored:
        raise AnalysisRunNotFoundError(no_runs_message(refresh_id))
    return build_runs_compare(refresh_id, stored, _compare_columns())


__all__ = ["compare_refresh_runs", "list_runs", "replay_run_document", "replay_run_text"]
