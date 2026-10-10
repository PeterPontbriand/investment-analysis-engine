"""Version dispatch and safe errors for stored workspace evidence, over injected codecs.

Each strategy's codec arrives as an :class:`EvidenceCodec` in a mapping the composition root builds, so
this module names no strategy. A result or stored run that matches no injected codec is rejected, never
handled as another strategy's.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from src.core.strategy_errors import find
from src.workspace.models import StrictJsonMapping
from src.workspace.runs import AnalysisRun
from src.workspace.strategy_types import NativeEvidence


class UnsupportedRunVersionError(ValueError):
    """The stored method or version has no supported evidence decoder."""

    reason_code = "unsupported_run_version"


class InvalidStoredRunError(ValueError):
    """Stored evidence violates its declared schema or envelope identity."""

    reason_code = "invalid_stored_run"


@dataclass(frozen=True)
class EvidenceCodec:
    """One strategy's evidence codec, its display label and the versions it writes and accepts.

    ``encode`` raises for an object that is not exactly the strategy's result type. ``decode`` receives the
    stored payload and the run envelope's ticker, and raises ``ValueError`` when the evidence is about
    another ticker.
    """

    label: str
    config_schema_version: int
    method_version: int
    result_schema_version: int
    evidence_codec_version: int
    encode: Callable[[object], StrictJsonMapping]
    decode: Callable[[StrictJsonMapping, str], NativeEvidence]


def encode_with(codec: EvidenceCodec, evidence: NativeEvidence) -> StrictJsonMapping:
    """Encode ``evidence`` with ``codec``, wrapping a schema failure as :class:`InvalidStoredRunError`."""
    try:
        return codec.encode(evidence)
    except (ValueError, TypeError) as exc:
        raise InvalidStoredRunError(f"Invalid {codec.label} evidence.") from exc


def decode_evidence(run: AnalysisRun, codecs: Mapping[tuple[str, str], EvidenceCodec]) -> NativeEvidence | None:
    """Decode supported evidence using the envelope's explicit version tuple.

    Attempts that ended before resolution may have no result. Version checks
    still apply; unsupported records must never trigger recomputation.
    """
    codec = find(codecs, (run.analysis_id, run.method_id))
    if (
        codec is None
        or type(run.run_schema_version) is not int
        or run.run_schema_version != 2
        or type(run.projection_version) is not int
        or run.projection_version != 1
        or type(run.evidence_codec_version) is not int
        or run.evidence_codec_version != codec.evidence_codec_version
        or (
            type(run.config_schema_version),
            type(run.method_version),
            type(run.result_schema_version),
        )
        != (int, int, int)
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
