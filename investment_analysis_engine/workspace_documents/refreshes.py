"""The ``runs refreshes --json`` document: one versioned JSON object holding a page of refresh summaries."""

from collections.abc import Sequence
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.reporting.documents.timestamp import DocumentTimestamp
from investment_analysis_engine.workspace.runs import RefreshSummary

# The descriptions of the summary fields the refreshes list and the runs comparison both carry, defined once.
WATCHLIST_ID_DESCRIPTION = (
    "The watchlist the refresh ran, as recorded when it ran; null for a refresh of a list of entries."
)
WATCHLIST_NAME_DESCRIPTION = (
    "The watchlist's name when the refresh ran, not its current name; null when watchlist_id is null."
)
FIRST_COMPLETED_DESCRIPTION = "When the refresh's earliest stored run completed."
LAST_COMPLETED_DESCRIPTION = "When the refresh's latest stored run completed."
RUN_COUNT_DESCRIPTION = "The number of stored runs; a stopped refresh stores fewer."


class RefreshOutcomeCountsDocument(BaseModel):
    """How many of a refresh's stored runs ended in each outcome; one count for every outcome."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    completed: int = Field(ge=0, description="Stored runs that ended completed.")
    unavailable: int = Field(ge=0, description="Stored runs that ended unavailable.")
    not_applicable: int = Field(ge=0, description="Stored runs that ended not applicable.")
    failed: int = Field(ge=0, description="Stored runs that ended failed.")


class RefreshSummaryItemDocument(BaseModel):
    """One refresh, summarized from its stored runs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    refresh_id: UUID
    watchlist_id: UUID | None = Field(description=WATCHLIST_ID_DESCRIPTION)
    watchlist_name: str | None = Field(description=WATCHLIST_NAME_DESCRIPTION)
    first_completed_at: DocumentTimestamp = Field(description=FIRST_COMPLETED_DESCRIPTION)
    last_completed_at: DocumentTimestamp = Field(description=LAST_COMPLETED_DESCRIPTION)
    run_count: int = Field(ge=1, description=RUN_COUNT_DESCRIPTION)
    outcome_counts: RefreshOutcomeCountsDocument


class RefreshesListDocument(BaseModel):
    """The whole ``runs refreshes --json`` output: one page of refreshes, most recently completed first."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    has_more: bool = Field(description="True when at least one more refresh follows this page for the same filter.")
    items: tuple[RefreshSummaryItemDocument, ...]


def outcome_counts_document(summary: RefreshSummary) -> RefreshOutcomeCountsDocument:
    """Return a refresh summary's outcome counts as the served document, one count for every outcome."""
    return RefreshOutcomeCountsDocument(**{outcome.value: summary.outcome_counts[outcome] for outcome in RunOutcome})


def build_refreshes_list_document(summaries: Sequence[RefreshSummary], *, has_more: bool) -> RefreshesListDocument:
    """Build the refreshes-list document from refresh summaries, keeping their order."""
    return RefreshesListDocument(
        has_more=has_more,
        items=tuple(
            RefreshSummaryItemDocument(
                refresh_id=item.refresh_id,
                watchlist_id=item.watchlist_id,
                watchlist_name=item.watchlist_name,
                first_completed_at=item.first_completed_at,
                last_completed_at=item.last_completed_at,
                run_count=item.run_count,
                outcome_counts=outcome_counts_document(item),
            )
            for item in summaries
        ),
    )


__all__ = [
    "FIRST_COMPLETED_DESCRIPTION",
    "LAST_COMPLETED_DESCRIPTION",
    "RUN_COUNT_DESCRIPTION",
    "WATCHLIST_ID_DESCRIPTION",
    "WATCHLIST_NAME_DESCRIPTION",
    "RefreshOutcomeCountsDocument",
    "RefreshSummaryItemDocument",
    "RefreshesListDocument",
    "build_refreshes_list_document",
    "outcome_counts_document",
]
