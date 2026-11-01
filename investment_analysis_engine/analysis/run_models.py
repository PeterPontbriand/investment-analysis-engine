"""Supporting types for the versioned, immutable run envelope.

This module owns only the shared value types referenced by the run/watchlist
envelope models in :mod:`investment_analysis_engine.workspace.runs`: the terminal outcome enum, a strict
recursive JSON value type that rejects non-finite numbers and non-primitives, an
inclusive date boundary, and the frozen/extra-forbid base convention shared with
the selection snapshots. It also holds the steps every strategy codec repeats when it
encodes and decodes its native evidence as strict JSON. It performs no persistence or
analysis work.
"""

import json
import math
from collections.abc import Callable, Mapping
from datetime import date
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, model_validator

from investment_analysis_engine.core.analysis_status import CalculationStatus


class RunOutcome(StrEnum):
    """Terminal outcome of a workspace analysis run.

    Only terminal states exist; there is deliberately no in-progress value because
    the envelope records an immutable completed attempt rather than live state.
    """

    COMPLETED = "completed"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"
    FAILED = "failed"

    @classmethod
    def from_status(cls, status: CalculationStatus) -> "RunOutcome":
        """Return the outcome of a run whose strategy reported ``status``.

        This is the one rule from a strategy's native status to the workspace outcome: ``ok`` completes,
        ``not_applicable`` is not applicable, ``input_unavailable`` is unavailable, and ``invalid_input`` and
        ``provider_error`` fail. Every strategy reports a status.
        """
        return _OUTCOME_BY_STATUS[status]


_OUTCOME_BY_STATUS: dict[CalculationStatus, RunOutcome] = {
    CalculationStatus.OK: RunOutcome.COMPLETED,
    CalculationStatus.NOT_APPLICABLE: RunOutcome.NOT_APPLICABLE,
    CalculationStatus.INPUT_UNAVAILABLE: RunOutcome.UNAVAILABLE,
    CalculationStatus.INVALID_INPUT: RunOutcome.FAILED,
    CalculationStatus.PROVIDER_ERROR: RunOutcome.FAILED,
}


def validate_json_value(value: object) -> object:
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
            validate_json_value(item)
        return value
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("JSON object keys must be strings.")
            validate_json_value(item)
        return value
    raise ValueError(f"Unsupported JSON primitive: {type(value).__name__}.")


# JSON-compatible value types used by the run envelope. The recursive shape is enforced at
# runtime by ``validate_json_value`` (see above); statically this is an opaque JSON blob.
JsonValue = Annotated[Any, BeforeValidator(validate_json_value)]

StrictJsonMapping = dict[str, JsonValue]

# The payload key that holds the result object of evidence decoded by ``decode_with_native_identifiers``.
NATIVE_RESULT_KEY = "result"
# The payload key that holds the analysis object of evidence decoded by ``decode_with_method_sections``.
METHOD_ANALYSIS_KEY = "analysis"
# The sections of that analysis object that each carry a constructor-excluded ``method`` identifier.
METHOD_SECTIONS = ("assembly", "result")


def snapshot_by_revalidation(wire: BaseModel, decode: Callable[[StrictJsonMapping], object]) -> StrictJsonMapping:
    """Capture a detached finite JSON snapshot of ``wire``, revalidating it by decoding the snapshot.

    Validation runs through JSON even for already-constructed native instances, so an invalid instance cannot bypass
    field and nested invariant checks.

    Args:
        wire: The strategy's evidence model, already built around the native result.
        decode: The strategy's own decoder, which raises on a snapshot it does not accept.

    Returns:
        The JSON-mode dump of ``wire``.
    """
    payload = wire.model_dump(mode="json")
    decode(payload)
    return payload


def validate_wire[ModelT: BaseModel](model_type: type[ModelT], wire: Mapping[str, object]) -> ModelT:
    """Validate ``wire`` as ``model_type`` in strict JSON mode, rejecting a non-finite number."""
    return model_type.model_validate_json(json.dumps(wire, allow_nan=False, ensure_ascii=False))


def decode_with_native_identifiers[ModelT: BaseModel](
    model_type: type[ModelT],
    payload: StrictJsonMapping,
    *,
    label: str,
    identifiers: Mapping[str, str],
    versions: Mapping[str, int],
) -> ModelT:
    """Decode evidence whose result object carries constructor-excluded identifiers and versions.

    The result object sits under ``NATIVE_RESULT_KEY``. The identifiers and versions are checked against the declared
    values, then removed so the native constructor restores them. The caller's payload is left intact.

    Args:
        model_type: The strategy's evidence model.
        payload: The stored evidence.
        label: The strategy's name as its error messages spell it.
        identifiers: Each constructor-excluded identifier key and its declared value.
        versions: Each constructor-excluded version key and its declared integer value.

    Returns:
        The validated evidence model.

    Raises:
        ValueError: If the payload is not strict JSON, the result is not an object, or an identifier or version does
            not match its declared value.
    """
    validate_json_value(payload)
    result = payload.get(NATIVE_RESULT_KEY)
    if not isinstance(result, dict):
        raise ValueError(f"{label} {NATIVE_RESULT_KEY} must be an object.")
    if any(result.get(name) != value for name, value in identifiers.items()) or any(
        type(result.get(name)) is not int or result.get(name) != value for name, value in versions.items()
    ):
        raise ValueError(f"{label} native identifiers or versions do not match the declared evidence.")
    native = {name: item for name, item in result.items() if name not in identifiers and name not in versions}
    return validate_wire(model_type, {**payload, NATIVE_RESULT_KEY: native})


def decode_with_method_sections[ModelT: BaseModel](
    model_type: type[ModelT],
    payload: StrictJsonMapping,
    *,
    label: str,
    method_id: str,
) -> ModelT:
    """Decode evidence whose named sections each carry a constructor-excluded ``method`` identifier.

    The analysis object sits under ``METHOD_ANALYSIS_KEY`` and each of its ``METHOD_SECTIONS`` has its ``method``
    checked against ``method_id`` and removed so the native constructor restores it. The caller's payload is left
    intact.

    Args:
        model_type: The strategy's evidence model.
        payload: The stored evidence.
        label: The strategy's name as its error messages spell it.
        method_id: The declared method identifier.

    Returns:
        The validated evidence model.

    Raises:
        ValueError: If the payload is not strict JSON, the analysis is not an object, or a section is missing or
            carries another method.
    """
    validate_json_value(payload)
    analysis = payload.get(METHOD_ANALYSIS_KEY)
    if not isinstance(analysis, dict):
        raise ValueError(f"{label} {METHOD_ANALYSIS_KEY} must be an object.")
    analysis = dict(analysis)
    for name in METHOD_SECTIONS:
        section = analysis.get(name)
        if not isinstance(section, dict) or section.get("method") != method_id:
            raise ValueError(f"{label} {'/'.join(METHOD_SECTIONS)} method mismatch.")
        analysis[name] = {item_key: item for item_key, item in section.items() if item_key != "method"}
    return validate_wire(model_type, {**payload, METHOD_ANALYSIS_KEY: analysis})


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
    "METHOD_ANALYSIS_KEY",
    "METHOD_SECTIONS",
    "NATIVE_RESULT_KEY",
    "JsonValue",
    "RunOutcome",
    "StrictJsonMapping",
    "decode_with_method_sections",
    "decode_with_native_identifiers",
    "snapshot_by_revalidation",
    "validate_wire",
]
