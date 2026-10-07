"""One classifier from an exception to a failure code and status, shared by every command family.

The direct commands, the workspace commands and per-job refresh failures all call
:func:`classify_failure`, so a given exception can never be reported under different codes by
different families. The two exception types defined here are raised by command code and understood
only through this module, which is why they live beside the table that classifies them.
"""

from dataclasses import dataclass

from src.data.base_client import DataFetchError
from src.data.market_data import NoEligibleObservationsError
from src.data.quality import DataQualityError, HistoricalDataQualityError, QualityOutcome
from src.data.repositories.readiness import DatabaseReadinessError
from src.data.repositories.watchlists import (
    WatchlistConflictError,
    WatchlistEntryNotFoundError,
)
from src.reporting.analysis_runs import UnsupportedProjectionError
from src.reporting.documents.failure import (
    FailureDatabase,
    FailureDiagnostic,
    FailureEnvelope,
    FailureReasonCode,
    FailureStatus,
    status_for,
)
from src.workspace.codecs import InvalidStoredRunError, UnsupportedRunVersionError
from src.workspace.watchlists import StoredSelectionError, WatchlistNotFoundError


class AnalysisConfigurationError(ValueError):
    """Safe operator-facing configuration guidance authored by the application."""


class InvalidParameterError(ValueError):
    """A command option value rejected before any work began; the message is safe to show as written."""


@dataclass(frozen=True)
class FailureClassification:
    """The stable code of a failure and the category that follows from it."""

    reason_code: FailureReasonCode
    status: FailureStatus


# Most specific first: every entry but the last is a ``ValueError`` subtype, and several are subtypes of one another.
CLASSIFICATION_RULES: tuple[tuple[type[BaseException], FailureReasonCode], ...] = (
    (HistoricalDataQualityError, FailureReasonCode.HISTORICAL_QUALITY),
    (DataFetchError, FailureReasonCode.PROVIDER_ERROR),
    (DataQualityError, FailureReasonCode.PROVIDER_ERROR),
    (AnalysisConfigurationError, FailureReasonCode.CONFIGURATION_ERROR),
    (NoEligibleObservationsError, FailureReasonCode.NO_ELIGIBLE_OBSERVATIONS),
    (InvalidParameterError, FailureReasonCode.INVALID_PARAMETER),
    (UnsupportedRunVersionError, FailureReasonCode.UNSUPPORTED_RUN_VERSION),
    (InvalidStoredRunError, FailureReasonCode.INVALID_STORED_RUN),
    (UnsupportedProjectionError, FailureReasonCode.UNSUPPORTED_PROJECTION),
    (StoredSelectionError, FailureReasonCode.STORED_SELECTION_UNREADABLE),
    (WatchlistNotFoundError, FailureReasonCode.WATCHLIST_NOT_FOUND),
    (WatchlistEntryNotFoundError, FailureReasonCode.WATCHLIST_ENTRY_NOT_FOUND),
    (WatchlistConflictError, FailureReasonCode.WATCHLIST_NAME_CONFLICT),
    (ValueError, FailureReasonCode.INVALID_INPUT),
)


def classify_failure(exception: BaseException) -> FailureClassification:
    """Map an exception to its stable code and status; an unrecognized exception is ``execution_error``."""
    code = FailureReasonCode.EXECUTION_ERROR
    if isinstance(exception, DatabaseReadinessError):
        code = FailureReasonCode(exception.reason.value)
    else:
        for exception_type, rule_code in CLASSIFICATION_RULES:
            if isinstance(exception, exception_type):
                code = rule_code
                break
    return FailureClassification(reason_code=code, status=status_for(code))


def failure_envelope(  # noqa: PLR0913
    reason_code: FailureReasonCode,
    reason: str,
    *,
    cause: BaseException | None = None,
    analysis: str | None = None,
    method: str | None = None,
    ticker: str | None = None,
) -> FailureEnvelope:
    """Build the envelope for ``reason_code``, taking diagnostics and database facts from ``cause``.

    ``reason`` is the sentence to show; the caller sanitizes it. Only a failed historical-quality
    exception contributes diagnostics, and only a readiness error contributes ``database``.
    """
    diagnostics: tuple[FailureDiagnostic, ...] = ()
    database: FailureDatabase | None = None
    if isinstance(cause, HistoricalDataQualityError):
        diagnostics = tuple(
            FailureDiagnostic(rule=item.rule_id, reason=item.reason)
            for item in cause.decisions
            if item.outcome is QualityOutcome.FAIL
        )
    if isinstance(cause, DatabaseReadinessError):
        path = cause.database_path
        database = FailureDatabase(
            database_path=None if path is None else str(path), expected_revision=cause.expected_revision
        )
    return FailureEnvelope(
        status=status_for(reason_code),
        reason_code=reason_code,
        reason=reason,
        analysis=analysis,
        method=method,
        ticker=ticker,
        diagnostics=diagnostics,
        database=database,
    )


__all__ = [
    "CLASSIFICATION_RULES",
    "AnalysisConfigurationError",
    "FailureClassification",
    "InvalidParameterError",
    "classify_failure",
    "failure_envelope",
]
