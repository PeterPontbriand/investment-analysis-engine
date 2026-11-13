"""The ``refresh --json`` summary document.

The document carries ``schema_version``, its own lineage, first among its keys. It was unversioned until it gained
the ``rate_limited`` provider failure code; ``reason_code`` was added to every result before that without a version.
Version 2 ends the document with ``provider_check``. Version 3 lets ``watchlist_id`` and ``watchlist_name`` be null,
both together, for a refresh of a list of entries that belongs to no watchlist. Version 4 calls a result's run
outcome ``outcome``; it was ``status``.
"""

from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.core.failure_codes import FailureReasonCode
from investment_analysis_engine.core.provider_check_element import ProviderCheckItem, require_unique_providers


class RefreshResultDocument(BaseModel):
    """One (ticker, selection) job of a refresh.

    Exactly one of a saved run (``analysis_run_id``), an unsaved outcome (``outcome`` with no run) and a failure
    (``error``) describes the job, and ``reason_code`` is set if and only if the job stopped because of an unexpected
    problem (``error``) or its ``outcome`` is ``failed``. An ``unavailable`` job is an analysis outcome and carries
    none.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: str
    method_id: str
    analysis_run_id: UUID | None = Field(description="The saved run; null when nothing was saved.")
    saved: bool
    outcome: RunOutcome | None = Field(
        description=(
            "How the job's run ended, whether or not it was saved; null for a job that stopped because of an "
            "unexpected problem, before it produced an outcome."
        )
    )
    error: str | None = Field(
        description=(
            "The message the application wrote for the failure, chosen by its code; null unless the job stopped "
            "because of an unexpected problem."
        )
    )
    reason_code: FailureReasonCode | None = Field(
        description=(
            "The stable code of the failure; null unless the job stopped because of an unexpected problem or its "
            "outcome is failed."
        )
    )

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        """Require the job to be a saved run, an unsaved outcome or a failure, with a code only on failure."""
        if self.saved != (self.analysis_run_id is not None):
            raise ValueError("saved is true if and only if analysis_run_id is set.")
        if (self.error is not None or self.outcome is RunOutcome.FAILED) != (self.reason_code is not None):
            raise ValueError("reason_code is set if and only if the job raised or its outcome is failed.")
        if (self.error is None) == (self.outcome is None):
            raise ValueError("outcome is set if and only if the job did not raise.")
        return self


class RefreshSummaryDocument(BaseModel):
    """The one document ``refresh --json`` writes when the refresh completes.

    ``schema_version`` is this document's own lineage and is independent of every other document's.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[4] = 4
    refresh_id: UUID
    watchlist_id: UUID | None = Field(description="The watchlist refreshed; null for a refresh of a list of entries.")
    watchlist_name: str | None = Field(
        description="The watchlist's name when it was refreshed; null exactly when watchlist_id is."
    )
    results: tuple[RefreshResultDocument, ...]
    counts: dict[str, int] = Field(
        description=(
            "How many jobs ended in each outcome. A job that stopped because of an unexpected problem, before it "
            "produced an outcome, is counted under the key `error`."
        )
    )
    provider_check: tuple[ProviderCheckItem, ...] | None = Field(
        description=(
            "What one test request found for each provider a failed job implicates, one entry per provider; "
            "null when no job failed on a provider."
        )
    )

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        """Require the watchlist's ID and name to be both set or both null, and at most one entry per provider."""
        if (self.watchlist_id is None) != (self.watchlist_name is None):
            raise ValueError("watchlist_id and watchlist_name must both be set or both null.")
        require_unique_providers(self.provider_check)
        return self


__all__ = ["RefreshResultDocument", "RefreshSummaryDocument"]
