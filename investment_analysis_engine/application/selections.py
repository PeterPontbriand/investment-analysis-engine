"""Building a watchlist selection from its model's fields: the one place a selection is validated.

``build_selection`` applies a strategy's configured defaults to the fields the caller left out, converts the
``as_of`` boundary, and lets the strategy's selection model validate the rest. The command line and the API both
call it, so a rule about a field's value is enforced once, by the model, and reported under the model's field names.
"""

from collections.abc import Mapping
from datetime import UTC, date, datetime, time
from typing import Final

from pydantic import ValidationError

from investment_analysis_engine.analysis.selection_base import SelectionRuleError
from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.parameters import ActionParameterError
from investment_analysis_engine.config.component_settings import load_component_settings
from investment_analysis_engine.core.strategy_errors import find, undeclared
from investment_analysis_engine.strategy_wiring import BY_METHOD_ID
from investment_analysis_engine.workspace.strategy_types import SelectionMember

_FIXED_FIELDS: Final = ("analysis_id", "method_id", "config_schema_version")
"""The fields every selection fixes by its class; a caller cannot supply them."""

_DATE_LENGTH: Final = 10
"""The length of ``YYYY-MM-DD``."""

_PYDANTIC_MESSAGE: Final = "pydantic_message"
"""The argument name that carries the text of a built-in field error."""


def as_of_boundary(value: date | datetime | None) -> datetime | None:
    """Return the selection's ``as_of`` boundary: a date is the end of that day in UTC, a timestamp stays as given.

    Raises:
        ActionParameterError: If ``value`` is a timestamp without a timezone offset (parameter ``as_of``).
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ActionParameterError(
                "Timestamp {as_of} values must include an explicit timezone offset.",
                parameters=("as_of",),
                rule="selection.as_of_offset",
            )
        return value
    return datetime.combine(value, time.max, tzinfo=UTC)


def parse_as_of_text(value: str | None) -> date | datetime | None:
    """Parse the text of an ``as_of`` boundary into a date or a timestamp, as written.

    The text is stripped. A 10-character value is a date; a trailing ``Z`` means a UTC offset; anything else is an
    ISO-8601 timestamp. The end-of-day rule for a date and the requirement of an offset belong to
    :func:`as_of_boundary`.

    Raises:
        ActionParameterError: If ``value`` is empty after stripping (parameter ``as_of``, rule
            ``selection.as_of_empty``) or is neither a date nor an ISO-8601 timestamp (rule
            ``selection.as_of_syntax``).
    """
    if value is None:
        return None
    text = value.strip()
    if not text:
        raise ActionParameterError(
            "{as_of} must be non-empty when supplied.", parameters=("as_of",), rule="selection.as_of_empty"
        )
    try:
        if len(text) == _DATE_LENGTH:
            return date.fromisoformat(text)
        normalized = f"{text[:-1]}+00:00" if text.endswith(("Z", "z")) else text
        return datetime.fromisoformat(normalized)
    except ValueError:
        raise ActionParameterError(
            "{as_of} must be YYYY-MM-DD or a valid timezone-aware ISO-8601 timestamp.",
            parameters=("as_of",),
            rule="selection.as_of_syntax",
        ) from None


def _field_name(location: tuple[int | str, ...]) -> str:
    """Return the dotted model field name of a pydantic error location."""
    return ".".join(str(part) for part in location)


def _rule_error(error: SelectionRuleError) -> ActionParameterError:
    """Return a selection rule's error as the action's parameter error."""
    return ActionParameterError(error.template, parameters=error.fields, rule=error.rule, arguments=error.arguments)


def _first_error(error: ValidationError) -> ActionParameterError:
    """Return the first validation error of a selection model as the action's parameter error.

    A rule the model raised keeps its own template, rule and values. A built-in field error is "Invalid
    {field}: <text>", or "{field} is required." for a missing field, and keeps its pydantic type and its plain
    context values.

    Raises:
        ValidationError: If the error belongs to the model as a whole and not to a rule or a field, which is a
            programming error in the model.
    """
    first = error.errors(include_input=False, include_url=False)[0]
    context = first.get("ctx") or {}
    cause = context.get("error")
    if isinstance(cause, SelectionRuleError):
        return _rule_error(cause)
    location = first["loc"]
    if not location:
        raise error
    field = _field_name(location)
    kind = first["type"]
    arguments: dict[str, object] = {
        key: value for key, value in context.items() if isinstance(value, str | int | float | bool)
    }
    if kind == "missing":
        return ActionParameterError(
            f"{{{field}}} is required.", parameters=(field,), rule="pydantic.missing", arguments=arguments
        )
    arguments[_PYDANTIC_MESSAGE] = first["msg"].removeprefix("Value error, ")
    return ActionParameterError(
        f"Invalid {{{field}}}: {{{_PYDANTIC_MESSAGE}}}",
        parameters=(field,),
        rule=f"pydantic.{kind}",
        arguments=arguments,
    )


def build_selection(context: ApplicationContext, method_id: str, fields: Mapping[str, object]) -> SelectionMember:
    """Build one validated selection for ``method_id`` from its model's fields.

    Each field the strategy names in ``selection_settings_fields`` that ``fields`` omits is filled from the
    strategy's settings, loaded through ``context``. ``as_of`` is a date (the end of that day in UTC) or a
    timestamp with a timezone offset. The first error is reported, in field order.

    Args:
        context: The application context, which locates the strategy's settings.
        method_id: The canonical method identifier of the strategy.
        fields: The selection model's fields by name; a nested model is a nested mapping. ``analysis_id``,
            ``method_id`` and ``config_schema_version`` are the class's and are rejected here.

    Returns:
        The validated selection, an instance of the strategy's selection class.

    Raises:
        ActionParameterError: If ``method_id`` is not a declared method (parameter ``method_id``) or a field is
            missing, unknown or breaks a rule; the parameters are model field names.
    """
    descriptor = find(BY_METHOD_ID, method_id)
    if descriptor is None:
        raise ActionParameterError(
            "{method_id} is not a declared method.", parameters=("method_id",), rule="selection.undeclared_method"
        )
    for fixed in _FIXED_FIELDS:
        if fixed in fields:
            raise ActionParameterError(
                f"Invalid {{{fixed}}}: {{{_PYDANTIC_MESSAGE}}}",
                parameters=(fixed,),
                rule="pydantic.extra_forbidden",
                arguments={_PYDANTIC_MESSAGE: "Extra inputs are not permitted"},
            )
    values = dict(fields)
    if values.get("as_of") is not None:
        boundary = values["as_of"]
        if not isinstance(boundary, date):
            raise ActionParameterError(
                f"Invalid {{as_of}}: {{{_PYDANTIC_MESSAGE}}}",
                parameters=("as_of",),
                rule="pydantic.date_type",
                arguments={_PYDANTIC_MESSAGE: "Input should be a valid date or datetime"},
            )
        values["as_of"] = as_of_boundary(boundary)
    omitted = [name for name in descriptor.selection_settings_fields if name not in values]
    if omitted and descriptor.settings_type is not None:
        configured = load_component_settings(descriptor.alias, descriptor.settings_type, context.settings.config_dir)
        for name in omitted:
            values[name] = getattr(configured, name)
    try:
        selection = descriptor.behavior.selection_type.model_validate(values)
    except ValidationError as error:
        raise _first_error(error) from None
    if not isinstance(selection, SelectionMember):
        raise undeclared("selection type", type(selection))
    return selection
