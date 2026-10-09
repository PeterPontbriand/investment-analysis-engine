"""Configuration for schema enforcement.

Provides settings for strictness, fallback behavior, and Ollama compatibility.
"""

from __future__ import annotations

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
        ollama_version: Override for Ollama version detection.
    """

    strict_mode: bool = True
    additional_properties: bool = False
    use_native_constraint: bool = True
    fallback_to_prompt: bool = True
    max_validation_retries: int = 3
    ollama_version: str | None = None


class _ConfigStore:
    """Mutable holder for the process-wide schema configuration."""

    current: SchemaConfig | None = None


def get_schema_config() -> SchemaConfig:
    """Get the global schema configuration, taking it from the application settings if not set.

    The values come from ``IAN_SCHEMA_CONFIG__<FIELD>`` environment variables through the settings class.
    """
    if _ConfigStore.current is None:
        from src.config import settings  # noqa: PLC0415 - src.config imports this module at load time

        _ConfigStore.current = settings.schema_config
    return _ConfigStore.current


def set_schema_config(config: SchemaConfig) -> None:
    """Set the global schema configuration."""
    _ConfigStore.current = config
