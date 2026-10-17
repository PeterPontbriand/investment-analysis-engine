"""Configuration for the graham_growth strategy."""

from __future__ import annotations

from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, StrictFloat, field_validator, model_validator

from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID

GrahamGrowthEPSBasis = Literal["three_year_average", "fiscal_year"]
"""The EPS bases Graham Growth accepts: the three-year average, or one completed fiscal year."""

_DEFAULT_EPS_BASIS: Final[GrahamGrowthEPSBasis] = "three_year_average"


class GrahamGrowthConfig(BaseModel):
    """Growth-value request with explicit growth and AAA yield in percent units."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    security_provider_id: str = "sec_edgar"
    quote_provider_id: str | None = None
    eps_basis: GrahamGrowthEPSBasis | None = None
    eps_override: StrictFloat | None = None
    quote_override: StrictFloat | None = None
    expected_growth: StrictFloat
    aaa_yield_override: StrictFloat

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

    @field_validator("eps_basis", mode="before")
    @classmethod
    def normalize_basis(cls, value: object) -> object:
        """Normalize text before validating the supported EPS basis literals."""
        return value.strip().lower() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_method(self) -> Self:
        """Resolve the EPS basis and the quote provider."""
        quote_provider = self.quote_provider_id
        if quote_provider is None:
            quote_provider = "yfinance" if self.security_provider_id == SEC_PROVIDER_ID else self.security_provider_id
        object.__setattr__(self, "eps_basis", self.eps_basis or _DEFAULT_EPS_BASIS)
        object.__setattr__(self, "quote_provider_id", quote_provider)
        return self
