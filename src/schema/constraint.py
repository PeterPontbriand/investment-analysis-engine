"""Ollama native JSON-schema constraint builder.

Implements the format=<JSON Schema> constraint for Ollama API calls,
converting Pydantic models to the JSON Schema format expected by
the Ollama client.

Ollama contract (as of structured-outputs support):
  - format="json"              → any valid JSON object
  - format=<schema dict>       → constrained decoding to that schema

There is no separate "schema" key and no top-level "strict" flag.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

from pydantic import BaseModel

from src.schema.exceptions import SchemaConstraintError
from src.schema.models import model_to_json_schema

logger = logging.getLogger(__name__)


class SchemaConstraint:
    """Represents a JSON Schema constraint for Ollama generation.

    Attributes:
        schema_dict: The JSON Schema dictionary (passed directly as `format`).
        model_class: Optional Pydantic model class for downstream validation.
        strict: Whether our validation layer should reject extra fields.
    """

    def __init__(
        self,
        schema_dict: dict[str, Any],
        model_class: type[BaseModel] | None = None,
        strict: bool = True,
    ) -> None:
        """Initialize a schema constraint.

        Args:
            schema_dict: JSON Schema dictionary to pass as Ollama `format`.
            model_class: Optional Pydantic model used for post-hoc validation.
            strict: Whether downstream validation should reject extra fields.
        """
        self.schema_dict = schema_dict
        self.model_class = model_class
        self.strict = strict

    def to_ollama_format(self) -> dict[str, Any]:
        """Return the value that should be passed as the `format` argument.

        Ollama expects the schema object itself (or the string "json").
        """
        return self.schema_dict

    def to_ollama_params(self) -> dict[str, Any]:
        """Get the keyword arguments to spread into ollama.chat() / ollama.generate().

        Returns:
            {"format": <schema dict>}
        """
        return {"format": self.schema_dict}

    def __repr__(self) -> str:
        """Return a concise representation for debugging."""
        name = self.model_class.__name__ if self.model_class else "None"
        return f"SchemaConstraint(model={name}, strict={self.strict})"


def _ensure_schema_strictness(
    schema_dict: dict[str, Any],
    additional_properties: bool,
) -> dict[str, Any]:
    """Apply additionalProperties recursively on nested object schemas."""
    schema = copy.deepcopy(schema_dict)

    def _walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        node_type = node.get("type")
        if node_type == "object" or "properties" in node:
            if "additionalProperties" not in node:
                node["additionalProperties"] = additional_properties
            for prop in node.get("properties", {}).values():
                _walk(prop)
        if node_type == "array" and "items" in node:
            _walk(node["items"])
        for defn in node.get("$defs", {}).values():
            _walk(defn)
        for defn in node.get("definitions", {}).values():
            _walk(defn)

    _walk(schema)
    return schema


def build_schema_constraint(
    model_class: type[BaseModel],
    strict: bool = True,
    additional_properties: bool = False,
) -> SchemaConstraint:
    """Build a SchemaConstraint from a Pydantic model class.

    Args:
        model_class: Pydantic model class defining the expected output.
        strict: Whether downstream Pydantic validation should reject extra fields.
        additional_properties: Whether the emitted JSON Schema allows extra keys.

    Returns:
        SchemaConstraint ready for Ollama.

    Raises:
        SchemaConstraintError: If schema generation fails.
    """
    try:
        schema_dict = model_to_json_schema(model_class)
        schema_dict = _ensure_schema_strictness(
            schema_dict,
            additional_properties=additional_properties,
        )

        if "required" not in schema_dict and hasattr(model_class, "model_fields"):
            required = [name for name, field in model_class.model_fields.items() if field.is_required()]
            if required:
                schema_dict["required"] = required

        return SchemaConstraint(
            schema_dict=schema_dict,
            model_class=model_class,
            strict=strict,
        )
    except Exception as e:
        logger.error(
            "Failed to build schema constraint for %s: %s",
            getattr(model_class, "__name__", model_class),
            e,
        )
        raise SchemaConstraintError(
            f"Failed to build schema for {getattr(model_class, '__name__', model_class)}: {e}"
        ) from e


def format_schema_for_ollama(
    model_class: type[BaseModel],
    strict: bool = True,
    additional_properties: bool = False,
) -> dict[str, Any]:
    """Return kwargs ready to spread into ollama.chat().

    Example:
        >>> params = format_schema_for_ollama(ToolCallResponse)
        >>> response = ollama.chat(model="llama3.1", messages=[...], **params)
    """
    constraint = build_schema_constraint(
        model_class=model_class,
        strict=strict,
        additional_properties=additional_properties,
    )
    return constraint.to_ollama_params()


def detect_ollama_schema_support(ollama_version: str | None) -> bool | None:
    """Classify Ollama native JSON-schema (structured outputs) capability.

    Structured outputs with a schema object were introduced substantially
    later than basic format="json". Versions before 0.5.0 are classified as
    known-unsupported for schema-constrained decoding; callers should still
    run Pydantic validation as the second line of defence in all cases.

    Args:
        ollama_version: Version string from the remote Ollama server's
            ``GET /api/version`` endpoint (e.g. ``"0.5.4"``). May be ``None``
            when the version could not be retrieved.

    Returns:
        True if the version is known to support schema-constrained generation
        (>= 0.5.0 or >= 1.0.0).
        False if the version is known to be below the threshold.
        None if the version is missing, empty, or unparseable (UNKNOWN state).
    """
    if ollama_version is None or not isinstance(ollama_version, str):
        return None
    if not ollama_version.strip():
        return None
    try:
        cleaned = ollama_version.strip().lower()
        for prefix in ("ollama version is ", "ollama version ", "version "):
            cleaned = cleaned.removeprefix(prefix)
        cleaned = cleaned.split()[0]
        parts = cleaned.split(".")
        if len(parts) < 2:
            # Only one component (e.g. "0") – cannot classify with confidence.
            return None
        major = int(parts[0])
        minor = int(parts[1].split("-")[0])
        return major >= 1 or (major == 0 and minor >= 5)
    except (ValueError, AttributeError, IndexError):
        logger.warning("Unable to parse Ollama version: %r", ollama_version)
        return None


def get_fallback_strategy() -> str:
    """Return the documented fallback strategy when native constraints are unavailable."""
    return (
        "When native schema constraints are not supported by the Ollama "
        "version or model, fall back to: (1) prompt engineering with "
        "explicit JSON format instructions, (2) Pydantic validation with "
        "retry on validation failure (see build_retry_messages), "
        "(3) circuit-breaker on repeated failures."
    )
