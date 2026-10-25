"""Graham Growth's replay projector: render a stored run using only the evidence it captured."""

from investment_analysis_engine.analysis.shared.financial_resolution import common_currency
from investment_analysis_engine.reporting.headline import Headline
from investment_analysis_engine.reporting.replay_inputs import ReplayInputs, ReplayOptions
from investment_analysis_engine.strategies._graham.replay import (
    EARNINGS_PERIOD_END_LABEL,
    friendly_graham_assembly,
    margin_cell,
    price_cell,
)
from investment_analysis_engine.strategies.graham_growth.presenter import (
    GrahamGrowthPresentation,
    growth_with_public_quote_reason,
    render_graham_growth,
)
from investment_analysis_engine.strategies.graham_growth.selection import GrahamGrowthSelection
from investment_analysis_engine.strategies.graham_growth.service import GrahamGrowthAnalysis


def project_graham_growth(
    inputs: ReplayInputs, evidence: GrahamGrowthAnalysis, selection: GrahamGrowthSelection, options: ReplayOptions
) -> str:
    """Reconstruct a Graham Growth presentation from stored evidence only.

    ``base_pe``/``growth_multiplier``/``baseline_aaa_yield`` come from the evidence's own captured ``policy``
    (the effective assumptions actually used at execution time), never from the live command's current
    configured Graham Growth settings (``GrahamGrowthSettings.to_policy()``, built at the composition root) — a
    future change to those defaults must never alter what an old run replays as.
    """
    del selection
    presentation = GrahamGrowthPresentation(
        ticker=evidence.ticker,
        assembly=growth_with_public_quote_reason(friendly_graham_assembly(inputs.ticker, evidence.assembly)),
        result=evidence.result,
        base_pe=evidence.policy.base_pe,
        growth_multiplier=evidence.policy.growth_multiplier,
        baseline_aaa_yield=evidence.policy.baseline_aaa_yield,
        as_of=evidence.as_of,
        effective_as_of=evidence.effective_as_of,
        margin_of_safety_percent=evidence.margin_of_safety_percent,
        instrument_profile=inputs.instrument_profile,
        price_comparison=evidence.price_comparison,
    )
    return render_graham_growth(presentation, options.mode)


def headline_graham_growth(analysis: GrahamGrowthAnalysis) -> Headline:
    """Return Graham Growth's side-by-side cells: the intrinsic value and the margin of safety.

    The value takes the strategy's own status. The unit carries the currency of the earnings input, or says none
    was recorded (EPS overridden). The period end is the observation period end of the earnings input, which is not
    recorded when EPS was an override. The taxonomy is not recorded.
    """
    assembly = analysis.assembly
    return Headline(
        cells=(
            price_cell(
                key="intrinsic_value",
                label="Value",
                value=analysis.result.growth_value,
                status=analysis.native_status,
                currency=common_currency(assembly.eps),
            ),
            margin_cell(
                comparison=analysis.price_comparison,
                percent=analysis.margin_of_safety_percent,
                native_status=analysis.native_status,
            ),
        ),
        period_end=None if assembly.eps is None else assembly.eps.observation_period_end,
        period_end_label=EARNINGS_PERIOD_END_LABEL,
    )
