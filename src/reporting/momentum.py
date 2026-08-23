"""Investor-facing presentation for SMA momentum analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.analysis.momentum.momentum_analyzer import MomentumConfig, MomentumMetrics
from src.core.constants import TrendStatus
from src.reporting.presentation import (
    PresentationMode,
    ResolutionDiagnostic,
    diagnostic_payload,
    format_datetime,
    format_money,
    format_number,
    json_document,
)

_SCHEMA_VERSION = 1
_LIMITATION = (
    "SMA momentum describes recent price trend; it is not a valuation, "
    "fundamental-quality conclusion, or investment recommendation."
)


@dataclass(frozen=True)
class MomentumPresentation:
    """Presentation context for one Momentum analysis."""

    metrics: MomentumMetrics
    config: MomentumConfig
    source_label: str | None = None
    data_as_of: datetime | None = None
    currency: str | None = None
    warnings: tuple[str, ...] = ()
    diagnostics: tuple[ResolutionDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        """Validate retained market-data timing without inventing missing metadata."""
        if self.data_as_of is not None and (
            self.data_as_of.tzinfo is None or self.data_as_of.tzinfo.utcoffset(self.data_as_of) is None
        ):
            msg = "data_as_of must be timezone-aware when provided."
            raise ValueError(msg)


def render_momentum(
    presentation: MomentumPresentation,
    mode: PresentationMode = PresentationMode.CONCISE,
) -> str:
    """Render Momentum using the same terminal grammar as Graham."""
    if mode is PresentationMode.JSON:
        return json_document(_payload(presentation))

    lines = _concise_lines(presentation)
    if mode is PresentationMode.DETAILS:
        lines.extend(_detail_lines(presentation))
    elif mode is PresentationMode.DIAGNOSTICS:
        lines.extend(_diagnostic_lines(presentation))
    return "\n".join(lines)


def _concise_lines(p: MomentumPresentation) -> list[str]:
    metrics = p.metrics
    lines = [
        f"{metrics.ticker.upper()} — Momentum",
        f"As of: {format_datetime(p.data_as_of)}",
        f"Status: {metrics.status.display_name(locale='en')}",
        f"Current price: {format_money(metrics.current_price, p.currency)}",
        f"Trend: {_trend_interpretation(metrics.status, p.config)}",
    ]
    crossover = _crossover_interpretation(metrics.crossover_signal)
    if crossover is not None:
        lines.append(f"Latest signal: {crossover}")

    source = p.source_label or "not retained by current Momentum result"
    freshness = format_datetime(p.data_as_of)
    lines.append(f"Sources / freshness: {source}; data as of {freshness}")

    warnings = list(p.warnings)
    if metrics.short_sma_val is None or metrics.long_sma_val is None:
        warnings.append("One or more moving-average values are unavailable; trend status is unknown.")
    if p.source_label is None or p.data_as_of is None:
        warnings.append("Momentum source/freshness metadata is incomplete; the presenter will not invent it.")
    if p.currency is None:
        warnings.append("Momentum price currency is not retained by the current result.")
    lines.extend(f"Warning: {warning}" for warning in warnings)
    lines.append(f"Limitation: {_LIMITATION}")
    return lines


def _detail_lines(p: MomentumPresentation) -> list[str]:
    metrics = p.metrics
    return [
        "",
        "Details",
        "-------",
        f"Short SMA window: {p.config.short_window}",
        f"Long SMA window: {p.config.long_window}",
        f"Short SMA value: {_optional_metric(metrics.short_sma_val, decimals=6)}",
        f"Long SMA value: {_optional_metric(metrics.long_sma_val, decimals=6)}",
        f"Raw crossover signal: {_optional_metric(metrics.crossover_signal, decimals=0)}",
        f"Analysis timestamp: {format_datetime(metrics.timestamp)}",
        f"Data source: {p.source_label or 'unavailable'}",
        f"Data observation time: {format_datetime(p.data_as_of)}",
        f"Currency: {p.currency or 'unavailable'}",
    ]


def _diagnostic_lines(p: MomentumPresentation) -> list[str]:
    lines = ["", "Diagnostics", "-----------"]
    if not p.diagnostics:
        lines.append(
            "No execution trace was retained for this run; the presenter will not infer provider or cache behavior."
        )
        return lines
    for item in p.diagnostics:
        lines.append(f"{item.field_name}: {item.stage} -> {item.outcome} — {item.message}")
    return lines


def _trend_interpretation(status: TrendStatus, config: MomentumConfig) -> str:
    if status is TrendStatus.BULLISH:
        return (
            f"the {config.short_window}-period average is above the "
            f"{config.long_window}-period average, indicating bullish price momentum"
        )
    if status is TrendStatus.BEARISH:
        return (
            f"the {config.short_window}-period average is at or below the "
            f"{config.long_window}-period average, indicating bearish price momentum"
        )
    return "the configured moving averages do not yet support a reliable trend classification"


def _crossover_interpretation(signal: float | None) -> str | None:
    if signal is None:
        return None
    if signal > 0:
        return "new bullish crossover detected on the latest observation"
    if signal < 0:
        return "new bearish crossover detected on the latest observation"
    return None


def _optional_metric(value: float | None, *, decimals: int) -> str:
    """Format an optional Momentum metric without exposing non-finite sentinels."""
    return "unavailable" if value is None else format_number(value, decimals=decimals)


def _payload(p: MomentumPresentation) -> dict[str, Any]:
    metrics = p.metrics
    warnings = list(p.warnings)
    if metrics.short_sma_val is None or metrics.long_sma_val is None:
        warnings.append("One or more moving-average values are unavailable; trend status is unknown.")
    if p.source_label is None or p.data_as_of is None:
        warnings.append("Momentum source/freshness metadata is incomplete; the presenter will not invent it.")
    if p.currency is None:
        warnings.append("Momentum price currency is not retained by the current result.")

    return {
        "schema_version": _SCHEMA_VERSION,
        "analysis": "momentum",
        "ticker": metrics.ticker.upper(),
        "method": "sma_crossover",
        "as_of": p.data_as_of.isoformat() if p.data_as_of else None,
        "analysis_timestamp": metrics.timestamp.isoformat(),
        "status": metrics.status.value,
        "result": {
            "current_price": metrics.current_price,
            "short_sma": metrics.short_sma_val,
            "long_sma": metrics.long_sma_val,
            "crossover_signal": metrics.crossover_signal,
        },
        "parameters": {
            "short_window": p.config.short_window,
            "long_window": p.config.long_window,
        },
        "source": {
            "provider": p.source_label,
            "data_as_of": p.data_as_of.isoformat() if p.data_as_of else None,
            "currency": p.currency,
        },
        "warnings": warnings,
        "limitations": [_LIMITATION],
        "diagnostics": [diagnostic_payload(item) for item in p.diagnostics],
    }
