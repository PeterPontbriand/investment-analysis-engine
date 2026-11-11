"""SQLite-backed append-only Analysis Run repository: insert, get, list.

No provider, network, or analysis work occurs here; only reads/writes against
a caller-owned, already-migrated :class:`SQLiteDatabase`. Runs are immutable
and append-only: insertion is the only write this repository exposes, a
duplicate ID is a conflict, and there is no update or delete. ``list`` reads
only the indexed relational summary columns and never decodes a full stored
envelope, so one corrupt record cannot break listing; ``get`` decodes and
cross-checks the full envelope against its own relational columns.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, ClassVar, cast
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy import and_, case, func, select, true
from sqlalchemy.exc import IntegrityError

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.core.failure_codes import FailureReasonCode
from investment_analysis_engine.data.repositories.schema import analysis_runs
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.workspace.runs import (
    AnalysisRun,
    AnalysisRunSummary,
    RefreshPage,
    RefreshQuery,
    RefreshSummary,
    RunPage,
    RunQuery,
)

_ENVELOPE_ADAPTER: TypeAdapter[AnalysisRun] = TypeAdapter(AnalysisRun)


@dataclass(frozen=True)
class StoredRefreshRun:
    """One run of a refresh as stored: its indexed identity, outcome and versions, with its envelope decoded on demand.

    The indexed fields are read without decoding the stored envelope, so a refresh that holds a run of an older
    version, or of a strategy no longer declared, can still be listed. ``envelope`` decodes and cross-checks the full
    record exactly as ``get`` does.
    """

    analysis_run_id: UUID
    ticker: str
    analysis_id: str
    method_id: str
    status: RunOutcome
    batch_position: int
    row: Mapping[str, Any] = field(repr=False, compare=False)

    def envelope(self) -> AnalysisRun:
        """Return the fully decoded run.

        Raises:
            ValueError: If the stored envelope is malformed or disagrees with its own indexed columns.
        """
        return SQLiteAnalysisRunRepository.decode_row(self.row)


class AnalysisRunConflictError(ValueError):
    """A run with the same ``analysis_run_id`` already exists; only a defect can cause it."""

    reason_code: ClassVar[FailureReasonCode] = FailureReasonCode.EXECUTION_ERROR


def _utc(value: datetime) -> str:
    """Encode a timezone-aware instant without guessing a missing timezone."""
    if value.utcoffset() is None:
        raise ValueError("Storage timestamps must be timezone-aware.")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _row(run: AnalysisRun) -> dict[str, Any]:
    """Encode the indexed relational columns plus the full envelope JSON."""
    return {
        "analysis_run_id": str(run.analysis_run_id),
        "refresh_id": None if run.refresh_id is None else str(run.refresh_id),
        "batch_position": run.batch_position,
        "ticker": run.ticker,
        "analysis_id": run.analysis_id,
        "method_id": run.method_id,
        "outcome": run.status.value,
        "completed_at": _utc(run.completed_at),
        "run_schema_version": run.run_schema_version,
        "config_schema_version": run.config_schema_version,
        "method_version": run.method_version,
        "result_schema_version": run.result_schema_version,
        "evidence_codec_version": run.evidence_codec_version,
        "projection_version": run.projection_version,
        "envelope_json": json.dumps(
            run.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ),
        "watchlist_id": None if run.watchlist_id is None else str(run.watchlist_id),
        "watchlist_name": run.watchlist_name,
    }


class SQLiteAnalysisRunRepository:
    """Persist Analysis Run envelopes in a borrowed migrated database."""

    def __init__(self, database: SQLiteDatabase) -> None:
        """Retain a caller-owned database without opening it or migrating."""
        self._database = database

    def insert(self, run: AnalysisRun) -> None:
        """Atomically append one terminal run.

        Raises:
            AnalysisRunConflictError: If ``run.analysis_run_id`` already exists.
        """
        try:
            with self._database.transaction() as connection:
                connection.execute(analysis_runs.insert().values(**_row(run)))
        except IntegrityError as exc:
            raise AnalysisRunConflictError(f"Analysis run {run.analysis_run_id} already exists.") from exc

    def get(self, run_id: UUID) -> AnalysisRun | None:
        """Return one fully decoded run, or None for an exact-ID miss.

        Raises:
            ValueError: If the stored envelope is malformed or disagrees with
                its own indexed relational columns.
        """
        with self._database.read() as connection:
            row = (
                connection.execute(select(analysis_runs).where(analysis_runs.c.analysis_run_id == str(run_id)))
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            return self._decode(dict(row))

    def list(self, query: RunQuery) -> RunPage:
        """Return a bounded, filtered page of run summaries and whether more rows follow it.

        The one query reads ``query.limit + 1`` rows: the first ``query.limit`` are the page, and ``has_more`` is
        true when the extra row came back. This needs no second count query and does not change the bounds of
        ``query``.

        Filters combine with AND; results order by completion descending then
        run ID descending. Only indexed summary columns are read, so an
        unsupported or corrupt full envelope elsewhere remains listable.
        """
        conditions: list[Any] = [true()]
        if query.ticker is not None:
            conditions.append(analysis_runs.c.ticker == query.ticker)
        if query.method_id is not None:
            conditions.append(analysis_runs.c.method_id == query.method_id)
        if query.status is not None:
            conditions.append(analysis_runs.c.outcome == query.status.value)
        if query.refresh_id is not None:
            conditions.append(analysis_runs.c.refresh_id == str(query.refresh_id))
        statement = (
            select(
                analysis_runs.c.analysis_run_id,
                analysis_runs.c.ticker,
                analysis_runs.c.method_id,
                analysis_runs.c.outcome,
                analysis_runs.c.completed_at,
                analysis_runs.c.refresh_id,
            )
            .where(and_(*conditions))
            .order_by(analysis_runs.c.completed_at.desc(), analysis_runs.c.analysis_run_id.desc())
            .limit(query.limit + 1)
            .offset(query.offset)
        )
        with self._database.read() as connection:
            rows = connection.execute(statement).mappings().all()
        summaries = tuple(
            AnalysisRunSummary(
                analysis_run_id=UUID(row["analysis_run_id"]),
                ticker=row["ticker"],
                method_id=row["method_id"],
                status=RunOutcome(row["outcome"]),
                completed_at=datetime.fromisoformat(row["completed_at"]),
                refresh_id=None if row["refresh_id"] is None else UUID(row["refresh_id"]),
            )
            for row in rows[: query.limit]
        )
        return RunPage(summaries=summaries, has_more=len(rows) > query.limit)

    def list_refreshes(self, query: RefreshQuery) -> RefreshPage:
        """Return a bounded page of refresh summaries, newest first, and whether more follow it.

        A refresh is the stored runs that share a ``refresh_id``; the rows are grouped in SQL and only indexed summary
        columns are read, so no envelope is decoded. Results order by the latest completion descending then refresh
        ID descending. A watchlist filter keeps the refreshes whose recorded watchlist ID matches, so a refresh of a
        list of entries appears only when there is no filter, and a filter that matches nothing returns an empty
        page. The filter selects refreshes by the watchlist index, then every stored run of a selected refresh is
        counted, including one whose own watchlist columns are empty. Counts are of stored runs only.
        """
        counts = [
            func.coalesce(func.sum(case((analysis_runs.c.outcome == outcome.value, 1), else_=0)), 0).label(
                outcome.value
            )
            for outcome in RunOutcome
        ]
        last_completed = func.max(analysis_runs.c.completed_at)
        statement = (
            select(
                analysis_runs.c.refresh_id,
                func.max(analysis_runs.c.watchlist_id).label("watchlist_id"),
                func.max(analysis_runs.c.watchlist_name).label("watchlist_name"),
                func.min(analysis_runs.c.completed_at).label("first_completed_at"),
                last_completed.label("last_completed_at"),
                func.count().label("run_count"),
                *counts,
            )
            .where(analysis_runs.c.refresh_id.is_not(None))
            .group_by(analysis_runs.c.refresh_id)
            .order_by(last_completed.desc(), analysis_runs.c.refresh_id.desc())
            .limit(query.limit + 1)
            .offset(query.offset)
        )
        if query.watchlist_id is not None:
            matching = analysis_runs.alias("matching")
            statement = statement.where(
                analysis_runs.c.refresh_id.in_(
                    select(matching.c.refresh_id).where(matching.c.watchlist_id == str(query.watchlist_id))
                )
            )
        with self._database.read() as connection:
            rows = connection.execute(statement).mappings().all()
        summaries = tuple(
            RefreshSummary(
                refresh_id=UUID(row["refresh_id"]),
                watchlist_id=None if row["watchlist_id"] is None else UUID(row["watchlist_id"]),
                watchlist_name=row["watchlist_name"],
                first_completed_at=datetime.fromisoformat(row["first_completed_at"]),
                last_completed_at=datetime.fromisoformat(row["last_completed_at"]),
                run_count=row["run_count"],
                outcome_counts={outcome: row[outcome.value] for outcome in RunOutcome},
            )
            for row in rows[: query.limit]
        )
        return RefreshPage(summaries=summaries, has_more=len(rows) > query.limit)

    def list_refresh_runs(self, refresh_id: UUID) -> tuple[StoredRefreshRun, ...]:
        """Return every run saved by one refresh, in batch order, with no row limit.

        A refresh can hold more runs than the 100-row bound of ``list``, so this read is separate. An unknown ID
        and a refresh run with ``--no-save`` both return an empty tuple; storage cannot tell them apart.
        """
        statement = (
            select(analysis_runs)
            .where(analysis_runs.c.refresh_id == str(refresh_id))
            .order_by(analysis_runs.c.batch_position.asc(), analysis_runs.c.analysis_run_id.asc())
        )
        with self._database.read() as connection:
            rows = [dict(row) for row in connection.execute(statement).mappings().all()]
        return tuple(
            StoredRefreshRun(
                analysis_run_id=UUID(row["analysis_run_id"]),
                ticker=row["ticker"],
                analysis_id=row["analysis_id"],
                method_id=row["method_id"],
                status=RunOutcome(row["outcome"]),
                batch_position=row["batch_position"],
                row=row,
            )
            for row in rows
        )

    @staticmethod
    def decode_row(row: Mapping[str, Any]) -> AnalysisRun:
        """Validate a stored row's envelope and confirm it matches its own indexed columns."""
        return SQLiteAnalysisRunRepository._decode(row)

    @staticmethod
    def _decode(row: Mapping[str, Any]) -> AnalysisRun:
        """Validate the stored envelope and confirm it matches its own row."""
        run = _ENVELOPE_ADAPTER.validate_json(cast(str, row["envelope_json"]))
        if _row(run) != dict(row):
            raise ValueError("Malformed or inconsistent Analysis Run encoding.")
        return run


__all__ = [
    "AnalysisRunConflictError",
    "SQLiteAnalysisRunRepository",
    "StoredRefreshRun",
]
