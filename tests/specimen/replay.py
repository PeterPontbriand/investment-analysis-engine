"""The specimen's replay projector: render a stored run using only the evidence it captured."""

from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.reporting.headline import CellKind, Headline, HeadlineCell
from investment_analysis_engine.reporting.replay_inputs import ReplayInputs, ReplayOptions
from tests.specimen.analyzer import SpecimenResult
from tests.specimen.envelope import SpecimenDocument
from tests.specimen.presenter import build_specimen_document, render_specimen
from tests.specimen.selection import SpecimenSelection
from tests.specimen.vocabulary import HEADLINE_TERMS


def project_specimen(
    inputs: ReplayInputs, evidence: SpecimenResult, selection: SpecimenSelection, options: ReplayOptions
) -> str:
    """Reconstruct the specimen's presentation from stored evidence only."""
    del inputs, selection
    return render_specimen(evidence, options.mode)


def project_specimen_document(
    inputs: ReplayInputs, evidence: SpecimenResult, selection: SpecimenSelection
) -> SpecimenDocument:
    """Return the specimen's document from stored evidence only."""
    del inputs, selection
    return build_specimen_document(evidence)


def headline_specimen(result: SpecimenResult) -> Headline:
    """Return the specimen's one cell: the scaled value, which the specimen always calculates."""
    return Headline(
        cells=(
            HeadlineCell(
                "scaled",
                "Scaled",
                HEADLINE_TERMS["scaled"],
                CellKind.NUMBER,
                result.scaled,
                "points",
                CalculationStatus.OK,
            ),
        )
    )
