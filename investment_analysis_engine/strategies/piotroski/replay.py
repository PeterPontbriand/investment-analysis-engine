"""The Piotroski F-Score strategy's replay projector.

It renders a stored run using only the evidence the run captured.
"""

from datetime import UTC, datetime, time

from investment_analysis_engine.reporting.headline import CellKind, Headline, HeadlineCell
from investment_analysis_engine.reporting.replay_inputs import ReplayInputs, ReplayOptions
from investment_analysis_engine.strategies.piotroski.analyzer import PiotroskiResult
from investment_analysis_engine.strategies.piotroski.envelope import PiotroskiDocument
from investment_analysis_engine.strategies.piotroski.presenter import (
    completeness_text,
    piotroski_document,
    render_piotroski,
    score_text,
)
from investment_analysis_engine.strategies.piotroski.selection import PiotroskiSelection


def project_piotroski(
    inputs: ReplayInputs, evidence: PiotroskiResult, selection: PiotroskiSelection, options: ReplayOptions
) -> str:
    """Reconstruct the Piotroski F-Score presentation from stored evidence only.

    The live command applies no presentation-time substitution, so the stored result is rendered as it is, with the
    run's own instrument profile.
    """
    del selection
    return render_piotroski(evidence, options.mode, instrument_profile=inputs.instrument_profile)


def project_piotroski_document(
    inputs: ReplayInputs, evidence: PiotroskiResult, selection: PiotroskiSelection
) -> PiotroskiDocument:
    """Return the Piotroski F-Score document from stored evidence only, as the live JSON mode writes it."""
    del selection
    return piotroski_document(evidence, instrument_profile=inputs.instrument_profile)


def headline_piotroski(result: PiotroskiResult) -> Headline:
    """Return the Piotroski F-Score cells of the side-by-side refresh table.

    Two text cells, the score as "x of n" and its completeness; a run with no score has no value in either. The period
    end is the anchor fiscal year-end and the taxonomy is the one the operands share.
    """
    anchor = result.anchor
    return Headline(
        cells=(
            HeadlineCell("score", "Score", CellKind.TEXT, score_text(result), None, None),
            HeadlineCell("completeness", "Completeness", CellKind.TEXT, completeness_text(result), None, None),
        ),
        period_end=None if anchor is None else datetime.combine(anchor.year_end, time.min, tzinfo=UTC),
        taxonomy=result.taxonomy,
        period_end_label="fiscal year-end",
    )
