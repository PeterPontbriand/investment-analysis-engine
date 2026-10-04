"""Shared validation base for production analysis-tool arguments."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
PositiveFiniteFloat = Annotated[float, Field(gt=0, allow_inf_nan=False)]


class AnalysisToolArguments(BaseModel):
    """Shared validation for production analysis-tool arguments."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ticker: str
    as_of: datetime | None = None

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
