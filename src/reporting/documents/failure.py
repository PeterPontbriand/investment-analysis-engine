"""The failure envelope: one typed document for every ``--json`` failure.

This is a leaf module: it imports nothing from the application, so the classifier, the command line
and the schema generator can all depend on it without a cycle. ``DatabaseMaintenanceReport`` is a
sibling shape that shares the code vocabulary below but is not a failure document.

The envelope reports a condition; it never offers a remedy. It has no field that names a command or
an action, and ``database`` carries facts about the target, not instructions.
"""

from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FailureReasonCode(StrEnum):
    """Stable failure categories a caller may branch on.

    A value is never renamed, repurposed or removed within the public contract. New values may be
    added, so a caller must treat an unrecognized value as a generic failure and use ``status`` for the
    category.
    """

    EXECUTION_ERROR = "execution_error"
    HISTORICAL_QUALITY = "historical_quality"
    PROVIDER_ERROR = "provider_error"
    CONFIGURATION_ERROR = "configuration_error"
    NO_ELIGIBLE_OBSERVATIONS = "no_eligible_observations"
    INVALID_INPUT = "invalid_input"
    INVALID_PARAMETER = "invalid_parameter"
    DATABASE_UPGRADE_REQUIRED = "database_upgrade_required"
    DATABASE_INCOMPATIBLE_SCHEMA = "database_incompatible_schema"
    DATABASE_BUSY = "database_busy"
    DATABASE_PERMISSION_DENIED = "database_permission_denied"
    DATABASE_INVALID_FILE = "database_invalid_file"
    DATABASE_IO_ERROR = "database_io_error"
    DATABASE_RESOURCES_UNAVAILABLE = "database_resources_unavailable"
    DATABASE_INITIALIZATION_FAILED = "database_initialization_failed"
    DATABASE_MIGRATION_FAILED = "database_migration_failed"
    INVALID_STORED_RUN = "invalid_stored_run"
    UNSUPPORTED_RUN_VERSION = "unsupported_run_version"
    WATCHLIST_NOT_FOUND = "watchlist_not_found"
    WATCHLIST_ENTRY_NOT_FOUND = "watchlist_entry_not_found"
    WATCHLIST_EMPTY = "watchlist_empty"
    WATCHLIST_NAME_CONFLICT = "watchlist_name_conflict"
    ANALYSIS_RUN_NOT_FOUND = "analysis_run_not_found"
    STORED_SELECTION_UNREADABLE = "stored_selection_unreadable"
    UNSUPPORTED_PROJECTION = "unsupported_projection"


FailureStatus = Literal["error", "input_unavailable"]

INPUT_UNAVAILABLE_CODES = frozenset(
    {
        FailureReasonCode.HISTORICAL_QUALITY,
        FailureReasonCode.PROVIDER_ERROR,
        FailureReasonCode.NO_ELIGIBLE_OBSERVATIONS,
    }
)


def status_for(code: FailureReasonCode) -> FailureStatus:
    """Return the category of a code: ``input_unavailable`` when the data could not be used, else ``error``."""
    return "input_unavailable" if code in INPUT_UNAVAILABLE_CODES else "error"


class FailureDiagnostic(BaseModel):
    """One failed historical-quality rule and its sanitized reason."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule: str
    reason: str


class FailureDatabase(BaseModel):
    """Facts about the database a ``database_*`` failure concerns, taken from the readiness error."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    database_path: str | None = Field(description="The configured target; null for an in-memory database.")
    expected_revision: str | None = Field(description="The bundled schema revision, when it could be determined.")


class FailureEnvelope(BaseModel):
    """The one JSON document written to standard output when a command with ``--json`` fails.

    ``schema_version`` is this document's own lineage: it identifies a shape only within this schema
    and is independent of the ``schema_version`` of every success document. A consumer dispatches on
    ``status`` and ``result`` first, then on ``analysis``. ``reason_code`` is stable; ``reason`` and
    ``diagnostics[].reason`` are sentences for people and carry no guarantee.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[6] = 6
    status: FailureStatus
    reason_code: FailureReasonCode
    reason: str
    analysis: str | None = Field(default=None, description="The analysis of a direct command; null otherwise.")
    method: str | None = Field(default=None, description="The method of a direct command; null otherwise.")
    ticker: str | None = Field(default=None, description="The requested ticker of a direct command; null otherwise.")
    result: None = Field(default=None, description="Always null, so success and failure share top-level keys.")
    diagnostics: tuple[FailureDiagnostic, ...] = ()
    database: FailureDatabase | None = Field(
        default=None, description="Set only for a database_* code; null otherwise."
    )

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        """Require the status to follow from the code and ``database`` to accompany only database codes."""
        if self.status != status_for(self.reason_code):
            raise ValueError(f"status {self.status!r} does not match reason_code {self.reason_code.value!r}.")
        if self.database is not None and not self.reason_code.value.startswith("database_"):
            raise ValueError("database is set only for a database_* reason_code.")
        return self


__all__ = [
    "INPUT_UNAVAILABLE_CODES",
    "FailureDatabase",
    "FailureDiagnostic",
    "FailureEnvelope",
    "FailureReasonCode",
    "FailureStatus",
    "status_for",
]
