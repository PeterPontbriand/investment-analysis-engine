"""The ``runs list --json`` document: one JSON array of run summaries.

The document is unversioned: it has no ``schema_version``, and it is an array, so it has nowhere to put one.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, RootModel

from src.reporting.documents.timestamp import DocumentTimestamp
from src.workspace.models import RunOutcome


class RunSummaryDocument(BaseModel):
    """One saved run, summarized."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    analysis_run_id: UUID
    ticker: str
    method_id: str
    status: RunOutcome
    completed_at: DocumentTimestamp
    refresh_id: UUID | None = Field(
        description="The refresh that saved the run; null for a run saved by a direct command."
    )


class RunsListDocument(RootModel[tuple[RunSummaryDocument, ...]]):
    """The whole ``runs list --json`` output: an array of run summaries, most recently completed first.

    This document is unversioned: it has no ``schema_version``.
    """

    model_config = ConfigDict(frozen=True)


__all__ = ["RunSummaryDocument", "RunsListDocument"]
