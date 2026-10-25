"""FCF Growth's replay projector: render a stored run using only the evidence it captured."""

from investment_analysis_engine.reporting.headline import UNIT_PERCENT, CellKind, Headline, HeadlineCell
from investment_analysis_engine.reporting.replay_inputs import ReplayInputs, ReplayOptions
from investment_analysis_engine.strategies.fcf_growth.models import FCFEarningsGrowthResult
from investment_analysis_engine.strategies.fcf_growth.presenter import render_fcf_earnings_growth, screen_word
from investment_analysis_engine.strategies.fcf_growth.selection import FCFGrowthSelection
from investment_analysis_engine.strategies.fcf_growth.vocabulary import FCFClassificationBasis


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


def headline_fcf_growth(result: FCFEarningsGrowthResult) -> Headline:
    """Return FCF-Growth's side-by-side cells: the FCF CAGR, the EPS CAGR and the classification.

    The first cell keeps the key ``fcf_cagr`` and names the run's classification basis in its label: total FCF or FCF
    per share. Each number cell is its metric as the result recorded it: the value, the metric's own status and its
    reason code. The classification is the word the concise output's ``Screen:`` line uses; it carries no status.
    The period end is the recorded end of the selected span. The taxonomy is not recorded.
    """
    per_share = result.policy.classification_basis is FCFClassificationBasis.FCF_PER_SHARE
    growth = result.fcf_per_share_cagr if per_share else result.fcf_cagr
    return Headline(
        cells=(
            HeadlineCell(
                "fcf_cagr",
                "FCF/share CAGR" if per_share else "FCF CAGR",
                CellKind.NUMBER,
                growth.value,
                UNIT_PERCENT,
                growth.status,
                growth.reason_code,
            ),
            HeadlineCell(
                "eps_cagr",
                "EPS CAGR",
                CellKind.NUMBER,
                result.eps_cagr.value,
                UNIT_PERCENT,
                result.eps_cagr.status,
                result.eps_cagr.reason_code,
            ),
            HeadlineCell("classification", "Class", CellKind.TEXT, screen_word(result.classification), None, None),
        ),
        period_end=result.period_end,
        period_end_label="selected span end",
    )
