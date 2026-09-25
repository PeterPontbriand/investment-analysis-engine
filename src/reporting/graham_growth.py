"""Investor-facing presentation for the Graham Growth Value strategy."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from src.analysis.shared.financial_resolution import PriceComparison
from src.analysis.strategy.graham_growth.calculation import GrahamGrowthValueResult, GrowthValueInputAssembly
from src.core.analysis_status import CalculationStatus
from src.data.financial.provenance import SourceKind
from src.data.instrument_profile import InstrumentProfile, profile_identity_resolution
from src.data.security_identity import SecurityIdentityResolution, security_identity_payload
from src.reporting.input_provenance import investor_input_lines
from src.reporting.presentation import PresentationMode, format_money, format_number, json_document
from src.reporting.valuation_presentation import (
    analysis_heading,
    common_currency,
    comparison_details,
    comparison_lines,
    comparison_payload,
    diagnostic_lines,
    effective_status_and_reason,
    identity_detail_lines,
    input_line,
    instrument_kind_payload,
    investor_comparison_evidence,
    kind_detail_lines,
    override_warnings,
    profile_diagnostic_lines,
    profile_diagnostic_payloads,
    public_quote_reason,
    quote_payload,
    quote_warnings,
    resolved_input_payload,
    result_heading,
    security_identity_diagnostic_entry,
    source_summary,
    status_label,
    trace_payload,
    validate_margin,
    validate_presentation_as_of,
    validate_ticker,
)

_SCHEMA_VERSION = 5
_GROWTH_LIMITATION = (
    "The Graham growth value is forecast-dependent and sensitive to the "
    "user-supplied growth assumption; it is not an investment recommendation."
)


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
    identity_resolution: SecurityIdentityResolution | None = None
    instrument_profile: InstrumentProfile | None = None
    price_comparison: PriceComparison | None = None

    def __post_init__(self) -> None:
        """Validate presentation-only coherence without performing finance math."""
        if self.identity_resolution is None and self.instrument_profile is not None:
            object.__setattr__(self, "identity_resolution", profile_identity_resolution(self.instrument_profile))
        validate_ticker(self.ticker)
        validate_margin(self.margin_of_safety_percent, self.assembly.current_price)
        if self.price_comparison is not None and self.price_comparison.percent != self.margin_of_safety_percent:
            raise ValueError("Comparison and legacy percentage disagree.")
        validate_presentation_as_of(
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


def growth_with_public_quote_reason(assembly: GrowthValueInputAssembly) -> GrowthValueInputAssembly:
    """Classify optional quote failures while preserving raw resolver trace events."""
    if assembly.quote_status is None:
        return assembly
    return replace(assembly, quote_reason=public_quote_reason(assembly.quote_status))


def render_graham_growth(
    presentation: GrahamGrowthPresentation,
    mode: PresentationMode = PresentationMode.CONCISE,
) -> str:
    """Render a Graham growth-value analysis using the approved investor grammar."""
    if mode is PresentationMode.JSON:
        return json_document(_growth_payload(presentation))

    lines = _growth_concise_lines(presentation)
    if mode is PresentationMode.DETAILS:
        if presentation.result is None:
            status, reason = effective_status_and_reason(
                presentation.assembly.status, presentation.assembly.reason, None, None
            )
            lines = [
                analysis_heading(
                    presentation.ticker,
                    "Graham Growth Value",
                    presentation.as_of,
                    presentation.identity_resolution,
                ),
                f"Status: {status_label(status)}",
                f"Reason: {reason or 'No reason was retained.'}",
            ]
        lines.extend(_growth_detail_lines(presentation))
    elif mode is PresentationMode.DIAGNOSTICS:
        lines.extend(_growth_technical_lines(presentation))
        lines.extend(
            diagnostic_lines(
                presentation.assembly.resolution_trace,
                presentation.assembly.quote_status,
                presentation.assembly.quote_reason,
            )
        )
        lines.extend(profile_diagnostic_lines(presentation.instrument_profile, presentation.identity_resolution))
        lines.extend(comparison_details(presentation.price_comparison))
    return "\n".join(lines)


def _growth_concise_lines(p: GrahamGrowthPresentation) -> list[str]:
    status, reason = effective_status_and_reason(
        p.assembly.status,
        p.assembly.reason,
        p.result.status if p.result else None,
        p.result.reason if p.result else None,
    )
    result_ok = p.result is not None and p.result.status is CalculationStatus.OK

    if result_ok:
        assert p.result is not None
        assert p.result.growth_value is not None
        currency = common_currency(p.assembly.eps)
        lines = [
            result_heading(
                p.ticker,
                "Graham Growth Value",
                p.as_of,
                format_money(p.result.growth_value, currency),
                p.identity_resolution,
            )
        ]
    else:
        lines = [
            analysis_heading(p.ticker, "Graham Growth Value", p.as_of, p.identity_resolution),
            f"Status: {status_label(status)}",
        ]
        if reason:
            lines.append(f"Reason: {reason}")

    growth = p.assembly.expected_growth
    if growth is not None:
        lines.append(f"Expected growth assumption: {format_number(growth.value)} percentage points")

    if result_ok:
        assert p.result is not None
        lines.extend(
            comparison_lines(
                p.assembly.current_price,
                p.margin_of_safety_percent,
                comparison=p.price_comparison,
                reference_value=p.result.growth_value,
                valuation_currency=common_currency(p.assembly.eps),
                reference_label="Graham growth value",
            )
        )

    lines.append("")
    lines.append(f"Sources / freshness: {source_summary((p.assembly.eps, p.assembly.current_aaa_yield))}")
    lines.extend(_growth_warning_lines(p))
    lines.append(f"Limitation: {_GROWTH_LIMITATION}")
    return lines


def _growth_technical_lines(p: GrahamGrowthPresentation) -> list[str]:
    lines = ["", "Details", "-------"]
    lines.extend(identity_detail_lines(p.identity_resolution))
    lines.extend(kind_detail_lines(p.instrument_profile))
    lines.extend(comparison_details(p.price_comparison))
    lines.extend(input_line("EPS", p.assembly.eps))
    lines.extend(input_line("Expected growth", p.assembly.expected_growth))
    lines.extend(input_line("Current AAA yield", p.assembly.current_aaa_yield))
    lines.extend(input_line("Current price", p.assembly.current_price))
    lines.extend(
        [
            "Method assumptions:",
            f"  base_pe: {format_number(p.base_pe)}",
            f"  growth_multiplier: {format_number(p.growth_multiplier)}",
            f"  baseline_aaa_yield: {format_number(p.baseline_aaa_yield)} percentage points",
        ]
    )
    return lines


def _growth_detail_lines(p: GrahamGrowthPresentation) -> list[str]:
    lines = ["", "Details — calculation inputs", "----------------------------"]
    if p.instrument_profile and p.instrument_profile.kind_evidence:
        lines.append(kind_detail_lines(p.instrument_profile)[0])
    for label, value in (
        ("Diluted EPS", p.assembly.eps),
        ("Expected annual growth", p.assembly.expected_growth),
        ("AAA bond yield", p.assembly.current_aaa_yield),
    ):
        lines.extend(investor_input_lines(label, value))
    lines.extend(
        [
            f"Growth Value = EPS × ({format_number(p.base_pe)} + {format_number(p.growth_multiplier)} × growth) "
            f"× {format_number(p.baseline_aaa_yield)} / AAA yield.",
            "Growth and yield use percentage points (5 means 5%). Growth is an assumption, not a forecast guarantee.",
            "Calculated using unrounded inputs; displayed inputs are rounded.",
        ]
    )
    lines.extend(investor_comparison_evidence(p.price_comparison))
    lines.append("Full source fields, assumptions and retrieval history: --diagnostics or --json.")
    return lines


def _growth_warnings(p: GrahamGrowthPresentation) -> list[str]:
    warnings = override_warnings((p.assembly.eps,))
    if (
        p.result is not None
        and p.result.status is CalculationStatus.OK
        and p.result.growth_value is not None
        and p.result.growth_value <= 0
    ):
        warnings.append("The Graham growth value is non-positive; percentage price comparison is omitted.")
    aaa_yield = p.assembly.current_aaa_yield
    if aaa_yield is not None and aaa_yield.source_kind is SourceKind.OVERRIDE:
        warnings.append("AAA yield is user-supplied rather than provider-verified.")
    warnings.extend(override_warnings((p.assembly.current_price,)))
    warnings.extend(quote_warnings(p.assembly.quote_status, p.assembly.quote_reason))
    return warnings


def _growth_warning_lines(p: GrahamGrowthPresentation) -> list[str]:
    return [f"Warning: {warning}" for warning in _growth_warnings(p)]


def _growth_payload(p: GrahamGrowthPresentation) -> dict[str, Any]:
    status, reason = effective_status_and_reason(
        p.assembly.status,
        p.assembly.reason,
        p.result.status if p.result else None,
        p.result.reason if p.result else None,
    )
    result_value = p.result.growth_value if p.result is not None and p.result.status is CalculationStatus.OK else None
    return {
        "schema_version": _SCHEMA_VERSION,
        "price_comparison": comparison_payload(p.price_comparison),
        "analysis": "graham_growth_value",
        "ticker": p.ticker.upper(),
        "security_identity": security_identity_payload(p.ticker, p.identity_resolution),
        "instrument_kind": instrument_kind_payload(p.instrument_profile),
        "method": "graham_growth_value",
        "as_of": None if p.as_of is None else p.as_of.isoformat(),
        "status": status.value,
        "reason": reason,
        "result": {
            "growth_value": result_value,
            "margin_of_safety_percent": p.margin_of_safety_percent,
        },
        "inputs": {
            "eps": resolved_input_payload(p.assembly.eps),
            "expected_growth": resolved_input_payload(p.assembly.expected_growth),
            "current_aaa_yield": resolved_input_payload(p.assembly.current_aaa_yield),
            "current_price": resolved_input_payload(p.assembly.current_price),
        },
        "method_assumptions": {
            "base_pe": p.base_pe,
            "growth_multiplier": p.growth_multiplier,
            "baseline_aaa_yield": p.baseline_aaa_yield,
        },
        "quote": quote_payload(
            p.assembly.current_price,
            p.assembly.quote_status,
            p.assembly.quote_reason,
        ),
        "warnings": _growth_warnings(p),
        "limitations": [_GROWTH_LIMITATION],
        "diagnostics": [
            *trace_payload(p.assembly.resolution_trace),
            *profile_diagnostic_payloads(p.instrument_profile),
            *security_identity_diagnostic_entry(p.instrument_profile, p.identity_resolution),
        ],
    }


__all__ = [
    "GrahamGrowthPresentation",
    "growth_with_public_quote_reason",
    "render_graham_growth",
]
