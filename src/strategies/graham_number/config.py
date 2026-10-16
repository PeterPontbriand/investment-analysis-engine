"""Configuration for the graham_number strategy."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, StrictFloat, field_validator, model_validator

from src.data.sec_edgar.financial_facts import SEC_PROVIDER_ID


class GrahamNumberConfig(BaseModel):
    """Graham Number request; its EPS is always the three-year average of fiscal EPS."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    security_provider_id: str = "sec_edgar"
    quote_provider_id: str | None = None
    eps_override: StrictFloat | None = None
    quote_override: StrictFloat | None = None
    bvps_override: StrictFloat | None = None

    @field_validator("security_provider_id", "quote_provider_id")
    @classmethod
    def normalize_provider(cls, value: str | None) -> str | None:
        """Normalize supplied provider identifiers without restricting injection."""
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("Provider identifier must not be blank.")
        return normalized

    @model_validator(mode="after")
    def validate_method(self) -> Self:
        """Resolve the quote provider."""
        quote_provider = self.quote_provider_id
        if quote_provider is None:
            quote_provider = "yfinance" if self.security_provider_id == SEC_PROVIDER_ID else self.security_provider_id
        object.__setattr__(self, "quote_provider_id", quote_provider)
        return self
