"""Builds the failure envelope for a stable reason code, taking diagnostics and database facts from the cause.

The code and the classifier live in ``investment_analysis_engine.core``; this module adds the facts only a reporting
layer attaches to a failure document, which is why it is the one place that names the exception types that carry them.
"""

import math
from datetime import date

from pydantic import JsonValue

from investment_analysis_engine.core.failure_classification import (
    parameters_of_exception,
    provider_failure_of_exception,
    violations_of_exception,
)
from investment_analysis_engine.core.failure_codes import FailureReasonCode, status_for
from investment_analysis_engine.core.operator_errors import RuleViolation
from investment_analysis_engine.core.provider_failure_element import ProviderFailure
from investment_analysis_engine.data.quality import HistoricalDataQualityError, QualityOutcome
from investment_analysis_engine.data.repositories.readiness import DatabaseReadinessError
from investment_analysis_engine.reporting.documents.failure import (
    FailureDatabase,
    FailureDiagnostic,
    FailureEnvelope,
    FailureRuleError,
)


def json_argument(value: object) -> JsonValue:
    """Return a rule argument as a JSON value.

    A string, integer, boolean and null are kept; a finite float is a number and a non-finite one its text (``inf``,
    ``-inf``, ``nan``), because JSON cannot carry it; a date or timestamp is ISO 8601 text; anything else is its text.
    """
    if value is None or isinstance(value, str | int | bool):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _rule_error(violation: RuleViolation) -> FailureRuleError:
    """Return a rule violation as the envelope's error item."""
    return FailureRuleError(
        rule=violation.rule,
        parameters=violation.parameters,
        arguments={name: json_argument(value) for name, value in violation.arguments.items()},
        message=violation.message,
    )


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
    violations = (
        violations_of_exception(cause)
        if cause is not None and reason_code is FailureReasonCode.INVALID_PARAMETER
        else None
    )
    return FailureEnvelope(
        status=status_for(reason_code),
        parameters=parameters,
        errors=None if violations is None else tuple(_rule_error(item) for item in violations),
        reason_code=reason_code,
        reason=reason,
        analysis=analysis,
        method=method,
        ticker=ticker,
        diagnostics=diagnostics,
        database=database,
        provider_failure=provider_failure,
    )


__all__ = ["failure_envelope", "json_argument"]
