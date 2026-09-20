"""Supporting types for the versioned, immutable run envelope.

This module owns only the shared value types referenced by the run/watchlist
envelope models in :mod:`src.workspace.runs`: the terminal outcome enum, a strict
recursive JSON value type that rejects non-finite numbers and non-primitives, an
inclusive date boundary, and the frozen/extra-forbid base convention shared with
the B1 selection snapshots. It performs no persistence, codec, or analysis work.
"""

import math
from datetime import date
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, model_validator


class RunOutcome(StrEnum):
    """Terminal outcome of a workspace analysis run.

    Only terminal states exist; there is deliberately no in-progress value because
    the envelope records an immutable completed attempt rather than live state.
    """

    COMPLETED = "completed"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"
    FAILED = "failed"
    CANCELLED = "cancelled"


def _validate_json_value(value: object) -> object:
    """Recursively validate that ``value`` is a JSON-compatible primitive tree.

    Pydantic 2.x cannot build a schema for a bare self-referential type alias, so the
    recursive shape is enforced here at runtime instead of through a union annotation.
    The function returns the input unchanged when it is valid and raises ``ValueError``
    (surfaced by Pydantic as a validation error) otherwise.

    Args:
        value: Any Python object to validate.

    Returns:
        The validated value, unmodified.

    Raises:
        ValueError: If the value contains non-finite floats, non-string mapping keys, or
            any type that is not a JSON primitive (``None``, ``bool``, ``int``, ``float``,
            ``str``, list, or dict).
    """
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("JSON values must be finite.")
        return value
    if isinstance(value, list):
        for item in value:
            _validate_json_value(item)
        return value
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("JSON object keys must be strings.")
            _validate_json_value(item)
        return value
    raise ValueError(f"Unsupported JSON primitive: {type(value).__name__}.")


# JSON-compatible value types used by the run envelope. The recursive shape is enforced at
# runtime by ``_validate_json_value`` (see above); statically this is an opaque JSON blob.
JsonValue = Annotated[Any, BeforeValidator(_validate_json_value)]

StrictJsonMapping = dict[str, JsonValue]


class _FrozenModel(BaseModel):
    """Shared strictness for workspace run-envelope models."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class EffectiveBoundary(_FrozenModel):
    """Inclusive date boundary applied to a run.

    ``start`` and/or ``end`` may be omitted; when both are present the end must not
    precede the start. Dates (rather than timestamps) capture observation-day
    granularity for source data.
    """

    start: date | None = None
    end: date | None = None

    @model_validator(mode="after")
    def _check_range(self) -> "EffectiveBoundary":
        """Require the boundary end to be on or after its start when both are set."""
        if self.start is not None and self.end is not None and self.end < self.start:
            raise ValueError("effective_boundary end must be on or after start.")
        return self


__all__ = [
    "EffectiveBoundary",
    "JsonValue",
    "RunOutcome",
    "StrictJsonMapping",
]
