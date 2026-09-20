"""Offline preservation and corrupt-record tests for Momentum evidence."""

import json
from dataclasses import replace
from datetime import UTC, date, datetime
from uuid import UUID

import pytest

from src.analysis.strategy.momentum.momentum_analyzer import MomentumMetrics, MomentumRun
from src.core.constants import TrendStatus
from src.core.metric_result import MetricResult, MetricStatus, ReasonCode
from src.data.financial.provenance import ComponentLineage, ResolvedInput, SourceKind
from src.data.financial.resolution_trace import ResolutionEvent, ResolutionOutcome, ResolutionStage, ResolutionTrace
from src.data.instrument_profile import (
    InstrumentKind,
    InstrumentKindEvidence,
    InstrumentProfile,
    InstrumentProfileCapability,
    InstrumentProfileDiagnostic,
    InstrumentProfileResolutionStatus,
)
from src.data.market_data import HistoricalDataResolution, MarketDataContext
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
from src.workspace.requests import MomentumSelection
from src.workspace.runs import AnalysisRun

STAMP = datetime(2026, 9, 10, 12, tzinfo=UTC)


def _evidence() -> MomentumRun:
    source = ResolvedInput(
        "historical_close",
        42.5,
        SourceKind.PROVIDER,
        STAMP,
        units="currency_per_share",
        currency="CAD",
        provider_id="yfinance",
        provider_field="Close",
        observed_at=STAMP,
        retrieved_at=STAMP,
        notes=("First annotation", "Second annotation"),
    )
    derived = ResolvedInput(
        "historical_close",
        42.5,
        SourceKind.DERIVED,
        STAMP,
        lineage=ComponentLineage("Retained transformation", (source,)),
    )
    profile = InstrumentProfile(
        "CNR.TO",
        SecurityIdentity("CNR.TO", "yfinance", STAMP, "Canadian National", "TSX", "123", "456"),
        InstrumentKindEvidence("CNR.TO", InstrumentKind.EQUITY, "EQUITY", "yfinance", STAMP),
        (
            InstrumentProfileDiagnostic(
                InstrumentProfileCapability.SECURITY_UNIT,
                "yfinance",
                InstrumentProfileResolutionStatus.UNSUPPORTED,
                "Capability unavailable.",
            ),
        ),
        security_unit_resolution=SecurityUnitResolution(SecurityUnitResolutionReason.PROVIDER_UNSUPPORTED),
    )
    return MomentumRun(
        MomentumMetrics(
            "CNR.TO", TrendStatus.BEARISH, 42.5, 44.0, 45.0, 0.0, STAMP, MetricResult.ok(30.0), MetricResult.ok(0.0)
        ),
        MarketDataContext("yfinance", "1d", date(2026, 9, 10), "CAD", 2, "adjusted"),
        (source, derived),
        ResolutionTrace(
            (
                ResolutionEvent(
                    "historical_close", ResolutionStage.CACHE, ResolutionOutcome.HIT, "Retained cache evidence."
                ),
                ResolutionEvent(
                    "momentum", ResolutionStage.DERIVATION, ResolutionOutcome.SUCCESS, "Calculated metrics."
                ),
            )
        ),
        profile,
        HistoricalDataResolution(SourceKind.CACHE, STAMP, STAMP, STAMP, 1),
    )


def _run(evidence: MomentumRun | None = None) -> AnalysisRun:
    return AnalysisRun(
        analysis_run_id=UUID("11111111-1111-4111-8111-111111111111"),
        ticker="CNR.TO",
        analysis_id="momentum",
        method_id="sma_crossover",
        config_schema_version=1,
        requested_config=MomentumSelection(short_window=50, long_window=200),
        started_at=STAMP,
        completed_at=STAMP,
        method_version=1,
        result_schema_version=1,
        evidence_codec_version=1,
        status=RunOutcome.COMPLETED,
        result_evidence=encode_evidence(evidence or _evidence()),
    )


def test_full_typed_round_trip_through_json_envelope() -> None:
    expected = _evidence()
    run = _run(expected)
    restored = decode_evidence(AnalysisRun.model_validate_json(run.model_dump_json()))
    assert restored == expected
    assert restored is not expected
    assert isinstance(restored, MomentumRun)
    assert isinstance(restored.metrics.status, TrendStatus)
    assert isinstance(restored.price_inputs[1].lineage, ComponentLineage)
    assert isinstance(restored.resolution_trace.events, tuple)
    assert run.result_evidence is not None
    assert json.loads(json.dumps(run.result_evidence, allow_nan=False)) == run.result_evidence


@pytest.mark.parametrize("retained", [False, True])
def test_optional_metrics_and_missing_profile_remain_explicit(retained: bool) -> None:
    original = _evidence()
    missing = MetricResult.failure(MetricStatus.UNAVAILABLE, ReasonCode.INSUFFICIENT_HISTORY, "Short history.")
    evidence = replace(
        original,
        metrics=replace(
            original.metrics,
            status=TrendStatus.UNKNOWN,
            short_sma_val=None,
            long_sma_val=None,
            crossover_signal=None,
            rsi_result=missing if retained else None,
            crossover_result=missing if retained else None,
        ),
        instrument_profile=None,
        data_resolution=None,
        price_inputs=(),
        resolution_trace=ResolutionTrace(),
    )
    assert decode_evidence(_run(evidence)) == evidence


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
def test_unknown_version_is_classified(field: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_decode(_payload: object) -> MomentumRun:
        raise AssertionError("Unsupported versions must be rejected before evidence decoding.")

    monkeypatch.setattr("src.workspace.codecs.decode_momentum", unexpected_decode)
    # Bypass envelope validation deliberately to exercise the decoder's own guard,
    # including version fields normally rejected by the envelope's Literal types.
    run = _run().model_copy(update={field: 99})
    with pytest.raises(UnsupportedRunVersionError, match="Unsupported") as error:
        decode_evidence(run)
    assert error.value.reason_code == "unsupported_run_version"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("current_price", float("nan")),
        ("short_sma_val", float("inf")),
        ("current_price", "42.5"),
        ("current_price", True),
        ("status", "invalid"),
        ("timestamp", "2026-09-10T12:00:00"),
        ("ticker", "MSFT"),
        ("extra", 1),
    ],
)
def test_corrupt_metric_fields_fail_safely(field: str, value: object) -> None:
    run = _run()
    assert run.result_evidence is not None
    run.result_evidence["run"]["metrics"][field] = value
    with pytest.raises(InvalidStoredRunError, match="Invalid stored Momentum evidence") as error:
        decode_evidence(run)
    assert error.value.reason_code == "invalid_stored_run"


@pytest.mark.parametrize("section", ["market_data", "instrument_profile", "data_resolution", "resolution_trace"])
def test_nested_unknown_fields_are_rejected(section: str) -> None:
    run = _run()
    assert run.result_evidence is not None
    run.result_evidence["run"][section]["unexpected"] = "data"
    with pytest.raises(InvalidStoredRunError):
        decode_evidence(run)


def test_mismatched_envelope_and_missing_payload() -> None:
    run = _run()
    with pytest.raises(InvalidStoredRunError):
        decode_evidence(run.model_copy(update={"ticker": "MSFT"}))
    with pytest.raises(UnsupportedRunVersionError):
        decode_evidence(run.model_copy(update={"method_id": "graham_number"}))
    failed = AnalysisRun.model_validate(
        {**run.model_dump(), "status": "failed", "failure_reason_code": "provider_error", "result_evidence": None}
    )
    assert decode_evidence(failed) is None


def test_invalid_native_instance_cannot_bypass_validation() -> None:
    evidence = _evidence()
    with pytest.raises(InvalidStoredRunError):
        encode_evidence(replace(evidence, metrics=replace(evidence.metrics, current_price=float("inf"))))


def test_security_unit_documents_round_trip_and_reject_naive_dates() -> None:
    evidence = _evidence()
    assert evidence.instrument_profile is not None
    unit = SecurityUnitEvidence(
        "CNR.TO",
        SecurityUnitKind.ORDINARY_SHARE,
        SecurityUnitKind.ORDINARY_SHARE,
        1.0,
        "sec_edgar",
        "Annual filing",
    )
    provenance = SecurityUnitProvenance(
        "single_common_class",
        "123",
        "Common shares",
        (SecurityUnitDocument("001", "https://www.sec.gov/example", ("c1", "c2"), STAMP, STAMP, "TSX"),),
    )
    profile = replace(
        evidence.instrument_profile,
        security_unit_evidence=unit,
        security_unit_resolution=SecurityUnitResolution(SecurityUnitResolutionReason.RESOLVED, unit, provenance),
    )
    evidence = replace(evidence, instrument_profile=profile)
    run = _run(evidence)
    assert decode_evidence(run) == evidence
    assert run.result_evidence is not None
    document = run.result_evidence["run"]["instrument_profile"]["security_unit_resolution"]["provenance"]["documents"][
        0
    ]
    document["available_at"] = "2026-09-10T12:00:00"
    with pytest.raises(InvalidStoredRunError):
        decode_evidence(run)


@pytest.mark.parametrize("location", ["input", "lineage", "trace", "metric", "profile"])
def test_nested_corrupt_evidence_is_rejected(location: str) -> None:
    run = _run()
    assert run.result_evidence is not None
    payload = run.result_evidence["run"]
    if location == "input":
        payload["price_inputs"][0]["resolved_at"] = "2026-09-10T12:00:00"
    elif location == "lineage":
        payload["price_inputs"][1]["lineage"]["components"][0]["value"] = float("-inf")
    elif location == "trace":
        payload["resolution_trace"]["events"][0]["stage"] = "unknown"
    elif location == "metric":
        payload["metrics"]["rsi_result"]["reason_code"] = "missing_fact"
    else:
        payload["instrument_profile"]["identity"]["ticker"] = "MSFT"
    with pytest.raises(InvalidStoredRunError):
        decode_evidence(run)
