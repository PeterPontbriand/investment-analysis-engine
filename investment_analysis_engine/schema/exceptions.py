"""Custom exceptions for the schema enforcement module.

All exceptions are designed to be recoverable and feed into the
circuit-breaker/retry path per Step 2.2 specification.
"""

from __future__ import annotations

from typing import Any


class SchemaError(Exception):
    """Base exception for all schema-related errors."""


class SchemaConstraintError(SchemaError):
    """Raised when building a schema constraint fails."""


class SchemaCompatibilityError(SchemaError):
    """Raised when the Ollama version or model doesn't support schema constraints."""


class SchemaValidationError(SchemaError):
    """Raised when Pydantic validation of a response fails.

    This is the primary exception for validation failures and is
    designed to be recoverable.
    """

    def __init__(
        self,
        message: str,
        errors: list[dict[str, Any]] | None = None,
        error_type: str | Any | None = None,
    ) -> None:
        """Initialize a validation error with optional structured details.

        Args:
            message: Human-readable error message.
            errors: Optional list of per-field error dicts.
            error_type: Optional classification string or enum value.
        """
        self.errors = errors or []
        self.error_type = error_type
        super().__init__(message)

    def __str__(self) -> str:
        """Return a summary including error type and count when available."""
        base = super().__str__()
        if self.error_type:
            base = f"{base} (type={self.error_type})"
        if self.errors:
            base = f"{base}: {len(self.errors)} validation errors"
        return base


class SchemaViolationError(SchemaError):
    """Raised when a schema constraint is violated during generation.

    Distinct from validation errors: occurs during generation rather than
    post-hoc validation.
    """
