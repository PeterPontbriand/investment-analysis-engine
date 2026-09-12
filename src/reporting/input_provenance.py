"""Financial input explanations preserving source, assumptions and nested lineage."""

from src.data.financial.provenance import ResolvedInput, SourceKind
from src.reporting.presentation import (
    format_date,
    format_number,
    format_utc_minute,
    provider_display_name,
)


def _basis_label(basis: str) -> str:
    return {
        "three_year_average": "3-year average",
        "ttm": "TTM",
        "fiscal_year_end": "fiscal-year-end",
        "fiscal_year": "fiscal year",
        "latest_provider_quote": "latest provider quote",
    }.get(basis, basis)


def financial_basis(value: ResolvedInput) -> str | None:
    """Use an explicit basis or the consistent retained BVPS component basis."""
    if value.basis is not None:
        return value.basis
    if (
        value.field_name == "bvps"
        and value.lineage
        and value.lineage.components
        and {item.basis for item in value.lineage.components} == {"fiscal_year_end"}
    ):
        return "fiscal_year_end"
    return None


def investor_value(value: ResolvedInput) -> str:
    """Format financial magnitudes without implying six-decimal source precision."""
    suffix = " shares" if value.units == "shares" else f" {value.currency or 'currency unknown'}"
    if value.units == "percentage_points":
        return f"{format_number(value.value)}%"
    magnitude = abs(value.value)
    if magnitude >= 1_000_000_000:
        return f"{format_number(value.value / 1_000_000_000, decimals=3)} billion{suffix}"
    if magnitude >= 1_000_000:
        return f"{format_number(value.value / 1_000_000, decimals=3)} million{suffix}"
    return f"{format_number(value.value, decimals=4 if value.units == 'currency_per_share' else 0)}{suffix}"


def investor_input_lines(label: str, value: ResolvedInput | None) -> list[str]:
    """Explain retained calculation inputs once, leaving raw lineage to diagnostics."""
    if value is None:
        return [f"{label}: unavailable — input was not resolved"]
    basis = financial_basis(value)
    if basis is None and value.source_kind is SourceKind.OVERRIDE:
        basis = "user supplied"
    period = f"; period ending {format_date(value.observation_period_end)}" if value.observation_period_end else ""
    lines = [f"{label}: {investor_value(value)} ({_basis_label(basis) if basis else 'basis not retained'}{period})"]
    if value.source_kind is SourceKind.OVERRIDE:
        lines.append("  Assumption supplied by the user; not independently verified.")
    else:
        lines.append(
            f"  Source: {provider_display_name(value.provider_id)}; available: {format_date(value.available_at)}."
        )
    seen: set[str] = set()

    def components(parent: ResolvedInput) -> None:
        if parent.lineage is None:
            return
        for item in parent.lineage.components:
            name = item.field_name.removeprefix("us-gaap:").replace("_", " ")
            name = {
                "eps": "Diluted EPS",
                "CommonStockSharesIssued": "Common shares issued",
                "TreasuryStockCommonShares": "Treasury shares",
            }.get(name, name.capitalize())
            row = f"  {name} ({format_date(item.observation_period_end)}): {investor_value(item)}"
            if row not in seen:
                lines.append(row)
                seen.add(row)
            if item.field_name == "preferred_shares_outstanding" and (item.provider_field or "").startswith(
                "inferred:"
            ):
                lines.append(
                    "  Preferred shares are treated as zero under the application's evidence guard; "
                    "not an explicitly reported zero."
                )
            components(item)

    components(value)
    return lines


def input_source_label(value: ResolvedInput) -> str:
    """Describe acquisition separately from observed, derived or inferred origin."""
    if value.source_kind is SourceKind.OVERRIDE:
        return "user override"
    provider = provider_display_name(value.provider_id)
    origin = value.origin_source_kind if value.source_kind is SourceKind.CACHE else value.source_kind
    inferred = (value.provider_field or "").startswith("inferred:")
    if value.source_kind is SourceKind.CACHE:
        label = "inferred" if inferred else origin.value if origin is not None else "unknown"
        return f"cache (original={label}, provider={provider})"
    if inferred:
        return f"inferred ({provider})"
    if origin is SourceKind.DERIVED:
        providers = (
            sorted({provider_display_name(item.provider_id) for item in value.lineage.components if item.provider_id})
            if value.lineage
            else []
        )
        return f"derived from {', '.join(providers) if providers else provider}"
    if (value.provider_field or "").startswith("derived:"):
        return f"provider-derived ({provider})"
    return f"provider ({provider})"


def input_detail_lines(label: str, value: ResolvedInput | None) -> list[str]:
    """Render retained facts recursively without manufacturing absent metadata."""
    if value is None:
        return [f"{label}: unavailable — input was not resolved"]
    override = value.source_kind is SourceKind.OVERRIDE
    point = value.field_name == "current_price"
    annual = value.observation_period_end is not None
    inapplicable = "not applicable — point quote" if point else "not applicable — user supplied" if override else None
    field = value.provider_field or (
        "not applicable — derived from the listed components"
        if value.lineage
        else "not applicable — user supplied"
        if override
        else "not supplied by provider"
    )
    missing = "not supplied by provider"
    retained_basis = financial_basis(value)
    basis = _basis_label(retained_basis) if retained_basis else missing
    if not value.basis and (point or override):
        basis = "latest provider quote" if point else "user supplied"
    currency = value.currency or ("not applicable — share count" if value.units == "shares" else missing)
    period_start = inapplicable or missing
    if annual and value.observation_period_start is None:
        period_start = "not applicable — fiscal-year-end snapshot"
    if value.observation_period_start is not None:
        period_start = format_date(value.observation_period_start)
    period_end = format_date(value.observation_period_end) if annual else inapplicable or missing
    observed = "not provider verified"
    if annual:
        observed = "not applicable — annual financial statement"
    elif point:
        observed = "market observation time not supplied"
    if value.observed_at is not None:
        observed = format_utc_minute(value.observed_at)
    available = "not provider verified" if override else missing
    if value.available_at is not None:
        available = format_utc_minute(value.available_at)
    retrieved = "not applicable — user supplied" if override else "not retained"
    if value.retrieved_at is not None:
        retrieved = format_utc_minute(value.retrieved_at)
    lines = [
        f"{label}: {format_number(value.value, decimals=6)}",
        f"  basis: {basis}",
        f"  units: {value.units.replace('_', ' ') if value.units else missing}",
        f"  currency: {currency}",
        f"  source: {input_source_label(value)}",
        f"  provider: {'not applicable — user supplied' if override else provider_display_name(value.provider_id)}",
        f"  provider field: {field}",
        f"  period start: {period_start}",
        f"  period end: {period_end}",
        f"  observed at: {observed}",
        f"  available at: {available}",
        f"  retrieved at: {retrieved}",
    ]
    if value.notes:
        lines.append(f"  notes: {'; '.join(value.notes)}")
    if value.lineage is not None:
        lines.append(f"  derivation: {value.lineage.transformation}")
        for index, component in enumerate(value.lineage.components, start=1):
            lines.append(f"  component {index}:")
            lines.append(f"    field name: {component.field_name}")
            lines.extend(f"    {line}" for line in input_detail_lines("value", component))
    return lines
