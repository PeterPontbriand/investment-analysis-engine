"""Pure report replay for stored Analysis Runs (projection v1).

``project_run(run, options)`` renders an already-persisted ``AnalysisRun``
using only evidence captured when the run executed. It must never call
analyzers, financial calculators, providers, profile resolvers, mutable
caches, settings defaults, LLMs, or the current time: every value it shows
was decided at execution time, not at replay time.

Financial derivations that the live presenter computes at render time (for
Momentum, the SMA spread and its percentage) are read from the run's own
``presentation_inputs`` instead of being recomputed from raw metrics, so a
future change to that formula can never silently alter a historical
replay. Pure formatting/label helpers already used by the live direct
commands are reused as-is; only the financial-derivation substitution point
is new. This module owns exactly one supported projection version (v1);
an unsupported version or an unimplemented method/analysis pair raises
rather than guessing or upgrading silently.
"""

from dataclasses import dataclass, replace

from src.analysis.strategy.fcf_earnings_growth.models import FCFEarningsGrowthResult
from src.analysis.strategy.graham_growth.calculation import GrowthValueInputAssembly
from src.analysis.strategy.graham_growth.service import GrahamGrowthAnalysis
from src.analysis.strategy.graham_number.calculation import GrahamNumberInputAssembly
from src.analysis.strategy.graham_number.service import GrahamNumberAnalysis
from src.analysis.strategy.momentum.momentum_analyzer import MomentumRun
from src.core.analysis_status import CalculationStatus
from src.reporting.fcf_earnings_growth import render_fcf_earnings_growth
from src.reporting.graham_growth import GrahamGrowthPresentation, growth_with_public_quote_reason, render_graham_growth
from src.reporting.graham_number import GrahamNumberPresentation, number_with_public_quote_reason, render_graham_number
from src.reporting.momentum import MomentumPresentation, render_momentum
from src.reporting.presentation import PresentationMode
from src.reporting.valuation_presentation import friendly_valuation_failure
from src.workspace.codecs import decode_evidence
from src.workspace.requests import MomentumSelection
from src.workspace.runs import AnalysisRun

# Statuses whose stored `assembly.reason`/`result.reason` is already investor-facing
# (a successful calculation, or a method-level inapplicability message authored at
# the source); every other non-OK status carries a raw resolver reason that the live
# commands only ever show after `friendly_valuation_failure` normalizes it.
_GRAHAM_REASON_ALREADY_SAFE = (CalculationStatus.OK, CalculationStatus.NOT_APPLICABLE)

_SUPPORTED_PROJECTION_VERSION = 1


class UnsupportedProjectionError(ValueError):
    """The run's projection version, or its (analysis_id, method_id), has no v1 replay."""


@dataclass(frozen=True)
class ReplayOptions:
    """Explicit view selection for one replay.

    Locale and time formatting are not configurable: projection v1 reuses
    the existing formatting helpers, which are already fixed to the
    en-CA-style number/currency conventions and ISO-8601 UTC timestamps
    the direct commands already show.
    """

    mode: PresentationMode = PresentationMode.CONCISE


def project_run(run: AnalysisRun, options: ReplayOptions | None = None) -> str:
    """Render one stored run using only its own captured evidence.

    Uses the run's own stored ``projection_version``; there is no automatic
    upgrade to a later version.

    Args:
        run: An already-persisted, reopened `AnalysisRun`.
        options: The requested view; defaults to the concise mode.

    Returns:
        The rendered text (or JSON document, when `options.mode` is JSON).

    Raises:
        UnsupportedProjectionError: If `run.projection_version` is not the
            one this module implements, or if no v1 replay exists yet for
            `run`'s `(analysis_id, method_id)` pair.
    """
    resolved_options = options if options is not None else ReplayOptions()
    if run.projection_version != _SUPPORTED_PROJECTION_VERSION:
        raise UnsupportedProjectionError(f"Unsupported projection version: {run.projection_version}.")
    if (run.analysis_id, run.method_id) == ("momentum", "sma_crossover"):
        return _project_momentum_v1(run, resolved_options)
    if (run.analysis_id, run.method_id) == ("graham_number", "graham_number"):
        return _project_graham_number_v1(run, resolved_options)
    if (run.analysis_id, run.method_id) == ("graham_growth_value", "graham_growth_value"):
        return _project_graham_growth_v1(run, resolved_options)
    if (run.analysis_id, run.method_id) == ("fcf_earnings_growth", "reported_fcf_eps_cagr"):
        return _project_fcf_growth_v1(run, resolved_options)
    raise UnsupportedProjectionError(
        f"No v1 replay is implemented for analysis={run.analysis_id!r}, method={run.method_id!r}."
    )


def _project_momentum_v1(run: AnalysisRun, options: ReplayOptions) -> str:
    """Reconstruct a Momentum presentation from stored evidence only.

    Identity/kind evidence comes from the envelope's own ``instrument_profile``
    field rather than the native evidence's copy: Momentum's analyzer never
    sets `MomentumRun.instrument_profile` (the profile is composed outside the
    calculator), so that field is always null for this method and would
    otherwise render as "unavailable" even when a profile was captured.
    """
    # decode_evidence dispatches on (run.analysis_id, run.method_id), which project_run
    # already confirmed is momentum's pair; AnalysisRun's own validator likewise
    # guarantees requested_config/effective_config match that same pair. Neither
    # assertion below is user-facing validation — both are internal invariants
    # already enforced elsewhere, asserted here only so mypy can narrow the type.
    evidence = decode_evidence(run)
    assert isinstance(evidence, MomentumRun)
    selection = run.effective_config if run.effective_config is not None else run.requested_config
    assert isinstance(selection, MomentumSelection)

    # Unlike the envelope's typed fields, presentation_inputs is a generic JSON
    # mapping with no schema tying its keys to specific types; a reopened row is
    # a real system boundary, so this is genuine validation, not paranoia.
    presentation_inputs = run.presentation_inputs or {}
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
        instrument_profile=run.instrument_profile,
        use_captured_spread=True,
        captured_sma_spread=captured_spread,
        captured_sma_spread_percent=captured_spread_percent,
    )
    return render_momentum(presentation, options.mode)


def _project_graham_number_v1(run: AnalysisRun, options: ReplayOptions) -> str:
    """Reconstruct a Graham Number presentation from stored evidence only.

    Identity/kind evidence comes from the envelope's own ``instrument_profile``
    field rather than the native analysis's copy: the analyzer may leave
    `GrahamNumberAnalysis.instrument_profile` unset, so replay must use the
    profile captured on the run itself to render identity correctly.
    """
    # decode_evidence dispatches on (run.analysis_id, run.method_id), which project_run
    # already confirmed is Graham Number's pair; neither assertion below is user-facing
    # validation — both are internal invariants asserted here only so mypy can narrow the type.
    evidence = decode_evidence(run)
    assert isinstance(evidence, GrahamNumberAnalysis)

    presentation = GrahamNumberPresentation(
        ticker=evidence.ticker,
        assembly=number_with_public_quote_reason(_friendly_graham_assembly(run.ticker, evidence.assembly)),
        result=evidence.result,
        as_of=evidence.as_of,
        margin_of_safety_percent=evidence.margin_of_safety_percent,
        instrument_profile=run.instrument_profile,
        price_comparison=evidence.price_comparison,
    )
    return render_graham_number(presentation, options.mode)


def _project_graham_growth_v1(run: AnalysisRun, options: ReplayOptions) -> str:
    """Reconstruct a Graham Growth presentation from stored evidence only.

    ``base_pe``/``growth_multiplier``/``baseline_aaa_yield`` come from the
    evidence's own captured ``policy`` (the effective assumptions actually
    used at execution time), never from the live command's current
    `growth_assumptions()` settings lookup — a future change to those
    defaults must never alter what an old run replays as.
    """
    evidence = decode_evidence(run)
    assert isinstance(evidence, GrahamGrowthAnalysis)

    presentation = GrahamGrowthPresentation(
        ticker=evidence.ticker,
        assembly=growth_with_public_quote_reason(_friendly_graham_assembly(run.ticker, evidence.assembly)),
        result=evidence.result,
        base_pe=evidence.policy.base_pe,
        growth_multiplier=evidence.policy.growth_multiplier,
        baseline_aaa_yield=evidence.policy.baseline_aaa_yield,
        as_of=evidence.as_of,
        margin_of_safety_percent=evidence.margin_of_safety_percent,
        instrument_profile=run.instrument_profile,
        price_comparison=evidence.price_comparison,
    )
    return render_graham_growth(presentation, options.mode)


def _project_fcf_growth_v1(run: AnalysisRun, options: ReplayOptions) -> str:
    """Reconstruct an FCF/Earnings Growth presentation from stored evidence only.

    Unlike Graham, the live command applies no presentation-time label
    normalization before rendering — `render_fcf_earnings_growth` already
    derives every displayed label/status directly from the stored result, so
    no substitution point is needed here beyond decoding and reusing the
    envelope's own ``instrument_profile`` (the adapter never reads the
    analyzer's own ``result.instrument_profile`` back for rendering either).
    """
    evidence = decode_evidence(run)
    assert isinstance(evidence, FCFEarningsGrowthResult)
    return render_fcf_earnings_growth(evidence, options.mode, instrument_profile=run.instrument_profile)


def _friendly_graham_assembly[AssemblyT: (GrahamNumberInputAssembly, GrowthValueInputAssembly)](
    ticker: str, assembly: AssemblyT
) -> AssemblyT:
    """Replace a genuine failure's raw reason with the live command's investor-facing text.

    Mirrors `cli._number_failure_output`/`_growth_failure_output` exactly: a
    successful or NOT_APPLICABLE assembly's reason is already safe to show
    verbatim (or, for OK, is None); any other status carries a raw resolver
    reason at capture time that the live command only ever displays after
    `friendly_valuation_failure` normalizes it.
    """
    if assembly.status in _GRAHAM_REASON_ALREADY_SAFE:
        return assembly
    return replace(assembly, reason=friendly_valuation_failure(ticker, assembly.status, assembly.reason))


__all__ = [
    "ReplayOptions",
    "UnsupportedProjectionError",
    "project_run",
]
