"""The one timestamp type every JSON document model uses.

A document emits an instant as ``datetime.isoformat()`` spells it: ``+00:00`` for UTC, and any other offset exactly
as the value carries it. Pydantic's own JSON mode spells UTC ``Z``, so a document model that declared a plain
``datetime`` or ``AwareDatetime`` field would emit a different spelling from the other documents; declaring
:data:`DocumentTimestamp` keeps one. This is a leaf module: it imports nothing from the application.
"""

from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, PlainSerializer, WithJsonSchema


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

__all__ = ["DocumentTimestamp"]
