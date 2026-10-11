"""Builds the failure envelope for a stable reason code, taking diagnostics and database facts from the cause.

The code and the classifier live in ``src.core``; this module adds the facts only a reporting layer attaches to a
failure document, which is why it is the one place that names the exception types that carry them.
"""

from src.core.failure_classification import provider_failure_of
from src.core.failure_codes import PROVIDER_CODE_BY_KIND, FailureReasonCode, status_for
from src.core.provider_failure_element import ProviderFailure
from src.core.provider_failure_kind import ProviderFailureRecord
from src.data.base_client import DataFetchError
from src.data.financial.facts import FinancialProviderError
from src.data.quality import HistoricalDataQualityError, QualityOutcome
from src.data.repositories.readiness import DatabaseReadinessError
from src.reporting.documents.failure import FailureDatabase, FailureDiagnostic, FailureEnvelope


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


__all__ = ["failure_envelope"]
