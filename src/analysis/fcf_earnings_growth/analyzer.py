"""Execution boundary for free-cash-flow and earnings-growth analysis."""

from __future__ import annotations

from datetime import UTC, datetime

from src.analysis.fcf_earnings_growth.calculators import classify_fcf_earnings_growth
from src.analysis.fcf_earnings_growth.input_resolver import ProductionAnnualGrowthSeriesResolver
from src.analysis.fcf_earnings_growth.models import (
    Classification,
    FCFEarningsGrowthPolicy,
    FCFEarningsGrowthResult,
    ForwardEvidence,
    ForwardEvidenceStatus,
    MetricResult,
    MetricStatus,
    ReasonCode,
    TrendClassification,
)
from src.core.analysis_status import CalculationStatus
from src.data.financial.provenance import ResolvedInput


def _unavailable_metric(reason_code: ReasonCode, reason: str) -> MetricResult:
    return MetricResult.failure(MetricStatus.UNAVAILABLE, reason_code, reason)


def _forward_evidence(latest_actual_eps: ResolvedInput | None) -> ForwardEvidence:
    reason = "No evidence-approved FY1/FY2 consensus EPS provider mapping is available."
    unavailable = _unavailable_metric(ReasonCode.CONSENSUS_UNAVAILABLE, reason)
    return ForwardEvidence(
        status=ForwardEvidenceStatus.UNAVAILABLE,
        latest_actual_eps=latest_actual_eps,
        fy1_consensus_eps=None,
        fy2_consensus_eps=None,
        actual_to_fy1_growth=unavailable,
        fy1_to_fy2_growth=unavailable,
        confirms_positive_growth=None,
    )


class FCFEarningsGrowthAnalyzer:
    """Resolve approved inputs and produce the strategy's canonical typed result."""

    def __init__(self, resolver: ProductionAnnualGrowthSeriesResolver) -> None:
        """Initialize the analyzer with its annual-series resolver."""
        self._resolver = resolver

    def run_analysis(  # noqa: PLR0913
        self,
        *,
        ticker: str,
        policy: FCFEarningsGrowthPolicy,
        currency: str,
        as_of: datetime | None,
        provider_id: str,
        use_cache: bool = True,
        effective_as_of: datetime | None = None,
    ) -> FCFEarningsGrowthResult:
        """Run one deterministic analysis without optional unapproved data substitutions."""
        boundary = effective_as_of or as_of or datetime.now(UTC)
        assembly = self._resolver.resolve(
            policy=policy,
            subject_id=ticker,
            currency=currency,
            as_of=as_of,
            provider_id=provider_id,
            use_cache=use_cache,
        )
        latest_eps = assembly.observations[-1].diluted_eps if assembly.observations else None
        forward = _forward_evidence(latest_eps)
        yield_reason = "No evidence-approved market-capitalization provider mapping is available."
        fcf_yield = (
            _unavailable_metric(ReasonCode.MARKET_CAP_UNAVAILABLE, yield_reason)
            if policy.include_fcf_yield
            else MetricResult.failure(
                MetricStatus.NOT_APPLICABLE, ReasonCode.NOT_REQUESTED, "FCF yield was not requested."
            )
        )

        if assembly.status is CalculationStatus.OK:
            decision = classify_fcf_earnings_growth(
                policy=policy,
                fcf_cagr=assembly.fcf_cagr,
                fcf_per_share_cagr=assembly.fcf_per_share_cagr,
                eps_cagr=assembly.eps_cagr,
                forward_evidence=forward,
            )
            classification = decision.classification
            reason_code = decision.reason_code
            reason = decision.reason
            trend = decision.trend_classification
        else:
            classification = Classification.INDETERMINATE
            reason_code = assembly.reason_code or ReasonCode.MISSING_FACT
            reason = assembly.reason or "Required historical evidence is unavailable."
            trend = TrendClassification.INSUFFICIENT_OR_NONMEANINGFUL_GROWTH

        warnings: list[str] = []
        if assembly.used_horizon_fallback:
            warnings.append("Automatic horizon selection fell back because five elapsed years were unavailable.")
        if policy.include_fcf_yield:
            warnings.append(yield_reason)
        if policy.forward_policy.value != "display_only":
            warnings.append("Forward consensus policy was selected, but approved consensus evidence is unavailable.")

        return FCFEarningsGrowthResult(
            ticker=ticker.strip().upper(),
            requested_as_of=as_of,
            effective_as_of=boundary,
            policy=policy,
            execution_status=assembly.status,
            classification=classification,
            classification_reason_code=reason_code,
            classification_reason=reason,
            selected_horizon_years=assembly.selected_horizon_years,
            selected_observation_count=assembly.selected_observation_count,
            used_horizon_fallback=assembly.used_horizon_fallback,
            period_start=assembly.observations[0].period_start if assembly.observations else None,
            period_end=assembly.observations[-1].period_end if assembly.observations else None,
            annual_observations=assembly.observations,
            fcf_cagr=assembly.fcf_cagr,
            fcf_per_share_cagr=assembly.fcf_per_share_cagr,
            eps_cagr=assembly.eps_cagr,
            trend_classification=trend,
            market_capitalization=None,
            fcf_yield=fcf_yield,
            forward_evidence=forward,
            warnings=tuple(warnings),
            diagnostics=assembly.resolution_trace,
        )
