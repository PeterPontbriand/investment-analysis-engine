"""Stored runs with a chosen refresh, watchlist, completion time and outcome, for the refreshes-list tests."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.workspace.runs import AnalysisRun
from tests.workspace.test_momentum_codec import _run as _momentum_run

CORE_ID = UUID("5d0c0000-0000-4000-8000-000000000001")
VALUE_ID = UUID("5d0c0000-0000-4000-8000-000000000002")


def at(minute: int) -> datetime:
    """Return a UTC instant on a fixed day, ``minute`` minutes past ten."""
    return datetime(2026, 11, 1, 10, minute, tzinfo=UTC)


def refresh_run(  # noqa: PLR0913
    refresh_id: UUID | None,
    position: int,
    completed_at: datetime,
    *,
    watchlist: tuple[UUID, str] | None = None,
    status: RunOutcome = RunOutcome.COMPLETED,
) -> AnalysisRun:
    """Return a stored-run envelope that belongs to ``refresh_id`` and was completed at ``completed_at``.

    The copy is not revalidated, so ``status`` changes only what listing reads: the outcome column.
    """
    return _momentum_run().model_copy(
        update={
            "analysis_run_id": uuid4(),
            "refresh_id": refresh_id,
            "batch_position": None if refresh_id is None else position,
            "watchlist_id": None if watchlist is None else watchlist[0],
            "watchlist_name": None if watchlist is None else watchlist[1],
            "started_at": completed_at,
            "completed_at": completed_at,
            "status": status,
        }
    )
