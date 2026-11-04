"""The Analysis Run read operations: list, replay and compare."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.database import open_database
from investment_analysis_engine.core.operator_errors import InvalidParameterError
from investment_analysis_engine.reporting.replay_inputs import ReplayOptions, TextPresentationMode
from investment_analysis_engine.strategy_wiring import (
    BY_METHOD_ID,
    DOCUMENTS_BY_KEY,
    EVIDENCE_BY_KEY,
    REPLAYS_BY_KEY,
    STRATEGIES,
)
from investment_analysis_engine.workspace.codecs import InvalidStoredRunError
from investment_analysis_engine.workspace.repositories.analysis_runs import SQLiteAnalysisRunRepository
from investment_analysis_engine.workspace.runs import (
    RUN_QUERY_MAX_LIMIT,
    RUN_QUERY_MIN_LIMIT,
    AnalysisRun,
    AnalysisRunNotFoundError,
    RunPage,
    RunQuery,
)
from investment_analysis_engine.workspace.watchlists import normalize_ticker
from investment_analysis_engine.workspace_documents.run_replay import project_run, project_run_document
from investment_analysis_engine.workspace_documents.runs_compare import (
    CompareColumn,
    RunsCompareDocument,
    build_runs_compare,
    no_runs_message,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunQueryNames:
    """How a caller spells each runs-list parameter, so a rejection names the parameter the caller used."""

    ticker: str
    method: str
    status: str
    refresh_id: str
    limit: str
    offset: str


def declared_method_id(value: str, *, name: str) -> str:
    """Return ``value`` when it is the ``method_id`` of a declared strategy.

    Raises:
        InvalidParameterError: If no declared strategy has that method identifier; ``name`` is the caller's
            spelling of the parameter.
    """
    if value not in BY_METHOD_ID:
        allowed = ", ".join(BY_METHOD_ID)
        raise InvalidParameterError(f"{name} must be one of: {allowed}.", parameters=(name,))
    return value


def parse_refresh_id(value: str, *, name: str) -> UUID:
    """Return ``value`` as a refresh ID.

    Raises:
        InvalidParameterError: If ``value`` is not a UUID; ``name`` is the caller's spelling of the parameter.
    """
    try:
        return UUID(value)
    except ValueError as exc:
        raise InvalidParameterError(f"{name} {value!r} is not a valid refresh ID.", parameters=(name,)) from exc


def build_run_query(  # noqa: PLR0913
    *,
    names: RunQueryNames,
    resolve_method: Callable[[str], str],
    ticker: str | None,
    method: str | None,
    status: str | None,
    refresh_id: str | None,
    limit: int,
    offset: int,
) -> RunQuery:
    """Check the raw values of a runs-list request, in the order the parameters are listed, and build the query.

    Args:
        names: The caller's spelling of each parameter, used in every message and in ``parameters``.
        resolve_method: Maps the caller's raw method value to a method identifier, raising
            :class:`InvalidParameterError` for one it does not accept.
        ticker: The raw ticker filter, or ``None``.
        method: The raw method filter, or ``None``.
        status: The raw outcome filter, or ``None``.
        refresh_id: The raw refresh ID filter, or ``None``.
        limit: The row limit.
        offset: The number of rows to skip.

    Raises:
        InvalidParameterError: If any value is rejected; the first rejected parameter is reported.
    """
    if ticker is not None and not ticker.strip():
        raise InvalidParameterError(f"{names.ticker} must not be empty.", parameters=(names.ticker,))
    method_id = None if method is None else resolve_method(method)
    outcome = None
    if status is not None:
        try:
            outcome = RunOutcome(status)
        except ValueError as exc:
            allowed = ", ".join(item.value for item in RunOutcome)
            raise InvalidParameterError(
                f"{names.status} must be one of: {allowed}.", parameters=(names.status,)
            ) from exc
    refresh_batch = None if refresh_id is None else parse_refresh_id(refresh_id, name=names.refresh_id)
    if not RUN_QUERY_MIN_LIMIT <= limit <= RUN_QUERY_MAX_LIMIT:
        raise InvalidParameterError(
            f"{names.limit} must be between {RUN_QUERY_MIN_LIMIT} and {RUN_QUERY_MAX_LIMIT}.",
            parameters=(names.limit,),
        )
    if offset < 0:
        raise InvalidParameterError(f"{names.offset} must be 0 or greater.", parameters=(names.offset,))
    return RunQuery(
        ticker=None if ticker is None else normalize_ticker(ticker),
        method_id=method_id,
        status=outcome,
        refresh_id=refresh_batch,
        limit=limit,
        offset=offset,
    )


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


def list_runs(context: ApplicationContext, query: RunQuery) -> RunPage:
    """Return the page of run summaries matching ``query``, most recently completed first, and whether more follow."""
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


__all__ = [
    "RunQueryNames",
    "build_run_query",
    "compare_refresh_runs",
    "declared_method_id",
    "list_runs",
    "parse_refresh_id",
    "replay_run_document",
    "replay_run_text",
]
