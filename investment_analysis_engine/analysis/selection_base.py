"""Shared base for the workspace selection snapshots."""

from pydantic import BaseModel, ConfigDict, field_validator


class FrozenSelection(BaseModel):
    """Shared strictness for workspace selection snapshots."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    @field_validator("config_schema_version", mode="before", check_fields=False)
    @classmethod
    def _require_integer_version(cls, value: object) -> object:
        """Reject boolean/float lookalikes before validating the version literal."""
        if type(value) is not int:
            raise ValueError("config_schema_version must be an integer.")
        return value
