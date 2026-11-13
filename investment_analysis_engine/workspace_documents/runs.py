"""The ``runs list --json`` document: one versioned JSON object holding a page of run summaries."""

from collections.abc import Sequence
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.reporting.documents.timestamp import DocumentTimestamp
from investment_analysis_engine.workspace.runs import AnalysisRunSummary


class RunSummaryDocument(BaseModel):
    """One saved run, summarized."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    analysis_run_id: UUID
    ticker: str
    method_id: str
    outcome: RunOutcome
    completed_at: DocumentTimestamp
    refresh_id: UUID | None = Field(
        description="The refresh that saved the run; null for a run saved by a direct command."
    )


class RunsListDocument(BaseModel):
    """The whole ``runs list --json`` output: one page of run summaries, most recently completed first."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[2] = 2
    has_more: bool = Field(description="True when at least one more run follows this page for the same filters.")
    items: tuple[RunSummaryDocument, ...]


def build_runs_list_document(summaries: Sequence[AnalysisRunSummary], *, has_more: bool) -> RunsListDocument:
    """Build the runs-list document from run summaries, keeping their order."""
    return RunsListDocument(
        has_more=has_more,
        items=tuple(
            RunSummaryDocument(
                analysis_run_id=item.analysis_run_id,
                ticker=item.ticker,
                method_id=item.method_id,
                outcome=item.status,
                completed_at=item.completed_at,
                refresh_id=item.refresh_id,
            )
            for item in summaries
        ),
    )


__all__ = ["RunSummaryDocument", "RunsListDocument", "build_runs_list_document"]
