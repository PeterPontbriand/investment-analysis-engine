"""The parameter error an application action raises, and how a caller renames its parameters.

An action rejects a bad argument under its own parameter names (``name``, ``entry_number``). A caller that
spells those parameters differently, such as the command line with ``NAME`` and ``INDEX``, fills its own
names into the action's message template, so its message and the ``parameters`` it reports are its own.
"""

from collections.abc import Mapping, Sequence

from investment_analysis_engine.core.operator_errors import InvalidParameterError


class ActionParameterError(InvalidParameterError):
    """An action argument rejected before any work began.

    ``template`` is the message with each parameter written as ``{parameter}``; the message itself fills in the
    action's own names, and :meth:`named` fills in a caller's.
    """

    def __init__(self, template: str, *, parameters: Sequence[str]) -> None:
        """Keep the template and render its message with the action's own parameter names."""
        names = tuple(parameters)
        super().__init__(template.format_map({name: name for name in names}), parameters=names)
        self.template = template
        self.action_parameters = names

    def named(self, names: Mapping[str, str]) -> InvalidParameterError:
        """Return the same rejection under a caller's spelling of each parameter.

        Args:
            names: The caller's name for each of the action's parameters this error names.

        Raises:
            KeyError: If ``names`` lacks one of the parameters this error names.
        """
        spelled = {parameter: names[parameter] for parameter in self.action_parameters}
        return InvalidParameterError(self.template.format_map(spelled), parameters=tuple(spelled.values()))


__all__ = ["ActionParameterError"]
