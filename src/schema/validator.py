"""Pydantic validation as second-line defense.

Validates LLM responses against Pydantic models, classifies errors,
and provides recovery-friendly error information plus a small helper
for building retry messages.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, cast

from pydantic import BaseModel, ValidationError

from src.schema.exceptions import SchemaValidationError

logger = logging.getLogger(__name__)


class ValidationErrorType(StrEnum):
    """Classification of validation errors."""

    MISSING_FIELD = "missing_field"
    INVALID_TYPE = "invalid_type"
    EXTRA_FIELD = "extra_field"  # When extra="forbid" / strict mode
    VALUE_ERROR = "value_error"  # Custom validator / constraint failures
    MALFORMED_JSON = "malformed_json"
    UNKNOWN = "unknown"


@dataclass
class ValidationResult:
    """Result of a validation attempt.

    Attributes:
        valid: Whether validation succeeded.
        data: Validated model (if valid) or raw parsed data / text (if invalid).
        errors: List of error detail dicts.
        error_type: Classification of the primary error.
        is_recoverable: Whether this error can be retried.
    """

    valid: bool
    data: Any
    errors: list[dict[str, Any]] = field(default_factory=list)
    error_type: ValidationErrorType | None = None
    is_recoverable: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for telemetry logging."""
        return {
            "valid": self.valid,
            "error_type": self.error_type.value if self.error_type else None,
            "is_recoverable": self.is_recoverable,
            "error_count": len(self.errors),
        }

    def error_summary(self, max_errors: int = 5) -> str:
        """Human-readable summary suitable for inclusion in a retry prompt."""
        if self.valid:
            return "Validation succeeded."
        lines = [f"Validation failed ({self.error_type.value if self.error_type else 'unknown'}):"]
        for err in self.errors[:max_errors]:
            loc = err.get("loc") or "(root)"
            msg = err.get("msg") or err.get("detail") or "unknown error"
            lines.append(f"  - {loc}: {msg}")
        if len(self.errors) > max_errors:
            lines.append(f"  ... and {len(self.errors) - max_errors} more")
        return "\n".join(lines)


def validate_response(
    response_text: str,
    model_class: type[BaseModel],
    strict: bool = True,
) -> ValidationResult:
    """Validate an LLM response against a Pydantic model.

    This is the primary entry point for second-line validation.

    Args:
        response_text: Raw text response from the LLM.
        model_class: Pydantic model class to validate against.
        strict: When True, prefer strict type checking. Extra-field rejection
            is controlled by the model's own ConfigDict(extra=...).

    Returns:
        ValidationResult with validation outcome.
    """
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.warning("Malformed JSON in response: %s", e)
        return ValidationResult(
            valid=False,
            data=response_text,
            errors=[
                {
                    "error": "malformed_json",
                    "detail": str(e),
                    "loc": "",
                    "msg": str(e),
                    "type": "json_invalid",
                }
            ],
            error_type=ValidationErrorType.MALFORMED_JSON,
            is_recoverable=True,
        )

    try:
        validated = model_class.model_validate(data, strict=True) if strict else model_class.model_validate(data)
        return ValidationResult(
            valid=True,
            data=validated,
            errors=[],
            error_type=None,
            is_recoverable=True,
        )
    except ValidationError as e:
        error_info = _classify_validation_errors(e, model_class)
        error_type = _determine_primary_error_type(error_info)

        logger.debug(
            "Validation failed for %s: %d errors, type=%s",
            model_class.__name__,
            len(error_info),
            error_type,
        )

        return ValidationResult(
            valid=False,
            data=data,
            errors=error_info,
            error_type=error_type,
            is_recoverable=True,  # All schema violations are treated as recoverable
        )


def validate_with_schema[T: BaseModel](
    response_text: str,
    model_class: type[T],
    strict: bool = True,
) -> T:
    """Validate and return the validated model, raising on failure."""
    result = validate_response(response_text, model_class, strict)
    if not result.valid:
        raise SchemaValidationError(
            f"Validation failed for {model_class.__name__}",
            errors=result.errors,
            error_type=result.error_type.value if result.error_type else None,
        )
    return cast(T, result.data)


_TYPE_MAP: dict[str, ValidationErrorType] = {
    "missing": ValidationErrorType.MISSING_FIELD,
    "literal_error": ValidationErrorType.INVALID_TYPE,
    "enum": ValidationErrorType.INVALID_TYPE,
    "int_type": ValidationErrorType.INVALID_TYPE,
    "float_type": ValidationErrorType.INVALID_TYPE,
    "string_type": ValidationErrorType.INVALID_TYPE,
    "bool_type": ValidationErrorType.INVALID_TYPE,
    "list_type": ValidationErrorType.INVALID_TYPE,
    "dict_type": ValidationErrorType.INVALID_TYPE,
    "value_error": ValidationErrorType.VALUE_ERROR,
    "assertion_error": ValidationErrorType.VALUE_ERROR,
    "less_than_equal": ValidationErrorType.VALUE_ERROR,
    "greater_than_equal": ValidationErrorType.VALUE_ERROR,
    "less_than": ValidationErrorType.VALUE_ERROR,
    "greater_than": ValidationErrorType.VALUE_ERROR,
    "extra_forbidden": ValidationErrorType.EXTRA_FIELD,
    "json_invalid": ValidationErrorType.MALFORMED_JSON,
}


def classify_validation_error(error: Exception) -> ValidationErrorType:
    """Classify a validation exception into an error type."""
    if isinstance(error, json.JSONDecodeError):
        return ValidationErrorType.MALFORMED_JSON

    if not isinstance(error, ValidationError):
        return ValidationErrorType.UNKNOWN

    for err in error.errors():
        mapped = _TYPE_MAP.get(err.get("type", ""))
        if mapped is not None:
            return mapped
    return ValidationErrorType.UNKNOWN


def build_retry_messages(
    original_messages: Sequence[dict[str, Any]],
    validation_result: ValidationResult,
    *,
    assistant_content: str | None = None,
    max_errors: int = 5,
) -> list[dict[str, Any]]:
    """Build a new messages list that includes feedback about the validation failure.

    Intended for use in a retry loop:

        result = validate_response(...)
        if not result.valid and result.is_recoverable:
            messages = build_retry_messages(messages, result, assistant_content=raw)
            # re-call ollama.chat with the new messages

    Args:
        original_messages: The message list used for the failed attempt.
        validation_result: The failed ValidationResult.
        assistant_content: Optional raw assistant reply to include in history.
        max_errors: How many individual errors to surface in the prompt.

    Returns:
        New list of message dicts ready for the next ollama.chat call.
    """
    messages: list[dict[str, Any]] = [dict(m) for m in original_messages]

    if assistant_content is not None:
        messages.append({"role": "assistant", "content": assistant_content})

    feedback = (
        "Your previous response did not match the required schema.\n"
        f"{validation_result.error_summary(max_errors=max_errors)}\n\n"
        "Please respond again with a single valid JSON object that satisfies "
        "all required fields and types. Do not include any extra fields or "
        "explanatory text outside the JSON."
    )
    messages.append({"role": "user", "content": feedback})
    return messages


def _classify_validation_errors(
    error: ValidationError,
    model_class: type[BaseModel],
) -> list[dict[str, Any]]:
    """Extract and classify individual validation errors."""
    errors: list[dict[str, Any]] = []
    for err in error.errors():
        loc_parts = err.get("loc", ())
        loc = ".".join(str(p) for p in loc_parts) if loc_parts else ""
        error_info: dict[str, Any] = {
            "loc": loc,
            "type": err.get("type", "unknown"),
            "msg": err.get("msg", "Unknown error"),
        }
        if err.get("type") == "missing" and loc_parts:
            error_info["expected_type"] = _get_field_type(model_class, str(loc_parts[0]))
        errors.append(error_info)
    return errors


def _determine_primary_error_type(
    errors: list[dict[str, Any]],
) -> ValidationErrorType:
    """Determine the primary error type from a list of errors."""
    if not errors:
        return ValidationErrorType.UNKNOWN
    for err in errors:
        mapped = _TYPE_MAP.get(err.get("type", ""))
        if mapped is not None:
            return mapped
    return ValidationErrorType.UNKNOWN


def _get_field_type(model_class: type[BaseModel], field_name: str) -> str | None:
    """Get the expected type of a field for error context."""
    if not field_name:
        return None
    field_info = model_class.model_fields.get(field_name)
    if field_info is not None:
        return str(field_info.annotation)
    return None
