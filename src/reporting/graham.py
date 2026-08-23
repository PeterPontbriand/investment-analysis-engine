"""Investor-facing presentation for the two Graham valuation methods."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.analysis.graham_value.models import (
    CalculationStatus,
    GrahamGrowthValueResult,
    GrahamNumberResult,
)
from src.analysis.graham_value.provenance import ResolvedInput, SourceKind
from src.analysis.graham_value.resolution_trace import ResolutionTrace
from src.analysis.graham_value.resolver import (
    GrahamNumberInputAssembly,
    GrowthValueInputAssembly,
)
from src.reporting.presentation import (
    PresentationMode,
    format_as_of,
    format_datetime,
    format_money,
    format_number,
    json_document,
)

_SCHEMA_VERSION = 1
_NUMBER_LIMITATION = (
    "The Graham Number is a maximum indicated price / screening ceiling, "
    "not a complete intrinsic-value conclusion or investment recommendation."
)
_GROWTH_LIMITATION = (
    "The Graham growth value is forecast-dependent and sensitive to the "
    "user-supplied growth assumption; it is not an investment recommendation."
)


@dataclass(frozen=True)
class GrahamNumberPresentation:
    """Presentation context for one completed/attempted Graham Number analysis."""

    ticker: str
    assembly: GrahamNumberInputAssembly
    result: GrahamNumberResult | None
    as_of: datetime | None = None
    margin_of_safety_percent: float | None = None

    def __post_init__(self) -> None:
        """Validate presentation-only coherence without performing finance math."""
        _validate_ticker(self.ticker)
        _validate_margin(self.margin_of_safety_percent, self.assembly.current_price)
        _validate_presentation_as_of(self.as_of, self.assembly.eps, self.assembly.bvps, self.assembly.current_price)
        if (
            self.result is not None
            and self.result.status is CalculationStatus.OK
            and self.assembly.status is not CalculationStatus.OK
        ):
            msg = "An OK Graham Number result cannot accompany a non-OK input assembly."
            raise ValueError(msg)


@dataclass(frozen=True)
class GrahamGrowthPresentation:
    """Presentation context for one completed/attempted Graham growth analysis."""

    ticker: str
    assembly: GrowthValueInputAssembly
    result: GrahamGrowthValueResult | None
    base_pe: float
    growth_multiplier: float
    baseline_aaa_yield: float
    as_of: datetime | None = None
    margin_of_safety_percent: float | None = None

    def __post_init__(self) -> None:
        """Validate presentation-only coherence without performing finance math."""
        _validate_ticker(self.ticker)
        _validate_margin(self.margin_of_safety_percent, self.assembly.current_price)
        _validate_presentation_as_of(
            self.as_of,
            self.assembly.eps,
            self.assembly.expected_growth,
            self.assembly.current_aaa_yield,
            self.assembly.current_price,
        )
        for name, value in (
            ("base_pe", self.base_pe),
            ("growth_multiplier", self.growth_multiplier),
            ("baseline_aaa_yield", self.baseline_aaa_yield),
        ):
            if not math.isfinite(value):
                msg = f"{name} must be finite for presentation (received {value!r})."
                raise ValueError(msg)
        if (
            self.result is not None
            and self.result.status is CalculationStatus.OK
            and self.assembly.status is not CalculationStatus.OK
        ):
            msg = "An OK Graham growth result cannot accompany a non-OK input assembly."
            raise ValueError(msg)


def render_graham_number(
    presentation: GrahamNumberPresentation,
    mode: PresentationMode = PresentationMode.CONCISE,
) -> str:
    """Render a Graham Number analysis using the approved investor grammar."""
    if mode is PresentationMode.JSON:
        return json_document(_number_payload(presentation))

    lines = _number_concise_lines(presentation)
    if mode is PresentationMode.DETAILS:
        lines.extend(_number_detail_lines(presentation))
    elif mode is PresentationMode.DIAGNOSTICS:
        lines.extend(_diagnostic_lines(presentation.assembly.resolution_trace, presentation.assembly))
    return "\n".join(lines)


def render_graham_growth(
    presentation: GrahamGrowthPresentation,
    mode: PresentationMode = PresentationMode.CONCISE,
) -> str:
    """Render a Graham growth-value analysis using the approved investor grammar."""
    if mode is PresentationMode.JSON:
        return json_document(_growth_payload(presentation))

    lines = _growth_concise_lines(presentation)
    if mode is PresentationMode.DETAILS:
        lines.extend(_growth_detail_lines(presentation))
    elif mode is PresentationMode.DIAGNOSTICS:
        lines.extend(_diagnostic_lines(presentation.assembly.resolution_trace, presentation.assembly))
    return "\n".join(lines)


def _number_concise_lines(p: GrahamNumberPresentation) -> list[str]:
    status, reason = _effective_status_and_reason(p.assembly.status, p.assembly.reason, p.result)
    lines = [
        f"{p.ticker.upper()} — Graham Number",
        f"As of: {format_as_of(p.as_of)}",
        f"Status: {status.value}",
    ]

    if p.result is not None and p.result.status is CalculationStatus.OK:
        assert p.result.maximum_indicated_price is not None
        currency = _common_currency(p.assembly.eps, p.assembly.bvps)
        lines.append(f"Maximum indicated price: {format_money(p.result.maximum_indicated_price, currency)}")
        lines.extend(_comparison_lines(p.assembly.current_price, p.margin_of_safety_percent))
    elif reason:
        lines.append(f"Reason: {reason}")

    lines.extend(_headline_input_lines(p.assembly.eps, p.assembly.bvps))
    lines.append(f"Sources / freshness: {_source_summary((p.assembly.eps, p.assembly.bvps))}")
    lines.extend(_number_warning_lines(p))
    lines.append(f"Limitation: {_NUMBER_LIMITATION}")
    return lines


def _growth_concise_lines(p: GrahamGrowthPresentation) -> list[str]:
    status, reason = _effective_status_and_reason(p.assembly.status, p.assembly.reason, p.result)
    lines = [
        f"{p.ticker.upper()} — Graham Growth Value",
        f"As of: {format_as_of(p.as_of)}",
        f"Status: {status.value}",
    ]

    growth = p.assembly.expected_growth
    if growth is not None:
        lines.append(f"USER ASSUMPTION — expected growth: {format_number(growth.value)} percentage points")

    if p.result is not None and p.result.status is CalculationStatus.OK:
        assert p.result.growth_value is not None
        currency = _common_currency(p.assembly.eps, p.assembly.current_price)
        lines.append(f"Forecast-dependent growth value: {format_money(p.result.growth_value, currency)}")
        lines.extend(_comparison_lines(p.assembly.current_price, p.margin_of_safety_percent))
    elif reason:
        lines.append(f"Reason: {reason}")

    lines.append(f"Sources / freshness: {_source_summary((p.assembly.eps, p.assembly.current_aaa_yield))}")
    lines.extend(_growth_warning_lines(p))
    lines.append(f"Limitation: {_GROWTH_LIMITATION}")
    return lines


def _number_detail_lines(p: GrahamNumberPresentation) -> list[str]:
    lines = ["", "Details", "-------"]
    lines.extend(_input_detail_lines("EPS", p.assembly.eps))
    lines.extend(_input_detail_lines("BVPS", p.assembly.bvps))
    lines.extend(_input_detail_lines("Current price", p.assembly.current_price))
    return lines


def _growth_detail_lines(p: GrahamGrowthPresentation) -> list[str]:
    lines = ["", "Details", "-------"]
    lines.extend(_input_detail_lines("EPS", p.assembly.eps))
    lines.extend(_input_detail_lines("Expected growth", p.assembly.expected_growth))
    lines.extend(_input_detail_lines("Current AAA yield", p.assembly.current_aaa_yield))
    lines.extend(_input_detail_lines("Current price", p.assembly.current_price))
    lines.extend(
        [
            "Method assumptions:",
            f"  base_pe: {format_number(p.base_pe)}",
            f"  growth_multiplier: {format_number(p.growth_multiplier)}",
            f"  baseline_aaa_yield: {format_number(p.baseline_aaa_yield)} percentage points",
        ]
    )
    return lines


def _input_detail_lines(label: str, value: ResolvedInput | None) -> list[str]:
    if value is None:
        return [f"{label}: unavailable"]

    source = _source_label(value)
    lines = [
        f"{label}: {format_number(value.value, decimals=6)}",
        f"  basis: {value.basis or 'unspecified'}",
        f"  units: {value.units or 'unspecified'}",
        f"  currency: {value.currency or 'n/a'}",
        f"  source: {source}",
        f"  provider: {value.provider_id or 'n/a'}",
        f"  provider field: {value.provider_field or 'n/a'}",
        f"  period start: {format_datetime(value.observation_period_start)}",
        f"  period end: {format_datetime(value.observation_period_end)}",
        f"  observed at: {format_datetime(value.observed_at)}",
        f"  available at: {format_datetime(value.available_at)}",
        f"  retrieved at: {format_datetime(value.retrieved_at)}",
        f"  resolved at: {format_datetime(value.resolved_at)}",
    ]
    if value.notes:
        lines.append(f"  notes: {'; '.join(value.notes)}")
    if value.lineage is not None:
        lines.append(f"  derivation: {value.lineage.transformation}")
        for index, component in enumerate(value.lineage.components, start=1):
            lines.extend(
                [
                    f"  component {index}:",
                    f"    field name: {component.field_name}",
                    f"    value: {format_number(component.value, decimals=6)}",
                    f"    source: {_source_label(component)}",
                    f"    provider: {component.provider_id or 'n/a'}",
                    f"    provider field: {component.provider_field or 'n/a'}",
                    f"    basis: {component.basis or 'unspecified'}",
                    f"    period end: {format_datetime(component.observation_period_end)}",
                    f"    available at: {format_datetime(component.available_at)}",
                ]
            )
    return lines


def _diagnostic_lines(
    trace: ResolutionTrace,
    assembly: GrahamNumberInputAssembly | GrowthValueInputAssembly,
) -> list[str]:
    lines = ["", "Diagnostics", "-----------"]
    if trace.events:
        lines.extend(
            (f"{event.field_name}: {event.stage.value} -> {event.outcome.value} — {event.message}")
            for event in trace.events
        )
    else:
        lines.append(
            "No resolver execution trace was retained for this run; "
            "the presenter will not infer cache or provider behavior."
        )
    if assembly.quote_status is not None and not any(event.field_name == "current_price" for event in trace.events):
        lines.append(f"current_price: {assembly.quote_status.value} — {assembly.quote_reason or 'no reason retained'}")
    return lines


def _headline_input_lines(eps: ResolvedInput | None, bvps: ResolvedInput | None) -> list[str]:
    lines: list[str] = []
    if eps is not None:
        lines.append(f"EPS ({eps.basis or 'unspecified basis'}): {format_money(eps.value, eps.currency)}")
    if bvps is not None:
        lines.append(f"Book value per common share: {format_money(bvps.value, bvps.currency)}")
    return lines


def _comparison_lines(
    current_price: ResolvedInput | None,
    margin_of_safety_percent: float | None,
) -> list[str]:
    if current_price is None:
        return ["Current price: unavailable", "Price comparison: unavailable (no current quote)"]

    lines = [f"Current price: {format_money(current_price.value, current_price.currency)}"]
    if margin_of_safety_percent is None:
        lines.append("Price comparison: unavailable")
    elif margin_of_safety_percent >= 0:
        lines.append(f"Price relationship: {format_number(margin_of_safety_percent)}% below the method reference value")
    else:
        lines.append(
            f"Price relationship: {format_number(abs(margin_of_safety_percent))}% above the method reference value"
        )
    return lines


def _number_warnings(p: GrahamNumberPresentation) -> list[str]:
    warnings = _override_warnings((p.assembly.eps, p.assembly.bvps))
    warnings.extend(_quote_warnings(p.assembly.quote_status, p.assembly.quote_reason))
    return warnings


def _number_warning_lines(p: GrahamNumberPresentation) -> list[str]:
    return [f"Warning: {warning}" for warning in _number_warnings(p)]


def _growth_warnings(p: GrahamGrowthPresentation) -> list[str]:
    warnings = _override_warnings((p.assembly.eps, p.assembly.expected_growth, p.assembly.current_aaa_yield))
    warnings.extend(_quote_warnings(p.assembly.quote_status, p.assembly.quote_reason))
    return warnings


def _growth_warning_lines(p: GrahamGrowthPresentation) -> list[str]:
    return [f"Warning: {warning}" for warning in _growth_warnings(p)]


def _override_warnings(inputs: tuple[ResolvedInput | None, ...]) -> list[str]:
    warnings: list[str] = []
    for item in inputs:
        if item is not None and item.source_kind is SourceKind.OVERRIDE:
            warnings.append(f"{item.field_name} is a user override, not provider-verified data.")
    return warnings


def _quote_warnings(
    status: CalculationStatus | None,
    reason: str | None,
) -> list[str]:
    if status is None:
        return []
    return [
        f"Current quote unavailable; comparison fields are omitted ({status.value}: {reason or 'no reason retained'})."
    ]


def _source_summary(inputs: tuple[ResolvedInput | None, ...]) -> str:
    parts: list[str] = []
    for item in inputs:
        if item is None:
            continue
        freshness = item.available_at or item.observed_at or item.observation_period_end
        parts.append(f"{item.field_name}={_source_label(item)} ({format_datetime(freshness)})")
    return "; ".join(parts) if parts else "unavailable"


def _source_label(value: ResolvedInput) -> str:
    if value.source_kind is SourceKind.OVERRIDE:
        return "user override"
    if value.source_kind is SourceKind.CACHE:
        origin = value.origin_source_kind.value if value.origin_source_kind is not None else "unknown"
        provider = f", provider={value.provider_id}" if value.provider_id else ""
        return f"cache (original={origin}{provider})"
    if value.source_kind is SourceKind.DERIVED:
        providers = (
            sorted({component.provider_id for component in value.lineage.components if component.provider_id})
            if value.lineage is not None
            else []
        )
        provider_text = ",".join(providers) if providers else value.provider_id or "retained lineage"
        return f"derived ({provider_text})"
    return f"provider ({value.provider_id or 'unspecified'})"


def _resolved_input_payload(value: ResolvedInput | None) -> dict[str, Any] | None:
    if value is None:
        return None
    payload: dict[str, Any] = {
        "field_name": value.field_name,
        "value": value.value,
        "source_kind": value.source_kind.value,
        "origin_source_kind": (value.origin_source_kind.value if value.origin_source_kind is not None else None),
        "basis": value.basis,
        "units": value.units,
        "currency": value.currency,
        "provider_id": value.provider_id,
        "provider_field": value.provider_field,
        "observation_period_start": _json_datetime(value.observation_period_start),
        "observation_period_end": _json_datetime(value.observation_period_end),
        "observed_at": _json_datetime(value.observed_at),
        "available_at": _json_datetime(value.available_at),
        "as_of": _json_datetime(value.as_of),
        "retrieved_at": _json_datetime(value.retrieved_at),
        "resolved_at": _json_datetime(value.resolved_at),
        "cache_schema_version": value.cache_schema_version,
        "notes": list(value.notes),
        "lineage": None,
    }
    if value.lineage is not None:
        payload["lineage"] = {
            "transformation": value.lineage.transformation,
            "components": [_resolved_input_payload(component) for component in value.lineage.components],
        }
    return payload


def _number_payload(p: GrahamNumberPresentation) -> dict[str, Any]:
    status, reason = _effective_status_and_reason(p.assembly.status, p.assembly.reason, p.result)
    result_value = (
        p.result.maximum_indicated_price if p.result is not None and p.result.status is CalculationStatus.OK else None
    )
    return {
        "schema_version": _SCHEMA_VERSION,
        "analysis": "graham",
        "ticker": p.ticker.upper(),
        "method": "graham_number",
        "as_of": _json_datetime(p.as_of),
        "status": status.value,
        "reason": reason,
        "result": {
            "maximum_indicated_price": result_value,
            "margin_of_safety_percent": p.margin_of_safety_percent,
        },
        "inputs": {
            "eps": _resolved_input_payload(p.assembly.eps),
            "bvps": _resolved_input_payload(p.assembly.bvps),
            "current_price": _resolved_input_payload(p.assembly.current_price),
        },
        "quote": _quote_payload(
            p.assembly.current_price,
            p.assembly.quote_status,
            p.assembly.quote_reason,
        ),
        "warnings": _number_warnings(p),
        "limitations": [_NUMBER_LIMITATION],
        "diagnostics": _trace_payload(p.assembly.resolution_trace),
    }


def _growth_payload(p: GrahamGrowthPresentation) -> dict[str, Any]:
    status, reason = _effective_status_and_reason(p.assembly.status, p.assembly.reason, p.result)
    result_value = p.result.growth_value if p.result is not None and p.result.status is CalculationStatus.OK else None
    return {
        "schema_version": _SCHEMA_VERSION,
        "analysis": "graham",
        "ticker": p.ticker.upper(),
        "method": "graham_growth_value",
        "as_of": _json_datetime(p.as_of),
        "status": status.value,
        "reason": reason,
        "result": {
            "growth_value": result_value,
            "margin_of_safety_percent": p.margin_of_safety_percent,
        },
        "inputs": {
            "eps": _resolved_input_payload(p.assembly.eps),
            "expected_growth": _resolved_input_payload(p.assembly.expected_growth),
            "current_aaa_yield": _resolved_input_payload(p.assembly.current_aaa_yield),
            "current_price": _resolved_input_payload(p.assembly.current_price),
        },
        "method_assumptions": {
            "base_pe": p.base_pe,
            "growth_multiplier": p.growth_multiplier,
            "baseline_aaa_yield": p.baseline_aaa_yield,
        },
        "quote": _quote_payload(
            p.assembly.current_price,
            p.assembly.quote_status,
            p.assembly.quote_reason,
        ),
        "warnings": _growth_warnings(p),
        "limitations": [_GROWTH_LIMITATION],
        "diagnostics": _trace_payload(p.assembly.resolution_trace),
    }


def _trace_payload(trace: ResolutionTrace) -> list[dict[str, str]]:
    """Convert immutable resolver trace events to the JSON diagnostics shape."""
    return [
        {
            "field_name": event.field_name,
            "stage": event.stage.value,
            "outcome": event.outcome.value,
            "message": event.message,
        }
        for event in trace.events
    ]


def _quote_payload(
    current_price: ResolvedInput | None,
    status: CalculationStatus | None,
    reason: str | None,
) -> dict[str, str | None]:
    if status is not None:
        return {"status": status.value, "reason": reason}
    if current_price is not None:
        return {"status": "ok", "reason": None}
    return {"status": "not_attempted", "reason": None}


def _effective_status_and_reason(
    assembly_status: CalculationStatus,
    assembly_reason: str | None,
    result: GrahamNumberResult | GrahamGrowthValueResult | None,
) -> tuple[CalculationStatus, str | None]:
    if assembly_status is not CalculationStatus.OK:
        return assembly_status, assembly_reason
    if result is None:
        return CalculationStatus.INPUT_UNAVAILABLE, "Calculation result was not supplied to the presenter."
    return result.status, result.reason


def _common_currency(*inputs: ResolvedInput | None) -> str | None:
    currencies = {item.currency for item in inputs if item is not None and item.currency}
    if len(currencies) == 1:
        return next(iter(currencies))
    return None


def _validate_presentation_as_of(as_of: datetime | None, *inputs: ResolvedInput | None) -> None:
    """Require the displayed analysis boundary to match every resolved method input."""
    if as_of is not None and (as_of.tzinfo is None or as_of.tzinfo.utcoffset(as_of) is None):
        msg = "Presentation as_of must be timezone-aware when provided."
        raise ValueError(msg)

    for resolved_input in inputs:
        if resolved_input is not None and resolved_input.as_of != as_of:
            msg = (
                f"Presentation as_of ({as_of!r}) does not match resolved "
                f"{resolved_input.field_name} as_of ({resolved_input.as_of!r})."
            )
            raise ValueError(msg)


def _validate_ticker(ticker: str) -> None:
    if not ticker.strip():
        msg = "ticker must be a non-empty string."
        raise ValueError(msg)


def _validate_margin(
    margin_of_safety_percent: float | None,
    current_price: ResolvedInput | None,
) -> None:
    if margin_of_safety_percent is None:
        return
    if current_price is None:
        msg = "margin_of_safety_percent requires a resolved current price."
        raise ValueError(msg)
    if not math.isfinite(margin_of_safety_percent):
        msg = "margin_of_safety_percent must be finite."
        raise ValueError(msg)


def _json_datetime(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()
