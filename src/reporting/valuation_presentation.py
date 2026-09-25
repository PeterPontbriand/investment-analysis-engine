"""Shared valuation-presentation primitives: price comparison, margin, and EPS-basis display.

Strategy-neutral by design, matching `src/analysis/shared/financial_resolution.py` on the
calculation side — every reference-value-vs-current-price screen (Graham Number, Graham Growth
Value today; NCAV, EPV, reverse DCF later) presents the same price-relationship evidence the same
way. General evidence display (status/heading prose, identity/profile lines and payloads,
diagnostics, source/freshness labels, resolved-input detail/payload, and display-name lookups)
lives in the narrower-scoped `src/reporting/evidence_presentation.py` instead — those concerns
apply to every strategy, not only ones that compare a reference value against a current price.
"""

from __future__ import annotations

import math
from typing import Any

from src.analysis.shared.financial_resolution import PriceComparison
from src.core.analysis_status import CalculationStatus
from src.data.financial.provenance import ResolvedInput, SourceKind
from src.data.financial.quote_freshness import evaluate_quote_freshness
from src.reporting.evidence_presentation import basis_display_name, json_datetime
from src.reporting.presentation import (
    format_date,
    format_money,
    format_number,
    format_utc_minute,
    provider_display_name,
)

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


# ---------------------------------------------------------------------------
# EPS-basis display
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Quote warnings / payload
# ---------------------------------------------------------------------------


def quote_warnings(status: CalculationStatus | None, _reason: str | None) -> list[str]:
    """Warn when a current-quote attempt did not return OK."""
    if status is None:
        return []
    return ["Current quote unavailable; price comparison omitted."]


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
# Margin validation
# ---------------------------------------------------------------------------


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
