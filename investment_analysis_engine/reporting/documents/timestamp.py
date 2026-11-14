"""The one timestamp type every JSON document model uses.

A document emits an instant as ``datetime.isoformat()`` spells it: ``+00:00`` for UTC, and any other offset exactly
as the value carries it. Pydantic's own JSON mode spells UTC ``Z``, so a document model that declared a plain
``datetime`` or ``AwareDatetime`` field would emit a different spelling from the other documents; declaring
:data:`DocumentTimestamp` keeps one. This is a leaf module: it imports nothing from the application.
"""

from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Any

from pydantic import AwareDatetime, BaseModel, BeforeValidator, PlainSerializer, WithJsonSchema
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


def is_end_of_day_utc(value: datetime) -> bool:
    """Return whether ``value`` is the last instant of a UTC day, which is how a date given as an ``as_of`` is stored.

    This is the one definition of the rule: ``as_of_text`` serves such an instant as its date, and text output
    prints it as its date. A timestamp entered as exactly ``23:59:59.999999`` in UTC cannot be told from a date and
    is treated as one.
    """
    return value.utcoffset() == timedelta(0) and value.timetz().replace(tzinfo=None) == time.max


def as_of_text(value: datetime) -> str:
    """Return an ``as_of`` boundary as it was given: a date for the end of a UTC day, else the instant as written."""
    return value.date().isoformat() if is_end_of_day_utc(value) else value.isoformat()


def _read_as_of(value: Any) -> Any:
    """Read the date a document serves as the end of that day in UTC, so a document accepts what it writes."""
    if isinstance(value, str) and len(value) == len("YYYY-MM-DD"):
        try:
            value = date.fromisoformat(value)
        except ValueError:
            return value
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime.combine(value, time.max, tzinfo=UTC)
    return value


DocumentAsOf = Annotated[
    AwareDatetime,
    BeforeValidator(_read_as_of),
    PlainSerializer(as_of_text, return_type=str, when_used="json"),
    WithJsonSchema(
        {
            "anyOf": [
                {"type": "string", "format": "date"},
                {"type": "string", "format": "date-time"},
            ],
            "description": "A date (YYYY-MM-DD) when the boundary was given as a date, else an ISO 8601 instant "
            "with its UTC offset.",
        },
        mode="serialization",
    ),
]
"""An ``as_of`` boundary in a document: served as it was requested, a date or an instant, never an invented time."""


def _spell_instants(value: Any, *, key: str | None = None) -> Any:
    """Return ``value`` with every datetime in it as text; one under ``as_of`` is spelled as written."""
    if isinstance(value, datetime):
        return as_of_text(value) if key == "as_of" else value.isoformat()
    if isinstance(value, dict):
        return {name: _spell_instants(item, key=name) for name, item in value.items()}
    if isinstance(value, list | tuple):
        return [_spell_instants(item) for item in value]
    return value


def document_json_value(model: BaseModel) -> Any:
    """Return ``model`` as JSON-ready data with every instant spelled as :data:`DocumentTimestamp` spells it.

    For a model the document does not own, such as a stored selection: it is dumped without any change to the model,
    and only its instants are re-spelled, so the model, and anything stored from it, is unchanged. An ``as_of`` is
    spelled by :func:`as_of_text`.
    """
    return to_jsonable_python(_spell_instants(model.model_dump(mode="python")))


__all__ = ["DocumentAsOf", "DocumentTimestamp", "as_of_text", "document_json_value", "is_end_of_day_utc"]
