"""The reason code and message of a failed Graham input, and the code a Graham analysis serves.

Every non-OK Graham assembly and result carries a reason code and a message written where the code is set. The
presenters show the message as written.
"""

from dataclasses import dataclass

from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.failure_classification import provider_stopped_status_of_record
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureRecord
from investment_analysis_engine.data.financial.resolver import InputResolutionResult
from investment_analysis_engine.reporting.provider_messages import is_no_data, no_data_message


def provider_error_message(security_subject_id: str) -> str:
    """Return the message of a run stopped because the provider could not retrieve required data."""
    return (
        f"Unable to analyze {security_subject_id}: the configured provider could not retrieve required security data."
    )


@dataclass(frozen=True)
class FailedInput:
    """The status, code and message of a Graham input whose resolution was not OK."""

    status: CalculationStatus
    code: ReasonCode
    message: str


def provider_stop(record: ProviderFailureRecord | None, *, security_subject_id: str, what: str) -> FailedInput:
    """Return the outcome of a provider failure that stopped a required input.

    A ``no_data`` failure is ``input_unavailable`` with ``provider_no_data`` and a message naming the provider; any
    other failure, classified or not, is ``provider_error`` with the generic provider-error message.
    """
    status = provider_stopped_status_of_record(record)
    if record is not None and is_no_data(record):
        return FailedInput(
            status,
            ReasonCode.PROVIDER_NO_DATA,
            no_data_message(record, what=what, ticker=security_subject_id),
        )
    return FailedInput(status, ReasonCode.PROVIDER_ERROR, provider_error_message(security_subject_id))


def _what_of(label: str) -> str:
    """Return a label as it reads mid-line: the first word in lower case unless it is an acronym."""
    return label if label.split(maxsplit=1)[0].isupper() else label[:1].lower() + label[1:]


def failed_input_outcome(result: InputResolutionResult, *, security_subject_id: str, label: str) -> FailedInput:
    """Return the status, code and message of an input whose resolution was not OK.

    Args:
        result: The failed resolution; its status is not ``OK``.
        security_subject_id: The ticker the provider messages name.
        label: The input's name as a message leads with it, such as ``"Earnings per share"``.

    Returns:
        The resolution's own code for an unavailable input, the provider outcome of :func:`provider_stop` for a
        provider failure and ``invalid_request`` for an input the resolver refused.

    Raises:
        ValueError: If the resolution is ``OK``.
    """
    if result.status is CalculationStatus.OK:
        raise ValueError("An OK resolution has no failure to describe.")
    if result.status is CalculationStatus.PROVIDER_ERROR:
        return provider_stop(result.provider_failure, security_subject_id=security_subject_id, what=_what_of(label))
    if result.status is CalculationStatus.INPUT_UNAVAILABLE:
        assert result.reason_code is not None
        return FailedInput(result.status, result.reason_code, f"{label} is unavailable: {result.reason}")
    return FailedInput(result.status, ReasonCode.INVALID_REQUEST, f"{label} is invalid: {result.reason}")


def served_reason_code(
    assembly_status: CalculationStatus,
    assembly_code: ReasonCode | None,
    result_status: CalculationStatus,
    result_code: ReasonCode | None,
) -> ReasonCode | None:
    """Return the assembly's code when it is not OK, else the result's code when it is not OK, else ``None``."""
    if assembly_status is not CalculationStatus.OK:
        return assembly_code
    return None if result_status is CalculationStatus.OK else result_code
