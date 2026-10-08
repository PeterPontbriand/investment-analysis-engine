"""Graham Growth's replay projector: render a stored run using only the evidence it captured."""

from src.reporting.replay_inputs import ReplayInputs, ReplayOptions
from src.strategies._graham.replay import friendly_graham_assembly
from src.strategies.graham_growth.presenter import (
    GrahamGrowthPresentation,
    growth_with_public_quote_reason,
    render_graham_growth,
)
from src.strategies.graham_growth.selection import GrahamGrowthSelection
from src.strategies.graham_growth.service import GrahamGrowthAnalysis


def project_graham_growth(
    inputs: ReplayInputs, evidence: GrahamGrowthAnalysis, selection: GrahamGrowthSelection, options: ReplayOptions
) -> str:
    """Reconstruct a Graham Growth presentation from stored evidence only.

    ``base_pe``/``growth_multiplier``/``baseline_aaa_yield`` come from the evidence's own captured ``policy``
    (the effective assumptions actually used at execution time), never from the live command's current
    `growth_assumptions()` settings lookup — a future change to those defaults must never alter what an old run
    replays as.
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
        margin_of_safety_percent=evidence.margin_of_safety_percent,
        instrument_profile=inputs.instrument_profile,
        price_comparison=evidence.price_comparison,
    )
    return render_graham_growth(presentation, options.mode)
