"""Configuration for the graham_number strategy."""

from __future__ import annotations

from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, StrictFloat, field_validator, model_validator

from src.data.financial.eps_basis import (
    MASSIVE_ONLY_EPS_BASIS,
    default_eps_basis_for_provider,
    is_massive_provider,
    is_sec_edgar_provider,
)

# Graham Number's own accepted SEC EDGAR basis, per `docs/user/GRAHAM_NUMBER.md` §"EPS basis":
# never an explicit single-fiscal-year or ttm basis with SEC EDGAR, unlike Graham Growth.
GrahamNumberEPSBasis = Literal["three_year_average", "ttm"]

_SEC_EDGAR_ACCEPTED_BASES: Final[frozenset[str]] = frozenset({"three_year_average"})


class GrahamNumberConfig(BaseModel):
    """Graham Number request, defaulting to three-year-average fiscal EPS."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    security_provider_id: str = "sec_edgar"
    quote_provider_id: str | None = None
    eps_basis: GrahamNumberEPSBasis | None = None
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

    @field_validator("eps_basis", mode="before")
    @classmethod
    def normalize_basis(cls, value: object) -> object:
        """Normalize text before validating the supported EPS basis literals."""
        return value.strip().lower() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_method(self) -> Self:
        """Resolve the provider-dependent EPS basis/quote provider and enforce the book-value contract."""
        basis = self.eps_basis or default_eps_basis_for_provider(self.security_provider_id)
        if is_sec_edgar_provider(self.security_provider_id) and basis not in _SEC_EDGAR_ACCEPTED_BASES:
            allowed = ", ".join(sorted(_SEC_EDGAR_ACCEPTED_BASES))
            raise ValueError(f"SEC EDGAR requires eps_basis to be one of ({allowed}) (received {basis!r}).")
        if is_massive_provider(self.security_provider_id) and basis != MASSIVE_ONLY_EPS_BASIS:
            raise ValueError(f"Massive requires eps_basis={MASSIVE_ONLY_EPS_BASIS!r} (received {basis!r}).")
        quote_provider = self.quote_provider_id
        if quote_provider is None:
            quote_provider = (
                "yfinance" if is_sec_edgar_provider(self.security_provider_id) else self.security_provider_id
            )
        object.__setattr__(self, "eps_basis", basis)
        object.__setattr__(self, "quote_provider_id", quote_provider)
        if is_massive_provider(self.security_provider_id) and self.bvps_override is None:
            raise ValueError("Massive Graham Number requires bvps_override.")
        return self
