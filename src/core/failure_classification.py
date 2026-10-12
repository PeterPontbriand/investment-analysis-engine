"""One classifier from an exception to a failure code and status, shared by every command family.

The direct commands, the workspace commands and per-job refresh failures all call :func:`classify_failure`,
so a given exception can never be reported under different codes by different families.

The classifier names no exception type. An exception class states its own stable code in a ``reason_code``
attribute where it is defined; the classifier reads that attribute. Otherwise a ``ValueError`` is
``invalid_input`` and anything else is ``execution_error``.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from src.core.analysis_status import CalculationStatus
from src.core.failure_codes import (
    PROVIDER_CODE_BY_KIND,
    FailureReasonCode,
    FailureStatus,
    status_for,
)
from src.core.provider_failure_element import ProviderFailure, ProviderFailureInput
from src.core.provider_failure_kind import PROVIDER_KIND_PRECEDENCE, ProviderFailureKind, ProviderFailureRecord


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
    "provider_failure_of",
    "provider_failure_of_exception",
]
