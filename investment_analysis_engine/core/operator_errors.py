"""Errors authored by the application whose message is safe to show an operator as written.

This is a leaf module: it imports only ``investment_analysis_engine.core``. Each class states its own stable failure
code.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import ClassVar

from investment_analysis_engine.core.failure_codes import FailureReasonCode


class AnalysisConfigurationError(ValueError):
    """Safe operator-facing configuration guidance authored by the application."""

    reason_code: ClassVar[FailureReasonCode] = FailureReasonCode.CONFIGURATION_ERROR


@dataclass(frozen=True)
class RuleViolation:
    """One broken rule of a rejected argument, in the spelling of the caller that reports it.

    Attributes:
        rule: The stable identifier of the rule, ``<scope>.<rule>`` such as ``momentum.window_order``.
        parameters: The caller's names of the parameters the rule names.
        arguments: The values the rule's message shows, by placeholder name, as the rule saw them.
        message: The rule's message, with the caller's parameter names filled in.
    """

    rule: str
    parameters: tuple[str, ...]
    arguments: Mapping[str, object]
    message: str


class InvalidParameterError(ValueError):
    """A command option or argument rejected before any work began; the message is safe to show as written.

    ``parameters`` names the offending options and arguments: an option by its declared primary long spelling
    (``--short-window``) and an argument by the upper-case name the message uses (``TICKER``). The failure
    envelope carries them, so the code that rejects the value owns its names.
    """

    reason_code: ClassVar[FailureReasonCode] = FailureReasonCode.INVALID_PARAMETER

    def __init__(self, message: str, *, parameters: Sequence[str], violations: Sequence[RuleViolation] = ()) -> None:
        """Keep the message, the non-empty names of the offending parameters and the rule violations behind them."""
        super().__init__(message)
        names = tuple(parameters)
        if not names or not all(names):
            raise ValueError("InvalidParameterError needs the non-empty name of each offending parameter.")
        self.parameters: tuple[str, ...] = names
        self.violations: tuple[RuleViolation, ...] = tuple(violations)


__all__ = ["AnalysisConfigurationError", "InvalidParameterError", "RuleViolation"]
