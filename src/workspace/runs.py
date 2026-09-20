"""Versioned, immutable run envelope and watchlist models for the workspace.

These frozen Pydantic models capture a single terminal analysis attempt (identity,
request snapshot, timing, versions, outcome, evidence) plus the query/summary
projections and the ordered watchlist aggregate described by the Slice B2 field
spec. They are pure types and validation: no SQLite persistence, codec, execution,
or adapter behavior is introduced here. Selection values reuse B1's discriminated
``AnalysisSelection`` union so request/effective configs keep their canonical
identifiers and finite-value guarantees.
"""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, field_validator, model_validator

from src.core.analysis_status import CalculationStatus
from src.data.instrument_profile import InstrumentProfile
from src.workspace.models import EffectiveBoundary, RunOutcome, StrictJsonMapping, _FrozenModel
from src.workspace.requests import AnalysisSelection


class AnalysisRun(_FrozenModel):
    """Immutable terminal record of one workspace analysis attempt.

    The envelope freezes the requested and (when materialized) effective selection,
    canonical identifiers, timing, schema/method versions, outcome, and evidence for
    a single run. Cross-field invariants enforce time ordering, status-dependent
    requirements, identifier consistency with the embedded configs, and paired-field
    presence; all financial floats inside evidence/presentation must be finite JSON
    primitives.
    """

    # Identity
    analysis_run_id: UUID
    refresh_id: UUID | None = None
    batch_position: int | None = Field(default=None, ge=0)
    watchlist_id: UUID | None = None
    watchlist_name: str | None = None
    telemetry_run_id: UUID | None = None

    # Request
    ticker: str
    analysis_id: str
    method_id: str
    config_schema_version: int = Field(ge=1)
    requested_config: AnalysisSelection
    effective_config: AnalysisSelection | None = None

    # Time
    started_at: AwareDatetime
    completed_at: AwareDatetime
    requested_as_of: AwareDatetime | None = None
    effective_boundary: EffectiveBoundary | None = None
    source_observation_dates: tuple[date, ...] = ()
    source_retrieval_at: AwareDatetime | None = None

    # Versions
    run_schema_version: Literal[1] = 1
    method_version: int = Field(ge=1)
    result_schema_version: int = Field(ge=1)
    evidence_codec_version: int = Field(ge=1)
    projection_version: Literal[1] = 1

    # Outcome
    status: RunOutcome
    native_status: CalculationStatus | None = None
    native_reason: str | None = None
    failure_reason_code: str | None = None

    # Evidence / Presentation
    result_evidence: StrictJsonMapping | None = None
    presentation_inputs: StrictJsonMapping | None = None
    instrument_profile: InstrumentProfile | None = None

    @field_validator("ticker")
    @classmethod
    def _normalize_ticker(cls, value: str) -> str:
        """Normalize the ticker and reject blank values, as B1 selections do."""
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("ticker must not be empty.")
        return normalized

    @field_validator(
        "config_schema_version",
        "method_version",
        "result_schema_version",
        "evidence_codec_version",
        mode="before",
    )
    @classmethod
    def _require_integer_versions(cls, value: object) -> object:
        """Reject boolean/float/string lookalikes before validating the version."""
        if type(value) is not int:
            raise ValueError("version fields must be integers.")
        return value

    @model_validator(mode="after")
    def _validate_envelope(self) -> "AnalysisRun":
        """Enforce cross-field invariants across time, outcome, and identity."""
        if self.completed_at < self.started_at:
            raise ValueError("completed_at must be on or after started_at.")

        if (self.refresh_id is None) != (self.batch_position is None):
            raise ValueError("refresh_id and batch_position must both be set or both null.")
        if (self.watchlist_id is None) != (self.watchlist_name is None):
            raise ValueError("watchlist_id and watchlist_name must both be set or both null.")

        requested = self.requested_config
        if (
            self.analysis_id != requested.analysis_id
            or self.method_id != requested.method_id
            or self.config_schema_version != requested.config_schema_version
        ):
            raise ValueError("analysis/method identifiers and version must match requested_config.")
        effective = self.effective_config
        if effective is not None and (
            self.analysis_id != effective.analysis_id
            or self.method_id != effective.method_id
            or self.config_schema_version != effective.config_schema_version
        ):
            raise ValueError("analysis/method identifiers and version must match effective_config.")

        if self.status is RunOutcome.FAILED and not (self.failure_reason_code and self.failure_reason_code.strip()):
            raise ValueError("failure_reason_code is required when status is failed.")
        if self.status is RunOutcome.COMPLETED and self.result_evidence is None:
            raise ValueError("result_evidence is required when status is completed.")

        if self.instrument_profile is not None and self.instrument_profile.ticker != self.ticker:
            raise ValueError("instrument_profile ticker must match ticker.")

        return self


class AnalysisRunSummary(_FrozenModel):
    """Indexed projection of a run envelope, carrying only the summary columns."""

    analysis_run_id: UUID
    ticker: str
    method_id: str
    status: RunOutcome
    completed_at: AwareDatetime
    refresh_id: UUID | None = None


class RunQuery(_FrozenModel):
    """Bounded filter set for querying run summaries."""

    ticker: str | None = None
    method_id: str | None = None
    status: RunOutcome | None = None
    refresh_id: UUID | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class WatchlistEntry(_FrozenModel):
    """One (ticker, selection) pair within a watchlist, addressed by its own position.

    An entry's position is its index within its watchlist's ``entries`` tuple —
    there is no separate stored position field on the entry itself, mirroring
    how the previous ``members``/``selections`` tuples never carried one
    either. The same ``selection.method_id`` may appear on more than one
    entry, whether for different tickers or for the same ticker with a
    different provider/configuration (Amendment A1, §12): unlike the
    superseded model, a watchlist no longer restricts itself to one
    selection per method.
    """

    ticker: str
    selection: AnalysisSelection


class Watchlist(_FrozenModel):
    """Ordered watchlist aggregate: a name plus one ordered list of entries.

    ``display_name`` preserves the user's spelling while ``normalized_name`` is its
    trimmed/casefolded form used for uniqueness. ``entries`` is the watchlist's
    single property (Amendment A1, §12): each entry independently pairs one
    ticker with one selection, so a watchlist no longer forces every member to
    receive every selection.
    """

    watchlist_id: UUID
    display_name: str
    normalized_name: str
    created_at: AwareDatetime
    updated_at: AwareDatetime | None = None
    entries: tuple[WatchlistEntry, ...] = ()

    @model_validator(mode="after")
    def _validate_watchlist(self) -> "Watchlist":
        """Enforce name normalization invariants (W1-W2)."""
        derived = self.display_name.strip().casefold()
        if not derived:
            raise ValueError("display_name must not be blank.")
        if self.normalized_name != derived:
            raise ValueError("normalized_name must equal display_name.strip().casefold().")
        return self


class WatchlistSummary(_FrozenModel):
    """Lightweight projection of a watchlist with an entry count."""

    watchlist_id: UUID
    display_name: str
    entry_count: int = Field(ge=0)
    created_at: AwareDatetime
    updated_at: AwareDatetime | None = None


__all__ = [
    "AnalysisRun",
    "AnalysisRunSummary",
    "RunQuery",
    "Watchlist",
    "WatchlistEntry",
    "WatchlistSummary",
]
