"""Configuration for the graham_growth strategy."""

from __future__ import annotations

from typing import Self

from pydantic import StrictFloat, model_validator

from src.analysis.shared.graham_contracts import _GrahamConfig


class GrahamGrowthConfig(_GrahamConfig):
    """Growth-value request with explicit growth and AAA yield in percent units."""

    expected_growth: StrictFloat
    aaa_yield_override: StrictFloat

    @model_validator(mode="after")
    def validate_method(self) -> Self:
        """Resolve the provider-dependent EPS basis and quote provider."""
        self._resolve_defaults("three_year_average" if self.security_provider_id == "sec_edgar" else "ttm")
        return self
