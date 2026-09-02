"""Investor-facing presentation for the two Graham valuation methods."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

from src.analysis.graham_value.input_resolver import GrahamNumberInputAssembly, GrowthValueInputAssembly
from src.analysis.graham_value.models import GrahamGrowthValueResult, GrahamNumberResult
from src.core.analysis_status import CalculationStatus
from src.data.financial.provenance import ResolvedInput, SourceKind
from src.data.financial.resolution_trace import ResolutionTrace
from src.data.instrument_profile import (
    InstrumentProfile,
    instrument_kind_evidence_payload,
    profile_identity_resolution,
)
from src.data.security_identity import (
    IdentityResolutionStatus,
    SecurityIdentityResolution,
    security_display_label,
    security_identity_payload,
)
from src.reporting.presentation import (
    PresentationMode,
    format_as_of,
    format_date,
    format_money,
    format_number,
    format_utc_minute,
    humanized_status,
    json_document,
    provider_display_name,
)

# ---------------------------------------------------------------------------
# Strategy-specific display labels
# ---------------------------------------------------------------------------

# Explicit human-readable display labels for basis identifiers used in
# Graham analysis.  Unknown basis identifiers fall through to their raw
# form so that test fixtures and future basis values remain visible.
# A future localisation layer can replace or parameterise these values
# without altering the machine identifiers themselves.
BASIS_DISPLAY_NAMES: Final[dict[str, str]] = {
    "three_year_average": "3-year average",
    "ttm": "TTM",
    "fiscal_year_end": "fiscal-year-end",
    "fiscal_year": "fiscal year",
}

FIELD_DISPLAY_NAMES: Final[dict[str, str]] = {
    "eps": "EPS",
    "bvps": "BVPS",
    "current_price": "Current price",
    "current_aaa_yield": "Current AAA yield",
    "expected_growth": "Expected growth",
}

UNITS_DISPLAY_NAMES: Final[dict[str, str]] = {
    "currency_per_share": "currency per share",
    "percentage_points": "percentage points",
    "ratio": "ratio",
}


def basis_display_name(basis: str | None) -> str:
    """Return an explicit human-readable label for a basis identifier.

    Args:
        basis: Machine-readable basis identifier (e.g. ``"three_year_average"``).

    Returns:
        The corresponding display label, or the raw identifier when no
        explicit mapping exists.  Returns ``"unavailable"`` when *basis*
        is ``None``.
    """
    if basis is None:
        return "unavailable"
    return BASIS_DISPLAY_NAMES.get(basis, basis)


def field_display_name(field_name: str) -> str:
    """Return an explicit human-readable label for a field identifier.

    Args:
        field_name: Machine-readable field name (e.g. ``"eps"``).

    Returns:
        The corresponding display label, or the raw identifier when no
        explicit mapping exists.
    """
    return FIELD_DISPLAY_NAMES.get(field_name, field_name)


def units_display_name(units: str | None) -> str:
    """Return an explicit human-readable label for a units identifier.

    Args:
        units: Machine-readable units identifier (e.g. ``"currency_per_share"``).

    Returns:
        The corresponding display label, or the raw identifier when no
        explicit mapping exists.  Returns ``"unavailable"`` when *units*
        is ``None``.
    """
    if units is None:
        return "unavailable"
    return UNITS_DISPLAY_NAMES.get(units, units)


# ---------------------------------------------------------------------------
# Constants and models
# ---------------------------------------------------------------------------

_SCHEMA_VERSION = 3
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
    identity_resolution: SecurityIdentityResolution | None = None
    instrument_profile: InstrumentProfile | None = None

    def __post_init__(self) -> None:
        """Validate presentation-only coherence without performing finance math."""
        if self.identity_resolution is None and self.instrument_profile is not None:
            object.__setattr__(self, "identity_resolution", profile_identity_resolution(self.instrument_profile))
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
    identity_resolution: SecurityIdentityResolution | None = None
    instrument_profile: InstrumentProfile | None = None

    def __post_init__(self) -> None:
        """Validate presentation-only coherence without performing finance math."""
        if self.identity_resolution is None and self.instrument_profile is not None:
            object.__setattr__(self, "identity_resolution", profile_identity_resolution(self.instrument_profile))
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


# ---------------------------------------------------------------------------
# Public render entry points
# ---------------------------------------------------------------------------


def render_graham_number(
    presentation: GrahamNumberPresentation,
    mode: PresentationMode = PresentationMode.CONCISE,
) -> str:
    """Render a Graham Number analysis using the approved investor grammar."""
    if mode is PresentationMode.JSON:
        return json_document(_number_payload(presentation))

    lines = _number_concise_lines(presentation)
    if mode is PresentationMode.DETAILS:
        if presentation.result is None:
            status, reason = _effective_status_and_reason(
                presentation.assembly.status, presentation.assembly.reason, presentation.result
            )
            lines = [
                _analysis_heading(
                    presentation.ticker,
                    "Graham Number",
                    presentation.as_of,
                    presentation.identity_resolution,
                ),
                f"Status: {_status_label(status)}",
                f"Reason: {reason or 'No reason was retained.'}",
            ]
        lines.extend(_number_detail_lines(presentation))
    elif mode is PresentationMode.DIAGNOSTICS:
        lines.extend(_diagnostic_lines(presentation.assembly.resolution_trace, presentation.assembly))
        lines.extend(_profile_diagnostic_lines(presentation.instrument_profile, presentation.identity_resolution))
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
        if presentation.result is None:
            status, reason = _effective_status_and_reason(
                presentation.assembly.status, presentation.assembly.reason, presentation.result
            )
            lines = [
                _analysis_heading(
                    presentation.ticker,
                    "Graham Growth Value",
                    presentation.as_of,
                    presentation.identity_resolution,
                ),
                f"Status: {_status_label(status)}",
                f"Reason: {reason or 'No reason was retained.'}",
            ]
        lines.extend(_growth_detail_lines(presentation))
    elif mode is PresentationMode.DIAGNOSTICS:
        lines.extend(_diagnostic_lines(presentation.assembly.resolution_trace, presentation.assembly))
        lines.extend(_profile_diagnostic_lines(presentation.instrument_profile, presentation.identity_resolution))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Concise output
# ---------------------------------------------------------------------------


def _number_concise_lines(p: GrahamNumberPresentation) -> list[str]:
    status, reason = _effective_status_and_reason(p.assembly.status, p.assembly.reason, p.result)
    result_ok = p.result is not None and p.result.status is CalculationStatus.OK

    if result_ok:
        assert p.result is not None
        assert p.result.maximum_indicated_price is not None
        currency = _common_currency(p.assembly.eps, p.assembly.bvps)
        heading = _result_heading(
            p.ticker,
            "Graham Number (maximum indicated price)",
            p.as_of,
            format_money(p.result.maximum_indicated_price, currency),
            p.identity_resolution,
        )
        lines = [heading]
        lines.extend(
            _comparison_lines(
                p.assembly.current_price,
                p.margin_of_safety_percent,
                reference_value=p.result.maximum_indicated_price,
                valuation_currency=currency,
                reference_label="Graham Number",
            )
        )
    else:
        lines = [
            _analysis_heading(p.ticker, "Graham Number", p.as_of, p.identity_resolution),
            f"Status: {_status_label(status)}",
        ]
        if reason:
            lines.append(f"Reason: {_number_reason(p, status, reason)}")

    lines.append("")
    basis_summary = _number_basis_summary(p.assembly.eps, p.assembly.bvps)
    if basis_summary is not None:
        lines.append(f"Basis: {basis_summary}")
    lines.extend(_headline_input_lines(p.assembly.eps, p.assembly.bvps))
    lines.append(f"Sources / freshness: {_source_summary((p.assembly.eps, p.assembly.bvps))}")
    lines.extend(_number_warning_lines(p))
    lines.append(f"Limitation: {_NUMBER_LIMITATION}")
    return lines


def _growth_concise_lines(p: GrahamGrowthPresentation) -> list[str]:
    status, reason = _effective_status_and_reason(p.assembly.status, p.assembly.reason, p.result)
    result_ok = p.result is not None and p.result.status is CalculationStatus.OK

    if result_ok:
        assert p.result is not None
        assert p.result.growth_value is not None
        currency = _common_currency(p.assembly.eps)
        lines = [
            _result_heading(
                p.ticker,
                "Graham Growth Value",
                p.as_of,
                format_money(p.result.growth_value, currency),
                p.identity_resolution,
            )
        ]
    else:
        lines = [
            _analysis_heading(p.ticker, "Graham Growth Value", p.as_of, p.identity_resolution),
            f"Status: {_status_label(status)}",
        ]
        if reason:
            lines.append(f"Reason: {reason}")

    growth = p.assembly.expected_growth
    if growth is not None:
        lines.append(f"Expected growth assumption: {format_number(growth.value)} percentage points")

    if result_ok:
        assert p.result is not None
        lines.extend(
            _comparison_lines(
                p.assembly.current_price,
                p.margin_of_safety_percent,
                reference_value=p.result.growth_value,
                valuation_currency=_common_currency(p.assembly.eps),
                reference_label="Graham growth value",
            )
        )

    lines.append("")
    lines.append(f"Sources / freshness: {_source_summary((p.assembly.eps, p.assembly.current_aaa_yield))}")
    lines.extend(_growth_warning_lines(p))
    lines.append(f"Limitation: {_GROWTH_LIMITATION}")
    return lines


# ---------------------------------------------------------------------------
# Headings
# ---------------------------------------------------------------------------


def _analysis_heading(
    ticker: str,
    label: str,
    as_of: datetime | None,
    identity_resolution: SecurityIdentityResolution | None,
) -> str:
    """Render a method heading, surfacing historical boundaries only when requested."""
    boundary = f" as of {format_as_of(as_of)}" if as_of is not None else ""
    return f"{security_display_label(ticker, identity_resolution)} — {label}{boundary}"


def _result_heading(
    ticker: str,
    label: str,
    as_of: datetime | None,
    result_text: str,
    identity_resolution: SecurityIdentityResolution | None,
) -> str:
    """Put the investor-facing result directly in the successful report heading."""
    return f"{_analysis_heading(ticker, label, as_of, identity_resolution)}: {result_text}"


# ---------------------------------------------------------------------------
# Details output
# ---------------------------------------------------------------------------


def _number_detail_lines(p: GrahamNumberPresentation) -> list[str]:
    lines = ["", "Details", "-------"]
    lines.extend(_identity_detail_lines(p.identity_resolution))
    lines.extend(_kind_detail_lines(p.instrument_profile))
    lines.extend(_input_detail_lines("EPS", p.assembly.eps))
    lines.extend(_input_detail_lines("BVPS", p.assembly.bvps))
    lines.extend(_input_detail_lines("Current price", p.assembly.current_price))
    return lines


def _growth_detail_lines(p: GrahamGrowthPresentation) -> list[str]:
    lines = ["", "Details", "-------"]
    lines.extend(_identity_detail_lines(p.identity_resolution))
    lines.extend(_kind_detail_lines(p.instrument_profile))
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


def _identity_detail_lines(resolution: SecurityIdentityResolution | None) -> list[str]:
    """Describe current identity metadata separately from historical financial inputs."""
    if resolution is None or resolution.identity is None:
        return ["Security identity: unavailable"]
    identity = resolution.identity
    return [
        f"Instrument name: {identity.instrument_name or 'unavailable'}",
        f"Listing venue: {identity.listing_venue or 'unavailable'}",
        f"Identity provider: {provider_display_name(identity.provider_id)}",
        f"Identity resolved: {format_utc_minute(identity.resolved_at)} (current descriptive metadata)",
    ]


def _identity_diagnostic_lines(resolution: SecurityIdentityResolution | None) -> list[str]:
    """Expose identity resolution only as software diagnostics, never warnings."""
    if resolution is None:
        return []
    return [f"security_identity: provider/{resolution.status.value} — {resolution.message}"]


def _kind_detail_lines(profile: InstrumentProfile | None) -> list[str]:
    """Describe retained kind evidence separately from identity and financial inputs."""
    if profile is None or profile.kind_evidence is None:
        return ["Instrument kind: unavailable"]
    evidence = profile.kind_evidence
    return [
        f"Instrument kind: {evidence.kind.value if evidence.kind is not None else 'unreviewed'}",
        f"Kind provider value: {evidence.provider_value}",
        f"Kind provider: {provider_display_name(evidence.provider_id)}",
        f"Kind resolved: {format_utc_minute(evidence.resolved_at)} (current classification metadata)",
    ]


def _profile_diagnostic_lines(
    profile: InstrumentProfile | None,
    identity_resolution: SecurityIdentityResolution | None,
) -> list[str]:
    """Render ordered profile attempts, falling back to the legacy identity diagnostic."""
    if profile is None:
        return _identity_diagnostic_lines(identity_resolution)
    return [
        f"{item.capability.value}: {item.provider_id}/{item.status.value} — {item.message}"
        for item in profile.diagnostics
    ]


def _input_detail_lines(label: str, value: ResolvedInput | None) -> list[str]:
    if value is None:
        return [f"{label}: unavailable"]

    source = _source_label(value)
    lines = [
        f"{label}: {format_number(value.value, decimals=6)}",
        f"  basis: {basis_display_name(_display_basis(value))}",
        f"  units: {units_display_name(value.units)}",
        f"  currency: {value.currency or 'n/a'}",
        f"  source: {source}",
        f"  provider: {provider_display_name(value.provider_id)}",
        f"  provider field: {value.provider_field or 'n/a'}",
        f"  period start: {format_date(value.observation_period_start)}",
        f"  period end: {format_date(value.observation_period_end)}",
        f"  observed at: {format_utc_minute(value.observed_at)}",
        f"  available at: {format_utc_minute(value.available_at)}",
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
                    f"    provider: {provider_display_name(component.provider_id)}",
                    f"    provider field: {component.provider_field or 'n/a'}",
                    f"    basis: {basis_display_name(component.basis)}",
                    f"    period end: {format_date(component.observation_period_end)}",
                    f"    available at: {format_utc_minute(component.available_at)}",
                ]
            )
    return lines


# ---------------------------------------------------------------------------
# Diagnostics output (technical identifiers intentionally retained)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Concise helpers
# ---------------------------------------------------------------------------


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
    return f"{_eps_basis_label(eps)} + {_bvps_basis_label(bvps)}"


def _eps_basis_label(value: ResolvedInput) -> str:
    """Describe EPS basis, preserving whether retained evidence is diluted EPS."""
    if value.basis == "three_year_average":
        qualifier = " diluted" if _uses_diluted_eps(value) else ""
        return f"3-year average{qualifier} EPS"
    if value.basis == "ttm":
        return "TTM EPS"
    if value.basis is not None:
        return f"{basis_display_name(value.basis)} EPS"
    return "EPS basis unspecified"


def _uses_diluted_eps(value: ResolvedInput) -> bool:
    """Return whether all retained provider-field evidence identifies diluted EPS."""
    fields: list[str] = []
    if value.provider_field is not None:
        fields.append(value.provider_field)
    if value.lineage is not None:
        fields.extend(component.provider_field for component in value.lineage.components if component.provider_field)
    return bool(fields) and all("diluted" in field.lower() for field in fields)


def _bvps_basis_label(value: ResolvedInput) -> str:
    """Describe the period basis used for book value per common share."""
    basis = _display_basis(value)
    if basis == "fiscal_year_end":
        return "latest eligible fiscal-year-end BVPS"
    if basis != "unspecified":
        return f"{basis_display_name(basis)} BVPS"
    return "BVPS basis unspecified"


def _comparison_lines(
    current_price: ResolvedInput | None,
    margin_of_safety_percent: float | None,
    *,
    reference_value: float | None = None,
    valuation_currency: str | None = None,
    reference_label: str,
) -> list[str]:
    if current_price is None:
        return ["Current price: unavailable", "Price comparison: unavailable (no current quote)"]

    lines = [f"Current price: {format_money(current_price.value, current_price.currency)}"]
    if reference_value is not None and reference_value <= 0:
        lines.append(f"Price comparison: unavailable ({reference_label} is non-positive)")
    elif (
        valuation_currency is not None
        and current_price.currency is not None
        and valuation_currency != current_price.currency
    ):
        lines.append("Price comparison: unavailable (valuation and quote currencies differ)")
    elif margin_of_safety_percent is None:
        lines.append("Price comparison: unavailable")
    elif margin_of_safety_percent >= 0:
        lines.append(f"Price relationship: {format_number(margin_of_safety_percent)}% below the {reference_label}")
    else:
        lines.append(f"Price relationship: {format_number(abs(margin_of_safety_percent))}% above the {reference_label}")
    return lines


# ---------------------------------------------------------------------------
# Warnings
# ---------------------------------------------------------------------------


def _number_warnings(p: GrahamNumberPresentation) -> list[str]:
    warnings = _override_warnings((p.assembly.eps, p.assembly.bvps, p.assembly.current_price))
    status, _ = _effective_status_and_reason(p.assembly.status, p.assembly.reason, p.result)
    if status is CalculationStatus.OK:
        warnings.extend(_quote_warnings(p.assembly.quote_status, p.assembly.quote_reason))
    return warnings


def _number_warning_lines(p: GrahamNumberPresentation) -> list[str]:
    return [f"Warning: {warning}" for warning in _number_warnings(p)]


def _growth_warnings(p: GrahamGrowthPresentation) -> list[str]:
    warnings = _override_warnings((p.assembly.eps,))
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
    warnings.extend(_override_warnings((p.assembly.current_price,)))
    warnings.extend(_quote_warnings(p.assembly.quote_status, p.assembly.quote_reason))
    return warnings


def _growth_warning_lines(p: GrahamGrowthPresentation) -> list[str]:
    return [f"Warning: {warning}" for warning in _growth_warnings(p)]


def _override_warnings(inputs: tuple[ResolvedInput | None, ...]) -> list[str]:
    warnings: list[str] = []
    for item in inputs:
        if item is not None and item.source_kind is SourceKind.OVERRIDE:
            label = field_display_name(item.field_name)
            warnings.append(f"{label} is a user override, not provider-verified data.")
    return warnings


def _quote_warnings(
    status: CalculationStatus | None,
    _reason: str | None,
) -> list[str]:
    if status is None:
        return []
    return ["Current quote unavailable; price comparison omitted."]


# ---------------------------------------------------------------------------
# Source / freshness / status helpers
# ---------------------------------------------------------------------------


def _source_summary(inputs: tuple[ResolvedInput | None, ...]) -> str:
    parts: list[str] = []
    for item in inputs:
        if item is None:
            continue
        label = field_display_name(item.field_name)
        parts.append(f"{label} — {_source_label(item)} ({_freshness_label(item)})")
    return "; ".join(parts) if parts else "unavailable"


def _display_basis(value: ResolvedInput) -> str:
    """Return explicit basis, or infer fiscal-year-end BVPS from its lineage."""
    if value.basis is not None:
        return value.basis
    if value.field_name == "bvps" and value.lineage is not None and value.lineage.components:
        component_bases = {component.basis for component in value.lineage.components}
        if component_bases == {"fiscal_year_end"}:
            return "fiscal_year_end"
    return "unspecified"


def _status_label(status: CalculationStatus) -> str:
    """Render enum status values in investor-facing prose."""
    return humanized_status(status)


def _number_reason(
    presentation: GrahamNumberPresentation,
    status: CalculationStatus,
    fallback: str,
) -> str:
    """Translate Number applicability failures without changing typed results."""
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


def _freshness_label(value: ResolvedInput) -> str:
    """Describe the best retained freshness boundary using date semantics."""
    if value.available_at is not None:
        return f"available {format_date(value.available_at)}"
    if value.observed_at is not None:
        return f"observed {format_date(value.observed_at)}"
    if value.observation_period_end is not None:
        return f"period end {format_date(value.observation_period_end)}"
    return "freshness unavailable"


def _source_label(value: ResolvedInput) -> str:
    if value.source_kind is SourceKind.OVERRIDE:
        return "user override"
    if value.source_kind is SourceKind.CACHE:
        origin = value.origin_source_kind.value if value.origin_source_kind is not None else "unknown"
        provider = f", provider={provider_display_name(value.provider_id)}" if value.provider_id else ""
        return f"cache (original={origin}{provider})"
    if value.source_kind is SourceKind.PROVIDER and value.provider_field is not None:
        provider = provider_display_name(value.provider_id)
        if value.provider_field.startswith("inferred:"):
            return f"inferred ({provider})"
        if value.provider_field.startswith("derived:"):
            return f"provider-derived ({provider})"
    if value.source_kind is SourceKind.DERIVED:
        providers = (
            sorted(
                {
                    provider_display_name(component.provider_id)
                    for component in value.lineage.components
                    if component.provider_id
                }
            )
            if value.lineage is not None
            else []
        )
        provider_text = ", ".join(providers) if providers else provider_display_name(value.provider_id)
        return f"derived from {provider_text}"
    return f"provider ({provider_display_name(value.provider_id)})"


# ---------------------------------------------------------------------------
# JSON payload builders (machine identifiers intentionally retained)
# ---------------------------------------------------------------------------


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
        "security_identity": security_identity_payload(p.ticker, p.identity_resolution),
        "instrument_kind": instrument_kind_evidence_payload(
            p.instrument_profile.kind_evidence if p.instrument_profile is not None else None
        ),
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
        "diagnostics": [
            *_trace_payload(p.assembly.resolution_trace),
            *_profile_diagnostic_payloads(p.instrument_profile),
            *(
                [
                    {
                        "field_name": "security_identity",
                        "stage": "provider",
                        "outcome": p.identity_resolution.status.value,
                        "message": p.identity_resolution.message,
                    }
                ]
                if p.instrument_profile is None
                and p.identity_resolution is not None
                and p.identity_resolution.status is not IdentityResolutionStatus.RESOLVED
                else []
            ),
        ],
    }


def _growth_payload(p: GrahamGrowthPresentation) -> dict[str, Any]:
    status, reason = _effective_status_and_reason(p.assembly.status, p.assembly.reason, p.result)
    result_value = p.result.growth_value if p.result is not None and p.result.status is CalculationStatus.OK else None
    return {
        "schema_version": _SCHEMA_VERSION,
        "analysis": "graham",
        "ticker": p.ticker.upper(),
        "security_identity": security_identity_payload(p.ticker, p.identity_resolution),
        "instrument_kind": instrument_kind_evidence_payload(
            p.instrument_profile.kind_evidence if p.instrument_profile is not None else None
        ),
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
        "diagnostics": [
            *_trace_payload(p.assembly.resolution_trace),
            *_profile_diagnostic_payloads(p.instrument_profile),
            *(
                [
                    {
                        "field_name": "security_identity",
                        "stage": "provider",
                        "outcome": p.identity_resolution.status.value,
                        "message": p.identity_resolution.message,
                    }
                ]
                if p.instrument_profile is None
                and p.identity_resolution is not None
                and p.identity_resolution.status is not IdentityResolutionStatus.RESOLVED
                else []
            ),
        ],
    }


def _profile_diagnostic_payloads(profile: InstrumentProfile | None) -> list[dict[str, str]]:
    """Convert ordered profile diagnostics to the stable presentation shape."""
    if profile is None:
        return []
    return [
        {
            "field_name": item.capability.value,
            "stage": "provider",
            "outcome": item.status.value,
            "message": item.message,
            "provider_id": item.provider_id,
        }
        for item in profile.diagnostics
    ]


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


# ---------------------------------------------------------------------------
# Shared validation and utility helpers
# ---------------------------------------------------------------------------


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
