"""Configuration for the graham_growth strategy."""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, StrictFloat, field_validator

GrahamGrowthEPSBasis = Literal["three_year_average", "fiscal_year"]
"""The EPS bases Graham Growth accepts: the three-year average, or one completed fiscal year."""

_DEFAULT_EPS_BASIS: Final[GrahamGrowthEPSBasis] = "three_year_average"


class GrahamGrowthConfig(BaseModel):
    """Growth-value request with explicit growth and AAA yield in percent units."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    eps_basis: GrahamGrowthEPSBasis = _DEFAULT_EPS_BASIS
    eps_override: StrictFloat | None = None
    quote_override: StrictFloat | None = None
    expected_growth: StrictFloat
    aaa_yield_override: StrictFloat

    @field_validator("eps_basis", mode="before")
    @classmethod
    def normalize_basis(cls, value: object) -> object:
        """Normalize text before validating the supported EPS basis literals."""
        return value.strip().lower() if isinstance(value, str) else value
