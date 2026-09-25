"""Investor-facing presentation for the Graham Number strategy."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from src.analysis.shared.financial_resolution import PriceComparison
from src.analysis.strategy.graham_number.calculation import GrahamNumberInputAssembly, GrahamNumberResult
from src.core.analysis_status import CalculationStatus
from src.data.financial.provenance import ResolvedInput
from src.data.financial.resolution_trace import ResolutionOutcome
from src.data.instrument_profile import InstrumentProfile, profile_identity_resolution
from src.data.security_identity import SecurityIdentityResolution, security_identity_payload
from src.reporting.input_provenance import investor_input_lines
from src.reporting.presentation import PresentationMode, format_money, json_document
from src.reporting.valuation_presentation import (
    analysis_heading,
    basis_display_name,
    common_currency,
    comparison_details,
    comparison_lines,
    comparison_payload,
    diagnostic_lines,
    display_basis,
    effective_status_and_reason,
    eps_basis_label,
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
_NUMBER_LIMITATION = (
    "The Graham Number is a maximum indicated price / screening ceiling, "
    "not a complete intrinsic-value conclusion or investment recommendation."
)


@dataclass(frozen=True)
class GrahamNumberPresentation:
    """Presentation context for one completed/attempted Graham Number analysis."""

    ticker: str
    assembly: GrahamNumberInputAssembly
    result: GrahamNumberResult | None
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
        validate_presentation_as_of(self.as_of, self.assembly.eps, self.assembly.bvps, self.assembly.current_price)
        if (
            self.result is not None
            and self.result.status is CalculationStatus.OK
            and self.assembly.status is not CalculationStatus.OK
        ):
            msg = "An OK Graham Number result cannot accompany a non-OK input assembly."
            raise ValueError(msg)


def number_with_public_quote_reason(assembly: GrahamNumberInputAssembly) -> GrahamNumberInputAssembly:
    """Classify optional quote failures while preserving raw resolver trace events."""
    if assembly.quote_status is None:
        return assembly
    return replace(assembly, quote_reason=public_quote_reason(assembly.quote_status))


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
        lines.extend(_number_technical_lines(presentation))
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


def _number_concise_lines(p: GrahamNumberPresentation) -> list[str]:
    status, reason = effective_status_and_reason(
        p.assembly.status,
        p.assembly.reason,
        p.result.status if p.result else None,
        p.result.reason if p.result else None,
    )
    result_ok = p.result is not None and p.result.status is CalculationStatus.OK

    if result_ok:
        assert p.result is not None
        assert p.result.maximum_indicated_price is not None
        currency = common_currency(p.assembly.eps, p.assembly.bvps)
        heading = result_heading(
            p.ticker,
            "Graham Number (maximum indicated price)",
            p.as_of,
            format_money(p.result.maximum_indicated_price, currency),
            p.identity_resolution,
        )
        lines = [heading]
        lines.extend(
            comparison_lines(
                p.assembly.current_price,
                p.margin_of_safety_percent,
                comparison=p.price_comparison,
                reference_value=p.result.maximum_indicated_price,
                valuation_currency=currency,
                reference_label="Graham Number",
            )
        )
    else:
        lines = [
            analysis_heading(p.ticker, "Graham Number", p.as_of, p.identity_resolution),
        ]
        if p.result is None:
            lines.append("Graham Number could not be calculated.")
        lines.append(f"Status: {status_label(status)}")
        if reason:
            lines.append(f"Reason: {_number_reason(p, status, reason)}")

    lines.append("")
    basis_summary = _number_basis_summary(p.assembly.eps, p.assembly.bvps)
    if basis_summary is not None:
        lines.append(f"Basis: {basis_summary}")
    lines.extend(_headline_input_lines(p.assembly.eps, p.assembly.bvps))
    if p.result is None:
        lines.append("Price comparison was not performed because the Graham Number could not be calculated.")
        if _number_quote_not_requested(p):
            lines.append("Current price: not requested because required calculation inputs could not be resolved.")
    lines.append(f"Sources / freshness: {source_summary((p.assembly.eps, p.assembly.bvps))}")
    lines.extend(_number_warning_lines(p))
    lines.append(f"Limitation: {_NUMBER_LIMITATION}")
    return lines


def _number_technical_lines(p: GrahamNumberPresentation) -> list[str]:
    lines = ["", "Details", "-------"]
    lines.extend(identity_detail_lines(p.identity_resolution))
    lines.extend(kind_detail_lines(p.instrument_profile))
    lines.extend(comparison_details(p.price_comparison))
    lines.extend(input_line("EPS", p.assembly.eps))
    lines.extend(input_line("BVPS", p.assembly.bvps))
    if not _number_quote_not_requested(p):
        lines.extend(input_line("Current price", p.assembly.current_price))
    return lines


def _number_quote_not_requested(p: GrahamNumberPresentation) -> bool:
    """Distinguish early assembly failure from an attempted quote resolution."""
    return (
        p.assembly.status is not CalculationStatus.OK
        and p.assembly.current_price is None
        and p.assembly.quote_status is None
        and not any(event.field_name == "current_price" for event in p.assembly.resolution_trace.events)
    )


def _number_detail_lines(p: GrahamNumberPresentation) -> list[str]:
    lines = ["", "Details — calculation inputs", "----------------------------"]
    if p.instrument_profile and p.instrument_profile.kind_evidence:
        lines.append(kind_detail_lines(p.instrument_profile)[0])
    lines.extend(investor_input_lines("Diluted EPS used", p.assembly.eps))
    lines.extend(investor_input_lines("Book value per common share", p.assembly.bvps))
    if p.assembly.eps is not None and p.assembly.eps.basis == "three_year_average":
        lines.append("Average EPS is the arithmetic mean of the three annual diluted EPS values.")
    if p.assembly.bvps is not None and p.assembly.bvps.lineage is not None:
        lines.append("Book value per common share = common equity / period-end common shares outstanding.")
    lines.extend(
        [
            "Graham Number = sqrt(22.5 × selected EPS × book value per share).",
            "The formula uses unrounded inputs; displayed inputs are rounded.",
        ]
    )
    lines.extend(investor_comparison_evidence(p.price_comparison))
    lines.append("Full source fields, assumptions and retrieval history: --diagnostics or --json.")
    return lines


def _headline_input_lines(eps: ResolvedInput | None, bvps: ResolvedInput | None) -> list[str]:
    lines: list[str] = []
    if eps is not None:
        basis_label = basis_display_name(eps.basis) if eps.basis is not None else "unspecified basis"
        lines.append(f"EPS ({basis_label}): {format_money(eps.value, eps.currency)}")
    if bvps is not None:
        lines.append(f"Book value per common share: {format_money(bvps.value, bvps.currency)}")
    return lines


def _number_basis_summary(eps: ResolvedInput | None, bvps: ResolvedInput | None) -> str | None:
    """Describe the actual Number input bases in investor-readable language."""
    if eps is None or bvps is None:
        return None
    return f"{eps_basis_label(eps)} + {_bvps_basis_label(bvps)}"


def _bvps_basis_label(value: ResolvedInput) -> str:
    """Describe the period basis used for book value per common share."""
    basis = display_basis(value)
    if basis == "fiscal_year_end":
        return "latest eligible fiscal-year-end BVPS"
    if basis != "unspecified":
        return f"{basis_display_name(basis)} BVPS"
    return "BVPS basis unspecified"


def _number_warnings(p: GrahamNumberPresentation) -> list[str]:
    warnings = override_warnings((p.assembly.eps, p.assembly.bvps, p.assembly.current_price))
    status, _ = effective_status_and_reason(
        p.assembly.status,
        p.assembly.reason,
        p.result.status if p.result else None,
        p.result.reason if p.result else None,
    )
    if status is CalculationStatus.OK:
        warnings.extend(quote_warnings(p.assembly.quote_status, p.assembly.quote_reason))
    return warnings


def _number_warning_lines(p: GrahamNumberPresentation) -> list[str]:
    return [f"Warning: {warning}" for warning in _number_warnings(p)]


def _number_reason(  # noqa: PLR0911
    presentation: GrahamNumberPresentation,
    status: CalculationStatus,
    fallback: str,
) -> str:
    """Translate retained input and applicability evidence without exposing raw errors."""
    if status is CalculationStatus.INPUT_UNAVAILABLE:
        assembly = presentation.assembly
        if assembly.eps is None:
            return "Eligible earnings per share could not be resolved for the requested basis and analysis date."
        if assembly.bvps is None:
            labels = {
                "preferred_shares_outstanding": "preferred-share evidence",
                "stockholders_equity": "stockholders' equity",
                "common_shares_outstanding": "period-end common shares outstanding",
            }
            for event in reversed(assembly.resolution_trace.events):
                if event.field_name in labels and event.outcome is ResolutionOutcome.UNAVAILABLE:
                    explanation = (
                        "Book value per common share could not be established because eligible "
                        f"{labels[event.field_name]} could not be resolved."
                    )
                    if event.field_name == "preferred_shares_outstanding":
                        explanation += " Missing preferred-share data is not assumed to be zero."
                    return explanation
            return "Eligible book value per common share could not be resolved for the requested analysis date."
    if status is not CalculationStatus.NOT_APPLICABLE:
        return fallback
    eps = presentation.assembly.eps
    bvps = presentation.assembly.bvps
    if eps is not None and eps.value <= 0:
        condition = "negative" if eps.value < 0 else "zero"
        return (
            f"Earnings per share is {condition} ({format_money(eps.value, eps.currency)}), "
            "so the Graham Number does not apply."
        )
    if bvps is not None and bvps.value <= 0:
        condition = "negative" if bvps.value < 0 else "zero"
        return (
            f"Book value per common share is {condition} ({format_money(bvps.value, bvps.currency)}), "
            "so the Graham Number does not apply."
        )
    return fallback


def _number_payload(p: GrahamNumberPresentation) -> dict[str, Any]:
    status, reason = effective_status_and_reason(
        p.assembly.status,
        p.assembly.reason,
        p.result.status if p.result else None,
        p.result.reason if p.result else None,
    )
    if reason:
        reason = _number_reason(p, status, reason)
    result_value = (
        p.result.maximum_indicated_price if p.result is not None and p.result.status is CalculationStatus.OK else None
    )
    return {
        "schema_version": _SCHEMA_VERSION,
        "price_comparison": comparison_payload(p.price_comparison),
        "analysis": "graham_number",
        "ticker": p.ticker.upper(),
        "security_identity": security_identity_payload(p.ticker, p.identity_resolution),
        "instrument_kind": instrument_kind_payload(p.instrument_profile),
        "method": "graham_number",
        "as_of": None if p.as_of is None else p.as_of.isoformat(),
        "status": status.value,
        "reason": reason,
        "result": {
            "maximum_indicated_price": result_value,
            "margin_of_safety_percent": p.margin_of_safety_percent,
        },
        "inputs": {
            "eps": resolved_input_payload(p.assembly.eps),
            "bvps": resolved_input_payload(p.assembly.bvps),
            "current_price": resolved_input_payload(p.assembly.current_price),
        },
        "quote": quote_payload(
            p.assembly.current_price,
            p.assembly.quote_status,
            p.assembly.quote_reason,
        ),
        "warnings": _number_warnings(p),
        "limitations": [_NUMBER_LIMITATION],
        "diagnostics": [
            *trace_payload(p.assembly.resolution_trace),
            *profile_diagnostic_payloads(p.instrument_profile),
            *security_identity_diagnostic_entry(p.instrument_profile, p.identity_resolution),
        ],
    }


__all__ = [
    "GrahamNumberPresentation",
    "number_with_public_quote_reason",
    "render_graham_number",
]
