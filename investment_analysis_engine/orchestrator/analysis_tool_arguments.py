"""Shared validation base for production analysis-tool arguments."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
PositiveFiniteFloat = Annotated[float, Field(gt=0, allow_inf_nan=False)]


class AnalysisToolArguments(BaseModel):
    """Shared validation for production analysis-tool arguments.

    Attributes:
        ticker: The instrument symbol, normalized to upper case.
        as_of: The timezone-aware point-in-time boundary, or ``None`` for the latest data.
        use_cache: Whether the analysis may read and write the strategy's data caches. Every strategy offers it, so
            it is declared here once and no arguments model redeclares it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    ticker: str
    as_of: datetime | None = None
    use_cache: bool = True

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        """Normalize and require a non-empty ticker symbol."""
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("ticker must be a non-empty string.")
        return normalized

    @field_validator("as_of")
    @classmethod
    def require_aware_as_of(cls, value: datetime | None) -> datetime | None:
        """Reject ambiguous point-in-time boundaries."""
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("as_of must be timezone-aware.")
        return value
