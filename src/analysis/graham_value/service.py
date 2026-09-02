"""Reusable execution services for the two Graham analysis methods."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import datetime

from src.analysis.graham_value.calculators import compute_graham_growth_value, compute_graham_number
from src.analysis.graham_value.input_resolver import (
    GrahamInputResolver,
    GrahamNumberInputAssembly,
    GrowthValueInputAssembly,
)
from src.analysis.graham_value.models import GrahamGrowthValueResult, GrahamNumberResult
from src.core.analysis_status import CalculationStatus
from src.data.financial.facts import financial_facts_analysis_scope
from src.data.financial.provenance import ResolvedInput, SourceKind
from src.data.instrument_profile import InstrumentKind, InstrumentProfile
from src.data.security_unit import SecurityUnitEvidence, evaluate_security_unit_compatibility


@dataclass(frozen=True)
class GrahamGrowthCalculationPolicy:
    """Configured constants used by the Graham growth-value calculation."""

    base_pe: float
    growth_multiplier: float
    baseline_aaa_yield: float

    def __post_init__(self) -> None:
        """Reject non-finite or financially invalid calculation constants."""
        values = (self.base_pe, self.growth_multiplier, self.baseline_aaa_yield)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Graham growth calculation constants must be finite.")
        if self.base_pe <= 0:
            raise ValueError("Graham growth base_pe must be positive.")
        if self.growth_multiplier < 0:
            raise ValueError("Graham growth growth_multiplier must be non-negative.")
        if self.baseline_aaa_yield <= 0:
            raise ValueError("Graham growth baseline_aaa_yield must be positive.")


@dataclass(frozen=True)
class GrahamNumberAnalysis:
    """Complete typed execution evidence for one Graham Number analysis."""

    ticker: str
    as_of: datetime | None
    assembly: GrahamNumberInputAssembly
    result: GrahamNumberResult
    margin_of_safety_percent: float | None
    instrument_profile: InstrumentProfile | None = None


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


def run_graham_number_analysis(  # noqa: PLR0913
    *,
    resolver: GrahamInputResolver,
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
    _validate_profile_ticker(ticker, instrument_profile)
    if _is_known_etf(instrument_profile):
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
    if assembly.status is CalculationStatus.OK and not _has_provider_backed_security_evidence(
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
        margin = _margin_of_safety(
            result.maximum_indicated_price,
            assembly.current_price,
            valuation_currency=_common_currency(assembly.eps, assembly.bvps),
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


def run_graham_growth_analysis(  # noqa: PLR0913
    *,
    resolver: GrahamInputResolver,
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
    _validate_profile_ticker(ticker, instrument_profile)
    if _is_known_etf(instrument_profile):
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
    if assembly.status is CalculationStatus.OK and not _has_provider_backed_security_evidence(
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
        margin = _margin_of_safety(
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


def _validate_profile_ticker(ticker: str, profile: InstrumentProfile | None) -> None:
    """Reject accidental reuse of evidence for another requested instrument."""
    if profile is not None and profile.ticker != ticker.strip().upper():
        raise ValueError("Instrument profile ticker does not match the Graham analysis ticker.")


def _is_known_etf(profile: InstrumentProfile | None) -> bool:
    """Return whether affirmative provider evidence classifies the instrument as an ETF."""
    return (
        profile is not None and profile.kind_evidence is not None and profile.kind_evidence.kind is InstrumentKind.ETF
    )


def _etf_not_applicable_reason(method_name: str) -> str:
    """Explain why a company-level Graham method does not apply to an ETF."""
    return (
        f"{method_name} is a company-level valuation method and does not apply directly to an ETF. "
        "No constituent-level or aggregate ETF valuation was performed."
    )


def _has_provider_backed_security_evidence(*inputs: ResolvedInput | None) -> bool:
    """Return whether at least one security fact carries non-override provenance."""
    return any(value is not None and value.source_kind is not SourceKind.OVERRIDE for value in inputs)


def _unverified_ticker_reason(ticker: str) -> str:
    """Return the public failure used when only overrides support a ticker."""
    return (
        f"Unable to analyze {ticker}: no provider-backed security fact or quote was resolved. "
        "Fully override-driven security analysis is not accepted in v0.2."
    )


def _margin_of_safety(
    reference_value: float | None,
    current_price: ResolvedInput | None,
    *,
    valuation_currency: str | None = None,
    security_unit_evidence: SecurityUnitEvidence | None = None,
    require_security_unit_evidence: bool = False,
) -> float | None:
    """Compute comparison only when value, quote, and known currencies are compatible."""
    if reference_value is None or current_price is None or reference_value <= 0:
        return None
    if (
        require_security_unit_evidence
        and not evaluate_security_unit_compatibility(
            security_unit_evidence,
            filing_currency=valuation_currency,
            quote_currency=current_price.currency,
        ).is_compatible
    ):
        return None
    if (
        valuation_currency is not None
        and current_price.currency is not None
        and valuation_currency != current_price.currency
    ):
        return None
    margin = ((reference_value - current_price.value) / reference_value) * 100.0
    return margin if math.isfinite(margin) else None


def _common_currency(*inputs: ResolvedInput | None) -> str | None:
    """Return one shared known currency, or None when inputs disagree or omit it."""
    currencies = {item.currency for item in inputs if item is not None and item.currency}
    return next(iter(currencies)) if len(currencies) == 1 else None
