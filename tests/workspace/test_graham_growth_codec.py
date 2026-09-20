"""Deterministic Graham Growth evidence preservation and dispatch tests."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest

from src.analysis.shared.financial_resolution import PriceComparison
from src.analysis.strategy.graham_growth.calculation import (
    GrahamGrowthCalculationPolicy,
    GrahamGrowthValueResult,
    GrowthValueInputAssembly,
)
from src.analysis.strategy.graham_growth.service import GrahamGrowthAnalysis
from src.core.analysis_status import CalculationStatus
from src.data.financial.provenance import ComponentLineage, ResolvedInput, SourceKind
from src.data.financial.quote_freshness import QuoteFreshnessEvidence
from src.data.financial.resolution_trace import ResolutionEvent, ResolutionOutcome, ResolutionStage, ResolutionTrace
from src.data.instrument_profile import InstrumentKind, InstrumentKindEvidence, InstrumentProfile
from src.data.security_identity import SecurityIdentity
from src.data.security_unit import (
    SecurityUnitDocument,
    SecurityUnitEvidence,
    SecurityUnitKind,
    SecurityUnitProvenance,
    SecurityUnitResolution,
    SecurityUnitResolutionReason,
)
from src.workspace.codecs import InvalidStoredRunError, UnsupportedRunVersionError, decode_evidence, encode_evidence
from src.workspace.models import RunOutcome
from src.workspace.requests import GrahamGrowthSelection
from src.workspace.runs import AnalysisRun

STAMP = datetime(2026, 9, 10, 12, tzinfo=UTC)


def _analysis() -> GrahamGrowthAnalysis:
    eps = ResolvedInput(
        "eps",
        4.0,
        SourceKind.PROVIDER,
        STAMP,
        provider_id="sec_edgar",
        units="currency_per_share",
        currency="USD",
        observed_at=STAMP,
        available_at=STAMP,
        retrieved_at=STAMP,
        notes=("First", "Second"),
    )
    averaged = ResolvedInput(
        "eps",
        4.0,
        SourceKind.DERIVED,
        STAMP,
        basis="three_year_average",
        lineage=ComponentLineage("Average annual EPS", (eps, eps, eps)),
    )
    growth = ResolvedInput(
        "expected_growth", 6.0, SourceKind.OVERRIDE, STAMP, units="percentage_points", notes=("Explicit forecast",)
    )
    aaa = ResolvedInput("current_aaa_yield", 4.4, SourceKind.OVERRIDE, STAMP, units="percentage_points")
    quote = ResolvedInput(
        "current_price",
        24.0,
        SourceKind.CACHE,
        STAMP,
        origin_source_kind=SourceKind.PROVIDER,
        cache_schema_version=1,
        provider_id="yfinance",
        retrieved_at=STAMP,
    )
    unit = SecurityUnitEvidence(
        "KO", SecurityUnitKind.ORDINARY_SHARE, SecurityUnitKind.ORDINARY_SHARE, 1.0, "sec_edgar", "Annual filing"
    )
    resolution = SecurityUnitResolution(
        SecurityUnitResolutionReason.RESOLVED,
        unit,
        SecurityUnitProvenance(
            "single_common_class",
            "123",
            "Common stock",
            (SecurityUnitDocument("001", "https://www.sec.gov/example", ("c1", "c2"), STAMP, STAMP),),
        ),
    )
    profile = InstrumentProfile(
        "KO",
        SecurityIdentity("KO", "sec_edgar", STAMP, "Coca-Cola", "NYSE", "123"),
        InstrumentKindEvidence("KO", InstrumentKind.EQUITY, "EQUITY", "yfinance", STAMP),
        (),
        unit,
        resolution,
    )
    freshness = QuoteFreshnessEvidence("recent_retrieval", STAMP, STAMP, 0.0, 300.0, None)
    trace = ResolutionTrace(
        (
            ResolutionEvent("eps", ResolutionStage.PROVIDER, ResolutionOutcome.SUCCESS, "Resolved EPS."),
            ResolutionEvent("expected_growth", ResolutionStage.OVERRIDE, ResolutionOutcome.SUCCESS, "Used override."),
        )
    )
    assembly = GrowthValueInputAssembly(
        CalculationStatus.OK, averaged, growth, aaa, quote, quote_freshness=freshness, resolution_trace=trace
    )
    return GrahamGrowthAnalysis(
        "KO",
        STAMP,
        assembly,
        GrahamGrowthValueResult(CalculationStatus.OK, 30.0),
        GrahamGrowthCalculationPolicy(1.5, 1.0, 4.4),
        20.0,
        profile,
        PriceComparison("available", "compatible", 20.0, resolution, freshness),
    )


def _run(analysis: GrahamGrowthAnalysis | None = None) -> AnalysisRun:
    return AnalysisRun(
        analysis_run_id=UUID("11111111-1111-4111-8111-111111111111"),
        ticker="KO",
        analysis_id="graham",
        method_id="graham_growth_value",
        config_schema_version=1,
        requested_config=GrahamGrowthSelection(expected_growth=6.0, aaa_yield_override=4.4),
        started_at=STAMP,
        completed_at=STAMP,
        method_version=1,
        result_schema_version=1,
        evidence_codec_version=1,
        status=RunOutcome.COMPLETED,
        result_evidence=encode_evidence(analysis or _analysis()),
    )


def test_full_growth_evidence_round_trip() -> None:
    original = _analysis()
    run = _run(original)
    restored = decode_evidence(AnalysisRun.model_validate_json(run.model_dump_json()))
    assert isinstance(restored, GrahamGrowthAnalysis)
    assert restored == original
    # Native assembly equality deliberately excludes the resolver trace.
    assert restored.assembly.resolution_trace == original.assembly.resolution_trace
    assert restored.assembly.eps is not original.assembly.eps
    assert encode_evidence(restored) == run.result_evidence


@pytest.mark.parametrize(
    "status",
    [
        CalculationStatus.INPUT_UNAVAILABLE,
        CalculationStatus.NOT_APPLICABLE,
        CalculationStatus.INVALID_INPUT,
        CalculationStatus.PROVIDER_ERROR,
    ],
)
def test_non_success_keeps_reason_and_partial_evidence(status: CalculationStatus) -> None:
    original = _analysis()
    reason = "Required evidence unavailable or method inapplicable."
    analysis = replace(
        original,
        assembly=replace(original.assembly, status=status, reason=reason, expected_growth=None),
        result=GrahamGrowthValueResult(status, reason=reason),
        margin_of_safety_percent=None,
        price_comparison=PriceComparison("unavailable", "calculation_unavailable"),
    )
    assert decode_evidence(_run(analysis)) == analysis


def test_etf_and_missing_profile_round_trip() -> None:
    original = _analysis()
    profile = InstrumentProfile(
        "KO", None, InstrumentKindEvidence("KO", InstrumentKind.ETF, "ETF", "yfinance", STAMP), ()
    )
    analysis = replace(
        original,
        assembly=GrowthValueInputAssembly(CalculationStatus.NOT_APPLICABLE, reason="ETF"),
        result=GrahamGrowthValueResult(CalculationStatus.NOT_APPLICABLE, reason="ETF"),
        margin_of_safety_percent=None,
        price_comparison=None,
        instrument_profile=profile,
    )
    assert decode_evidence(_run(analysis)) == analysis
    analysis = replace(analysis, instrument_profile=None)
    assert decode_evidence(_run(analysis)) == analysis


def test_valid_result_survives_missing_quote() -> None:
    original = _analysis()
    analysis = replace(
        original,
        assembly=replace(
            original.assembly,
            current_price=None,
            quote_status=CalculationStatus.INPUT_UNAVAILABLE,
            quote_reason="Quote missing",
            quote_freshness=None,
        ),
        price_comparison=PriceComparison("unavailable", "missing_quote"),
        margin_of_safety_percent=None,
    )
    assert decode_evidence(_run(analysis)) == analysis


@pytest.mark.parametrize(
    "field",
    [
        "run_schema_version",
        "config_schema_version",
        "method_version",
        "result_schema_version",
        "evidence_codec_version",
        "projection_version",
    ],
)
def test_all_versions_rejected_before_decoding(field: str, monkeypatch: pytest.MonkeyPatch) -> None:
    run = _run().model_copy(update={field: 99})

    def unexpected_decode(_payload: object) -> GrahamGrowthAnalysis:
        raise AssertionError("Decoder must not be called.")

    monkeypatch.setattr("src.workspace.codecs.decode_graham_growth", unexpected_decode)
    with pytest.raises(UnsupportedRunVersionError):
        decode_evidence(run)


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("assembly", "method", "graham_number"),
        ("result", "method", "graham_number"),
        ("assembly", "eps", None),
        ("result", "growth_value", float("inf")),
        ("result", "growth_value", "30"),
        ("result", "growth_value", True),
        ("result", "status", "unknown"),
        ("assembly", "extra", 1),
        ("result", "reason", "Contradiction"),
        ("price_comparison", "percent", 10.0),
        ("instrument_profile", "ticker", "MSFT"),
    ],
)
def test_corrupt_nested_evidence_is_classified(section: str, field: str, value: object) -> None:
    run = _run()
    assert run.result_evidence is not None
    run.result_evidence["analysis"][section][field] = value
    with pytest.raises(InvalidStoredRunError):
        decode_evidence(run)


def test_ticker_mismatch_wrong_payload_and_absent_evidence() -> None:
    run = _run()
    with pytest.raises(InvalidStoredRunError):
        decode_evidence(run.model_copy(update={"ticker": "MSFT"}))
    with pytest.raises(InvalidStoredRunError):
        decode_evidence(run.model_copy(update={"result_evidence": {"run": {}}}))
    failed = AnalysisRun.model_validate(
        {**run.model_dump(), "status": "failed", "failure_reason_code": "provider_error", "result_evidence": None}
    )
    assert decode_evidence(failed) is None


@pytest.mark.parametrize("location", ["as_of", "freshness", "document", "analysis_ticker", "method_missing"])
def test_context_corruption_is_rejected(location: str) -> None:
    run = _run()
    assert run.result_evidence is not None
    payload = run.result_evidence["analysis"]
    if location == "as_of":
        payload["as_of"] = "2026-09-10T12:00:00"
    elif location == "freshness":
        payload["assembly"]["quote_freshness"]["evaluated_at"] = "2026-09-10T12:00:00"
    elif location == "document":
        resolution = payload["price_comparison"]["security_unit_resolution"]
        resolution["provenance"]["documents"][0]["retrieved_at"] = "2026-09-10T12:00:00"
    elif location == "analysis_ticker":
        payload["ticker"] = "MSFT"
    else:
        del payload["result"]["method"]
    with pytest.raises(InvalidStoredRunError):
        decode_evidence(run)


def test_invalid_native_result_is_rejected() -> None:
    original = _analysis()
    invalid = replace(original, result=GrahamGrowthValueResult(CalculationStatus.OK, float("nan")))
    with pytest.raises(InvalidStoredRunError):
        encode_evidence(invalid)


def test_decode_does_not_recalculate_and_preserves_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    run = _run()
    before = run.model_dump_json()

    def unexpected_call(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Stored evidence must not trigger execution or calculation.")

    for target in (
        "src.analysis.strategy.graham_growth.calculation.compute_graham_growth_value",
        "src.analysis.strategy.graham_growth.service.compute_graham_growth_value",
        "src.analysis.strategy.graham_growth.service.run_graham_growth_analysis",
        "src.analysis.strategy.graham_growth.service.evaluate_price_comparison",
        "src.analysis.strategy.graham_growth.service.complete_security_unit_profile",
    ):
        monkeypatch.setattr(target, unexpected_call)
    restored = decode_evidence(run)
    assert isinstance(restored, GrahamGrowthAnalysis)
    assert restored.result.growth_value == 30.0
    assert restored.margin_of_safety_percent == 20.0
    assert run.model_dump_json() == before


def test_failed_assembly_requires_reason_and_consistent_result() -> None:
    run = _run()
    assert run.result_evidence is not None
    run.result_evidence["analysis"]["assembly"]["status"] = "input_unavailable"
    with pytest.raises(InvalidStoredRunError):
        decode_evidence(run)


@pytest.mark.parametrize(("growth", "eps", "value"), [(0.0, 4.0, 6.0), (-1.0, 4.0, 2.0), (6.0, -4.0, -30.0)])
def test_signed_assumptions_and_results_are_preserved(growth: float, eps: float, value: float) -> None:
    original = _analysis()
    assert original.assembly.eps is not None
    assert original.assembly.expected_growth is not None
    analysis = replace(
        original,
        assembly=replace(
            original.assembly,
            eps=replace(original.assembly.eps, value=eps),
            expected_growth=replace(original.assembly.expected_growth, value=growth),
        ),
        result=GrahamGrowthValueResult(CalculationStatus.OK, value),
        margin_of_safety_percent=None,
        price_comparison=None,
    )
    restored = decode_evidence(_run(analysis))
    assert isinstance(restored, GrahamGrowthAnalysis)
    assert restored == analysis
    assert restored.policy == GrahamGrowthCalculationPolicy(1.5, 1.0, 4.4)


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("policy", "base_pe", 0.0),
        ("policy", "growth_multiplier", -1.0),
        ("policy", "baseline_aaa_yield", float("nan")),
        ("policy", "base_pe", "8.5"),
        ("policy", "growth_multiplier", True),
        ("policy", "extra", 1),
        ("assembly", "expected_growth", None),
        ("assembly", "current_aaa_yield", None),
        # BVPS is a foreign Number field, rejected even when null; Growth does not require it.
        ("assembly", "bvps", None),
        ("result", "maximum_indicated_price", 30.0),
    ],
)
def test_growth_specific_corruption(section: str, field: str, value: object) -> None:
    run = _run()
    assert run.result_evidence is not None
    run.result_evidence["analysis"][section][field] = value
    with pytest.raises(InvalidStoredRunError):
        decode_evidence(run)


def test_successful_assembly_can_retain_invalid_calculation() -> None:
    original = _analysis()
    assert original.assembly.expected_growth is not None
    analysis = replace(
        original,
        assembly=replace(original.assembly, expected_growth=replace(original.assembly.expected_growth, value=-2.0)),
        result=GrahamGrowthValueResult(CalculationStatus.INVALID_INPUT, reason="Nonpositive valuation P/E"),
        margin_of_safety_percent=None,
        price_comparison=PriceComparison("unavailable", "calculation_unavailable"),
    )
    assert decode_evidence(_run(analysis)) == analysis


def test_mismatched_dispatch_pair_is_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    # Both identifiers are supported individually, but this combination is not.
    run = _run().model_copy(update={"analysis_id": "momentum"})

    def unexpected_decode(_payload: object) -> GrahamGrowthAnalysis:
        raise AssertionError("Mismatched identifiers must fail before decoding.")

    monkeypatch.setattr("src.workspace.codecs.decode_graham_growth", unexpected_decode)
    with pytest.raises(UnsupportedRunVersionError):
        decode_evidence(run)
