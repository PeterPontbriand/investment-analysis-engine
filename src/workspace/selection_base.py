"""Shared base and supported-provider vocabulary for the workspace selection snapshots."""

from collections.abc import Mapping
from typing import cast

from pydantic import BaseModel, ConfigDict, field_validator

# Provider identifiers supported by the current CLI composition. These mirror the
# stable IDs declared in ``src.data.massive.constants``,
# ``src.data.sec_edgar.financial_facts`` and ``src.data.yfinance.client``; they are
# used as literals here (as the base Graham configs do) to keep this request model
# free of the production provider stack.
CLI_SECURITY_PROVIDERS = ("sec_edgar", "massive")
CLI_QUOTE_PROVIDERS = ("yfinance", "massive")


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


def config_object(body: Mapping[str, object]) -> dict[str, object]:
    """Return the ``config`` object of a Momentum or Graham configuration body.

    These bodies contain only an optional ``config`` object that carries no selection identifiers.

    Raises:
        ValueError: The body has another key, ``config`` is not an object, or it supplies an identifier.
    """
    if body.keys() - {"config"}:
        raise ValueError("Configuration body may contain only 'config'.")
    supplied = body.get("config", {})
    if not isinstance(supplied, dict):
        raise ValueError("'config' must be a JSON object.")
    config = cast(dict[str, object], supplied)
    if config.keys() & {"analysis_id", "method_id", "config_schema_version"}:
        raise ValueError("Selection identifiers and version cannot be supplied in configuration.")
    return config
