"""The one timestamp type every JSON document model uses.

A document emits an instant as ``datetime.isoformat()`` spells it: ``+00:00`` for UTC, and any other offset exactly
as the value carries it. Pydantic's own JSON mode spells UTC ``Z``, so a document model that declared a plain
``datetime`` or ``AwareDatetime`` field would emit a different spelling from the other documents; declaring
:data:`DocumentTimestamp` keeps one. This is a leaf module: it imports nothing from the application.
"""

from datetime import datetime
from typing import Annotated, Any

from pydantic import AwareDatetime, BaseModel, PlainSerializer, WithJsonSchema
from pydantic_core import to_jsonable_python


def _isoformat(value: datetime) -> str:
    """Return ``value`` as ``isoformat()`` writes it, keeping its own offset."""
    return value.isoformat()


DocumentTimestamp = Annotated[
    AwareDatetime,
    PlainSerializer(_isoformat, return_type=str, when_used="json"),
    WithJsonSchema(
        {
            "type": "string",
            "format": "date-time",
            "description": "An ISO 8601 instant with its UTC offset, e.g. +00:00.",
        },
        mode="serialization",
    ),
]


def _spell_instants(value: Any) -> Any:
    """Return ``value`` with every datetime inside it replaced by its ``isoformat()`` text."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _spell_instants(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_spell_instants(item) for item in value]
    return value


def document_json_value(model: BaseModel) -> Any:
    """Return ``model`` as JSON-ready data with every instant spelled as :data:`DocumentTimestamp` spells it.

    For a model the document does not own, such as a stored selection: it is dumped without any change to the model,
    and only its instants are re-spelled, so the model, and anything stored from it, is unchanged.
    """
    return to_jsonable_python(_spell_instants(model.model_dump(mode="python")))


__all__ = ["DocumentTimestamp", "document_json_value"]
