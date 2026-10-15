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
"""

from collections.abc import Mapping

from src.reporting.replay_inputs import ReplayInputs, ReplayOptions, ReplayProjector, UnsupportedProjectionError
from src.workspace.codecs import EvidenceCodec, decode_evidence
from src.workspace.runs import AnalysisRun

_SUPPORTED_PROJECTION_VERSION = 1


def project_run(
    run: AnalysisRun,
    options: ReplayOptions | None = None,
    *,
    codecs: Mapping[tuple[str, str], EvidenceCodec],
    replays: Mapping[tuple[str, str], ReplayProjector],
) -> str:
    """Render one stored run using only its own captured evidence.

    Uses the run's own stored ``projection_version``; there is no automatic
    upgrade to a later version.

    Args:
        run: An already-persisted, reopened `AnalysisRun`.
        options: The requested view; defaults to the concise mode.
        codecs: The evidence codec of each declared strategy, keyed by ``(analysis_id, method_id)``.
        replays: The replay projector of each declared strategy, keyed the same way.

    Returns:
        The rendered text (or JSON document, when `options.mode` is JSON).

    Raises:
        UnsupportedProjectionError: If `run.projection_version` is not the
            one this module implements, or if `replays` declares no projector for `run`'s
            `(analysis_id, method_id)` pair.
    """
    resolved_options = options if options is not None else ReplayOptions()
    if run.projection_version != _SUPPORTED_PROJECTION_VERSION:
        raise UnsupportedProjectionError(f"Unsupported projection version: {run.projection_version}.")
    projector = replays.get((run.analysis_id, run.method_id))
    if projector is None:
        raise UnsupportedProjectionError(
            f"No v1 replay is implemented for analysis={run.analysis_id!r}, method={run.method_id!r}."
        )
    # decode_evidence dispatches on (run.analysis_id, run.method_id), which the projector lookup above matched;
    # the projector's own exact-type guards reject evidence or a selection that is not its strategy's.
    evidence = decode_evidence(run, codecs)
    selection = run.effective_config if run.effective_config is not None else run.requested_config
    inputs = ReplayInputs(
        ticker=run.ticker, instrument_profile=run.instrument_profile, presentation_inputs=run.presentation_inputs
    )
    return projector(inputs, evidence, selection, resolved_options)


__all__ = ["project_run"]
