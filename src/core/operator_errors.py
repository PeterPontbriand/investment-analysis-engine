"""Errors authored by the application whose message is safe to show an operator as written.

This is a leaf module: it imports only ``src.core``. Each class states its own stable failure code.
"""

from typing import ClassVar

from src.core.failure_codes import FailureReasonCode


class AnalysisConfigurationError(ValueError):
    """Safe operator-facing configuration guidance authored by the application."""

    reason_code: ClassVar[FailureReasonCode] = FailureReasonCode.CONFIGURATION_ERROR


class InvalidParameterError(ValueError):
    """A command option value rejected before any work began; the message is safe to show as written."""

    reason_code: ClassVar[FailureReasonCode] = FailureReasonCode.INVALID_PARAMETER


__all__ = ["AnalysisConfigurationError", "InvalidParameterError"]
