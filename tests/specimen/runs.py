"""The specimen's stored run, its store and its decode and replay.

A production ``AnalysisRun`` validates its selection against the closed production union, which the specimen is
not part of, so the specimen stores a run of its own with the same version tuple. Decoding and replay mirror the
production functions and raise the same errors.
"""

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict

from investment_analysis_engine.analysis.run_models import StrictJsonMapping
from investment_analysis_engine.core.strategy_errors import find
from investment_analysis_engine.reporting.replay_inputs import (
    ReplayInputs,
    ReplayOptions,
    ReplayProjector,
    UnsupportedProjectionError,
)
from investment_analysis_engine.workspace.codecs import EvidenceCodec, InvalidStoredRunError, UnsupportedRunVersionError
from investment_analysis_engine.workspace.strategy_types import NativeEvidence
from tests.specimen.codec import encode_specimen
from tests.specimen.execution import SpecimenExecution
from tests.specimen.selection import SpecimenSelection
from tests.specimen.vocabulary import (
    ANALYSIS_ID,
    CONFIG_SCHEMA_VERSION,
    EVIDENCE_CODEC_VERSION,
    METHOD_ID,
    METHOD_VERSION,
    RESULT_SCHEMA_VERSION,
)


class SpecimenRun(BaseModel):
    """One stored specimen run: its ticker, version tuple, selection and encoded evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: str
    analysis_id: str
    method_id: str
    config_schema_version: int
    method_version: int
    result_schema_version: int
    evidence_codec_version: int
    requested_config: SpecimenSelection
    result_evidence: StrictJsonMapping | None


class SpecimenRunStore:
    """An in-memory run store, which the specimen's ``--save-run`` inserts into."""

    def __init__(self) -> None:
        """Start with no stored run."""
        self.runs: list[SpecimenRun] = []

    def insert(self, run: SpecimenRun) -> None:
        """Retain ``run`` as stored."""
        self.runs.append(run)

    def clear(self) -> None:
        """Forget every stored run."""
        self.runs.clear()


SPECIMEN_RUN_STORE = SpecimenRunStore()
"""The store the specimen's command writes to; a test clears it before and reads it after a command."""


def build_specimen_run(ticker: str, selection: SpecimenSelection, execution: SpecimenExecution) -> SpecimenRun:
    """Assemble the run for one execution, with the versions the specimen's descriptor declares."""
    return SpecimenRun(
        ticker=ticker.strip().upper(),
        analysis_id=ANALYSIS_ID,
        method_id=METHOD_ID,
        config_schema_version=CONFIG_SCHEMA_VERSION,
        method_version=METHOD_VERSION,
        result_schema_version=RESULT_SCHEMA_VERSION,
        evidence_codec_version=EVIDENCE_CODEC_VERSION,
        requested_config=selection,
        result_evidence=encode_specimen(execution.native_evidence),
    )


def decode_specimen_run(run: SpecimenRun, codecs: Mapping[tuple[str, str], EvidenceCodec]) -> NativeEvidence | None:
    """Decode the run's evidence with the codec its identifiers and versions select, as production does."""
    codec = find(codecs, (run.analysis_id, run.method_id))
    if (
        codec is None
        or run.evidence_codec_version != codec.evidence_codec_version
        or (run.config_schema_version, run.method_version, run.result_schema_version)
        != (codec.config_schema_version, codec.method_version, codec.result_schema_version)
    ):
        raise UnsupportedRunVersionError("Unsupported Analysis Run method or version.")
    if run.result_evidence is None:
        return None
    try:
        return codec.decode(run.result_evidence, run.ticker)
    except (ValueError, TypeError) as exc:
        raise InvalidStoredRunError(f"Invalid stored {codec.label} evidence.") from exc


def project_specimen_run(
    run: SpecimenRun,
    options: ReplayOptions | None = None,
    *,
    codecs: Mapping[tuple[str, str], EvidenceCodec],
    replays: Mapping[tuple[str, str], ReplayProjector],
) -> str:
    """Render the run from its own evidence with the projector its identifiers select, as production does."""
    projector = replays.get((run.analysis_id, run.method_id))
    if projector is None:
        raise UnsupportedProjectionError(
            f"No v1 replay is implemented for analysis={run.analysis_id!r}, method={run.method_id!r}."
        )
    evidence = decode_specimen_run(run, codecs)
    inputs = ReplayInputs(ticker=run.ticker, instrument_profile=None, presentation_inputs=None)
    return projector(inputs, evidence, run.requested_config, options if options is not None else ReplayOptions())
