"""Execution boundary for free-cash-flow and earnings-growth analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext, BaseAnalyzer, require_ticker
from investment_analysis_engine.analysis.shared.cash_flow import compute_fcf_yield
from investment_analysis_engine.analysis.shared.financial_resolution import is_known_etf, validate_profile_ticker
from investment_analysis_engine.analysis.shared.market_cap import MarketCapEvidence
from investment_analysis_engine.analysis.shared.metric_evidence import InputUnavailable
from investment_analysis_engine.analysis.shared.metric_inputs import (
    MetricInputsFailure,
    anchor_year_end_scope,
    resolve_market_cap_inputs,
)
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.metric_result import MetricResult, MetricStatus, ReasonCode
from investment_analysis_engine.data.financial.provenance import ResolvedInput
from investment_analysis_engine.data.financial.resolver import InputResolver
from investment_analysis_engine.data.instrument_profile import InstrumentProfile
from investment_analysis_engine.data.market_data import DatedSplitAdjustedHistoryProvider
from investment_analysis_engine.data.sec_edgar.cover_listing import CoverListingProvider
from investment_analysis_engine.data.sec_edgar.financial_facts import AnchorYearEnd
from investment_analysis_engine.data.yfinance.client import YFINANCE_PROVIDER_ID
from investment_analysis_engine.strategies.fcf_growth.calculators import classify_fcf_earnings_growth
from investment_analysis_engine.strategies.fcf_growth.input_resolver import ProductionAnnualGrowthSeriesResolver
from investment_analysis_engine.strategies.fcf_growth.models import (
    AnnualGrowthObservation,
    FCFEarningsGrowthConfig,
    FCFEarningsGrowthPolicy,
    FCFEarningsGrowthResult,
    ForwardEvidence,
)
from investment_analysis_engine.strategies.fcf_growth.vocabulary import (
    Classification,
    ForwardEvidenceStatus,
    TrendClassification,
)


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


@dataclass(frozen=True)
class MarketCapDependencies:
    """What the optional FCF yield needs to value the company at the boundary, composed once per run.

    Attributes:
        resolver: Resolves the share counts and the current quote.
        split_history: Gives the split-adjusted close and the split history.
        listing: Reads the anchor filing's cover for the listing check.
    """

    resolver: InputResolver
    split_history: DatedSplitAdjustedHistoryProvider
    listing: CoverListingProvider


@dataclass(frozen=True)
class _YieldOutcome:
    """The market-capitalization evidence, the yield and the warnings the yield adds to the result."""

    market_capitalization: MarketCapEvidence | None
    fcf_yield: MetricResult
    warnings: tuple[str, ...] = ()


def _yield_outcome(market_capitalization: MarketCapEvidence | None, fcf_yield: MetricResult) -> _YieldOutcome:
    """Return the outcome, with a warning stating why the yield is not a number."""
    if fcf_yield.status is MetricStatus.OK:
        return _YieldOutcome(market_capitalization, fcf_yield)
    return _YieldOutcome(market_capitalization, fcf_yield, (f"FCF yield is unavailable: {fcf_yield.reason}",))


def _failure_yield(failure: MetricInputsFailure) -> _YieldOutcome:
    """Return the outcome of a market-data failure: the yield is unavailable and the run is untouched.

    The wording comes from the provider-failure record, never from the provider's own error text.
    """
    record = failure.provider_failure
    subject = failure.input_name.replace("_", " ")
    reason = (
        f"The {subject} could not be obtained from its provider."
        if record is None
        else f"Provider {record.provider_id} failed ({record.kind.value}) while the {subject} was obtained."
    )
    return _yield_outcome(None, _unavailable_metric(failure.reason_code, reason))


def _yield_of(latest: AnnualGrowthObservation, market_cap: MarketCapEvidence) -> _YieldOutcome:
    """Return the latest year's free cash flow over the market capitalization, or why there is no yield."""
    result = market_cap.result
    if result.status is not MetricStatus.OK or result.value is None:
        assert result.reason_code is not None  # a MetricResult that is not ok carries its code
        refusal = MetricResult.failure(result.status, result.reason_code, result.reason or "No market cap.")
        return _yield_outcome(market_cap, refusal)
    return _yield_outcome(market_cap, compute_fcf_yield(latest.free_cash_flow.value, result.value))


class FCFEarningsGrowthAnalyzer(BaseAnalyzer[FCFEarningsGrowthConfig, FCFEarningsGrowthResult]):
    """Resolve approved inputs and produce the strategy's canonical typed result."""

    def __init__(self, resolver: ProductionAnnualGrowthSeriesResolver, market_data: MarketCapDependencies) -> None:
        """Initialize the analyzer with its annual-series resolver and the dependencies of the FCF yield."""
        self._resolver = resolver
        self._market_data = market_data

    def _fcf_yield(
        self,
        ticker: str,
        policy: FCFEarningsGrowthPolicy,
        observations: tuple[AnnualGrowthObservation, ...],
        context: AnalysisContext,
    ) -> _YieldOutcome:
        """Return the optional FCF yield at the anchor year-end, requesting market data only when it is wanted.

        No market-data request is made when the yield is not requested or when no fiscal year was resolved. A
        market-data failure makes the yield unavailable and nothing else: the analysis is not affected.
        """
        if not policy.include_fcf_yield:
            return _YieldOutcome(
                None,
                MetricResult.failure(
                    MetricStatus.NOT_APPLICABLE, ReasonCode.NOT_REQUESTED, "FCF yield was not requested."
                ),
            )
        if not observations:
            reason = "No completed fiscal year of free cash flow was resolved."
            return _yield_outcome(None, _unavailable_metric(ReasonCode.MISSING_FACT, reason))
        with anchor_year_end_scope(self._market_data.resolver, ticker=ticker, as_of=context.as_of) as anchor:
            if isinstance(anchor, MetricInputsFailure):
                return _failure_yield(anchor)
            if isinstance(anchor, InputUnavailable):
                return _yield_outcome(None, _unavailable_metric(anchor.reason_code, anchor.reason))
            return self._yield_at(anchor, ticker, observations[-1], context)

    def _yield_at(
        self, anchor: AnchorYearEnd, ticker: str, latest: AnnualGrowthObservation, context: AnalysisContext
    ) -> _YieldOutcome:
        """Return the latest year's yield at the anchor year-end, which that year must end at (never an older year)."""
        if latest.period_end.date() != anchor.year_end:
            reason = (
                f"The latest free-cash-flow year ends {latest.period_end.date()}, not the anchor filing's fiscal "
                f"year-end {anchor.year_end}; the yield is never computed from an older year."
            )
            return _yield_outcome(None, _unavailable_metric(ReasonCode.INCOMPATIBLE_PERIOD, reason))
        inputs = resolve_market_cap_inputs(
            self._market_data.resolver,
            self._market_data.split_history,
            self._market_data.listing,
            anchor=anchor,
            ticker=ticker,
            filing_currency=latest.free_cash_flow.currency,
            quote_provider_id=YFINANCE_PROVIDER_ID,
            as_of=context.as_of,
            use_cache=context.use_cache,
        )
        if isinstance(inputs, MetricInputsFailure):
            return _failure_yield(inputs)
        return _yield_of(latest, inputs.market_cap())

    def run_analysis(
        self, ticker: str, config: FCFEarningsGrowthConfig, context: AnalysisContext
    ) -> FCFEarningsGrowthResult:
        """Run one deterministic analysis without optional unapproved data substitutions."""
        boundary = context.effective_as_of
        if boundary.utcoffset() is None:
            raise ValueError("FCF effective execution time must be timezone-aware.")
        policy = config.policy
        instrument_profile = context.instrument_profile
        normalized_ticker = require_ticker(ticker)
        validate_profile_ticker(
            ticker,
            instrument_profile,
            mismatch_message="Instrument profile ticker does not match the FCF & Earnings Growth analysis ticker.",
        )
        if is_known_etf(instrument_profile):
            assert instrument_profile is not None
            return _etf_not_applicable_result(
                ticker=normalized_ticker,
                policy=policy,
                requested_as_of=context.as_of,
                effective_as_of=boundary,
                instrument_profile=instrument_profile,
            )
        assembly = self._resolver.resolve(
            policy=policy,
            subject_id=ticker,
            currency=config.currency,
            as_of=context.as_of,
            use_cache=context.use_cache,
            effective_as_of=boundary,
        )
        latest_eps = assembly.observations[-1].diluted_eps if assembly.observations else None
        forward = _forward_evidence(latest_eps)
        yield_outcome = self._fcf_yield(normalized_ticker, policy, assembly.observations, context)

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
        warnings.extend(yield_outcome.warnings)
        if policy.forward_policy.value != "display_only":
            warnings.append("Forward consensus policy was selected, but approved consensus evidence is unavailable.")

        return FCFEarningsGrowthResult(
            ticker=normalized_ticker,
            requested_as_of=context.as_of,
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
            market_capitalization=yield_outcome.market_capitalization,
            fcf_yield=yield_outcome.fcf_yield,
            forward_evidence=forward,
            warnings=tuple(warnings),
            diagnostics=assembly.resolution_trace,
            provider_failure=assembly.provider_failure,
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
