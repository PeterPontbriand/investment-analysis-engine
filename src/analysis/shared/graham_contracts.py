"""Shared Graham configuration and method contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, StrictFloat, field_validator

from src.data.financial.resolution_trace import ResolutionEvent, ResolutionOutcome, ResolutionStage, ResolutionTrace


class GrahamMethod(StrEnum):
    """Explicit method discriminator for Graham valuation calculations."""

    NUMBER = "graham_number"
    GROWTH_VALUE = "graham_growth_value"


class _GrahamConfig(BaseModel):
    """Common request fields; financial validity remains with execution services."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    security_provider_id: str = "sec_edgar"
    quote_provider_id: str | None = None
    eps_basis: Literal["three_year_average", "ttm"] | None = None
    eps_override: StrictFloat | None = None
    quote_override: StrictFloat | None = None
    as_of: AwareDatetime | None = None
    use_cache: bool = True

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

    def _resolve_defaults(self, default_basis: Literal["three_year_average", "ttm"]) -> None:
        basis = self.eps_basis or default_basis
        if self.security_provider_id == "sec_edgar" and basis != "three_year_average":
            raise ValueError("SEC EDGAR requires eps_basis='three_year_average'.")
        if self.security_provider_id == "massive" and basis != "ttm":
            raise ValueError("Massive requires eps_basis='ttm'.")
        quote_provider = self.quote_provider_id
        if quote_provider is None:
            quote_provider = "yfinance" if self.security_provider_id == "sec_edgar" else self.security_provider_id
        object.__setattr__(self, "eps_basis", basis)
        object.__setattr__(self, "quote_provider_id", quote_provider)


def _resolve_ticker(ticker: str | None, default_ticker: str | None) -> str:
    selected = ticker if ticker is not None else default_ticker
    if selected is None or not selected.strip():
        raise ValueError("A nonblank ticker is required.")
    return selected.strip().upper()


def _event(
    field_name: str,
    stage: ResolutionStage,
    outcome: ResolutionOutcome,
    message: str,
) -> ResolutionEvent:
    """Construct an assembly trace event from caller-supplied text."""
    return ResolutionEvent(field_name=field_name, stage=stage, outcome=outcome, message=message)


def _trace_event(
    field_name: str,
    stage: ResolutionStage,
    outcome: ResolutionOutcome,
    message: str,
) -> ResolutionTrace:
    """Construct a one-event assembly trace from caller-supplied text."""
    return ResolutionTrace(events=(_event(field_name, stage, outcome, message),))
