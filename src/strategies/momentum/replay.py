"""Momentum's replay projector: render a stored run using only the evidence it captured."""

from src.reporting.replay_inputs import ReplayInputs, ReplayOptions, UnsupportedProjectionError
from src.strategies.momentum.analyzer import MomentumRun
from src.strategies.momentum.presenter import MomentumPresentation, render_momentum
from src.strategies.momentum.selection import MomentumSelection


def project_momentum(
    inputs: ReplayInputs, evidence: MomentumRun, selection: MomentumSelection, options: ReplayOptions
) -> str:
    """Reconstruct a Momentum presentation from stored evidence only.

    Identity/kind evidence comes from the run's own ``instrument_profile`` rather than the native evidence's
    copy: Momentum's analyzer never sets `MomentumRun.instrument_profile` (the profile is composed outside the
    calculator), so that field is always null for this method and would otherwise render as "unavailable" even
    when a profile was captured.

    Raises:
        UnsupportedProjectionError: If a stored presentation input is not a number or null.
    """
    # Unlike the envelope's typed fields, presentation_inputs is a generic JSON mapping with no schema tying
    # its keys to specific types; a reopened row is a real system boundary, so this is genuine validation.
    presentation_inputs = inputs.presentation_inputs or {}
    captured_spread = presentation_inputs.get("sma_spread")
    captured_spread_percent = presentation_inputs.get("sma_spread_percent")
    if not isinstance(captured_spread, (float, int)) and captured_spread is not None:
        raise UnsupportedProjectionError("Stored sma_spread is not a finite number or null.")
    if not isinstance(captured_spread_percent, (float, int)) and captured_spread_percent is not None:
        raise UnsupportedProjectionError("Stored sma_spread_percent is not a finite number or null.")

    presentation = MomentumPresentation(
        metrics=evidence.metrics,
        config=selection.to_momentum_config(),
        market_data=evidence.market_data,
        resolution_trace=evidence.resolution_trace,
        data_resolution=evidence.data_resolution,
        instrument_profile=inputs.instrument_profile,
        use_captured_spread=True,
        captured_sma_spread=captured_spread,
        captured_sma_spread_percent=captured_spread_percent,
    )
    return render_momentum(presentation, options.mode)
