"""Investor-facing presentation for the two Graham valuation methods."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

from src.analysis.shared.financial_resolution import PriceComparison
from src.analysis.strategy.graham_growth.calculation import GrahamGrowthValueResult, GrowthValueInputAssembly
from src.analysis.strategy.graham_number.calculation import GrahamNumberInputAssembly, GrahamNumberResult
from src.core.analysis_status import CalculationStatus
from src.data.financial.provenance import ResolvedInput, SourceKind
from src.data.financial.quote_freshness import evaluate_quote_freshness
from src.data.financial.resolution_trace import ResolutionOutcome, ResolutionTrace
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
from src.reporting.input_provenance import financial_basis, input_detail_lines, input_source_label, investor_input_lines
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

_SCHEMA_VERSION = 5
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
    price_comparison: PriceComparison | None = None

    def __post_init__(self) -> None:
        """Validate presentation-only coherence without performing finance math."""
        if self.identity_resolution is None and self.instrument_profile is not None:
            object.__setattr__(self, "identity_resolution", profile_identity_resolution(self.instrument_profile))
        _validate_ticker(self.ticker)
        _validate_margin(self.margin_of_safety_percent, self.assembly.current_price)
        if self.price_comparison is not None and self.price_comparison.percent != self.margin_of_safety_percent:
            raise ValueError("Comparison and legacy percentage disagree.")
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
    price_comparison: PriceComparison | None = None

    def __post_init__(self) -> None:
        """Validate presentation-only coherence without performing finance math."""
        if self.identity_resolution is None and self.instrument_profile is not None:
            object.__setattr__(self, "identity_resolution", profile_identity_resolution(self.instrument_profile))
        _validate_ticker(self.ticker)
        _validate_margin(self.margin_of_safety_percent, self.assembly.current_price)
        if self.price_comparison is not None and self.price_comparison.percent != self.margin_of_safety_percent:
            raise ValueError("Comparison and legacy percentage disagree.")
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
        lines.extend(_number_detail_lines(presentation))
    elif mode is PresentationMode.DIAGNOSTICS:
        lines.extend(_number_technical_lines(presentation))
        lines.extend(_diagnostic_lines(presentation.assembly.resolution_trace, presentation.assembly))
        lines.extend(_profile_diagnostic_lines(presentation.instrument_profile, presentation.identity_resolution))
        lines.extend(_comparison_details(presentation.price_comparison))
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
        lines.extend(_growth_technical_lines(presentation))
        lines.extend(_diagnostic_lines(presentation.assembly.resolution_trace, presentation.assembly))
        lines.extend(_profile_diagnostic_lines(presentation.instrument_profile, presentation.identity_resolution))
        lines.extend(_comparison_details(presentation.price_comparison))
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
                comparison=p.price_comparison,
                reference_value=p.result.maximum_indicated_price,
                valuation_currency=currency,
                reference_label="Graham Number",
            )
        )
    else:
        lines = [
            _analysis_heading(p.ticker, "Graham Number", p.as_of, p.identity_resolution),
        ]
        if p.result is None:
            lines.append("Graham Number could not be calculated.")
        lines.append(f"Status: {_status_label(status)}")
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
                comparison=p.price_comparison,
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


def _number_technical_lines(p: GrahamNumberPresentation) -> list[str]:
    lines = ["", "Details", "-------"]
    lines.extend(_identity_detail_lines(p.identity_resolution))
    lines.extend(_kind_detail_lines(p.instrument_profile))
    lines.extend(_comparison_details(p.price_comparison))
    lines.extend(_input_detail_lines("EPS", p.assembly.eps))
    lines.extend(_input_detail_lines("BVPS", p.assembly.bvps))
    if not _number_quote_not_requested(p):
        lines.extend(_input_detail_lines("Current price", p.assembly.current_price))
    return lines


def _number_quote_not_requested(p: GrahamNumberPresentation) -> bool:
    """Distinguish early assembly failure from an attempted quote resolution."""
    return (
        p.assembly.status is not CalculationStatus.OK
        and p.assembly.current_price is None
        and p.assembly.quote_status is None
        and not any(event.field_name == "current_price" for event in p.assembly.resolution_trace.events)
    )


def _growth_technical_lines(p: GrahamGrowthPresentation) -> list[str]:
    lines = ["", "Details", "-------"]
    lines.extend(_identity_detail_lines(p.identity_resolution))
    lines.extend(_kind_detail_lines(p.instrument_profile))
    lines.extend(_comparison_details(p.price_comparison))
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


def _number_detail_lines(p: GrahamNumberPresentation) -> list[str]:
    lines = ["", "Details — calculation inputs", "----------------------------"]
    if p.instrument_profile and p.instrument_profile.kind_evidence:
        lines.append(_kind_detail_lines(p.instrument_profile)[0])
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
    lines.extend(_investor_comparison_evidence(p.price_comparison))
    lines.append("Full source fields, assumptions and retrieval history: --diagnostics or --json.")
    return lines


def _growth_detail_lines(p: GrahamGrowthPresentation) -> list[str]:
    lines = ["", "Details — calculation inputs", "----------------------------"]
    if p.instrument_profile and p.instrument_profile.kind_evidence:
        lines.append(_kind_detail_lines(p.instrument_profile)[0])
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
    lines.extend(_investor_comparison_evidence(p.price_comparison))
    lines.append("Full source fields, assumptions and retrieval history: --diagnostics or --json.")
    return lines


def _investor_comparison_evidence(comparison: PriceComparison | None) -> list[str]:
    if comparison is None or comparison.reason == "calculation_unavailable":
        return []
    lines = ["", "Evidence and assumptions", f"Share-unit comparison: {comparison.reason.replace('_', ' ')}"]
    resolution = comparison.security_unit_resolution
    if resolution is not None and resolution.provenance is not None:
        for document in resolution.provenance.documents:
            if document.listing_venue:
                lines.append(f"Filing lists {document.listing_venue}; current venue not independently verified.")
            lines.append(f"Filing accepted {format_date(document.available_at)}: {document.url}")
    return lines


def _identity_detail_lines(resolution: SecurityIdentityResolution | None) -> list[str]:
    """Describe current identity metadata separately from historical financial inputs."""
    if resolution is None or resolution.identity is None:
        return ["Security identity: unavailable"]
    identity = resolution.identity
    return [
        f"Instrument name: {identity.instrument_name or 'unavailable'}",
        f"Current listing venue: {identity.listing_venue or 'not supplied by selected identity provider'}",
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
    return input_detail_lines(label, value)


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


def _comparison_reason(reason: str) -> str:
    """Translate stable comparison decisions without exposing provider exceptions."""
    return {
        "missing_evidence": "share-unit evidence is missing; use --no-cache to refresh legacy inputs",
        "provider_unsupported": "share-unit evidence is unsupported by this provider",
        "provider_error": "share-unit evidence could not be retrieved",
        "unsupported_temporal_evidence": "historical share-unit evidence is unsupported",
        "source_mismatch": "filing and quoted security identities could not be matched",
        "ambiguous_class": "filing and quoted share classes could not be matched",
        "multi_class_ambiguity": "filing and quoted share classes could not be matched",
        "unsupported_evidence": "filing share-unit evidence is unsupported or inconsistent",
        "unknown_ratio": "the quoted-to-filing share ratio is unknown",
        "unsupported_unit_kind": "the quoted share unit is unsupported",
        "non_unit_ratio": "the quoted-to-filing share ratio is not 1:1",
        "currency_mismatch": "valuation and quote currencies differ",
        "missing_quote": "no current quote",
        "nonpositive_reference": "the reference value is non-positive",
        "calculation_unavailable": "the reference calculation is unavailable",
        "nonfinite_comparison": "the price relationship is not finite",
    }.get(reason, "share-unit compatibility could not be established")


def _comparison_payload(comparison: PriceComparison | None) -> dict[str, Any] | None:
    if comparison is None:
        return None
    resolution = comparison.security_unit_resolution
    evidence = resolution.evidence if resolution else None
    provenance = resolution.provenance if resolution else None
    return {
        "status": comparison.status,
        "reason": comparison.reason,
        "percent": comparison.percent,
        "quote_freshness": None
        if comparison.quote_freshness is None
        else {
            "status": comparison.quote_freshness.status,
            "evaluated_at": comparison.quote_freshness.evaluated_at.isoformat(),
            "retrieved_at": _json_datetime(comparison.quote_freshness.retrieved_at),
            "retrieval_age_seconds": comparison.quote_freshness.retrieval_age_seconds,
            "max_retrieval_age_seconds": comparison.quote_freshness.max_retrieval_age_seconds,
            "market_observed_at": _json_datetime(comparison.quote_freshness.market_observed_at),
        },
        "security_unit_evidence": None
        if evidence is None
        else {
            "ticker": evidence.ticker,
            "filing_unit_kind": evidence.filing_unit_kind.value,
            "quoted_unit_kind": evidence.quoted_unit_kind.value,
            "underlying_shares_per_quoted_unit": evidence.underlying_shares_per_quoted_unit,
            "provider_id": evidence.provider_id,
            "source": evidence.source,
        },
        "provenance": None
        if provenance is None
        else {
            "mapping_id": provenance.mapping_id,
            "cik": provenance.cik,
            "class_title": provenance.class_title,
            "documents": [
                {
                    "accession": item.accession,
                    "url": item.url,
                    "context_ids": list(item.context_ids),
                    "available_at": item.available_at.isoformat(),
                    "retrieved_at": item.retrieved_at.isoformat(),
                    "listing_venue": item.listing_venue,
                }
                for item in provenance.documents
            ],
        },
    }


def _comparison_details(comparison: PriceComparison | None) -> list[str]:
    if comparison is None:
        return []
    lines = [f"Price comparison status: {comparison.status} ({comparison.reason})"]
    resolution = comparison.security_unit_resolution
    if resolution is not None and resolution.evidence is not None:
        evidence = resolution.evidence
        lines.extend(
            [
                f"Share-unit provider: {provider_display_name(evidence.provider_id)}",
                f"Filing unit: {evidence.filing_unit_kind.value}; quoted unit: {evidence.quoted_unit_kind.value}",
                f"Underlying shares per quoted unit: {evidence.underlying_shares_per_quoted_unit}",
            ]
        )
    if resolution is not None and resolution.provenance is not None:
        provenance = resolution.provenance
        lines.extend([f"Share-unit mapping: {provenance.mapping_id}", f"Share class: {provenance.class_title}"])
        for document in provenance.documents:
            if document.listing_venue:
                lines.append(
                    f"Filing listing venue: {document.listing_venue} "
                    f"(filing available {format_utc_minute(document.available_at)})"
                )
            lines.append(
                f"Share evidence: SEC EDGAR {document.accession}; "
                f"available {format_utc_minute(document.available_at)}; "
                f"retrieved {format_utc_minute(document.retrieved_at)}"
            )
            lines.append(f"Share contexts: {', '.join(document.context_ids)}")
    return lines


def _comparison_lines(  # noqa: PLR0913
    current_price: ResolvedInput | None,
    margin_of_safety_percent: float | None,
    *,
    reference_value: float | None = None,
    valuation_currency: str | None = None,
    reference_label: str,
    comparison: PriceComparison | None = None,
) -> list[str]:
    if current_price is None:
        return ["Current price: unavailable", "Price comparison: unavailable (no current quote)"]

    label = "User-supplied price" if current_price.source_kind is SourceKind.OVERRIDE else "Latest available quote"
    lines = [f"{label}: {format_money(current_price.value, current_price.currency)}"]
    if current_price.source_kind is not SourceKind.OVERRIDE:
        lines.append(f"Quote retrieved: {format_utc_minute(current_price.retrieved_at)}")
        timing = comparison.quote_freshness if comparison is not None else None
        if timing is not None and timing.retrieval_age_seconds is not None:
            lines.append(f"Quote response age: {timing.retrieval_age_seconds:.0f} seconds")
        observed = (
            timing.market_observed_at
            if timing is not None
            else evaluate_quote_freshness(current_price, now=current_price.resolved_at).market_observed_at
        )
        if observed is None:
            lines.append("Market observation time not supplied.")
        else:
            lines.append(f"Market observation: {format_utc_minute(observed)}")
    if reference_value is not None and reference_value <= 0:
        lines.append(f"Price comparison: unavailable ({reference_label} is non-positive)")
    elif (
        valuation_currency is not None
        and current_price.currency is not None
        and valuation_currency != current_price.currency
    ):
        lines.append("Price comparison: unavailable (valuation and quote currencies differ)")
    elif comparison is not None and comparison.status == "unavailable":
        lines.append(f"Price comparison: unavailable ({_comparison_reason(comparison.reason)})")
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
        source = _source_label(item)
        if item.source_kind is SourceKind.CACHE:
            source = f"{provider_display_name(item.provider_id)} (saved input)"
        parts.append(f"{label} — {source} ({_freshness_label(item)})")
    return "; ".join(parts) if parts else "unavailable"


def _display_basis(value: ResolvedInput) -> str:
    """Return explicit basis, or infer fiscal-year-end BVPS from its lineage."""
    return financial_basis(value) or "unspecified"


def _status_label(status: CalculationStatus) -> str:
    """Render enum status values in investor-facing prose."""
    return humanized_status(status)


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


def _freshness_label(value: ResolvedInput) -> str:
    """Describe the best retained freshness boundary using date semantics."""
    if value.source_kind is SourceKind.OVERRIDE:
        return "user supplied; not provider verified"
    if value.available_at is not None:
        return f"available {format_date(value.available_at)}"
    if value.observed_at is not None:
        return f"observed {format_date(value.observed_at)}"
    if value.observation_period_end is not None:
        return f"period end {format_date(value.observation_period_end)}"
    return "freshness unavailable"


def _source_label(value: ResolvedInput) -> str:
    return input_source_label(value)


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
        "price_comparison": _comparison_payload(p.price_comparison),
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
        "price_comparison": _comparison_payload(p.price_comparison),
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
