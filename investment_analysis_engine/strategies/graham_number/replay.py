"""Graham Number's replay projector: render a stored run using only the evidence it captured."""

from investment_analysis_engine.analysis.shared.financial_resolution import common_currency
from investment_analysis_engine.reporting.headline import Headline
from investment_analysis_engine.reporting.replay_inputs import ReplayInputs, ReplayOptions
from investment_analysis_engine.strategies._graham.replay import (
    EARNINGS_PERIOD_END_LABEL,
    friendly_graham_assembly,
    margin_cell,
    price_cell,
)
from investment_analysis_engine.strategies.graham_number.presenter import (
    GrahamNumberPresentation,
    number_with_public_quote_reason,
    render_graham_number,
)
from investment_analysis_engine.strategies.graham_number.selection import GrahamNumberSelection
from investment_analysis_engine.strategies.graham_number.service import GrahamNumberAnalysis


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
        effective_as_of=evidence.effective_as_of,
        margin_of_safety_percent=evidence.margin_of_safety_percent,
        instrument_profile=inputs.instrument_profile,
        price_comparison=evidence.price_comparison,
    )
    return render_graham_number(presentation, options.mode)


def headline_graham_number(analysis: GrahamNumberAnalysis) -> Headline:
    """Return the Graham Number's side-by-side cells: the maximum indicated price and the margin of safety.

    The price takes the strategy's own status. The unit carries the currency the earnings and book value share, or
    says none was recorded (both overridden). The period end is the observation period end of the earnings input,
    which is not recorded when EPS was an override. The taxonomy is not recorded.
    """
    assembly = analysis.assembly
    return Headline(
        cells=(
            price_cell(
                key="maximum_indicated_price",
                label="Max price",
                value=analysis.result.maximum_indicated_price,
                status=analysis.native_status,
                currency=common_currency(assembly.eps, assembly.bvps),
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
