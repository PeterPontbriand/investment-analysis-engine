"""Deterministic replay tests for projection v1 (Momentum): no recalculation, no live calls."""

import json
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import patch
from uuid import UUID

import pytest

from src.analysis.strategy.fcf_earnings_growth.models import FCFEarningsGrowthResult, MetricResult
from src.analysis.strategy.graham_growth.calculation import (
    GrahamGrowthCalculationPolicy,
    GrahamGrowthValueResult,
    GrowthValueInputAssembly,
)
from src.analysis.strategy.graham_growth.service import GrahamGrowthAnalysis
from src.analysis.strategy.graham_number.calculation import GrahamNumberInputAssembly, GrahamNumberResult
from src.analysis.strategy.graham_number.service import GrahamNumberAnalysis
from src.analysis.strategy.momentum.momentum_analyzer import MomentumAnalyzer, MomentumRun
from src.core.analysis_status import CalculationStatus
from src.data.financial.provenance import ResolvedInput, SourceKind
from src.data.instrument_profile import InstrumentKind, InstrumentProfile
from src.evaluation.fixtures.instrument_profiles import fixture_instrument_profile, fixture_known_etf_profile
from src.evaluation.fixtures.market_data import FixtureDataClient
from src.reporting.analysis_runs import ReplayOptions, UnsupportedProjectionError, project_run
from src.reporting.presentation import PresentationMode
from src.workspace.codecs import decode_evidence, encode_evidence
from src.workspace.execution import ExecutionCapture, execute
from src.workspace.models import RunOutcome
from src.workspace.momentum_execution import run_momentum
from src.workspace.requests import (
    AnalysisRequest,
    FCFGrowthSelection,
    GrahamGrowthSelection,
    GrahamNumberSelection,
    MomentumSelection,
)
from src.workspace.runs import AnalysisRun
from tests.workspace.test_fcf_growth_codec import _result as _fcf_codec_result

NOW = datetime(2026, 9, 19, 12, 0, 0, tzinfo=UTC)
RUN_ID = UUID("22222222-2222-4222-8222-222222222222")


class _FixtureClient(FixtureDataClient):
    """FixtureDataClient with a stable provider identity for the full resolver path."""

    @property
    def provider_id(self) -> str:
        return "fixture"


@pytest.fixture(autouse=True)
def mock_momentum_settings() -> Iterator[None]:
    """Materialize deterministic Momentum defaults for the analyzer's fallback ticker."""
    mock_analysis = {"default": {"default_ticker": "BTC-USD", "data_start_date": "2026-01-01"}}
    with patch("src.config.ProjectSettings.get_analysis_settings", return_value=mock_analysis):
        yield


class _FakeSink:
    """Minimal AnalysisRunSink that just records; not exercised by replay tests directly."""

    def insert(self, run: AnalysisRun) -> None:
        del run


def _build_run(profile: InstrumentProfile | None = None) -> AnalysisRun:
    """A real, deterministic, persisted-shape Momentum run: the checked-in replay fixture.

    ``presentation_inputs`` is deliberately set to a value that does NOT match
    what the real fixture SMAs would produce if recomputed, so tests can prove
    replay consumes the stored value rather than recalculating it.
    """
    selection = MomentumSelection(short_window=2, long_window=3)
    request = AnalysisRequest(ticker="AAPL", selection=selection)

    def capture() -> ExecutionCapture:
        client = _FixtureClient()
        native = run_momentum(selection, "AAPL", client)
        return ExecutionCapture(
            native_evidence=native,
            profile=profile,
            outcome=RunOutcome.COMPLETED,
            presentation_inputs={"sma_spread": 999.0, "sma_spread_percent": 111.0},
        )

    return execute(request, capture=capture, repository=_FakeSink(), id_factory=lambda: RUN_ID, clock=lambda: NOW)


def _graham_analysis() -> GrahamNumberAnalysis:
    """A deterministic Graham Number analysis whose stored result cannot be recomputed from its inputs.

    The assembly inputs (EPS 4.0, BVPS 10.0) would recompute to a Graham Number of 30.0, but the
    stored ``result`` is 42.0 — so a passing render proves replay consumed the stored evidence
    rather than recalculating it. The native profile copy is deliberately absent.
    """
    eps = ResolvedInput("eps", 4.0, SourceKind.PROVIDER, NOW, provider_id="sec_edgar", as_of=NOW)
    bvps = ResolvedInput("book_value_per_share", 10.0, SourceKind.OVERRIDE, NOW, as_of=NOW)
    assembly = GrahamNumberInputAssembly(CalculationStatus.OK, eps, bvps, None)
    return GrahamNumberAnalysis(
        ticker="KO",
        as_of=NOW,
        assembly=assembly,
        result=GrahamNumberResult(status=CalculationStatus.OK, maximum_indicated_price=42.0),
        margin_of_safety_percent=None,
    )


def _graham_run(
    profile: InstrumentProfile | None = None,
    *,
    analysis: GrahamNumberAnalysis | None = None,
) -> AnalysisRun:
    """A persisted-shape Graham Number run built directly from stored evidence."""
    if analysis is None:
        analysis = _graham_analysis()
    return AnalysisRun(
        analysis_run_id=RUN_ID,
        ticker=analysis.ticker,
        analysis_id="graham",
        method_id="graham_number",
        config_schema_version=1,
        requested_config=GrahamNumberSelection(),
        started_at=NOW,
        completed_at=NOW,
        method_version=1,
        result_schema_version=1,
        evidence_codec_version=1,
        status=RunOutcome.COMPLETED,
        result_evidence=encode_evidence(analysis),
        instrument_profile=profile,
    )


def test_project_run_concise_uses_the_stored_spread_not_a_recomputed_one() -> None:
    """The strongest proof of 'no recalculation'.

    The fixture's real SMAs imply a different spread than the deliberately
    mismatched value stored in presentation_inputs. If replay recomputed
    instead of consuming the stored value, this assertion would fail.
    """
    run = _build_run()
    evidence = decode_evidence(run)
    assert isinstance(evidence, MomentumRun)
    assert evidence.metrics.short_sma_val is not None
    assert evidence.metrics.long_sma_val is not None
    real_spread = evidence.metrics.short_sma_val - evidence.metrics.long_sma_val
    assert real_spread != 999.0  # sanity: the stored/real mismatch is genuine, not coincidental

    rendered = project_run(run, ReplayOptions(mode=PresentationMode.CONCISE))
    assert "SMA spread: 999.00 (currency unspecified) (111.00%)" in rendered


def test_project_run_renders_the_captured_profile_not_the_native_evidence_copy() -> None:
    """Prove replay reads the envelope's own captured profile, not the native copy.

    Momentum's analyzer never sets MomentumRun.instrument_profile; the envelope's
    own top-level field is what replay must use, or a captured profile would
    always render as unavailable even though it was genuinely captured.
    """
    profile = fixture_instrument_profile("AAPL", kind=InstrumentKind.EQUITY, provider_value="EQUITY")
    run = _build_run(profile=profile)
    evidence = decode_evidence(run)
    assert isinstance(evidence, MomentumRun)
    assert evidence.instrument_profile is None  # confirms the native copy is genuinely absent
    assert run.instrument_profile == profile

    rendered = project_run(run, ReplayOptions(mode=PresentationMode.DETAILS))
    assert "Instrument kind: equity" in rendered
    assert "Instrument kind: unavailable" not in rendered


def test_project_run_all_modes_render_from_the_reopened_run() -> None:
    run = _build_run()
    for mode in PresentationMode:
        rendered = project_run(run, ReplayOptions(mode=mode))
        assert rendered
        assert "AAPL" in rendered


def test_project_run_json_matches_the_run_owns_captured_values() -> None:
    run = _build_run()
    payload = json.loads(project_run(run, ReplayOptions(mode=PresentationMode.JSON)))
    assert payload["result"]["sma_spread"] == 999.0
    assert payload["result"]["sma_spread_percent"] == 111.0
    assert payload["ticker"] == "AAPL"


def test_project_run_defaults_to_concise() -> None:
    run = _build_run()
    assert project_run(run) == project_run(run, ReplayOptions(mode=PresentationMode.CONCISE))


def test_project_run_rejects_an_unsupported_projection_version() -> None:
    run = _build_run().model_copy(update={"projection_version": 2})
    with pytest.raises(UnsupportedProjectionError, match="projection version"):
        project_run(run)


def test_project_run_rejects_an_unimplemented_method() -> None:
    run = _build_run().model_copy(update={"analysis_id": "piotroski", "method_id": "f_score"})
    with pytest.raises(UnsupportedProjectionError, match="No v1 replay"):
        project_run(run)


def test_project_run_rejects_a_malformed_stored_presentation_input() -> None:
    """presentation_inputs has no per-key schema; a reopened row is a real boundary."""
    run = _build_run().model_copy(update={"presentation_inputs": {"sma_spread": "not-a-number"}})
    with pytest.raises(UnsupportedProjectionError, match="sma_spread"):
        project_run(run)


def test_project_run_rejects_a_malformed_stored_spread_percent() -> None:
    run = _build_run().model_copy(
        update={"presentation_inputs": {"sma_spread": 1.0, "sma_spread_percent": "not-a-number"}}
    )
    with pytest.raises(UnsupportedProjectionError, match="sma_spread_percent"):
        project_run(run)


def test_project_run_never_calls_the_live_analyzer_or_settings() -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Replay must not call the live analyzer or read settings.")

    run = _build_run()
    with (
        patch.object(MomentumAnalyzer, "run_with_context", forbidden),
        patch.object(MomentumAnalyzer, "run_analysis", forbidden),
        patch("src.config.ProjectSettings.get_momentum_analysis", forbidden),
    ):
        assert project_run(run, ReplayOptions(mode=PresentationMode.DETAILS))


# --- Graham Number (graham / graham_number) v1 replay -----------------------


def test_graham_project_run_renders_the_stored_result_not_a_recomputed_one() -> None:
    """Replay must render the stored result; recomputing from inputs would give a different value."""
    run = _graham_run()
    evidence = decode_evidence(run)
    assert isinstance(evidence, GrahamNumberAnalysis)
    # The assembly inputs (EPS 4.0, BVPS 10.0) recompute to sqrt(22.5 * 4 * 10) == 30.0, not the stored 42.0.
    assert evidence.result.maximum_indicated_price == 42.0

    rendered = project_run(run, ReplayOptions(mode=PresentationMode.CONCISE))
    assert "KO" in rendered
    # The stored value renders; a recompute would render 30.00 instead.
    assert "42.00" in rendered
    assert "30.00" not in rendered


def test_graham_project_run_renders_the_captured_profile_not_the_native_evidence_copy() -> None:
    """Prove replay reads the envelope's own captured profile, not the native copy."""
    profile = fixture_instrument_profile("KO", kind=InstrumentKind.EQUITY, provider_value="EQUITY")
    run = _graham_run(profile=profile)
    evidence = decode_evidence(run)
    assert isinstance(evidence, GrahamNumberAnalysis)
    assert evidence.instrument_profile is None  # confirms the native copy is genuinely absent
    assert run.instrument_profile == profile

    rendered = project_run(run, ReplayOptions(mode=PresentationMode.DETAILS))
    assert "Instrument kind: equity" in rendered
    assert "Instrument kind: unavailable" not in rendered


def test_graham_project_run_all_modes_render_from_the_reopened_run() -> None:
    run = _graham_run()
    for mode in PresentationMode:
        rendered = project_run(run, ReplayOptions(mode=mode))
        assert rendered
        assert "KO" in rendered


def test_graham_project_run_json_matches_the_stored_result() -> None:
    run = _graham_run()
    payload = json.loads(project_run(run, ReplayOptions(mode=PresentationMode.JSON)))
    assert payload["result"]["maximum_indicated_price"] == 42.0
    assert payload["ticker"] == "KO"
    assert payload["analysis"] == "graham"
    assert payload["method"] == "graham_number"


def test_graham_project_run_defaults_to_concise() -> None:
    run = _graham_run()
    assert project_run(run) == project_run(run, ReplayOptions(mode=PresentationMode.CONCISE))


# --- Graham Number (graham / graham_number) v1 replay edge cases --------------


def _graham_invalid_input_analysis() -> GrahamNumberAnalysis:
    """A deterministic Graham Number run whose stored evidence is an invalid-input failure.

    ``reason`` is deliberately a raw/technical resolver message, matching what
    `execute_graham_number` actually persists (the CLI's investor-facing
    normalization is a presentation-time step, never applied before storage),
    so tests can prove replay reapplies it rather than showing the raw text.
    """
    raw_reason = "eps: resolved value failed strict finite validation"
    assembly = GrahamNumberInputAssembly(
        status=CalculationStatus.INVALID_INPUT,
        eps=ResolvedInput("eps", 4.0, SourceKind.PROVIDER, NOW, provider_id="sec_edgar", as_of=NOW),
        bvps=ResolvedInput("book_value_per_share", 10.0, SourceKind.OVERRIDE, NOW, as_of=NOW),
        reason=raw_reason,
    )
    return GrahamNumberAnalysis(
        ticker="KO",
        as_of=NOW,
        assembly=assembly,
        result=GrahamNumberResult(status=CalculationStatus.INVALID_INPUT, reason=raw_reason),
        margin_of_safety_percent=None,
    )


def test_graham_project_run_invalid_input_renders_stored_failure_without_recalculation() -> None:
    """Replay normalizes the stored raw reason to the live command's investor-facing text.

    Proves the retroactive E2 fix: replay must reapply `friendly_graham_failure` to a
    genuine failure's stored raw reason, exactly as `cli._number_failure_output` does,
    rather than leaking the resolver's technical text. It also proves no Graham Number
    value is fabricated for a failed analysis.
    """
    run = _graham_run(analysis=_graham_invalid_input_analysis())
    evidence = decode_evidence(run)
    assert isinstance(evidence, GrahamNumberAnalysis)
    assert evidence.assembly.status is CalculationStatus.INVALID_INPUT
    assert evidence.assembly.reason == "eps: resolved value failed strict finite validation"
    assert evidence.result.status is CalculationStatus.INVALID_INPUT
    assert evidence.margin_of_safety_percent is None

    rendered = project_run(run, ReplayOptions(mode=PresentationMode.CONCISE))
    assert "KO" in rendered
    assert "Status: invalid input" in rendered
    # The raw resolver reason is normalized to the live command's investor-facing sentence...
    assert "Unable to analyze KO: the requested Graham inputs are invalid. Review the method and overrides." in rendered
    # ...and the raw technical string must never leak through.
    assert "resolved value failed strict finite validation" not in rendered
    assert "Graham Number (maximum indicated price)" not in rendered


def _graham_quote_failure_analysis() -> GrahamNumberAnalysis:
    """A successful Number analysis whose optional quote lookup failed with a raw technical reason.

    ``quote_status`` is a genuine failure status and ``quote_reason`` is deliberately NOT
    investor-facing; replay must render the normalized public sentence, not this text.
    """
    eps = ResolvedInput("eps", 4.0, SourceKind.PROVIDER, NOW, provider_id="sec_edgar", as_of=NOW)
    bvps = ResolvedInput("book_value_per_share", 10.0, SourceKind.OVERRIDE, NOW, as_of=NOW)
    assembly = GrahamNumberInputAssembly(
        status=CalculationStatus.OK,
        eps=eps,
        bvps=bvps,
        current_price=None,
        quote_status=CalculationStatus.PROVIDER_ERROR,
        quote_reason="Provider error: connection reset",
    )
    return GrahamNumberAnalysis(
        ticker="KO",
        as_of=NOW,
        assembly=assembly,
        result=GrahamNumberResult(status=CalculationStatus.OK, maximum_indicated_price=42.0),
        margin_of_safety_percent=None,
    )


def test_graham_project_run_normalizes_raw_quote_reason_to_public_sentence() -> None:
    """Replay renders the investor-facing quote sentence and never leaks the raw technical reason."""
    run = _graham_run(analysis=_graham_quote_failure_analysis())
    evidence = decode_evidence(run)
    assert isinstance(evidence, GrahamNumberAnalysis)
    # The stored evidence carries a genuine quote failure with a deliberately raw/technical reason.
    assert evidence.assembly.quote_status is CalculationStatus.PROVIDER_ERROR
    assert evidence.assembly.quote_reason == "Provider error: connection reset"

    rendered = project_run(run, ReplayOptions(mode=PresentationMode.DIAGNOSTICS))
    # The stored technical reason must be replaced by the investor-facing sentence...
    assert "The configured quote provider could not complete the request." in rendered
    # ...and the raw technical string must never appear anywhere in the replay output.
    assert "Provider error: connection reset" not in rendered


def _graham_etf_not_applicable_analysis() -> GrahamNumberAnalysis:
    """A deterministic Graham Number run whose stored evidence is the ETF not-applicable failure."""
    reason = (
        "Graham Number is a company-level valuation method and does not apply directly to an ETF. "
        "No constituent-level or aggregate ETF valuation was performed."
    )
    assembly = GrahamNumberInputAssembly(status=CalculationStatus.NOT_APPLICABLE, reason=reason)
    return GrahamNumberAnalysis(
        ticker="FLSW",
        as_of=NOW,
        assembly=assembly,
        result=GrahamNumberResult(status=CalculationStatus.NOT_APPLICABLE, reason=reason),
        margin_of_safety_percent=None,
    )


def test_graham_project_run_etf_not_applicable_renders_stored_failure() -> None:
    """Replay renders the stored ETF not-applicable status and reason; it does not fabricate a Graham Number."""
    profile = fixture_known_etf_profile()
    run = _graham_run(profile=profile, analysis=_graham_etf_not_applicable_analysis())
    evidence = decode_evidence(run)
    assert isinstance(evidence, GrahamNumberAnalysis)
    assert evidence.assembly.status is CalculationStatus.NOT_APPLICABLE
    assert evidence.result.status is CalculationStatus.NOT_APPLICABLE
    assert evidence.margin_of_safety_percent is None

    rendered = project_run(run, ReplayOptions(mode=PresentationMode.CONCISE))
    assert "FLSW" in rendered
    assert "Status: not applicable" in rendered
    # The stored ETF reason renders verbatim; no Graham Number value is fabricated.
    assert "Graham Number is a company-level valuation method and does not apply directly to an ETF." in rendered
    assert "Graham Number (maximum indicated price)" not in rendered


def test_graham_project_run_comparison_unavailable_renders_stored_result_without_price() -> None:
    """Replay renders the stored Graham Number and marks the price comparison explicitly unavailable."""
    run = _graham_run()
    evidence = decode_evidence(run)
    assert isinstance(evidence, GrahamNumberAnalysis)
    assert evidence.result.status is CalculationStatus.OK
    assert evidence.assembly.current_price is None
    assert evidence.margin_of_safety_percent is None

    rendered = project_run(run, ReplayOptions(mode=PresentationMode.CONCISE))
    # The stored Graham Number renders...
    assert "42.00" in rendered
    # ...but the price comparison is explicitly unavailable (no quote was fabricated).
    assert "Current price: unavailable" in rendered
    assert "Price comparison: unavailable (no current quote)" in rendered


def test_graham_project_run_failure_fixtures_render_in_all_modes() -> None:
    """The invalid-input and ETF not-applicable runs render in every mode without fabricating a Graham Number."""
    failure_runs = (
        _graham_run(analysis=_graham_invalid_input_analysis()),
        _graham_run(profile=fixture_known_etf_profile(), analysis=_graham_etf_not_applicable_analysis()),
    )
    for run in failure_runs:
        for mode in PresentationMode:
            rendered = project_run(run, ReplayOptions(mode=mode))
            assert rendered
            assert "Graham Number (maximum indicated price)" not in rendered


# ---------------------------------------------------------------------------
# Graham Growth (E3)
# ---------------------------------------------------------------------------

_GROWTH_POLICY = GrahamGrowthCalculationPolicy(base_pe=8.5, growth_multiplier=2.0, baseline_aaa_yield=4.4)


def _growth_analysis(
    *,
    growth_value: float = 999.0,
    current_price: ResolvedInput | None = None,
    margin_of_safety_percent: float | None = None,
) -> GrahamGrowthAnalysis:
    """A deterministic Graham Growth analysis whose stored result cannot be recomputed from its inputs.

    ``growth_value`` (999.0 by default) is deliberately unrelated to the assembly's
    EPS/expected-growth/AAA-yield inputs, so a passing render proves replay consumed
    the stored evidence rather than recalculating it.
    """
    eps = ResolvedInput("eps", 4.0, SourceKind.PROVIDER, NOW, provider_id="sec_edgar", as_of=NOW)
    expected_growth = ResolvedInput("expected_growth", 6.0, SourceKind.OVERRIDE, NOW, as_of=NOW)
    current_aaa_yield = ResolvedInput("current_aaa_yield", 4.4, SourceKind.OVERRIDE, NOW, as_of=NOW)
    assembly = GrowthValueInputAssembly(
        status=CalculationStatus.OK,
        eps=eps,
        expected_growth=expected_growth,
        current_aaa_yield=current_aaa_yield,
        current_price=current_price,
    )
    return GrahamGrowthAnalysis(
        ticker="KO",
        as_of=NOW,
        assembly=assembly,
        result=GrahamGrowthValueResult(status=CalculationStatus.OK, growth_value=growth_value),
        policy=_GROWTH_POLICY,
        margin_of_safety_percent=margin_of_safety_percent,
    )


def _growth_run(
    profile: InstrumentProfile | None = None,
    *,
    analysis: GrahamGrowthAnalysis | None = None,
) -> AnalysisRun:
    """A persisted-shape Graham Growth run built directly from stored evidence."""
    if analysis is None:
        analysis = _growth_analysis()
    return AnalysisRun(
        analysis_run_id=RUN_ID,
        ticker=analysis.ticker,
        analysis_id="graham",
        method_id="graham_growth_value",
        config_schema_version=1,
        requested_config=GrahamGrowthSelection(expected_growth=6.0, aaa_yield_override=4.4),
        started_at=NOW,
        completed_at=NOW,
        method_version=1,
        result_schema_version=1,
        evidence_codec_version=1,
        status=RunOutcome.COMPLETED,
        result_evidence=encode_evidence(analysis),
        instrument_profile=profile,
    )


def test_growth_project_run_renders_the_stored_result_not_a_recomputed_one() -> None:
    """The strongest proof of 'no recalculation' for Growth: the stored growth_value renders verbatim."""
    run = _growth_run()
    evidence = decode_evidence(run)
    assert isinstance(evidence, GrahamGrowthAnalysis)
    assert evidence.result.growth_value == 999.0

    rendered = project_run(run, ReplayOptions(mode=PresentationMode.CONCISE))
    assert "999.00" in rendered


def test_growth_project_run_uses_the_stored_assumptions_not_current_settings() -> None:
    """Replay must never read the live command's current growth assumptions.

    Patches `ProjectSettings.get_graham_value_analysis` (the source `growth_assumptions()`
    reads) to raise; replay must still succeed and must show the *stored* policy
    (base_pe=8.5, growth_multiplier=2.0, baseline_aaa_yield=4.4), never a live default.
    """
    run = _growth_run()

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Replay must not read current Graham Growth assumption settings.")

    with patch("src.config.ProjectSettings.get_graham_value_analysis", forbidden):
        rendered = project_run(run, ReplayOptions(mode=PresentationMode.DETAILS))
    assert "Growth Value = EPS × (8.50 + 2.00 × growth) × 4.40 / AAA yield." in rendered


def test_growth_project_run_renders_negative_growth() -> None:
    """A negative growth value is a valid completed calculation, not an execution failure."""
    run = _growth_run(analysis=_growth_analysis(growth_value=-12.5))
    evidence = decode_evidence(run)
    assert isinstance(evidence, GrahamGrowthAnalysis)
    assert evidence.result.growth_value == -12.5

    rendered = project_run(run, ReplayOptions(mode=PresentationMode.CONCISE))
    assert "-12.50" in rendered


def test_growth_project_run_renders_the_captured_profile_not_the_native_evidence_copy() -> None:
    profile = fixture_instrument_profile("KO", kind=InstrumentKind.EQUITY, provider_value="EQUITY")
    run = _growth_run(profile=profile)
    evidence = decode_evidence(run)
    assert isinstance(evidence, GrahamGrowthAnalysis)
    assert evidence.instrument_profile is None
    assert run.instrument_profile == profile

    rendered = project_run(run, ReplayOptions(mode=PresentationMode.DETAILS))
    assert "Instrument kind: equity" in rendered


def test_growth_project_run_comparison_unavailable_renders_stored_result_without_price() -> None:
    """Replay renders the stored growth value and marks the price comparison explicitly unavailable."""
    run = _growth_run()
    evidence = decode_evidence(run)
    assert isinstance(evidence, GrahamGrowthAnalysis)
    assert evidence.assembly.current_price is None
    assert evidence.margin_of_safety_percent is None

    rendered = project_run(run, ReplayOptions(mode=PresentationMode.CONCISE))
    assert "Current price: unavailable" in rendered
    assert "Price comparison: unavailable (no current quote)" in rendered


def _growth_invalid_input_analysis() -> GrahamGrowthAnalysis:
    """A deterministic Graham Growth run whose stored evidence is an invalid-input failure.

    ``reason`` is deliberately a raw/technical resolver message, matching what
    `execute_graham_growth` actually persists, so tests can prove replay reapplies
    `friendly_graham_failure` rather than showing the raw text.
    """
    raw_reason = "expected_growth: override value failed strict finite validation"
    assembly = GrowthValueInputAssembly(status=CalculationStatus.INVALID_INPUT, reason=raw_reason)
    return GrahamGrowthAnalysis(
        ticker="KO",
        as_of=NOW,
        assembly=assembly,
        result=GrahamGrowthValueResult(status=CalculationStatus.INVALID_INPUT, reason=raw_reason),
        policy=_GROWTH_POLICY,
        margin_of_safety_percent=None,
    )


def test_growth_project_run_invalid_input_renders_normalized_reason() -> None:
    """Replay normalizes the stored raw reason to the live command's investor-facing text."""
    run = _growth_run(analysis=_growth_invalid_input_analysis())
    evidence = decode_evidence(run)
    assert isinstance(evidence, GrahamGrowthAnalysis)
    assert evidence.assembly.reason == "expected_growth: override value failed strict finite validation"

    rendered = project_run(run, ReplayOptions(mode=PresentationMode.CONCISE))
    assert "KO" in rendered
    assert "Unable to analyze KO: the requested Graham inputs are invalid. Review the method and overrides." in rendered
    assert "override value failed strict finite validation" not in rendered


def _growth_etf_not_applicable_analysis() -> GrahamGrowthAnalysis:
    """A deterministic Graham Growth run whose stored evidence is the ETF not-applicable failure."""
    reason = (
        "Graham growth value is a company-level valuation method and does not apply directly to an ETF. "
        "No constituent-level or aggregate ETF valuation was performed."
    )
    assembly = GrowthValueInputAssembly(status=CalculationStatus.NOT_APPLICABLE, reason=reason)
    return GrahamGrowthAnalysis(
        ticker="FLSW",
        as_of=NOW,
        assembly=assembly,
        result=GrahamGrowthValueResult(status=CalculationStatus.NOT_APPLICABLE, reason=reason),
        policy=_GROWTH_POLICY,
        margin_of_safety_percent=None,
    )


def test_growth_project_run_etf_not_applicable_renders_stored_failure() -> None:
    profile = fixture_known_etf_profile()
    run = _growth_run(profile=profile, analysis=_growth_etf_not_applicable_analysis())
    evidence = decode_evidence(run)
    assert isinstance(evidence, GrahamGrowthAnalysis)
    assert evidence.assembly.status is CalculationStatus.NOT_APPLICABLE

    rendered = project_run(run, ReplayOptions(mode=PresentationMode.CONCISE))
    assert "FLSW" in rendered
    assert "Graham growth value is a company-level valuation method and does not apply directly to an ETF." in rendered


def _growth_quote_failure_analysis() -> GrahamGrowthAnalysis:
    """A successful Growth analysis whose optional quote lookup failed with a raw technical reason."""
    eps = ResolvedInput("eps", 4.0, SourceKind.PROVIDER, NOW, provider_id="sec_edgar", as_of=NOW)
    expected_growth = ResolvedInput("expected_growth", 6.0, SourceKind.OVERRIDE, NOW, as_of=NOW)
    current_aaa_yield = ResolvedInput("current_aaa_yield", 4.4, SourceKind.OVERRIDE, NOW, as_of=NOW)
    assembly = GrowthValueInputAssembly(
        status=CalculationStatus.OK,
        eps=eps,
        expected_growth=expected_growth,
        current_aaa_yield=current_aaa_yield,
        current_price=None,
        quote_status=CalculationStatus.PROVIDER_ERROR,
        quote_reason="Provider error: connection reset",
    )
    return GrahamGrowthAnalysis(
        ticker="KO",
        as_of=NOW,
        assembly=assembly,
        result=GrahamGrowthValueResult(status=CalculationStatus.OK, growth_value=10.0),
        policy=_GROWTH_POLICY,
        margin_of_safety_percent=None,
    )


def test_growth_project_run_normalizes_raw_quote_reason_to_public_sentence() -> None:
    run = _growth_run(analysis=_growth_quote_failure_analysis())
    evidence = decode_evidence(run)
    assert isinstance(evidence, GrahamGrowthAnalysis)
    assert evidence.assembly.quote_status is CalculationStatus.PROVIDER_ERROR
    assert evidence.assembly.quote_reason == "Provider error: connection reset"

    rendered = project_run(run, ReplayOptions(mode=PresentationMode.DIAGNOSTICS))
    assert "The configured quote provider could not complete the request." in rendered
    assert "Provider error: connection reset" not in rendered


def test_growth_project_run_all_modes_render_from_the_reopened_run() -> None:
    runs = (
        _growth_run(),
        _growth_run(analysis=_growth_invalid_input_analysis()),
        _growth_run(profile=fixture_known_etf_profile(), analysis=_growth_etf_not_applicable_analysis()),
    )
    for run in runs:
        for mode in PresentationMode:
            rendered = project_run(run, ReplayOptions(mode=mode))
            assert rendered


def test_growth_project_run_json_matches_the_stored_result() -> None:
    run = _growth_run()
    payload = json.loads(project_run(run, ReplayOptions(mode=PresentationMode.JSON)))
    assert payload["ticker"] == "KO"


def test_growth_project_run_never_calls_the_live_analyzer_or_settings() -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Replay must not call the live Growth analyzer or read settings.")

    run = _growth_run()
    with (
        patch("src.analysis.strategy.graham_growth.analyzer.GrahamGrowthAnalyzer.run_analysis", forbidden),
        patch("src.config.ProjectSettings.get_graham_value_analysis", forbidden),
    ):
        assert project_run(run, ReplayOptions(mode=PresentationMode.DETAILS))


# ---------------------------------------------------------------------------
# FCF / Earnings Growth (E4)
# ---------------------------------------------------------------------------


def _fcf_run(
    profile: InstrumentProfile | None = None,
    *,
    result: FCFEarningsGrowthResult | None = None,
) -> AnalysisRun:
    """A persisted-shape FCF/Earnings Growth run built directly from stored evidence."""
    if result is None:
        result = _fcf_codec_result()
    return AnalysisRun(
        analysis_run_id=RUN_ID,
        ticker=result.ticker,
        analysis_id="fcf_earnings_growth",
        method_id="reported_fcf_eps_cagr",
        config_schema_version=1,
        requested_config=FCFGrowthSelection(),
        started_at=NOW,
        completed_at=NOW,
        method_version=2,
        result_schema_version=3,
        evidence_codec_version=1,
        status=RunOutcome.COMPLETED,
        result_evidence=encode_evidence(result),
        instrument_profile=profile,
    )


def test_fcf_project_run_renders_the_stored_result_not_a_recomputed_one() -> None:
    """The stored CAGR is deliberately inconsistent with the annual observations' real growth.

    The codec fixture's annual observations are identical year over year (a real
    recompute would show 0% CAGR); the stored `fcf_cagr` here is a distinct value the
    real inputs could not produce, so a passing render proves consumption, not
    recomputation.
    """
    result = replace(_fcf_codec_result(), fcf_cagr=MetricResult.ok(777.0))
    run = _fcf_run(result=result)
    evidence = decode_evidence(run)
    assert isinstance(evidence, FCFEarningsGrowthResult)
    assert evidence.fcf_cagr.value == 777.0

    rendered = project_run(run, ReplayOptions(mode=PresentationMode.CONCISE))
    assert "777.00%" in rendered


def test_fcf_project_run_renders_the_captured_profile_not_the_native_evidence_copy() -> None:
    """FCF's adapter never reads `result.instrument_profile` back for rendering either.

    The envelope's own `instrument_profile` field (populated from the composed
    profile the adapter actually used) is what replay must show, matching the
    adapter's documented behavior exactly.
    """
    profile = fixture_instrument_profile("KO", kind=InstrumentKind.EQUITY, provider_value="EQUITY")
    codec_result = _fcf_codec_result()
    result = replace(codec_result, instrument_profile=None)
    run = _fcf_run(profile=profile, result=result)
    evidence = decode_evidence(run)
    assert isinstance(evidence, FCFEarningsGrowthResult)
    assert evidence.instrument_profile is None
    assert run.instrument_profile == profile

    rendered = project_run(run, ReplayOptions(mode=PresentationMode.DETAILS))
    assert "Instrument kind: equity" in rendered


def test_fcf_project_run_renders_partial_evidence_and_missing_forward_context() -> None:
    """The codec fixture's forward evidence is naturally unavailable (no consensus data)."""
    run = _fcf_run()
    evidence = decode_evidence(run)
    assert isinstance(evidence, FCFEarningsGrowthResult)
    assert evidence.forward_evidence.fy1_consensus_eps is None

    rendered = project_run(run, ReplayOptions(mode=PresentationMode.DETAILS))
    assert "Forward EPS" in rendered


def test_fcf_project_run_all_modes_render_from_the_reopened_run() -> None:
    run = _fcf_run()
    for mode in PresentationMode:
        rendered = project_run(run, ReplayOptions(mode=mode))
        assert rendered
        assert "KO" in rendered


def test_fcf_project_run_json_matches_the_stored_result() -> None:
    run = _fcf_run()
    payload = json.loads(project_run(run, ReplayOptions(mode=PresentationMode.JSON)))
    assert payload["ticker"] == "KO"
    assert payload["result_schema_version"] == 3


def test_fcf_project_run_defaults_to_concise() -> None:
    run = _fcf_run()
    assert project_run(run) == project_run(run, ReplayOptions(mode=PresentationMode.CONCISE))


def test_fcf_project_run_never_calls_a_live_analyzer() -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Replay must not call a live FCF analyzer.")

    run = _fcf_run()
    with patch("src.analysis.strategy.fcf_earnings_growth.analyzer.FCFEarningsGrowthAnalyzer.run_analysis", forbidden):
        assert project_run(run, ReplayOptions(mode=PresentationMode.DIAGNOSTICS))
