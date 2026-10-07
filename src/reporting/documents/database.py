"""The maintenance report that ``ian db status`` and ``ian db upgrade`` write with ``--json``.

It is an inspection report, not a failure document: ``status`` says whether the operation ran, not
whether the database is ready, so ``db status`` on a database that needs upgrading reports
``"success"``. It shares the failure envelope's names for the stable code (``reason_code``) and the
sentence (``reason``), and its codes are drawn from the same vocabulary. Like the envelope it carries
facts and no instructions.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.reporting.documents.failure import FailureReasonCode


class DatabaseMaintenanceReport(BaseModel):
    """Versioned maintenance evidence independent of analysis-result documents.

    Version 2 renamed the stable code from ``reason`` to ``reason_code`` and the sentence from
    ``message`` to ``reason``. A reader of version 1 that branches on ``reason`` would silently read a
    sentence, so check ``schema_version`` first.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    command: Literal["db status", "db upgrade"]
    status: Literal["success", "error"] = Field(description="Whether the operation ran, not whether it succeeded.")
    database_path: str | None
    state: str | None
    current_revision: str | None
    expected_revision: str | None
    reason_code: FailureReasonCode | None = Field(description="The stable code, or null when there is none.")
    reason: str = Field(description="A sentence for people; not stable.")
    schema_version: Literal[2] = 2
