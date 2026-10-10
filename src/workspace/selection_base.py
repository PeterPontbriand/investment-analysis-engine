"""Shared base and supported-provider vocabulary for the workspace selection snapshots."""

from pydantic import BaseModel, ConfigDict, field_validator

# Provider identifiers supported by the current CLI composition. These mirror the
# stable IDs declared in ``src.data.sec_edgar.financial_facts`` and ``src.data.yfinance.client``; they are
# used as literals here (as the base Graham configs do) to keep this request model
# free of the production provider stack.
CLI_SECURITY_PROVIDERS = ("sec_edgar",)
CLI_QUOTE_PROVIDERS = ("yfinance",)


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
