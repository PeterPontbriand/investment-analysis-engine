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

from investment_analysis_engine.core.operator_errors import InvalidParameterError

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
        super().__init__(_substitute(template, replacements), parameters=names)
        self.template = template
        self.action_parameters = names
        self.rule = rule
        self.arguments = values

    def named(self, names: Mapping[str, str]) -> InvalidParameterError:
        """Return the same rejection under a caller's spelling of each parameter.

        Args:
            names: The caller's name for each of the action's parameters this error names.

        Raises:
            KeyError: If ``names`` lacks one of the parameters this error names.
        """
        spelled = {parameter: names[parameter] for parameter in self.action_parameters}
        replacements = spelled | {key: str(value) for key, value in self.arguments.items()}
        return InvalidParameterError(_substitute(self.template, replacements), parameters=tuple(spelled.values()))


__all__ = ["ActionParameterError"]
