"""Configuration for schema enforcement.

Provides settings for strictness, fallback behavior, and Ollama compatibility.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class SchemaConfig:
    """Configuration for native schema enforcement.

    Attributes:
        strict_mode: Whether to reject extra fields in validation.
        additional_properties: Whether to allow additional properties in schema.
        use_native_constraint: Whether to use native Ollama schema constraints.
        fallback_to_prompt: Whether to fall back to prompt-based constraints.
        max_validation_retries: Maximum retries on validation failure.
        log_validation_errors: Whether to log detailed validation errors.
        ollama_version: Override for Ollama version detection.
    """

    strict_mode: bool = True
    additional_properties: bool = False
    use_native_constraint: bool = True
    fallback_to_prompt: bool = True
    max_validation_retries: int = 3
    log_validation_errors: bool = True
    ollama_version: str | None = None

    @classmethod
    def from_env(cls) -> SchemaConfig:
        """Load configuration from environment variables.

        Environment variables:
            SCHEMA_STRICT_MODE: bool (default: True)
            SCHEMA_ADDITIONAL_PROPERTIES: bool (default: False)
            SCHEMA_USE_NATIVE: bool (default: True)
            SCHEMA_FALLBACK_TO_PROMPT: bool (default: True)
            SCHEMA_MAX_RETRIES: int (default: 3)
            SCHEMA_LOG_ERRORS: bool (default: True)
        """

        def _get_bool(key: str, default: bool) -> bool:
            val = os.environ.get(key)
            if val is None:
                return default
            return val.lower() in ("1", "true", "yes", "on")

        def _get_int(key: str, default: int) -> int:
            val = os.environ.get(key)
            if val is None:
                return default
            try:
                return int(val)
            except ValueError:
                return default

        return cls(
            strict_mode=_get_bool("SCHEMA_STRICT_MODE", True),
            additional_properties=_get_bool("SCHEMA_ADDITIONAL_PROPERTIES", False),
            use_native_constraint=_get_bool("SCHEMA_USE_NATIVE", True),
            fallback_to_prompt=_get_bool("SCHEMA_FALLBACK_TO_PROMPT", True),
            max_validation_retries=_get_int("SCHEMA_MAX_RETRIES", 3),
            log_validation_errors=_get_bool("SCHEMA_LOG_ERRORS", True),
            ollama_version=os.environ.get("OLLAMA_VERSION"),
        )


class _ConfigStore:
    """Mutable holder for the process-wide schema configuration."""

    current: SchemaConfig | None = None


def get_schema_config() -> SchemaConfig:
    """Get the global schema configuration, loading from env if not set."""
    if _ConfigStore.current is None:
        _ConfigStore.current = SchemaConfig.from_env()
    return _ConfigStore.current


def set_schema_config(config: SchemaConfig) -> None:
    """Set the global schema configuration."""
    _ConfigStore.current = config
