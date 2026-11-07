"""The selection form of a strategy: the JSON Schema of the fields a selection accepts and their configured defaults.

The schema is the one ``schemas/selections/<alias>.schema.json`` publishes, produced by ``selection_schema`` in
``application/selections.py``, which the schema generator calls too. The schemas carry no default for a field the
strategy's settings fill, because the configured value is the user's to change;
:func:`build_selection_form_document` states those values as they are now.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue
from pydantic_core import to_jsonable_python

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.selections import selection_schema
from investment_analysis_engine.config.component_settings import load_component_settings
from investment_analysis_engine.core.operator_errors import InvalidParameterError
from investment_analysis_engine.core.strategy_errors import find
from investment_analysis_engine.strategy_wiring import BY_METHOD_ID, StrategyDescriptor


class SelectionFormDocument(BaseModel):
    """What a client needs to build a form for one strategy's selection."""

    model_config = ConfigDict(frozen=True, extra="forbid", serialize_by_alias=True)

    schema_version: Literal[1] = 1
    schema_: dict[str, JsonValue] = Field(
        alias="schema",
        description="The JSON Schema of the selection fields a request may carry, as schemas/selections publishes it.",
    )
    defaults: dict[str, JsonValue] = Field(
        description=(
            "The configured value of each field the strategy's settings fill, by field name; empty for a strategy "
            "whose selection has none. A request that omits one of these fields gets this value."
        )
    )


def configured_defaults(context: ApplicationContext, descriptor: StrategyDescriptor) -> dict[str, JsonValue]:
    """Return the configured value of each selection field the strategy's settings fill, as JSON values."""
    if not descriptor.selection_settings_fields or descriptor.settings_type is None:
        return {}
    configured = load_component_settings(descriptor.alias, descriptor.settings_type, context.settings.config_dir)
    return {name: to_jsonable_python(getattr(configured, name)) for name in descriptor.selection_settings_fields}


def build_selection_form_document(context: ApplicationContext, method_id: str) -> SelectionFormDocument:
    """Build the selection form document of the strategy with ``method_id``, reading its settings through ``context``.

    Raises:
        InvalidParameterError: If ``method_id`` is not a declared method; the parameter is ``method_id``.
    """
    descriptor = find(BY_METHOD_ID, method_id)
    if descriptor is None:
        raise InvalidParameterError(f"method_id {method_id!r} is not a declared method.", parameters=("method_id",))
    return SelectionFormDocument.model_validate(
        {"schema": selection_schema(descriptor), "defaults": configured_defaults(context, descriptor)}
    )


__all__ = [
    "SelectionFormDocument",
    "build_selection_form_document",
    "configured_defaults",
]
