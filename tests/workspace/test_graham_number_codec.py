"""Deterministic Graham Number evidence preservation and dispatch tests."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest

from src.analysis.shared.financial_resolution import PriceComparison
from src.analysis.strategy.graham_number.calculation import GrahamNumberInputAssembly, GrahamNumberResult
from src.analysis.strategy.graham_number.service import GrahamNumberAnalysis
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
from src.workspace.requests import GrahamNumberSelection
from src.workspace.runs import AnalysisRun

STAMP = datetime(2026, 9, 10, 12, tzinfo=UTC)


def _analysis() -> GrahamNumberAnalysis:
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
    bvps = ResolvedInput("book_value_per_share", 10.0, SourceKind.OVERRIDE, STAMP, units="currency_per_share")
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
            ResolutionEvent("bvps", ResolutionStage.OVERRIDE, ResolutionOutcome.SUCCESS, "Used override."),
        )
    )
    assembly = GrahamNumberInputAssembly(
        CalculationStatus.OK, averaged, bvps, quote, quote_freshness=freshness, resolution_trace=trace
    )
    return GrahamNumberAnalysis(
        "KO",
        STAMP,
        assembly,
        GrahamNumberResult(CalculationStatus.OK, 30.0),
        20.0,
        profile,
        PriceComparison("available", "compatible", 20.0, resolution, freshness),
    )


def _run(analysis: GrahamNumberAnalysis | None = None) -> AnalysisRun:
    return AnalysisRun(
        analysis_run_id=UUID("11111111-1111-4111-8111-111111111111"),
        ticker="KO",
        analysis_id="graham_number",
        method_id="graham_number",
        config_schema_version=1,
        requested_config=GrahamNumberSelection(),
        started_at=STAMP,
        completed_at=STAMP,
        method_version=1,
        result_schema_version=1,
        evidence_codec_version=1,
        status=RunOutcome.COMPLETED,
        result_evidence=encode_evidence(analysis or _analysis()),
    )


def test_full_number_evidence_round_trip() -> None:
    original = _analysis()
    run = _run(original)
    restored = decode_evidence(AnalysisRun.model_validate_json(run.model_dump_json()))
    assert isinstance(restored, GrahamNumberAnalysis)
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
        assembly=replace(original.assembly, status=status, reason=reason, bvps=None),
        result=GrahamNumberResult(status, reason=reason),
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
        assembly=GrahamNumberInputAssembly(CalculationStatus.NOT_APPLICABLE, reason="ETF"),
        result=GrahamNumberResult(CalculationStatus.NOT_APPLICABLE, reason="ETF"),
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

    def unexpected_decode(_payload: object) -> GrahamNumberAnalysis:
        raise AssertionError("Decoder must not be called.")

    monkeypatch.setattr("src.workspace.codecs.decode_graham_number", unexpected_decode)
    with pytest.raises(UnsupportedRunVersionError):
        decode_evidence(run)


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("assembly", "method", "graham_growth_value"),
        ("result", "method", "graham_growth_value"),
        ("assembly", "eps", None),
        ("result", "maximum_indicated_price", float("inf")),
        ("result", "maximum_indicated_price", "30"),
        ("result", "maximum_indicated_price", True),
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
    invalid = replace(original, result=GrahamNumberResult(CalculationStatus.OK, float("nan")))
    with pytest.raises(InvalidStoredRunError):
        encode_evidence(invalid)


def test_decode_does_not_recalculate_and_preserves_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    run = _run()
    before = run.model_dump_json()

    def unexpected_call(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Stored evidence must not trigger execution or calculation.")

    for target in (
        "src.analysis.strategy.graham_number.calculation.compute_graham_number",
        "src.analysis.strategy.graham_number.service.compute_graham_number",
        "src.analysis.strategy.graham_number.service.run_graham_number_analysis",
        "src.analysis.strategy.graham_number.service.evaluate_price_comparison",
        "src.analysis.strategy.graham_number.service.complete_security_unit_profile",
    ):
        monkeypatch.setattr(target, unexpected_call)
    restored = decode_evidence(run)
    assert isinstance(restored, GrahamNumberAnalysis)
    assert restored.result.maximum_indicated_price == 30.0
    assert restored.margin_of_safety_percent == 20.0
    assert run.model_dump_json() == before


def test_failed_assembly_requires_reason_and_consistent_result() -> None:
    run = _run()
    assert run.result_evidence is not None
    run.result_evidence["analysis"]["assembly"]["status"] = "input_unavailable"
    with pytest.raises(InvalidStoredRunError):
        decode_evidence(run)
