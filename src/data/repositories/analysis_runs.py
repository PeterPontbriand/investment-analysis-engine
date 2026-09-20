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
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy import and_, select, true
from sqlalchemy.exc import IntegrityError

from src.data.repositories.schema import analysis_runs
from src.data.repositories.sqlite import SQLiteDatabase
from src.workspace.models import RunOutcome
from src.workspace.runs import AnalysisRun, AnalysisRunSummary, RunQuery

_ENVELOPE_ADAPTER: TypeAdapter[AnalysisRun] = TypeAdapter(AnalysisRun)


class AnalysisRunConflictError(ValueError):
    """A run with the same ``analysis_run_id`` already exists."""


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

    def list(self, query: RunQuery) -> tuple[AnalysisRunSummary, ...]:
        """Return a bounded, filtered page of run summaries.

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
            .limit(query.limit)
            .offset(query.offset)
        )
        with self._database.read() as connection:
            rows = connection.execute(statement).mappings().all()
        return tuple(
            AnalysisRunSummary(
                analysis_run_id=UUID(row["analysis_run_id"]),
                ticker=row["ticker"],
                method_id=row["method_id"],
                status=RunOutcome(row["outcome"]),
                completed_at=datetime.fromisoformat(row["completed_at"]),
                refresh_id=None if row["refresh_id"] is None else UUID(row["refresh_id"]),
            )
            for row in rows
        )

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
]
