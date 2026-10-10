"""One classifier from an exception to a failure code and status, shared by every command family.

The direct commands, the workspace commands and per-job refresh failures all call
:func:`classify_failure`, so a given exception can never be reported under different codes by
different families. The two exception types defined here are raised by command code and understood
only through this module, which is why they live beside the table that classifies them.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from src.core.analysis_status import CalculationStatus
from src.core.provider_failure_kind import ProviderFailureKind, ProviderFailureRecord
from src.data.base_client import DataFetchError
from src.data.financial.facts import FinancialProviderError
from src.data.market_data import NoEligibleObservationsError
from src.data.quality import HistoricalDataQualityError, QualityOutcome
from src.data.repositories.readiness import DatabaseReadinessError
from src.data.repositories.watchlists import (
    WatchlistConflictError,
    WatchlistEntryNotFoundError,
)
from src.reporting.documents.failure import (
    FailureDatabase,
    FailureDiagnostic,
    FailureEnvelope,
    FailureReasonCode,
    FailureStatus,
    ProviderFailure,
    ProviderFailureInput,
    status_for,
)
from src.reporting.replay_inputs import UnsupportedProjectionError
from src.workspace.codecs import InvalidStoredRunError, UnsupportedRunVersionError
from src.workspace.refresh import EmptyRefreshTargetError
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


# The one mapping from what an adapter observed to the stable code that reports it.
PROVIDER_CODE_BY_KIND: Mapping[ProviderFailureKind, FailureReasonCode] = MappingProxyType(
    {
        ProviderFailureKind.UNREACHABLE: FailureReasonCode.PROVIDER_UNREACHABLE,
        ProviderFailureKind.UNEXPECTED_RESPONSE: FailureReasonCode.PROVIDER_UNEXPECTED_RESPONSE,
        ProviderFailureKind.NO_DATA: FailureReasonCode.PROVIDER_NO_DATA,
    }
)

# An outage on any input outranks a shape change, which outranks an absent answer, so the one code names the
# condition most likely to need action.
PROVIDER_KIND_PRECEDENCE: tuple[ProviderFailureKind, ...] = (
    ProviderFailureKind.UNREACHABLE,
    ProviderFailureKind.UNEXPECTED_RESPONSE,
    ProviderFailureKind.NO_DATA,
)

# Most specific first: every entry but the last is a ``ValueError`` subtype, and several are subtypes of one another.
# ``DataFetchError`` and ``FinancialProviderError`` are classified by ``classify_failure`` from their kind.
CLASSIFICATION_RULES: tuple[tuple[type[BaseException], FailureReasonCode], ...] = (
    (HistoricalDataQualityError, FailureReasonCode.HISTORICAL_QUALITY),
    (AnalysisConfigurationError, FailureReasonCode.CONFIGURATION_ERROR),
    (NoEligibleObservationsError, FailureReasonCode.NO_ELIGIBLE_OBSERVATIONS),
    (InvalidParameterError, FailureReasonCode.INVALID_PARAMETER),
    (UnsupportedRunVersionError, FailureReasonCode.UNSUPPORTED_RUN_VERSION),
    (InvalidStoredRunError, FailureReasonCode.INVALID_STORED_RUN),
    (UnsupportedProjectionError, FailureReasonCode.UNSUPPORTED_PROJECTION),
    (StoredSelectionError, FailureReasonCode.STORED_SELECTION_UNREADABLE),
    (WatchlistNotFoundError, FailureReasonCode.WATCHLIST_NOT_FOUND),
    (EmptyRefreshTargetError, FailureReasonCode.WATCHLIST_EMPTY),
    (WatchlistEntryNotFoundError, FailureReasonCode.WATCHLIST_ENTRY_NOT_FOUND),
    (WatchlistConflictError, FailureReasonCode.WATCHLIST_NAME_CONFLICT),
    (ValueError, FailureReasonCode.INVALID_INPUT),
)


def classify_failure(exception: BaseException) -> FailureClassification:
    """Map an exception to its stable code and status; an unrecognized exception is ``execution_error``."""
    code = FailureReasonCode.EXECUTION_ERROR
    if isinstance(exception, DatabaseReadinessError):
        code = FailureReasonCode(exception.reason.value)
    elif isinstance(exception, DataFetchError | FinancialProviderError):
        code = FailureReasonCode.PROVIDER_ERROR if exception.kind is None else PROVIDER_CODE_BY_KIND[exception.kind]
    else:
        for exception_type, rule_code in CLASSIFICATION_RULES:
            if isinstance(exception, exception_type):
                code = rule_code
                break
    return FailureClassification(reason_code=code, status=status_for(code))


def provider_failure_of(records: Iterable[ProviderFailureRecord | None]) -> ProviderFailure | None:
    """Return the shared ``provider_failure`` element for the failed inputs, or ``None`` when none failed.

    A ``None`` record is an input that did not fail, or whose adapter did not classify its failure. The single
    code is the mapped code of the highest-precedence kind among the inputs, whatever their order.
    """
    inputs = tuple(
        ProviderFailureInput(input=record.input, provider_id=record.provider_id, kind=record.kind)
        for record in records
        if record is not None
    )
    if not inputs:
        return None
    kind = min((item.kind for item in inputs), key=PROVIDER_KIND_PRECEDENCE.index)
    return ProviderFailure(reason_code=PROVIDER_CODE_BY_KIND[kind], inputs=inputs)


def failure_reason_code(
    native_status: CalculationStatus, provider_failure: ProviderFailure | None
) -> FailureReasonCode:
    """Return the stable code of a failed run or refresh job from its native status and recorded failure.

    A provider error is the mapped provider code, or ``provider_error`` when the adapter did not classify it;
    invalid input is ``invalid_input``; any other native status is ``execution_error``.
    """
    if native_status is CalculationStatus.PROVIDER_ERROR:
        return FailureReasonCode.PROVIDER_ERROR if provider_failure is None else provider_failure.reason_code
    if native_status is CalculationStatus.INVALID_INPUT:
        return FailureReasonCode.INVALID_INPUT
    return FailureReasonCode.EXECUTION_ERROR


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
    exception contributes diagnostics, only a readiness error contributes ``database``, and only a provider
    failure that carries a kind contributes ``provider_failure`` (its one input is null: the failure was raised).
    """
    diagnostics: tuple[FailureDiagnostic, ...] = ()
    database: FailureDatabase | None = None
    provider_failure: ProviderFailure | None = None
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
    if (
        isinstance(cause, DataFetchError | FinancialProviderError)
        and cause.kind is not None
        and cause.provider_id is not None
        and PROVIDER_CODE_BY_KIND[cause.kind] is reason_code
    ):
        provider_failure = provider_failure_of((ProviderFailureRecord(cause.kind, cause.provider_id),))
    return FailureEnvelope(
        status=status_for(reason_code),
        reason_code=reason_code,
        reason=reason,
        analysis=analysis,
        method=method,
        ticker=ticker,
        diagnostics=diagnostics,
        database=database,
        provider_failure=provider_failure,
    )


__all__ = [
    "CLASSIFICATION_RULES",
    "PROVIDER_CODE_BY_KIND",
    "PROVIDER_KIND_PRECEDENCE",
    "AnalysisConfigurationError",
    "FailureClassification",
    "InvalidParameterError",
    "classify_failure",
    "failure_envelope",
    "failure_reason_code",
    "provider_failure_of",
]
