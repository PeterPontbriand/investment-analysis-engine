"""Errors authored by the application whose message is safe to show an operator as written.

This is a leaf module: it imports only ``investment_analysis_engine.core``. Each class states its own stable failure
code.
"""

from collections.abc import Sequence
from typing import ClassVar

from investment_analysis_engine.core.failure_codes import FailureReasonCode


class AnalysisConfigurationError(ValueError):
    """Safe operator-facing configuration guidance authored by the application."""

    reason_code: ClassVar[FailureReasonCode] = FailureReasonCode.CONFIGURATION_ERROR


class InvalidParameterError(ValueError):
    """A command option or argument rejected before any work began; the message is safe to show as written.

    ``parameters`` names the offending options and arguments: an option by its declared primary long spelling
    (``--short-window``) and an argument by the upper-case name the message uses (``TICKER``). The failure
    envelope carries them, so the code that rejects the value owns its names.
    """

    reason_code: ClassVar[FailureReasonCode] = FailureReasonCode.INVALID_PARAMETER

    def __init__(self, message: str, *, parameters: Sequence[str]) -> None:
        """Keep the message and the non-empty names of the offending parameters."""
        super().__init__(message)
        names = tuple(parameters)
        if not names or not all(names):
            raise ValueError("InvalidParameterError needs the non-empty name of each offending parameter.")
        self.parameters: tuple[str, ...] = names


__all__ = ["AnalysisConfigurationError", "InvalidParameterError"]
