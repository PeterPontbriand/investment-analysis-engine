"""Builds the failure envelope for a stable reason code, taking diagnostics and database facts from the cause.

The code and the classifier live in ``investment_analysis_engine.core``; this module adds the facts only a reporting
layer attaches to a failure document, which is why it is the one place that names the exception types that carry them.
"""

from investment_analysis_engine.core.failure_classification import (
    parameters_of_exception,
    provider_failure_of_exception,
)
from investment_analysis_engine.core.failure_codes import FailureReasonCode, status_for
from investment_analysis_engine.core.provider_failure_element import ProviderFailure
from investment_analysis_engine.data.quality import HistoricalDataQualityError, QualityOutcome
from investment_analysis_engine.data.repositories.readiness import DatabaseReadinessError
from investment_analysis_engine.reporting.documents.failure import FailureDatabase, FailureDiagnostic, FailureEnvelope


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

    ``reason`` is the message to show; the caller sanitizes it. Only a failed historical-quality
    exception contributes diagnostics, only a readiness error contributes ``database``, only an
    ``invalid_parameter`` exception contributes ``parameters``, and only a provider failure that carries a kind
    contributes ``provider_failure`` (its one input is null: the failure was raised).
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
    if cause is not None:
        element = provider_failure_of_exception(cause)
        if element is not None and element.reason_code is reason_code:
            provider_failure = element
    parameters = (
        parameters_of_exception(cause)
        if cause is not None and reason_code is FailureReasonCode.INVALID_PARAMETER
        else None
    )
    return FailureEnvelope(
        status=status_for(reason_code),
        parameters=parameters,
        reason_code=reason_code,
        reason=reason,
        analysis=analysis,
        method=method,
        ticker=ticker,
        diagnostics=diagnostics,
        database=database,
        provider_failure=provider_failure,
    )


__all__ = ["failure_envelope"]
