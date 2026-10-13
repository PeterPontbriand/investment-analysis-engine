"""Structured-output schema constraint formatting and validation of model output."""

from src.schema.config import get_schema_config, set_schema_config
from src.schema.constraint import (
    SchemaConstraint,
    build_schema_constraint,
    detect_ollama_schema_support,
    format_schema_for_ollama,
    get_fallback_strategy,
)
from src.schema.exceptions import (
    SchemaCompatibilityError,
    SchemaConstraintError,
    SchemaError,
    SchemaValidationError,
    SchemaViolationError,
)
from src.schema.models import (
    ToolCallResponse,
)
from src.schema.validator import (
    ValidationErrorType,
    ValidationResult,
    build_retry_messages,
    classify_validation_error,
    validate_response,
    validate_with_schema,
)

__all__ = [
    "SchemaCompatibilityError",
    "SchemaConstraint",
    "SchemaConstraintError",
    "SchemaError",
    "SchemaValidationError",
    "SchemaViolationError",
    "ToolCallResponse",
    "ValidationErrorType",
    "ValidationResult",
    "build_retry_messages",
    "build_schema_constraint",
    "classify_validation_error",
    "detect_ollama_schema_support",
    "format_schema_for_ollama",
    "get_fallback_strategy",
    "get_schema_config",
    "set_schema_config",
    "validate_response",
    "validate_with_schema",
]
