"""The reason code and message of a failed Graham input, and the code a Graham analysis serves.

Every non-OK Graham assembly and result carries a reason code and a message written where the code is set. The
presenters show the message as written.
"""

from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.data.financial.resolver import InputResolutionResult


def provider_error_message(security_subject_id: str) -> str:
    """Return the message of a run stopped because the provider could not retrieve required data."""
    return (
        f"Unable to analyze {security_subject_id}: the configured provider could not retrieve required security data."
    )


def failed_input_outcome(
    result: InputResolutionResult, *, security_subject_id: str, label: str
) -> tuple[ReasonCode, str]:
    """Return the code and message of an input whose resolution was not OK.

    Args:
        result: The failed resolution; its status is not ``OK``.
        security_subject_id: The ticker the provider-error message names.
        label: The input's name as a message leads with it, such as ``"Earnings per share"``.

    Returns:
        The resolution's own code for an unavailable input, ``provider_error`` for a provider failure and
        ``invalid_request`` for an input the resolver refused.

    Raises:
        ValueError: If the resolution is ``OK``.
    """
    if result.status is CalculationStatus.OK:
        raise ValueError("An OK resolution has no failure to describe.")
    if result.status is CalculationStatus.PROVIDER_ERROR:
        return ReasonCode.PROVIDER_ERROR, provider_error_message(security_subject_id)
    if result.status is CalculationStatus.INPUT_UNAVAILABLE:
        assert result.reason_code is not None
        return result.reason_code, f"{label} is unavailable: {result.reason}"
    return ReasonCode.INVALID_REQUEST, f"{label} is invalid: {result.reason}"


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
