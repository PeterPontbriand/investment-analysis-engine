"""Native Schema Enforcement Module (Step 2.2).

Provides Ollama native JSON-schema constraint formatting and Pydantic validation
as a second line of defense against unstructured/drifting LLM output.
"""

from src.schema.config import SchemaConfig, get_schema_config, set_schema_config
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
    PlanResponse,
    PlanStep,
    StructuredResponse,
    SynthesisResponse,
    ToolCallResponse,
    ToolCallStatus,
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
    "PlanResponse",
    "PlanStep",
    "SchemaCompatibilityError",
    "SchemaConfig",
    "SchemaConstraint",
    "SchemaConstraintError",
    "SchemaError",
    "SchemaValidationError",
    "SchemaViolationError",
    "StructuredResponse",
    "SynthesisResponse",
    "ToolCallResponse",
    "ToolCallStatus",
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
