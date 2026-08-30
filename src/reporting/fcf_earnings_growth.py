"""Investor-facing presentation for free-cash-flow and earnings growth."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from src.analysis.fcf_earnings_growth.models import (
    FCFClassificationBasis,
    FCFEarningsGrowthResult,
    ForwardEvidenceStatus,
    MetricResult,
    MetricStatus,
    TrendClassification,
)
from src.data.financial.provenance import ResolvedInput
from src.data.security_identity import (
    IdentityResolutionStatus,
    SecurityIdentityResolution,
    security_display_label,
    security_identity_payload,
)
from src.reporting.presentation import (
    PresentationMode,
    format_date,
    format_datetime,
    format_money,
    format_number,
    json_document,
    provider_display_name,
)

_LIMITATION = (
    "Historical financial strength does not establish market opportunity, scarcity, durability of moat, "
    "or an investment recommendation."
)

# The calculation result remains schema v2.  Adding the run-time identity
# snapshot changes only this machine-readable presentation contract.
_PRESENTATION_SCHEMA_VERSION = 3

_TREND_LABELS = {
    TrendClassification.BOTH_GROWING: "Both free cash flow and diluted EPS increased over the measured period.",
    TrendClassification.FCF_GROWING_EARNINGS_NOT: "Free cash flow increased, but diluted EPS did not.",
    TrendClassification.EARNINGS_GROWING_FCF_NOT: "Diluted EPS increased, but free cash flow did not.",
    TrendClassification.NEITHER_GROWING: "Neither free cash flow nor diluted EPS increased.",
    TrendClassification.INSUFFICIENT_OR_NONMEANINGFUL_GROWTH: (
        "Growth is insufficient or mathematically nonmeaningful for this screen."
    ),
}

_CLASSIFICATION_BASIS_LABELS = {
    FCFClassificationBasis.TOTAL_FCF: "Total company free cash flow",
    FCFClassificationBasis.FCF_PER_SHARE: "Free cash flow per diluted share",
}


def _metric(metric: MetricResult) -> str:
    if metric.status is MetricStatus.OK and metric.value is not None:
        return f"{metric.value:+.2f}%"
    return f"unavailable — {metric.reason or 'No meaningful value is available.'}"


def _period_line(result: FCFEarningsGrowthResult) -> str:
    if (
        result.period_start is None
        or result.period_end is None
        or result.selected_horizon_years is None
        or not result.annual_observations
    ):
        return "Period: unavailable"
    fallback = "; automatic fallback used" if result.used_horizon_fallback else ""
    first_fiscal_year = result.annual_observations[0].fiscal_year
    last_fiscal_year = result.annual_observations[-1].fiscal_year
    return (
        f"Period: FY{first_fiscal_year}–FY{last_fiscal_year} "
        f"({result.selected_horizon_years} elapsed years; "
        f"{result.selected_observation_count} annual observations{fallback})"
    )


def _source_summary(result: FCFEarningsGrowthResult) -> str:
    providers = sorted(
        {
            provider_display_name(item.provider_id)
            for observation in result.annual_observations
            for item in (
                observation.operating_cash_flow,
                observation.normalized_capital_expenditures,
                observation.diluted_eps,
                observation.weighted_average_diluted_shares,
            )
            if item is not None and item.provider_id is not None
        }
    )
    provider_text = ", ".join(providers) if providers else "unavailable"
    latest = max(
        (
            item.available_at
            for observation in result.annual_observations
            for item in (
                observation.operating_cash_flow,
                observation.normalized_capital_expenditures,
                observation.diluted_eps,
                observation.weighted_average_diluted_shares,
            )
            if item is not None and item.available_at is not None
        ),
        default=None,
    )
    return f"Source: {provider_text}; latest evidence available {format_date(latest)}"


def _concise(
    result: FCFEarningsGrowthResult,
    identity_resolution: SecurityIdentityResolution | None,
) -> list[str]:
    lines = [
        f"{security_display_label(result.ticker, identity_resolution)} — Free Cash Flow & Earnings Growth",
        "",
        f"Screen: {result.classification.value.upper()}",
        f"Classification basis: {_CLASSIFICATION_BASIS_LABELS[result.policy.classification_basis]}",
    ]
    if result.classification_reason:
        lines.append(f"Reason: {result.classification_reason}")
    lines.append(_period_line(result))
    if result.annual_observations:
        latest = result.annual_observations[-1]
        latest_fcf = format_money(latest.free_cash_flow.value, latest.free_cash_flow.currency)
        lines.append(f"Free cash flow (FY{latest.fiscal_year}): {latest_fcf}")
        if latest.free_cash_flow_per_diluted_share is not None:
            latest_per_share = format_money(
                latest.free_cash_flow_per_diluted_share.value,
                latest.free_cash_flow_per_diluted_share.currency,
            )
            lines.append(f"FCF per diluted share (FY{latest.fiscal_year}): {latest_per_share}")
    lines.extend(
        (
            f"Free cash flow CAGR: {_metric(result.fcf_cagr)}",
            f"FCF per diluted share CAGR: {_metric(result.fcf_per_share_cagr)}",
            f"Diluted EPS CAGR: {_metric(result.eps_cagr)}",
            f"Trend: {_TREND_LABELS[result.trend_classification]}",
        )
    )
    if result.policy.include_fcf_yield and result.fcf_yield.status is MetricStatus.OK:
        lines.append(f"FCF yield: {_metric(result.fcf_yield)}")
    if (
        result.forward_evidence.status is not ForwardEvidenceStatus.UNAVAILABLE
        or result.policy.forward_policy.value != "display_only"
    ):
        lines.append(
            f"Forward EPS: {result.forward_evidence.status.value.replace('_', ' ')} "
            f"({result.policy.forward_policy.value.replace('_', ' ')})"
        )
    lines.append(_source_summary(result))
    lines.extend(f"Warning: {warning}" for warning in result.warnings)
    lines.append(f"Limitation: {_LIMITATION}")
    return lines


def _input_details(label: str, value: ResolvedInput) -> list[str]:
    return [
        f"  {label}: {format_number(value.value)} {value.units or ''}".rstrip(),
        f"    provider: {provider_display_name(value.provider_id)}",
        f"    provider field: {value.provider_field or 'unavailable'}",
        f"    available: {format_datetime(value.available_at)}",
        f"    retrieved: {format_datetime(value.retrieved_at)}",
    ]


def _details(
    result: FCFEarningsGrowthResult,
    identity_resolution: SecurityIdentityResolution | None,
) -> list[str]:
    lines = [*_concise(result, identity_resolution), "", "Details"]
    lines.extend(_identity_detail_lines(identity_resolution))
    for observation in result.annual_observations:
        period_start = format_date(observation.period_start)
        period_end = format_date(observation.period_end)
        lines.append(f"FY{observation.fiscal_year} ({period_start} to {period_end})")
        lines.extend(_input_details("Operating cash flow", observation.operating_cash_flow))
        lines.extend(_input_details("Normalized capital expenditures", observation.normalized_capital_expenditures))
        lines.extend(_input_details("Diluted EPS", observation.diluted_eps))
        if observation.weighted_average_diluted_shares is not None:
            lines.extend(_input_details("Weighted-average diluted shares", observation.weighted_average_diluted_shares))
        derived_fcf = format_money(observation.free_cash_flow.value, observation.free_cash_flow.currency)
        lines.append(f"  Derived free cash flow: {derived_fcf}")
        if observation.free_cash_flow.lineage is not None:
            lines.append(f"    derivation: {observation.free_cash_flow.lineage.transformation}")
        if observation.free_cash_flow_per_diluted_share is not None:
            derived_per_share = format_money(
                observation.free_cash_flow_per_diluted_share.value,
                observation.free_cash_flow_per_diluted_share.currency,
            )
            lines.append(f"  Derived FCF per diluted share: {derived_per_share}")
            if observation.free_cash_flow_per_diluted_share.lineage is not None:
                lines.append(f"    derivation: {observation.free_cash_flow_per_diluted_share.lineage.transformation}")
    return lines


def _diagnostics(
    result: FCFEarningsGrowthResult,
    identity_resolution: SecurityIdentityResolution | None,
) -> list[str]:
    lines = [
        *_concise(result, identity_resolution),
        "",
        "Diagnostics",
        f"Execution status: {result.execution_status.value}",
    ]
    if not result.diagnostics.events:
        lines.append("No execution trace was retained.")
    else:
        lines.extend(
            f"- {event.field_name}: {event.stage.value}/{event.outcome.value} — {event.message}"
            for event in result.diagnostics.events
        )
    if identity_resolution is not None:
        lines.append(
            f"- security_identity: provider/{identity_resolution.status.value} — {identity_resolution.message}"
        )
    return lines


def _identity_detail_lines(resolution: SecurityIdentityResolution | None) -> list[str]:
    """Describe current identity metadata separately from historical facts."""
    if resolution is None or resolution.identity is None:
        return ["Security identity: unavailable"]
    identity = resolution.identity
    return [
        f"Instrument name: {identity.instrument_name or 'unavailable'}",
        f"Listing venue: {identity.listing_venue or 'unavailable'}",
        f"Identity provider: {provider_display_name(identity.provider_id)}",
        f"Identity resolved: {format_datetime(identity.resolved_at)} (current descriptive metadata)",
    ]


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {key: _json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def render_fcf_earnings_growth(
    result: FCFEarningsGrowthResult,
    mode: PresentationMode,
    identity_resolution: SecurityIdentityResolution | None = None,
) -> str:
    """Render one canonical result without recalculation or reclassification."""
    if mode is PresentationMode.JSON:
        payload = _json_value(result)
        assert isinstance(payload, dict)
        payload["schema_version"] = _PRESENTATION_SCHEMA_VERSION
        payload["result_schema_version"] = result.schema_version
        payload["security_identity"] = security_identity_payload(result.ticker, identity_resolution)
        if identity_resolution is not None and identity_resolution.status is not IdentityResolutionStatus.RESOLVED:
            diagnostics = payload.get("diagnostics")
            if isinstance(diagnostics, dict):
                events = diagnostics.get("events")
                if isinstance(events, list):
                    events.append(
                        {
                            "field_name": "security_identity",
                            "stage": "provider",
                            "outcome": identity_resolution.status.value,
                            "message": identity_resolution.message,
                        }
                    )
        return json_document(payload)
    if mode is PresentationMode.DETAILS:
        return "\n".join(_details(result, identity_resolution))
    if mode is PresentationMode.DIAGNOSTICS:
        return "\n".join(_diagnostics(result, identity_resolution))
    return "\n".join(_concise(result, identity_resolution))
