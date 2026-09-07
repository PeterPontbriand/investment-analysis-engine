"""Configuration for the graham_number strategy."""

from __future__ import annotations

from typing import Self

from pydantic import StrictFloat, model_validator

from src.analysis.shared.graham_contracts import _GrahamConfig


class GrahamNumberConfig(_GrahamConfig):
    """Graham Number request, defaulting to three-year-average fiscal EPS."""

    bvps_override: StrictFloat | None = None

    @model_validator(mode="after")
    def validate_method(self) -> Self:
        """Resolve defaults and enforce the provider-specific book-value contract."""
        self._resolve_defaults("three_year_average")
        if self.security_provider_id == "massive" and self.bvps_override is None:
            raise ValueError("Massive Graham Number requires bvps_override.")
        return self
