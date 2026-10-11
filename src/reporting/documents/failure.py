"""The failure envelope: one typed document for every ``--json`` failure.

This module imports only ``src.core``, so the command line, the strategy documents and the schema generator can
all depend on it without a cycle. The code vocabulary and the ``provider_failure`` element live in ``src.core``.
``DatabaseMaintenanceReport`` is a sibling shape that shares the code vocabulary but is not a failure document.

The envelope reports a condition; it never offers a remedy. It has no field that names a command or
an action, and ``database`` carries facts about the target, not instructions.
"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.core.failure_codes import PROVIDER_FAILURE_CODES, FailureReasonCode, FailureStatus, status_for
from src.core.provider_failure_element import ProviderFailure


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

    schema_version: Literal[8] = 8
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
    provider_failure: ProviderFailure | None = Field(
        default=None,
        description="Set exactly when reason_code is one of the four provider failure codes; null otherwise.",
    )

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        """Require the status to follow from the code and ``database`` to accompany only database codes."""
        if self.status != status_for(self.reason_code):
            raise ValueError(f"status {self.status!r} does not match reason_code {self.reason_code.value!r}.")
        if self.database is not None and not self.reason_code.value.startswith("database_"):
            raise ValueError("database is set only for a database_* reason_code.")
        if self.reason_code in PROVIDER_FAILURE_CODES:
            if self.provider_failure is None:
                raise ValueError(f"reason_code {self.reason_code.value!r} requires provider_failure.")
            if self.provider_failure.reason_code != self.reason_code:
                raise ValueError("provider_failure.reason_code must equal reason_code.")
        elif self.provider_failure is not None:
            raise ValueError("provider_failure is set only for a provider failure reason_code.")
        return self


__all__ = [
    "FailureDatabase",
    "FailureDiagnostic",
    "FailureEnvelope",
]
