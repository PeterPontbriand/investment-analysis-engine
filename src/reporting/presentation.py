"""Shared presentation vocabulary for direct investor-facing analyses.

This module intentionally contains only rendering vocabulary and small formatting
helpers. Strategy result models remain strategy-specific.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, time
from enum import StrEnum
from typing import Any, Final

from src.core.analysis_status import CalculationStatus


class PresentationMode(StrEnum):
    """Progressive-disclosure modes shared by direct analysis commands."""

    CONCISE = "concise"
    DETAILS = "details"
    DIAGNOSTICS = "diagnostics"
    JSON = "json"


# ---------------------------------------------------------------------------
# Shared vocabulary
# ---------------------------------------------------------------------------

STATUS_LABELS: Final[dict[CalculationStatus, str]] = {
    CalculationStatus.OK: "ok",
    CalculationStatus.NOT_APPLICABLE: "not applicable",
    CalculationStatus.INVALID_INPUT: "invalid input",
    CalculationStatus.INPUT_UNAVAILABLE: "input unavailable",
    CalculationStatus.PROVIDER_ERROR: "provider error",
}


def humanized_status(status: CalculationStatus | None) -> str:
    """Return a reader-friendly phrase for a shared calculation status."""
    if status is None:
        return "unavailable"
    return STATUS_LABELS.get(status, status.value)


# ---------------------------------------------------------------------------
# Shared display-label helpers
# ---------------------------------------------------------------------------

# Explicit human-readable display labels for known provider identifiers.
# Unknown provider identifiers fall through to their raw form so that
# test fixtures and future providers remain visible in diagnostics without
# requiring a prior mapping entry.  A future localisation layer can replace
# or parameterise these values without altering the machine identifiers
# themselves.
PROVIDER_DISPLAY_NAMES: Final[dict[str, str]] = {
    "sec_edgar": "SEC EDGAR",
    "yfinance": "Yahoo Finance",
    "massive": "Massive",
}


def provider_display_name(provider_id: str | None) -> str:
    """Return an explicit human-readable display label for a provider identifier.

    Args:
        provider_id: Machine-readable provider identifier (e.g. ``"sec_edgar"``).

    Returns:
        The corresponding display label from :data:`PROVIDER_DISPLAY_NAMES`,
        or the raw identifier when no explicit mapping exists.  Returns
        ``"unavailable"`` when *provider_id* is ``None``.
    """
    if provider_id is None:
        return "unavailable"
    return PROVIDER_DISPLAY_NAMES.get(provider_id, provider_id)


# ---------------------------------------------------------------------------
# Shared formatting helpers
# ---------------------------------------------------------------------------


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
    """Format an analysis boundary without exposing end-of-day implementation detail."""
    if value is None:
        return "current"
    if value.timetz().replace(tzinfo=None) == time.max:
        return value.date().isoformat()
    return format_utc_minute(value)


def format_date(value: datetime | None) -> str:
    """Format optional reporting-period metadata as a calendar date."""
    return "unavailable" if value is None else value.date().isoformat()


def format_utc_minute(value: datetime | None) -> str:
    """Format an optional event timestamp at investor-useful UTC minute precision."""
    if value is None:
        return "unavailable"
    utc_value = value.astimezone(UTC)
    return utc_value.strftime("%Y-%m-%d %H:%M UTC")


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
