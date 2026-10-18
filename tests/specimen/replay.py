"""The specimen's replay projector: render a stored run using only the evidence it captured."""

from investment_analysis_engine.reporting.replay_inputs import ReplayInputs, ReplayOptions
from tests.specimen.analyzer import SpecimenResult
from tests.specimen.presenter import render_specimen
from tests.specimen.selection import SpecimenSelection


def project_specimen(
    inputs: ReplayInputs, evidence: SpecimenResult, selection: SpecimenSelection, options: ReplayOptions
) -> str:
    """Reconstruct the specimen's presentation from stored evidence only."""
    del inputs, selection
    return render_specimen(evidence, options.mode)
