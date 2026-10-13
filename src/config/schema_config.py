"""Configuration for native schema enforcement.

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
