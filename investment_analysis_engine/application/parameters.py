"""The parameter error an application action raises, and how a caller renames its parameters.

An action rejects a bad argument under its own parameter names (``name``, ``entry_number``, a selection field). A
caller that spells those parameters differently, such as the command line with ``NAME`` and ``INDEX``, fills its own
names into the action's message template, so its message and the ``parameters`` it reports are its own.

A template names a parameter as ``{parameter}`` and a value as ``{argument}``. Only the placeholders the error
declares are replaced, by explicit substitution and never by ``str.format``, because a dotted name such as
``policy.historical_horizon`` is attribute access in a format string.
"""

import re
from collections.abc import Mapping, Sequence

from investment_analysis_engine.core.operator_errors import InvalidParameterError, RuleViolation

_PLACEHOLDER = re.compile(r"\{([^{}]+)\}")


def _substitute(template: str, replacements: Mapping[str, str]) -> str:
    """Replace each declared ``{placeholder}`` in ``template`` with its text, in a single pass.

    Text inserted for one placeholder is never itself substituted, and a placeholder that is not declared stays as
    written.
    """
    return _PLACEHOLDER.sub(lambda match: replacements.get(match.group(1), match.group(0)), template)


class ActionParameterError(InvalidParameterError):
    """An action argument rejected before any work began.

    ``template`` is the message with each parameter written as ``{parameter}`` and each value as ``{argument}``;
    the message itself fills in the action's own names, and :meth:`named` fills in a caller's.

    Attributes:
        template: The message template.
        action_parameters: The action's own names of the parameters this error names.
        rule: The stable identifier of the rule that rejected the argument, ``<scope>.<rule>`` such as
            ``momentum.window_order`` or ``watchlist.blank_name``.
        arguments: The values the template shows, by placeholder name, as the rule saw them.
        errors: Every rejection this error stands for, in field order: itself for a single rejection, and for
            several (see :meth:`several`) each one, the first being the error's own rule, parameters and message.
    """

    def __init__(
        self,
        template: str,
        *,
        parameters: Sequence[str],
        rule: str,
        arguments: Mapping[str, object] | None = None,
    ) -> None:
        """Keep the template, rule and values, and render the message with the action's own parameter names."""
        names = tuple(parameters)
        values = dict(arguments or {})
        replacements = {name: name for name in names} | {key: str(value) for key, value in values.items()}
        message = _substitute(template, replacements)
        super().__init__(message, parameters=names, violations=(RuleViolation(rule, names, values, message),))
        self.errors: tuple[ActionParameterError, ...] = (self,)
        self.template = template
        self.action_parameters = names
        self.rule = rule
        self.arguments = values

    @classmethod
    def several(cls, errors: Sequence["ActionParameterError"]) -> "ActionParameterError":
        """Return one error for several rejections: the first's rule, parameters and message, and all of them listed.

        Raises:
            ValueError: If ``errors`` is empty.
        """
        if not errors:
            raise ValueError("several needs at least one error.")
        first = errors[0]
        combined = cls(first.template, parameters=first.action_parameters, rule=first.rule, arguments=first.arguments)
        combined.errors = tuple(errors)
        combined.violations = tuple(violation for error in errors for violation in error.violations)
        return combined

    def named(self, names: Mapping[str, str]) -> InvalidParameterError:
        """Return the same rejection under a caller's spelling of each parameter.

        The first error's parameters and message are the result's own; every error of :attr:`errors` is spelled the
        same way in its violations, a parameter the caller has no name for keeping the action's.

        Args:
            names: The caller's name for each of the action's parameters the first error names.

        Raises:
            KeyError: If ``names`` lacks one of the parameters the first error names.
        """
        spelled = {parameter: names[parameter] for parameter in self.action_parameters}
        violations = tuple(error._violation_named(names) for error in self.errors)  # noqa: SLF001
        return InvalidParameterError(
            _substitute(self.template, spelled | {key: str(value) for key, value in self.arguments.items()}),
            parameters=tuple(spelled.values()),
            violations=violations,
        )

    def _violation_named(self, names: Mapping[str, str]) -> RuleViolation:
        """Return this single rejection as a violation under a caller's names."""
        spelled = {parameter: names.get(parameter, parameter) for parameter in self.action_parameters}
        message = _substitute(self.template, spelled | {key: str(value) for key, value in self.arguments.items()})
        return RuleViolation(self.rule, tuple(spelled.values()), self.arguments, message)


__all__ = ["ActionParameterError"]
