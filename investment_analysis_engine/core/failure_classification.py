"""One classifier from an exception to a failure code and status, shared by every command family.

The direct commands, the workspace commands and per-job refresh failures all call :func:`classify_failure`,
so a given exception can never be reported under different codes by different families.

The classifier names no exception type. An exception class states its own stable code in a ``reason_code``
attribute where it is defined; the classifier reads that attribute. Otherwise a ``ValueError`` is
``invalid_input`` and anything else is ``execution_error``.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.failure_codes import (
    PROVIDER_CODE_BY_KIND,
    FailureReasonCode,
    FailureStatus,
    status_for,
)
from investment_analysis_engine.core.operator_errors import RuleViolation
from investment_analysis_engine.core.provider_failure_element import ProviderFailure, ProviderFailureInput
from investment_analysis_engine.core.provider_failure_kind import (
    PROVIDER_KIND_PRECEDENCE,
    ProviderFailureKind,
    ProviderFailureRecord,
)


@dataclass(frozen=True)
class FailureClassification:
    """The stable code of a failure and the category that follows from it."""

    reason_code: FailureReasonCode
    status: FailureStatus


def classify_failure(exception: BaseException) -> FailureClassification:
    """Map an exception to its stable code and status.

    An exception that declares a ``reason_code`` reports it; any other ``ValueError`` is ``invalid_input``;
    anything else is ``execution_error``.
    """
    declared = getattr(exception, "reason_code", None)
    if isinstance(declared, FailureReasonCode):
        code = declared
    elif isinstance(exception, ValueError):
        code = FailureReasonCode.INVALID_INPUT
    else:
        code = FailureReasonCode.EXECUTION_ERROR
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


def provider_stopped_status(provider_failure: ProviderFailure | None) -> CalculationStatus:
    """Return the calculation status of a run a provider failure stopped: the one rule every strategy applies.

    A run whose failed required inputs are all of kind ``no_data`` is ``input_unavailable``, because the provider
    answered and has nothing. A run with any other failed kind, or with a failure the adapter did not classify
    (``None``), is ``provider_error``. The element's code is that of the highest-precedence kind, so it is
    ``provider_no_data`` exactly when every failed input was ``no_data``.
    """
    if provider_failure is not None and provider_failure.reason_code is FailureReasonCode.PROVIDER_NO_DATA:
        return CalculationStatus.INPUT_UNAVAILABLE
    return CalculationStatus.PROVIDER_ERROR


def provider_stopped_status_of_record(record: ProviderFailureRecord | None) -> CalculationStatus:
    """Return :func:`provider_stopped_status` of the one failure record a strategy's assembly stopped at."""
    return provider_stopped_status(provider_failure_of((record,)))


def provider_failure_fits_status(status: CalculationStatus, provider_failure: ProviderFailure | None) -> bool:
    """Return whether a run of ``status`` may carry ``provider_failure``, the rule every validator applies.

    ``provider_error`` comes with a failure whose code is anything except ``provider_no_data``, or with none
    (unclassified); ``input_unavailable`` may come with a failure whose code is ``provider_no_data`` only; every
    other status has none.
    """
    if provider_failure is None:
        return True
    if status is CalculationStatus.PROVIDER_ERROR:
        return provider_failure.reason_code is not FailureReasonCode.PROVIDER_NO_DATA
    if status is CalculationStatus.INPUT_UNAVAILABLE:
        return provider_failure.reason_code is FailureReasonCode.PROVIDER_NO_DATA
    return False


def provider_record_fits_status(status: CalculationStatus, record: ProviderFailureRecord | None) -> bool:
    """Return :func:`provider_failure_fits_status` of the one failure record a result holds."""
    return provider_failure_fits_status(status, provider_failure_of((record,)))


def provider_failure_of_exception(exception: BaseException) -> ProviderFailure | None:
    """Return the ``provider_failure`` element of a raised provider failure, or ``None``.

    A raised provider failure carries a ``kind`` and a ``provider_id`` beside its message; the element is built
    from them with a null input, because the failure was raised rather than recorded against an input. Any
    other exception, and a provider failure the adapter did not classify, has no element. The function names no
    exception type, like :func:`classify_failure`.
    """
    kind = getattr(exception, "kind", None)
    provider_id = getattr(exception, "provider_id", None)
    if not isinstance(kind, ProviderFailureKind) or not isinstance(provider_id, str):
        return None
    return provider_failure_of((ProviderFailureRecord(kind, provider_id),))


def parameters_of_exception(exception: BaseException) -> tuple[str, ...] | None:
    """Return the offending option and argument names an exception declares in ``parameters``, or ``None``.

    Like :func:`provider_failure_of_exception`, the function names no exception type: an exception that carries a
    non-empty tuple of strings in ``parameters`` reports it.
    """
    names = getattr(exception, "parameters", None)
    if isinstance(names, tuple) and names and all(isinstance(name, str) and name for name in names):
        return names
    return None


def violations_of_exception(exception: BaseException) -> tuple[RuleViolation, ...] | None:
    """Return the rule violations an exception declares in ``violations``, or ``None`` when it declares none.

    Like :func:`parameters_of_exception`, the function names no exception type.
    """
    found = getattr(exception, "violations", None)
    if isinstance(found, tuple) and found and all(isinstance(item, RuleViolation) for item in found):
        return found
    return None


@dataclass(frozen=True)
class UnreadableEntryFacts:
    """The entry a stored-selection failure names.

    Attributes:
        entry_number: The 1-based position of the entry.
        ticker: The entry's ticker.
        method_id: The method identifier as stored.
        reason: The failure's message, which says why this version cannot read the entry.
    """

    entry_number: int
    ticker: str
    method_id: str
    reason: str


def unreadable_entry_of_exception(exception: BaseException) -> UnreadableEntryFacts | None:
    """Return the entry an exception names as unreadable, or ``None`` when it names none.

    Like :func:`parameters_of_exception`, the function names no exception type: an exception that carries an entry
    number, a ticker and a stored method identifier reports them, with its message as the reason.
    """
    entry_number = getattr(exception, "entry_number", None)
    ticker = getattr(exception, "ticker", None)
    method_id = getattr(exception, "method_id", None)
    if not (isinstance(entry_number, int) and isinstance(ticker, str) and isinstance(method_id, str)):
        return None
    return UnreadableEntryFacts(entry_number, ticker, method_id, str(exception))


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


__all__ = [
    "FailureClassification",
    "classify_failure",
    "failure_reason_code",
    "parameters_of_exception",
    "provider_failure_fits_status",
    "provider_failure_of",
    "provider_failure_of_exception",
    "provider_record_fits_status",
    "provider_stopped_status",
    "provider_stopped_status_of_record",
    "violations_of_exception",
]
