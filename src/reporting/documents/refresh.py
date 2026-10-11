"""The ``refresh --json`` summary document.

The document carries ``schema_version``, its own lineage, first among its keys. It was unversioned until it gained
the ``rate_limited`` provider failure code; ``reason_code`` was added to every result before that without a version.
Version 2 ends the document with ``provider_check``.
"""

from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.core.failure_codes import FailureReasonCode
from src.core.provider_check_element import ProviderCheckItem, require_unique_providers
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

    ``schema_version`` is this document's own lineage and is independent of every other document's.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[2] = 2
    refresh_id: UUID
    watchlist_id: UUID
    watchlist_name: str
    results: tuple[RefreshResultDocument, ...]
    counts: dict[str, int] = Field(description="Jobs per status; a job that raised counts as 'error'.")
    provider_check: tuple[ProviderCheckItem, ...] | None = Field(
        description=(
            "What one test request found for each provider a failed job implicates, one entry per provider; "
            "null when no job failed on a provider."
        )
    )

    @model_validator(mode="after")
    def _unique_providers(self) -> Self:
        """Require at most one entry per provider."""
        require_unique_providers(self.provider_check)
        return self


__all__ = ["RefreshResultDocument", "RefreshSummaryDocument"]
