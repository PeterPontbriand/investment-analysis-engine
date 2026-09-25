"""Shared valuation-presentation primitives: price comparison, identity, and resolved-input display.

Strategy-neutral by design, matching `src/analysis/shared/financial_resolution.py` on the
calculation side — every reference-value-vs-current-price screen (Graham Number, Graham Growth
Value today; NCAV, EPV, reverse DCF later) presents the same evidence shapes the same way.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Final

from src.analysis.shared.financial_resolution import PriceComparison
from src.core.analysis_status import CalculationStatus
from src.data.financial.provenance import ResolvedInput, SourceKind
from src.data.financial.quote_freshness import evaluate_quote_freshness
from src.data.financial.resolution_trace import ResolutionTrace
from src.data.instrument_profile import InstrumentProfile, instrument_kind_evidence_payload
from src.data.security_identity import IdentityResolutionStatus, SecurityIdentityResolution, security_display_label
from src.reporting.input_provenance import financial_basis, input_detail_lines, input_source_label
from src.reporting.presentation import (
    format_as_of,
    format_date,
    format_money,
    format_number,
    format_utc_minute,
    humanized_status,
    provider_display_name,
)

# ---------------------------------------------------------------------------
# Display labels
# ---------------------------------------------------------------------------

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
# Failure / status prose
# ---------------------------------------------------------------------------


def public_quote_reason(status: CalculationStatus) -> str:
    """Return a stable investor-facing explanation for optional quote failure."""
    if status is CalculationStatus.PROVIDER_ERROR:
        return "The configured quote provider could not complete the request."
    if status is CalculationStatus.INPUT_UNAVAILABLE:
        return "No eligible current quote was available from the configured quote source."
    return "The current quote could not be used for price comparison."


def friendly_valuation_failure(ticker: str, status: CalculationStatus, reason: str | None) -> str:
    """Map resolver failure classes to concise investor-facing errors."""
    if reason is not None and reason.startswith("Unable to analyze"):
        return reason
    if status is CalculationStatus.PROVIDER_ERROR:
        return f"Unable to analyze {ticker}: the configured provider could not retrieve required security data."
    if status is CalculationStatus.INPUT_UNAVAILABLE:
        return f"Unable to analyze {ticker}: required financial data is unavailable for the requested method."
    return f"Unable to analyze {ticker}: the requested inputs are invalid. Review the method and overrides."


def status_label(status: CalculationStatus) -> str:
    """Render enum status values in investor-facing prose."""
    return humanized_status(status)


def effective_status_and_reason(
    assembly_status: CalculationStatus,
    assembly_reason: str | None,
    result_status: CalculationStatus | None,
    result_reason: str | None,
) -> tuple[CalculationStatus, str | None]:
    """Prefer the calculation result's status/reason once assembly has succeeded."""
    if assembly_status is not CalculationStatus.OK:
        return assembly_status, assembly_reason
    if result_status is None:
        return CalculationStatus.INPUT_UNAVAILABLE, "Calculation result was not supplied to the presenter."
    return result_status, result_reason


# ---------------------------------------------------------------------------
# Headings
# ---------------------------------------------------------------------------


def analysis_heading(
    ticker: str,
    label: str,
    as_of: datetime | None,
    identity_resolution: SecurityIdentityResolution | None,
) -> str:
    """Render a method heading, surfacing historical boundaries only when requested."""
    boundary = f" as of {format_as_of(as_of)}" if as_of is not None else ""
    return f"{security_display_label(ticker, identity_resolution)} — {label}{boundary}"


def result_heading(
    ticker: str,
    label: str,
    as_of: datetime | None,
    result_text: str,
    identity_resolution: SecurityIdentityResolution | None,
) -> str:
    """Put the investor-facing result directly in the successful report heading."""
    return f"{analysis_heading(ticker, label, as_of, identity_resolution)}: {result_text}"


# ---------------------------------------------------------------------------
# Identity / kind / profile
# ---------------------------------------------------------------------------


def identity_detail_lines(resolution: SecurityIdentityResolution | None) -> list[str]:
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


def identity_diagnostic_lines(resolution: SecurityIdentityResolution | None) -> list[str]:
    """Expose identity resolution only as software diagnostics, never warnings."""
    if resolution is None:
        return []
    return [f"security_identity: provider/{resolution.status.value} — {resolution.message}"]


def kind_detail_lines(profile: InstrumentProfile | None) -> list[str]:
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


def profile_diagnostic_lines(
    profile: InstrumentProfile | None,
    identity_resolution: SecurityIdentityResolution | None,
) -> list[str]:
    """Render ordered profile attempts, falling back to the legacy identity diagnostic."""
    if profile is None:
        return identity_diagnostic_lines(identity_resolution)
    return [
        f"{item.capability.value}: {item.provider_id}/{item.status.value} — {item.message}"
        for item in profile.diagnostics
    ]


def profile_diagnostic_payloads(profile: InstrumentProfile | None) -> list[dict[str, str]]:
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


def security_identity_diagnostic_entry(
    instrument_profile: InstrumentProfile | None, identity_resolution: SecurityIdentityResolution | None
) -> list[dict[str, str]]:
    """Return the one-item legacy security-identity diagnostic when no profile diagnostics exist."""
    if (
        instrument_profile is None
        and identity_resolution is not None
        and identity_resolution.status is not IdentityResolutionStatus.RESOLVED
    ):
        return [
            {
                "field_name": "security_identity",
                "stage": "provider",
                "outcome": identity_resolution.status.value,
                "message": identity_resolution.message,
            }
        ]
    return []


def instrument_kind_payload(instrument_profile: InstrumentProfile | None) -> dict[str, Any] | None:
    """Return the instrument-kind evidence payload for one presentation's instrument profile."""
    return instrument_kind_evidence_payload(
        instrument_profile.kind_evidence if instrument_profile is not None else None
    )


# ---------------------------------------------------------------------------
# Resolved-input detail / diagnostics / payload
# ---------------------------------------------------------------------------


def input_line(label: str, value: ResolvedInput | None) -> list[str]:
    """Return the standard investor-facing detail lines for one resolved input."""
    return input_detail_lines(label, value)


def diagnostic_lines(
    trace: ResolutionTrace,
    quote_status: CalculationStatus | None,
    quote_reason: str | None,
) -> list[str]:
    """Render the ordered resolver trace, plus a quote status line when not already traced."""
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
    if quote_status is not None and not any(event.field_name == "current_price" for event in trace.events):
        lines.append(f"current_price: {quote_status.value} — {quote_reason or 'no reason retained'}")
    return lines


def source_summary(inputs: tuple[ResolvedInput | None, ...]) -> str:
    """Summarize each resolved input's source and freshness in one investor-facing line."""
    parts: list[str] = []
    for item in inputs:
        if item is None:
            continue
        label = field_display_name(item.field_name)
        source = source_label(item)
        if item.source_kind is SourceKind.CACHE:
            source = f"{provider_display_name(item.provider_id)} (saved input)"
        parts.append(f"{label} — {source} ({freshness_label(item)})")
    return "; ".join(parts) if parts else "unavailable"


def display_basis(value: ResolvedInput) -> str:
    """Return explicit basis, or infer fiscal-year-end BVPS from its lineage."""
    return financial_basis(value) or "unspecified"


def eps_basis_label(value: ResolvedInput) -> str:
    """Describe EPS basis, preserving whether retained evidence is diluted EPS."""
    if value.basis == "three_year_average":
        qualifier = " diluted" if uses_diluted_eps(value) else ""
        return f"3-year average{qualifier} EPS"
    if value.basis == "ttm":
        return "TTM EPS"
    if value.basis is not None:
        return f"{basis_display_name(value.basis)} EPS"
    return "EPS basis unspecified"


def uses_diluted_eps(value: ResolvedInput) -> bool:
    """Return whether all retained provider-field evidence identifies diluted EPS."""
    fields: list[str] = []
    if value.provider_field is not None:
        fields.append(value.provider_field)
    if value.lineage is not None:
        fields.extend(component.provider_field for component in value.lineage.components if component.provider_field)
    return bool(fields) and all("diluted" in field.lower() for field in fields)


def freshness_label(value: ResolvedInput) -> str:
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


def source_label(value: ResolvedInput) -> str:
    """Return the standard investor-facing source label for one resolved input."""
    return input_source_label(value)


def override_warnings(inputs: tuple[ResolvedInput | None, ...]) -> list[str]:
    """Warn about every user-supplied override among *inputs*."""
    warnings: list[str] = []
    for item in inputs:
        if item is not None and item.source_kind is SourceKind.OVERRIDE:
            label = field_display_name(item.field_name)
            warnings.append(f"{label} is a user override, not provider-verified data.")
    return warnings


def quote_warnings(status: CalculationStatus | None, _reason: str | None) -> list[str]:
    """Warn when a current-quote attempt did not return OK."""
    if status is None:
        return []
    return ["Current quote unavailable; price comparison omitted."]


def resolved_input_payload(value: ResolvedInput | None) -> dict[str, Any] | None:
    """Convert one resolved input to its stable JSON diagnostics shape."""
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
        "observation_period_start": json_datetime(value.observation_period_start),
        "observation_period_end": json_datetime(value.observation_period_end),
        "observed_at": json_datetime(value.observed_at),
        "available_at": json_datetime(value.available_at),
        "as_of": json_datetime(value.as_of),
        "retrieved_at": json_datetime(value.retrieved_at),
        "resolved_at": json_datetime(value.resolved_at),
        "cache_schema_version": value.cache_schema_version,
        "notes": list(value.notes),
        "lineage": None,
    }
    if value.lineage is not None:
        payload["lineage"] = {
            "transformation": value.lineage.transformation,
            "components": [resolved_input_payload(component) for component in value.lineage.components],
        }
    return payload


def trace_payload(trace: ResolutionTrace) -> list[dict[str, str]]:
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


def quote_payload(
    current_price: ResolvedInput | None,
    status: CalculationStatus | None,
    reason: str | None,
) -> dict[str, str | None]:
    """Return the stable quote-attempt payload shape."""
    if status is not None:
        return {"status": status.value, "reason": reason}
    if current_price is not None:
        return {"status": "ok", "reason": None}
    return {"status": "not_attempted", "reason": None}


# ---------------------------------------------------------------------------
# Price-relationship comparison
# ---------------------------------------------------------------------------


def investor_comparison_evidence(comparison: PriceComparison | None) -> list[str]:
    """Render share-unit evidence backing a price comparison, when available."""
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


def comparison_reason(reason: str) -> str:
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


def comparison_payload(comparison: PriceComparison | None) -> dict[str, Any] | None:
    """Convert one price comparison to its stable JSON diagnostics shape."""
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
            "retrieved_at": json_datetime(comparison.quote_freshness.retrieved_at),
            "retrieval_age_seconds": comparison.quote_freshness.retrieval_age_seconds,
            "max_retrieval_age_seconds": comparison.quote_freshness.max_retrieval_age_seconds,
            "market_observed_at": json_datetime(comparison.quote_freshness.market_observed_at),
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


def comparison_details(comparison: PriceComparison | None) -> list[str]:
    """Render diagnostic-mode share-unit comparison evidence lines."""
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


def comparison_lines(  # noqa: PLR0913
    current_price: ResolvedInput | None,
    margin_of_safety_percent: float | None,
    *,
    reference_value: float | None = None,
    valuation_currency: str | None = None,
    reference_label: str,
    comparison: PriceComparison | None = None,
) -> list[str]:
    """Render the concise-mode current-price/price-relationship lines."""
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
        lines.append(f"Price comparison: unavailable ({comparison_reason(comparison.reason)})")
    elif margin_of_safety_percent is None:
        lines.append("Price comparison: unavailable")
    elif margin_of_safety_percent >= 0:
        lines.append(f"Price relationship: {format_number(margin_of_safety_percent)}% below the {reference_label}")
    else:
        lines.append(f"Price relationship: {format_number(abs(margin_of_safety_percent))}% above the {reference_label}")
    return lines


# ---------------------------------------------------------------------------
# Shared validation helpers
# ---------------------------------------------------------------------------


def common_currency(*inputs: ResolvedInput | None) -> str | None:
    """Return one shared known currency, or None when inputs disagree or omit it."""
    currencies = {item.currency for item in inputs if item is not None and item.currency}
    if len(currencies) == 1:
        return next(iter(currencies))
    return None


def validate_presentation_as_of(as_of: datetime | None, *inputs: ResolvedInput | None) -> None:
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


def validate_ticker(ticker: str) -> None:
    """Reject a blank ticker at presentation-construction time."""
    if not ticker.strip():
        msg = "ticker must be a non-empty string."
        raise ValueError(msg)


def validate_margin(
    margin_of_safety_percent: float | None,
    current_price: ResolvedInput | None,
) -> None:
    """Require a finite margin only when a current price backs it."""
    if margin_of_safety_percent is None:
        return
    if current_price is None:
        msg = "margin_of_safety_percent requires a resolved current price."
        raise ValueError(msg)
    if not math.isfinite(margin_of_safety_percent):
        msg = "margin_of_safety_percent must be finite."
        raise ValueError(msg)


def json_datetime(value: datetime | None) -> str | None:
    """Render an optional datetime as its ISO-8601 string, or None."""
    return None if value is None else value.isoformat()
