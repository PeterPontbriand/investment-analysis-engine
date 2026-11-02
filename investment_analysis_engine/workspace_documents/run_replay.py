"""Pure report replay for stored Analysis Runs (projection v1).

``project_run(run, options, codecs=..., replays=...)`` renders an already-persisted ``AnalysisRun``
using only evidence captured when the run executed. It must never call
analyzers, financial calculators, providers, profile resolvers, mutable
caches, settings defaults, LLMs, or the current time: every value it shows
was decided at execution time, not at replay time.

This module is generic: it knows no strategy. It decodes the run with the injected evidence codecs and hands the
decoded evidence, the stored selection and the run's own captured facts to the projector the injected mapping
declares for the run's ``(analysis_id, method_id)``. Each projector lives in its strategy's ``replay.py``;
financial derivations the live presenter computes at render time (for Momentum, the SMA spread and its
percentage) are read from the run's own ``presentation_inputs`` instead of being recomputed from raw metrics, so
a future change to that formula can never silently alter a historical replay. This module owns exactly one
supported projection version (v1); an unsupported version or an undeclared method/analysis pair raises rather
than guessing or upgrading silently.

A replay has two projections. ``project_run`` renders the text presentation modes and returns ``str``;
``project_run_document`` returns the strategy's typed ``--json`` document. Serializing a document is the caller's
edge, so this module never writes JSON.
"""

from collections.abc import Mapping

from pydantic import BaseModel

from investment_analysis_engine.reporting.replay_inputs import (
    ReplayDocumentProjector,
    ReplayInputs,
    ReplayOptions,
    ReplayProjector,
    UnsupportedProjectionError,
)
from investment_analysis_engine.workspace.codecs import EvidenceCodec, decode_evidence
from investment_analysis_engine.workspace.runs import AnalysisRun

_SUPPORTED_PROJECTION_VERSION = 1


def _projector_for[ProjectorT](run: AnalysisRun, projectors: Mapping[tuple[str, str], ProjectorT]) -> ProjectorT:
    """Return the projector declared for ``run``, after checking the run's projection version.

    Raises:
        UnsupportedProjectionError: If `run.projection_version` is not the one this module implements, or if
            `projectors` declares none for `run`'s `(analysis_id, method_id)` pair.
    """
    if run.projection_version != _SUPPORTED_PROJECTION_VERSION:
        raise UnsupportedProjectionError(f"Unsupported projection version: {run.projection_version}.")
    projector = projectors.get((run.analysis_id, run.method_id))
    if projector is None:
        raise UnsupportedProjectionError(
            f"No v1 replay is implemented for analysis={run.analysis_id!r}, method={run.method_id!r}."
        )
    return projector


def _replay_arguments(
    run: AnalysisRun, codecs: Mapping[tuple[str, str], EvidenceCodec]
) -> tuple[ReplayInputs, object, object]:
    """Return the facts, decoded evidence and stored selection a projector is given for ``run``."""
    # decode_evidence dispatches on (run.analysis_id, run.method_id), which the projector lookup matched;
    # the projector's own exact-type guards reject evidence or a selection that is not its strategy's.
    evidence = decode_evidence(run, codecs)
    selection = run.effective_config if run.effective_config is not None else run.requested_config
    inputs = ReplayInputs(
        ticker=run.ticker, instrument_profile=run.instrument_profile, presentation_inputs=run.presentation_inputs
    )
    return inputs, evidence, selection


def project_run(
    run: AnalysisRun,
    options: ReplayOptions | None = None,
    *,
    codecs: Mapping[tuple[str, str], EvidenceCodec],
    replays: Mapping[tuple[str, str], ReplayProjector],
) -> str:
    """Render one stored run as text using only its own captured evidence.

    Uses the run's own stored ``projection_version``; there is no automatic
    upgrade to a later version.

    Args:
        run: An already-persisted, reopened `AnalysisRun`.
        options: The requested text view; defaults to the concise mode.
        codecs: The evidence codec of each declared strategy, keyed by ``(analysis_id, method_id)``.
        replays: The text projector of each declared strategy, keyed the same way.

    Returns:
        The rendered text.

    Raises:
        UnsupportedProjectionError: If `run.projection_version` is not the
            one this module implements, or if `replays` declares no projector for `run`'s
            `(analysis_id, method_id)` pair.
    """
    resolved_options = options if options is not None else ReplayOptions()
    projector = _projector_for(run, replays)
    inputs, evidence, selection = _replay_arguments(run, codecs)
    return projector(inputs, evidence, selection, resolved_options)


def project_run_document(
    run: AnalysisRun,
    *,
    codecs: Mapping[tuple[str, str], EvidenceCodec],
    documents: Mapping[tuple[str, str], ReplayDocumentProjector],
) -> BaseModel:
    """Return one stored run's typed ``--json`` document using only its own captured evidence.

    Args:
        run: An already-persisted, reopened `AnalysisRun`.
        codecs: The evidence codec of each declared strategy, keyed by ``(analysis_id, method_id)``.
        documents: The document projector of each declared strategy, keyed the same way.

    Returns:
        The strategy's document model; the caller serializes it.

    Raises:
        UnsupportedProjectionError: If `run.projection_version` is not the
            one this module implements, or if `documents` declares no projector for `run`'s
            `(analysis_id, method_id)` pair.
    """
    projector = _projector_for(run, documents)
    inputs, evidence, selection = _replay_arguments(run, codecs)
    return projector(inputs, evidence, selection)


__all__ = ["project_run", "project_run_document"]
