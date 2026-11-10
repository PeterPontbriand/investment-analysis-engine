"""Execution service for graham_growth."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from investment_analysis_engine.analysis.shared.anchor_filing import assess_anchor_filing
from investment_analysis_engine.analysis.shared.financial_resolution import (
    PriceComparison,
    evaluate_price_comparison,
    has_provider_backed_evidence,
    is_known_etf,
    validate_profile_ticker,
)
from investment_analysis_engine.analysis.shared.metric_inputs import anchor_year_end_scope
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.data.financial.facts import financial_facts_analysis_scope
from investment_analysis_engine.data.instrument_profile import InstrumentProfile, complete_security_unit_profile
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID, AnchorYearEnd
from investment_analysis_engine.data.security_unit import SecurityUnitRequest
from investment_analysis_engine.strategies._graham.anchor_years import anchor_stop
from investment_analysis_engine.strategies.graham_growth.calculation import (
    GrahamGrowthCalculationPolicy,
    GrahamGrowthInputResolver,
    GrahamGrowthValueResult,
    GrowthValueInputAssembly,
    compute_graham_growth_value,
)


@dataclass(frozen=True)
class GrahamGrowthAnalysis:
    """Complete typed execution evidence for one Graham growth-value analysis."""

    ticker: str
    as_of: datetime | None
    effective_as_of: datetime
    assembly: GrowthValueInputAssembly
    result: GrahamGrowthValueResult
    policy: GrahamGrowthCalculationPolicy
    margin_of_safety_percent: float | None
    instrument_profile: InstrumentProfile | None = None
    price_comparison: PriceComparison | None = None

    @property
    def native_status(self) -> CalculationStatus:
        """Return the assembly's status, or the calculation's when the assembly succeeded."""
        status = self.assembly.status
        return self.result.status if status is CalculationStatus.OK else status


def run_graham_growth_analysis(  # noqa: PLR0913
    *,
    resolver: GrahamGrowthInputResolver,
    ticker: str,
    eps_basis: str,
    eps_override: float | None,
    expected_growth: float,
    aaa_yield_override: float,
    quote_override: float | None,
    as_of: datetime | None,
    effective_as_of: datetime,
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

        def assemble(anchor: AnchorYearEnd | None) -> GrowthValueInputAssembly:
            """Assemble the inputs at the anchor, and report the anchor whatever the outcome."""
            assembled = resolver.assemble_growth_value(
                security_subject_id=ticker,
                anchor=anchor,
                eps_basis=eps_basis,
                eps_override=eps_override,
                expected_growth=expected_growth,
                aaa_yield_override=aaa_yield_override,
                quote_override=quote_override,
                as_of=as_of,
                use_cache=use_cache,
            )
            if anchor is not None:
                assembled = replace(assembled, anchor_filing=assess_anchor_filing(anchor, effective_as_of))
            return assembled

        def completed(
            profile: InstrumentProfile | None, assembled: GrowthValueInputAssembly
        ) -> InstrumentProfile | None:
            """Complete the profile's security-unit evidence from a successful assembly."""
            if profile is None or assembled.status is not CalculationStatus.OK or assembled.current_price is None:
                return profile
            return complete_security_unit_profile(
                profile,
                resolver.provider,
                SecurityUnitRequest(
                    ticker,
                    SEC_PROVIDER_ID,
                    as_of,
                    tuple(value for value in (assembled.eps,) if value is not None),
                    assembled.current_price,
                ),
            )

        if eps_override is not None:
            # EPS is overridden, so no anchor is requested and there is none to report. The plain analysis scope is
            # still open, so the share-unit check of a run with a quote reads the latest annual filing.
            with financial_facts_analysis_scope(
                resolver.provider, subject_id=ticker, provider_id=SEC_PROVIDER_ID, as_of=as_of
            ):
                assembly = assemble(None)
                instrument_profile = completed(instrument_profile, assembly)
        else:
            with anchor_year_end_scope(resolver, ticker=ticker, as_of=as_of) as anchor:
                if isinstance(anchor, AnchorYearEnd):
                    assembly = assemble(anchor)
                    instrument_profile = completed(instrument_profile, assembly)
                else:
                    stop = anchor_stop(anchor)
                    assembly = GrowthValueInputAssembly(
                        status=stop.status,
                        reason=stop.reason,
                        provider_failure=stop.provider_failure,
                        reason_code=stop.reason_code,
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
        comparison = evaluate_price_comparison(None, assembly.current_price)
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
        comparison = evaluate_price_comparison(
            result.growth_value,
            assembly.current_price,
            valuation_currency=assembly.eps.currency,
            security_unit_evidence=(
                instrument_profile.security_unit_evidence if instrument_profile is not None else None
            ),
            require_security_unit_evidence=instrument_profile is not None,
            security_unit_resolution=(instrument_profile.security_unit_resolution if instrument_profile else None),
        )

    comparison = replace(comparison, quote_freshness=assembly.quote_freshness)

    return GrahamGrowthAnalysis(
        ticker=ticker,
        as_of=as_of,
        effective_as_of=effective_as_of,
        assembly=assembly,
        result=result,
        policy=policy,
        margin_of_safety_percent=comparison.percent,
        price_comparison=comparison,
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
