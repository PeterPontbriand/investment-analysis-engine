"""FCF Growth's replay projector: render a stored run using only the evidence it captured."""

from src.reporting.replay_inputs import ReplayInputs, ReplayOptions
from src.strategies.fcf_growth.models import FCFEarningsGrowthResult
from src.strategies.fcf_growth.presenter import render_fcf_earnings_growth
from src.strategies.fcf_growth.selection import FCFGrowthSelection


def project_fcf_growth(
    inputs: ReplayInputs, evidence: FCFEarningsGrowthResult, selection: FCFGrowthSelection, options: ReplayOptions
) -> str:
    """Reconstruct an FCF/Earnings Growth presentation from stored evidence only.

    Unlike Graham, the live command applies no presentation-time label normalization before rendering —
    `render_fcf_earnings_growth` already derives every displayed label/status directly from the stored result,
    so no substitution point is needed here beyond reusing the run's own ``instrument_profile`` (the adapter
    never reads the analyzer's own ``result.instrument_profile`` back for rendering either).
    """
    del selection
    return render_fcf_earnings_growth(evidence, options.mode, instrument_profile=inputs.instrument_profile)
