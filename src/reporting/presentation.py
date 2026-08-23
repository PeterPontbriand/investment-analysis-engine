"""Shared presentation vocabulary for direct investor-facing analyses.

This module intentionally contains only rendering vocabulary and small formatting
helpers. Strategy result models remain strategy-specific.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class PresentationMode(StrEnum):
    """Progressive-disclosure modes shared by direct analysis commands."""

    CONCISE = "concise"
    DETAILS = "details"
    DIAGNOSTICS = "diagnostics"
    JSON = "json"


@dataclass(frozen=True)
class ResolutionDiagnostic:
    """One retained software-resolution diagnostic for presentation.

    Presenters never invent cache misses, provider attempts, or fallback steps.
    Callers may supply diagnostics only when the execution layer actually
    retained them.
    """

    field_name: str
    stage: str
    outcome: str
    message: str

    def __post_init__(self) -> None:
        """Require non-empty diagnostic fields."""
        for name, value in (
            ("field_name", self.field_name),
            ("stage", self.stage),
            ("outcome", self.outcome),
            ("message", self.message),
        ):
            if not value.strip():
                msg = f"{name} must be a non-empty string."
                raise ValueError(msg)


def format_as_of(value: datetime | None) -> str:
    """Format a requested analysis boundary; None means a current analysis."""
    return "current" if value is None else value.isoformat()


def format_datetime(value: datetime | None) -> str:
    """Format optional retained metadata without pretending missing means current."""
    return "unavailable" if value is None else value.isoformat()


def format_number(value: float, *, decimals: int = 2) -> str:
    """Format a finite numeric value for terminal display."""
    if not math.isfinite(value):
        msg = f"Cannot present non-finite value {value!r}."
        raise ValueError(msg)
    return f"{value:,.{decimals}f}"


def format_money(value: float, currency: str | None) -> str:
    """Format a monetary value without guessing an absent currency."""
    number = format_number(value)
    if currency:
        return f"{number} {currency}"
    return f"{number} (currency unspecified)"


def json_document(payload: dict[str, Any]) -> str:
    """Serialize a stable human-readable JSON document."""
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)


def diagnostic_payload(diagnostic: ResolutionDiagnostic) -> dict[str, str]:
    """Convert a retained diagnostic to JSON-ready data."""
    return asdict(diagnostic)
