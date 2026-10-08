"""Graham Number's replay projector: render a stored run using only the evidence it captured."""

from src.reporting.replay_inputs import ReplayInputs, ReplayOptions
from src.strategies._graham.replay import friendly_graham_assembly
from src.strategies.graham_number.presenter import (
    GrahamNumberPresentation,
    number_with_public_quote_reason,
    render_graham_number,
)
from src.strategies.graham_number.selection import GrahamNumberSelection
from src.strategies.graham_number.service import GrahamNumberAnalysis


def project_graham_number(
    inputs: ReplayInputs, evidence: GrahamNumberAnalysis, selection: GrahamNumberSelection, options: ReplayOptions
) -> str:
    """Reconstruct a Graham Number presentation from stored evidence only.

    Identity/kind evidence comes from the run's own ``instrument_profile`` rather than the native analysis's
    copy: the analyzer may leave `GrahamNumberAnalysis.instrument_profile` unset, so replay must use the
    profile captured on the run itself to render identity correctly.
    """
    del selection
    presentation = GrahamNumberPresentation(
        ticker=evidence.ticker,
        assembly=number_with_public_quote_reason(friendly_graham_assembly(inputs.ticker, evidence.assembly)),
        result=evidence.result,
        as_of=evidence.as_of,
        margin_of_safety_percent=evidence.margin_of_safety_percent,
        instrument_profile=inputs.instrument_profile,
        price_comparison=evidence.price_comparison,
    )
    return render_graham_number(presentation, options.mode)
