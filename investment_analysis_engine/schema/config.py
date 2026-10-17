"""Process-wide access to the schema-enforcement configuration (the shape is ``config.schema_config``)."""

from __future__ import annotations

from investment_analysis_engine.config import settings
from investment_analysis_engine.config.schema_config import SchemaConfig


class _ConfigStore:
    """Mutable holder for the process-wide schema configuration."""

    current: SchemaConfig | None = None


def get_schema_config() -> SchemaConfig:
    """Get the global schema configuration, taking it from the application settings if not set.

    The values come from ``IAN_SCHEMA_CONFIG__<FIELD>`` environment variables through the settings class.
    """
    if _ConfigStore.current is None:
        _ConfigStore.current = settings.schema_config
    return _ConfigStore.current


def set_schema_config(config: SchemaConfig) -> None:
    """Set the global schema configuration."""
    _ConfigStore.current = config
