"""The ``refresh --json`` summary document.

The document is unversioned: it has no ``schema_version``. SWC.4a added ``reason_code`` to every result without
a version change, and this module records that the document has never carried one.
"""

from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.reporting.documents.failure import FailureReasonCode
from src.workspace.models import RunOutcome


class RefreshResultDocument(BaseModel):
    """One (ticker, selection) job of a refresh.

    Exactly one of a saved run (``analysis_run_id``), an unsaved outcome (``status`` with no run) and a failure
    (``error``) describes the job, and ``reason_code`` is set if and only if the job raised (``error``) or its
    ``status`` is ``failed``. An ``unavailable`` job is an analysis outcome and carries none.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: str
    method_id: str
    analysis_run_id: UUID | None = Field(description="The saved run; null when nothing was saved.")
    saved: bool
    status: RunOutcome | None = Field(description="The run's or the unsaved outcome's status; null for a raised job.")
    error: str | None = Field(description="The failure's message for people; null unless the job raised.")
    reason_code: FailureReasonCode | None = Field(
        description="The stable code of the failure; null unless the job raised or its status is failed."
    )

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        """Require the job to be a saved run, an unsaved outcome or a raised failure, with a code only on failure."""
        if self.saved != (self.analysis_run_id is not None):
            raise ValueError("saved is true if and only if analysis_run_id is set.")
        if (self.error is not None or self.status is RunOutcome.FAILED) != (self.reason_code is not None):
            raise ValueError("reason_code is set if and only if the job raised or its status is failed.")
        if (self.error is None) == (self.status is None):
            raise ValueError("status is set if and only if the job did not raise.")
        return self


class RefreshSummaryDocument(BaseModel):
    """The one document ``refresh --json`` writes when the refresh completes.

    This document is unversioned: it has no ``schema_version``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    refresh_id: UUID
    watchlist_id: UUID
    watchlist_name: str
    results: tuple[RefreshResultDocument, ...]
    counts: dict[str, int] = Field(description="Jobs per status; a job that raised counts as 'error'.")


__all__ = ["RefreshResultDocument", "RefreshSummaryDocument"]
