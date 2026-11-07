"""The selection form of a strategy: the JSON Schema of the fields a selection accepts and their configured defaults.

The schema is the one ``schemas/selections/<alias>.schema.json`` publishes, produced by :func:`selection_schema`, which
the schema generator calls too. The schemas carry no default for a field the strategy's settings fill, because the
configured value is the user's to change; :func:`build_selection_form_document` states those values as they are now.
"""

from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue
from pydantic_core import to_jsonable_python

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.config.component_settings import load_component_settings
from investment_analysis_engine.core.operator_errors import InvalidParameterError
from investment_analysis_engine.core.strategy_errors import find
from investment_analysis_engine.strategy_wiring import BY_METHOD_ID, StrategyDescriptor

FIXED_SELECTION_FIELDS: Final = ("analysis_id", "method_id", "config_schema_version")
"""The fields a selection's class fixes; a client does not supply them and the schemas leave them out."""


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


def selection_schema(descriptor: StrategyDescriptor) -> dict[str, Any]:
    """Return the schema of the fields ``build_selection`` accepts for a strategy.

    It is the selection model's own schema with the fixed fields removed, ``as_of`` described as a date or a
    date-time with a timezone offset, and the fields the settings fill carrying neither a ``default`` nor a place in
    ``required``: the configured value is the caller's to ask for, not the schema's to state.
    """
    schema: dict[str, Any] = descriptor.behavior.selection_type.model_json_schema(mode="validation")
    properties: dict[str, Any] = schema["properties"]
    for name in FIXED_SELECTION_FIELDS:
        properties.pop(name, None)
    as_of = properties["as_of"]
    properties["as_of"] = {
        key: value
        for key, value in {
            "anyOf": [
                {"type": "string", "format": "date"},
                {"type": "string", "format": "date-time"},
                {"type": "null"},
            ],
            "default": as_of.get("default"),
            "description": as_of.get("description"),
            "title": as_of.get("title"),
        }.items()
        if value is not None or key == "default"
    }
    for name in descriptor.selection_settings_fields:
        properties[name].pop("default", None)
    required = [
        name
        for name in schema.get("required", [])
        if name not in FIXED_SELECTION_FIELDS and name not in descriptor.selection_settings_fields
    ]
    if required:
        schema["required"] = required
    else:
        schema.pop("required", None)
    return schema


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
    "FIXED_SELECTION_FIELDS",
    "SelectionFormDocument",
    "build_selection_form_document",
    "configured_defaults",
    "selection_schema",
]
