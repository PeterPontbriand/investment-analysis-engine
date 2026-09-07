"""Execution service for graham_number."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from src.analysis.shared.financial_resolution import (
    common_currency,
    has_provider_backed_evidence,
    is_known_etf,
    margin_of_safety,
    validate_profile_ticker,
)
from src.analysis.strategy.graham_number.calculation import (
    GrahamNumberInputAssembly,
    GrahamNumberInputResolver,
    GrahamNumberResult,
    compute_graham_number,
)
from src.core.analysis_status import CalculationStatus
from src.data.financial.facts import financial_facts_analysis_scope
from src.data.instrument_profile import InstrumentProfile


@dataclass(frozen=True)
class GrahamNumberAnalysis:
    """Complete typed execution evidence for one Graham Number analysis."""

    ticker: str
    as_of: datetime | None
    assembly: GrahamNumberInputAssembly
    result: GrahamNumberResult
    margin_of_safety_percent: float | None
    instrument_profile: InstrumentProfile | None = None


def run_graham_number_analysis(  # noqa: PLR0913
    *,
    resolver: GrahamNumberInputResolver,
    ticker: str,
    security_provider_id: str,
    quote_provider_id: str,
    eps_basis: str,
    eps_override: float | None,
    bvps_override: float | None,
    quote_override: float | None,
    as_of: datetime | None,
    use_cache: bool,
    instrument_profile: InstrumentProfile | None = None,
) -> GrahamNumberAnalysis:
    """Resolve and calculate one Graham Number analysis without rendering it."""
    validate_profile_ticker(
        ticker,
        instrument_profile,
        mismatch_message="Instrument profile ticker does not match the Graham analysis ticker.",
    )
    if is_known_etf(instrument_profile):
        assembly = GrahamNumberInputAssembly(
            status=CalculationStatus.NOT_APPLICABLE,
            reason=_etf_not_applicable_reason("Graham Number"),
        )
    else:
        with financial_facts_analysis_scope(
            resolver.provider,
            subject_id=ticker,
            provider_id=security_provider_id,
            as_of=as_of,
        ):
            assembly = resolver.assemble_graham_number(
                security_subject_id=ticker,
                security_provider_id=security_provider_id,
                eps_basis=eps_basis,
                eps_override=eps_override,
                bvps_override=bvps_override,
                quote_override=quote_override,
                quote_provider_id=quote_provider_id,
                as_of=as_of,
                use_cache=use_cache,
            )
    if assembly.status is CalculationStatus.OK and not has_provider_backed_evidence(
        assembly.eps, assembly.bvps, assembly.current_price
    ):
        assembly = replace(
            assembly,
            status=CalculationStatus.INPUT_UNAVAILABLE,
            reason=_unverified_ticker_reason(ticker),
        )

    if assembly.status is not CalculationStatus.OK:
        result = GrahamNumberResult(
            status=assembly.status,
            reason=assembly.reason or "Required Graham Number inputs are unavailable.",
        )
        margin = None
    else:
        assert assembly.eps is not None
        assert assembly.bvps is not None
        result = compute_graham_number(assembly.eps.value, assembly.bvps.value)
        margin = margin_of_safety(
            result.maximum_indicated_price,
            assembly.current_price,
            valuation_currency=common_currency(assembly.eps, assembly.bvps),
            security_unit_evidence=(
                instrument_profile.security_unit_evidence if instrument_profile is not None else None
            ),
            require_security_unit_evidence=instrument_profile is not None,
        )

    return GrahamNumberAnalysis(
        ticker=ticker,
        as_of=as_of,
        assembly=assembly,
        result=result,
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
