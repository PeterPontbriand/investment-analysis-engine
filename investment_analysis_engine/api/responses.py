"""How the API writes a response: one serializer for every body, and the status each failure code answers with."""

import json
from collections.abc import Mapping
from types import MappingProxyType

from pydantic import BaseModel
from starlette.responses import Response

from investment_analysis_engine.core.failure_codes import FailureReasonCode
from investment_analysis_engine.reporting.documents.failure import FailureEnvelope
from investment_analysis_engine.reporting.failure_envelope import failure_envelope

DEFAULT_FAILURE_STATUS = 500
"""The HTTP status of every failure code the table does not name."""

STATUS_BY_CODE: Mapping[FailureReasonCode, int] = MappingProxyType(
    {
        FailureReasonCode.INVALID_PARAMETER: 400,
        FailureReasonCode.HOST_NOT_ALLOWED: 400,
        FailureReasonCode.ORIGIN_NOT_ALLOWED: 400,
        FailureReasonCode.NOT_AUTHENTICATED: 401,
        FailureReasonCode.ANALYSIS_RUN_NOT_FOUND: 404,
        FailureReasonCode.WATCHLIST_NOT_FOUND: 404,
        FailureReasonCode.WATCHLIST_ENTRY_NOT_FOUND: 404,
        FailureReasonCode.REFRESH_JOB_NOT_FOUND: 404,
        FailureReasonCode.HELP_TERM_NOT_FOUND: 404,
        FailureReasonCode.HELP_DOCUMENT_NOT_FOUND: 404,
        FailureReasonCode.WATCHLIST_NAME_CONFLICT: 409,
        FailureReasonCode.STORED_SELECTION_UNREADABLE: 409,
        FailureReasonCode.WATCHLIST_EMPTY: 409,
        FailureReasonCode.REFRESH_JOB_RUNNING: 409,
        FailureReasonCode.ENDPOINT_NOT_FOUND: 404,
        FailureReasonCode.DATABASE_BUSY: 503,
    }
)
"""The HTTP status of a failure code; the code is what a client branches on, the status is coarse."""


def document_body(document: BaseModel) -> bytes:
    """Serialize a document: field order, compact, UTF-8, and no NaN or infinity."""
    return json.dumps(
        document.model_dump(mode="json"), ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")


class DescribedFailure(Exception):  # noqa: N818 - it names the failure it carries, as the application's errors do
    """A failure an operation has already described: its code, a message safe to show as written, and its cause.

    Attributes:
        code: The failure's stable code.
        message: The text shown to the client, as written.
        cause: The exception the failure was described from, which supplies the envelope's details.
    """

    def __init__(self, code: FailureReasonCode, message: str, cause: BaseException) -> None:
        """Keep the code, the message and the cause."""
        super().__init__(message)
        self.code = code
        self.message = message
        self.cause = cause


def document_response(document: BaseModel, *, status: int = 200, headers: Mapping[str, str] | None = None) -> Response:
    """Return ``document`` as the body of a response with the status and headers every response carries."""
    return Response(
        document_body(document),
        status_code=status,
        media_type="application/json",
        headers={"Cache-Control": "no-store", **(headers or {})},
    )


def failure_response(
    envelope: FailureEnvelope, *, status: int | None = None, headers: Mapping[str, str] | None = None
) -> Response:
    """Return a failure envelope as a response; the status follows from its code unless ``status`` is given."""
    chosen = STATUS_BY_CODE.get(envelope.reason_code, DEFAULT_FAILURE_STATUS) if status is None else status
    return document_response(envelope, status=chosen, headers=headers)


def failure_of(
    code: FailureReasonCode,
    message: str,
    *,
    status: int | None = None,
    headers: Mapping[str, str] | None = None,
) -> Response:
    """Return the response for a failure that has no exception behind it."""
    return failure_response(failure_envelope(code, message), status=status, headers=headers)


__all__ = [
    "DEFAULT_FAILURE_STATUS",
    "STATUS_BY_CODE",
    "document_body",
    "DescribedFailure",
    "document_response",
    "failure_of",
    "failure_response",
]
