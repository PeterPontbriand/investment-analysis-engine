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
from src.data.instrument_profile import InstrumentKind, InstrumentProfile


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


def _etf_not_applicable_forward(reason: str) -> ForwardEvidence:
    """Return coherent forward metrics when this company-level strategy does not apply."""
    metric = MetricResult.failure(
        MetricStatus.NOT_APPLICABLE,
        ReasonCode.INSTRUMENT_KIND_NOT_APPLICABLE,
        reason,
    )
    return ForwardEvidence(
        status=ForwardEvidenceStatus.UNAVAILABLE,
        latest_actual_eps=None,
        fy1_consensus_eps=None,
        fy2_consensus_eps=None,
        actual_to_fy1_growth=metric,
        fy1_to_fy2_growth=metric,
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
        instrument_profile: InstrumentProfile | None = None,
    ) -> FCFEarningsGrowthResult:
        """Run one deterministic analysis without optional unapproved data substitutions."""
        boundary = effective_as_of or as_of or datetime.now(UTC)
        normalized_ticker = ticker.strip().upper()
        if instrument_profile is not None and instrument_profile.ticker != normalized_ticker:
            raise ValueError("Instrument profile ticker does not match the FCF & Earnings Growth analysis ticker.")
        if (
            instrument_profile is not None
            and instrument_profile.kind_evidence is not None
            and instrument_profile.kind_evidence.kind is InstrumentKind.ETF
        ):
            return _etf_not_applicable_result(
                ticker=normalized_ticker,
                policy=policy,
                requested_as_of=as_of,
                effective_as_of=boundary,
                instrument_profile=instrument_profile,
            )
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
            instrument_profile=instrument_profile,
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


def _etf_not_applicable_result(
    *,
    ticker: str,
    policy: FCFEarningsGrowthPolicy,
    requested_as_of: datetime | None,
    effective_as_of: datetime,
    instrument_profile: InstrumentProfile,
) -> FCFEarningsGrowthResult:
    """Build the native completed outcome for a provider-confirmed ETF."""
    reason = (
        "Reported company free-cash-flow and diluted-EPS growth analysis does not apply directly to an ETF. "
        "No holdings-level or aggregate ETF analysis was performed."
    )
    metric = MetricResult.failure(
        MetricStatus.NOT_APPLICABLE,
        ReasonCode.INSTRUMENT_KIND_NOT_APPLICABLE,
        reason,
    )
    fcf_yield = (
        metric
        if policy.include_fcf_yield
        else MetricResult.failure(MetricStatus.NOT_APPLICABLE, ReasonCode.NOT_REQUESTED, "FCF yield was not requested.")
    )
    return FCFEarningsGrowthResult(
        ticker=ticker,
        requested_as_of=requested_as_of,
        effective_as_of=effective_as_of,
        policy=policy,
        instrument_profile=instrument_profile,
        execution_status=CalculationStatus.NOT_APPLICABLE,
        classification=Classification.INDETERMINATE,
        classification_reason_code=ReasonCode.INSTRUMENT_KIND_NOT_APPLICABLE,
        classification_reason=reason,
        selected_horizon_years=None,
        selected_observation_count=0,
        used_horizon_fallback=False,
        period_start=None,
        period_end=None,
        annual_observations=(),
        fcf_cagr=metric,
        fcf_per_share_cagr=metric,
        eps_cagr=metric,
        trend_classification=TrendClassification.INSUFFICIENT_OR_NONMEANINGFUL_GROWTH,
        market_capitalization=None,
        fcf_yield=fcf_yield,
        forward_evidence=_etf_not_applicable_forward(reason),
        warnings=(),
    )
