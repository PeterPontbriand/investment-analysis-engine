"""The run overview document: one stored run's identity, outcome and headline, for a client with its own display.

The overview is built from the stored row and the strategy's headline function alone; it calls no provider, cache or
clock and recalculates nothing. Its strategy and headline have the shapes of the comparison table's, and the headline
comes from the builder the table uses, so a run reads the same in both.
"""

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.reporting.documents.shared_parts import SecurityIdentityPart
from investment_analysis_engine.reporting.documents.timestamp import DocumentAsOf, DocumentTimestamp
from investment_analysis_engine.workspace.codecs import InvalidStoredRunError, UnsupportedRunVersionError
from investment_analysis_engine.workspace.repositories.analysis_runs import StoredRun
from investment_analysis_engine.workspace_documents.runs_compare import (
    CompareColumn,
    CompareHeadlineDocument,
    CompareStrategyDocument,
    HeadlineUnavailable,
    resolve_headline,
    strategy_document,
)


class RunOverviewDocument(BaseModel):
    """The whole run overview: what a run is, how it ended and its headline, or why it has none.

    ``schema_version`` is this document's own lineage and is independent of every other document's.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[3] = 3
    analysis_run_id: UUID
    ticker: str
    security_identity: SecurityIdentityPart = Field(
        description=(
            "The identity snapshot the run retained when it ran. Show a ticker tied to this run with it, never with "
            "the ticker's current profile, which can describe a different company after a ticker reuse. Every "
            "descriptive field is null when no provider gave one."
        )
    )
    outcome: RunOutcome = Field(description="The run's outcome, read from its stored record.")
    completed_at: DocumentTimestamp
    refresh_id: UUID | None = Field(
        description="The refresh that saved the run; null for a run saved by a direct command."
    )
    requested_as_of: DocumentAsOf | None = Field(
        description="The point in time the run asked for, as it was asked: a date or an instant; null means now."
    )
    strategy: CompareStrategyDocument = Field(description="The strategy that produced the run.")
    headline: CompareHeadlineDocument | None = Field(
        description="The run's cells; null when headline_unavailable is set."
    )
    headline_unavailable: HeadlineUnavailable | None = Field(description="Why the run has no headline, if it has none.")

    @model_validator(mode="after")
    def _one_of_headline_or_reason(self) -> Self:
        """Require exactly one of the headline and the reason it is missing."""
        if (self.headline is None) == (self.headline_unavailable is None):
            raise ValueError("A run has a headline or the reason it has none, and not both.")
        return self


class _StoredIdentity(BaseModel):
    """The identity fields of a stored envelope's instrument profile; the rest of the envelope is ignored."""

    model_config = ConfigDict(extra="ignore")

    instrument_name: str | None = None
    listing_venue: str | None = None
    issuer_identifier: str | None = None
    instrument_identifier: str | None = None
    provider_id: str | None = None
    resolved_at: datetime | None = None


class _StoredProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    identity: _StoredIdentity | None = None


class _StoredEnvelopeProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    instrument_profile: _StoredProfile | None = None


def _security_identity(record: StoredRun) -> SecurityIdentityPart:
    """Read the identity snapshot a run retained from its stored envelope, with no decoding of its strategy's parts.

    A run that retained no identity has every descriptive field null, as a strategy document shows it.

    Raises:
        InvalidStoredRunError: If the stored envelope cannot be read, naming the run.
    """
    try:
        stored = _StoredEnvelopeProfile.model_validate_json(record.row["envelope_json"])
    except (ValueError, KeyError, TypeError) as exc:
        raise InvalidStoredRunError(
            f"Analysis Run {record.analysis_run_id} could not be read: "
            "its stored record is malformed or does not match its summary."
        ) from exc
    identity = None if stored.instrument_profile is None else stored.instrument_profile.identity
    if identity is None:
        identity = _StoredIdentity()
    return SecurityIdentityPart(
        ticker=record.ticker,
        instrument_name=identity.instrument_name,
        listing_venue=identity.listing_venue,
        issuer_identifier=identity.issuer_identifier,
        instrument_identifier=identity.instrument_identifier,
        provider_id=identity.provider_id,
        resolved_at=identity.resolved_at,
    )


def build_run_overview(record: StoredRun, column: CompareColumn | None) -> RunOverviewDocument:
    """Build the overview of one stored run.

    Args:
        record: The stored run.
        column: The declared strategy that produced it, or ``None`` when no declared strategy did.

    Raises:
        UnsupportedRunVersionError: If the run was stored under a version this one cannot read.
        InvalidStoredRunError: If the run's envelope or evidence is invalid.
    """
    resolved = resolve_headline(record, column)
    if resolved.unavailable == "unsupported_version":
        raise UnsupportedRunVersionError("Unsupported Analysis Run method or version.")
    return RunOverviewDocument(
        analysis_run_id=record.analysis_run_id,
        ticker=record.ticker,
        security_identity=_security_identity(record),
        outcome=record.outcome,
        completed_at=record.completed_at,
        refresh_id=record.refresh_id,
        requested_as_of=resolved.requested_as_of,
        strategy=strategy_document(record.analysis_id, record.method_id, column),
        headline=resolved.headline,
        headline_unavailable=resolved.unavailable,
    )


__all__ = ["RunOverviewDocument", "build_run_overview"]
