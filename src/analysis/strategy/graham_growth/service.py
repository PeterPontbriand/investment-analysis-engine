"""Execution service for graham_growth."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from src.analysis.shared.financial_resolution import (
    has_provider_backed_evidence,
    is_known_etf,
    margin_of_safety,
    validate_profile_ticker,
)
from src.analysis.strategy.graham_growth.calculation import (
    GrahamGrowthCalculationPolicy,
    GrahamGrowthInputResolver,
    GrahamGrowthValueResult,
    GrowthValueInputAssembly,
    compute_graham_growth_value,
)
from src.core.analysis_status import CalculationStatus
from src.data.financial.facts import financial_facts_analysis_scope
from src.data.instrument_profile import InstrumentProfile


@dataclass(frozen=True)
class GrahamGrowthAnalysis:
    """Complete typed execution evidence for one Graham growth-value analysis."""

    ticker: str
    as_of: datetime | None
    assembly: GrowthValueInputAssembly
    result: GrahamGrowthValueResult
    policy: GrahamGrowthCalculationPolicy
    margin_of_safety_percent: float | None
    instrument_profile: InstrumentProfile | None = None


def run_graham_growth_analysis(  # noqa: PLR0913
    *,
    resolver: GrahamGrowthInputResolver,
    ticker: str,
    security_provider_id: str,
    quote_provider_id: str,
    eps_basis: str,
    eps_override: float | None,
    expected_growth: float,
    aaa_yield_override: float,
    quote_override: float | None,
    as_of: datetime | None,
    use_cache: bool,
    policy: GrahamGrowthCalculationPolicy,
    instrument_profile: InstrumentProfile | None = None,
) -> GrahamGrowthAnalysis:
    """Resolve and calculate one Graham growth-value analysis without rendering it."""
    validate_profile_ticker(
        ticker,
        instrument_profile,
        mismatch_message="Instrument profile ticker does not match the Graham analysis ticker.",
    )
    if is_known_etf(instrument_profile):
        assembly = GrowthValueInputAssembly(
            status=CalculationStatus.NOT_APPLICABLE,
            reason=_etf_not_applicable_reason("Graham growth-value method"),
        )
    else:
        with financial_facts_analysis_scope(
            resolver.provider,
            subject_id=ticker,
            provider_id=security_provider_id,
            as_of=as_of,
        ):
            assembly = resolver.assemble_growth_value(
                security_subject_id=ticker,
                security_provider_id=security_provider_id,
                eps_basis=eps_basis,
                eps_override=eps_override,
                expected_growth=expected_growth,
                aaa_subject_id="AAA",
                aaa_provider_id="user_override",
                aaa_yield_override=aaa_yield_override,
                quote_override=quote_override,
                quote_provider_id=quote_provider_id,
                as_of=as_of,
                use_cache=use_cache,
            )
    if assembly.status is CalculationStatus.OK and not has_provider_backed_evidence(
        assembly.eps, assembly.current_price
    ):
        assembly = replace(
            assembly,
            status=CalculationStatus.INPUT_UNAVAILABLE,
            reason=_unverified_ticker_reason(ticker),
        )

    if assembly.status is not CalculationStatus.OK:
        result = GrahamGrowthValueResult(
            status=assembly.status,
            reason=assembly.reason or "Required Graham growth-value inputs are unavailable.",
        )
        margin = None
    else:
        assert assembly.eps is not None
        assert assembly.expected_growth is not None
        assert assembly.current_aaa_yield is not None
        result = compute_graham_growth_value(
            normalized_eps=assembly.eps.value,
            expected_growth_rate=assembly.expected_growth.value,
            current_aaa_yield=assembly.current_aaa_yield.value,
            base_pe=policy.base_pe,
            growth_multiplier=policy.growth_multiplier,
            baseline_aaa_yield=policy.baseline_aaa_yield,
        )
        margin = margin_of_safety(
            result.growth_value,
            assembly.current_price,
            valuation_currency=assembly.eps.currency,
            security_unit_evidence=(
                instrument_profile.security_unit_evidence if instrument_profile is not None else None
            ),
            require_security_unit_evidence=instrument_profile is not None,
        )

    return GrahamGrowthAnalysis(
        ticker=ticker,
        as_of=as_of,
        assembly=assembly,
        result=result,
        policy=policy,
        margin_of_safety_percent=margin,
        instrument_profile=instrument_profile,
    )


def _etf_not_applicable_reason(method_name: str) -> str:
    """Explain why a company-level Graham method does not apply to an ETF."""
    return (
        f"{method_name} is a company-level valuation method and does not apply directly to an ETF. "
        "No constituent-level or aggregate ETF valuation was performed."
    )


def _unverified_ticker_reason(ticker: str) -> str:
    """Return the public failure used when only overrides support a ticker."""
    return (
        f"Unable to analyze {ticker}: no provider-backed security fact or quote was resolved. "
        "Fully override-driven security analysis is not accepted in v0.2."
    )
