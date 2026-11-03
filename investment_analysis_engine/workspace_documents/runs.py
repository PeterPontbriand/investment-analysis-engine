"""The ``runs list --json`` document: one JSON array of run summaries.

The document is unversioned: it has no ``schema_version``, and it is an array, so it has nowhere to put one.
"""

from collections.abc import Sequence
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, RootModel

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.reporting.documents.timestamp import DocumentTimestamp
from investment_analysis_engine.workspace.runs import AnalysisRunSummary


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


def build_runs_list_document(summaries: Sequence[AnalysisRunSummary]) -> RunsListDocument:
    """Build the runs-list document from run summaries, keeping their order."""
    return RunsListDocument(
        tuple(
            RunSummaryDocument(
                analysis_run_id=item.analysis_run_id,
                ticker=item.ticker,
                method_id=item.method_id,
                status=item.status,
                completed_at=item.completed_at,
                refresh_id=item.refresh_id,
            )
            for item in summaries
        )
    )


__all__ = ["RunSummaryDocument", "RunsListDocument", "build_runs_list_document"]
