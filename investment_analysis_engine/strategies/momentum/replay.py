"""Momentum's replay projector: render a stored run using only the evidence it captured."""

from investment_analysis_engine.reporting.headline import CellKind, CellUnit, Headline, HeadlineCell
from investment_analysis_engine.reporting.replay_inputs import ReplayInputs, ReplayOptions, UnsupportedProjectionError
from investment_analysis_engine.strategies.momentum.analyzer import MomentumRun
from investment_analysis_engine.strategies.momentum.envelope import MomentumDocument
from investment_analysis_engine.strategies.momentum.presenter import (
    MomentumPresentation,
    build_momentum_document,
    render_momentum,
    trend_word,
)
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.strategies.momentum.vocabulary import HEADLINE_TERMS


def _presentation(inputs: ReplayInputs, evidence: MomentumRun, selection: MomentumSelection) -> MomentumPresentation:
    """Reconstruct the Momentum presentation both projections show from stored evidence only.

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

    return MomentumPresentation(
        ticker=evidence.ticker,
        effective_as_of=evidence.effective_as_of,
        execution_status=evidence.execution_status,
        metrics=evidence.metrics,
        reason_code=evidence.reason_code,
        reason=evidence.reason,
        provider_failure=evidence.provider_failure,
        config=selection.to_momentum_config(),
        requested_as_of=selection.as_of,
        market_data=evidence.market_data,
        resolution_trace=evidence.resolution_trace,
        data_resolution=evidence.data_resolution,
        instrument_profile=inputs.instrument_profile,
        use_captured_spread=True,
        captured_sma_spread=captured_spread,
        captured_sma_spread_percent=captured_spread_percent,
    )


def project_momentum(
    inputs: ReplayInputs, evidence: MomentumRun, selection: MomentumSelection, options: ReplayOptions
) -> str:
    """Render the reconstructed Momentum presentation in the requested text mode.

    Raises:
        UnsupportedProjectionError: If a stored presentation input is not a number or null.
    """
    return render_momentum(_presentation(inputs, evidence, selection), options.mode)


def project_momentum_document(
    inputs: ReplayInputs, evidence: MomentumRun, selection: MomentumSelection
) -> MomentumDocument:
    """Return the reconstructed Momentum document, as the JSON mode of the live command writes it.

    Raises:
        UnsupportedProjectionError: If a stored presentation input is not a number or null.
    """
    return build_momentum_document(_presentation(inputs, evidence, selection))


def headline_momentum(run: MomentumRun) -> Headline:
    """Return Momentum's side-by-side cells: the trend word and the RSI.

    The trend is a text cell with no status; it has no value when no calculation ran or the trend is ``UNKNOWN``.
    The RSI takes its own metric's status and reason code, or, when no calculation ran, the run's status and reason
    code. Momentum has no fiscal period and no taxonomy.
    """
    metrics = run.metrics
    trend = HeadlineCell(
        "trend",
        "Trend",
        HEADLINE_TERMS["trend"],
        CellKind.TEXT,
        None if metrics is None else trend_word(metrics.status),
        None,
        None,
    )
    if metrics is None:
        rsi = HeadlineCell(
            "rsi",
            "RSI",
            HEADLINE_TERMS["rsi"],
            CellKind.NUMBER,
            None,
            CellUnit.POINTS,
            run.execution_status,
            run.reason_code,
        )
    else:
        metric = metrics.rsi_14
        rsi = HeadlineCell(
            "rsi",
            "RSI",
            HEADLINE_TERMS["rsi"],
            CellKind.NUMBER,
            metric.value,
            CellUnit.POINTS,
            metric.status,
            metric.reason_code,
        )
    return Headline(cells=(trend, rsi))
