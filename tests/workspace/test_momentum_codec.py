"""Offline preservation and corrupt-record tests for Momentum evidence."""

import json
from dataclasses import replace
from datetime import UTC, date, datetime
from uuid import UUID

import pytest

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.constants import TrendStatus
from investment_analysis_engine.core.metric_result import MetricResult, MetricStatus, ReasonCode
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind, ProviderFailureRecord
from investment_analysis_engine.data.financial.provenance import ComponentLineage, ResolvedInput, SourceKind
from investment_analysis_engine.data.financial.resolution_trace import (
    ResolutionEvent,
    ResolutionOutcome,
    ResolutionStage,
    ResolutionTrace,
)
from investment_analysis_engine.data.instrument_profile import (
    InstrumentKind,
    InstrumentKindEvidence,
    InstrumentProfile,
    InstrumentProfileCapability,
    InstrumentProfileDiagnostic,
    InstrumentProfileResolutionStatus,
)
from investment_analysis_engine.data.market_data import HistoricalDataResolution, MarketDataContext
from investment_analysis_engine.data.security_identity import SecurityIdentity
from investment_analysis_engine.data.security_unit import (
    SecurityUnitDocument,
    SecurityUnitEvidence,
    SecurityUnitKind,
    SecurityUnitProvenance,
    SecurityUnitResolution,
    SecurityUnitResolutionReason,
)
from investment_analysis_engine.strategies.momentum.analyzer import MomentumMetrics, MomentumRun
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.strategy_wiring import EVIDENCE_BY_KEY
from investment_analysis_engine.workspace.codecs import (
    InvalidStoredRunError,
    UnsupportedRunVersionError,
    decode_evidence,
)
from investment_analysis_engine.workspace.runs import AnalysisRun
from tests._wiring import codecs_with_decode, encode_native

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
        ticker="CNR.TO",
        effective_as_of=STAMP,
        execution_status=CalculationStatus.OK,
        metrics=MomentumMetrics(
            "CNR.TO", TrendStatus.BEARISH, 42.5, 44.0, 45.0, 0.0, STAMP, MetricResult.ok(30.0), MetricResult.ok(0.0)
        ),
        market_data=MarketDataContext("yfinance", "1d", date(2026, 9, 10), "CAD", 2, "adjusted"),
        price_inputs=(source, derived),
        resolution_trace=ResolutionTrace(
            (
                ResolutionEvent(
                    "historical_close", ResolutionStage.CACHE, ResolutionOutcome.HIT, "Retained cache evidence."
                ),
                ResolutionEvent(
                    "momentum", ResolutionStage.DERIVATION, ResolutionOutcome.SUCCESS, "Calculated metrics."
                ),
            )
        ),
        instrument_profile=profile,
        data_resolution=HistoricalDataResolution(SourceKind.CACHE, STAMP, STAMP, STAMP, 1),
    )


def _unavailable_evidence() -> MomentumRun:
    """A run that stopped before any calculation: no metrics, no price series."""
    return MomentumRun(
        ticker="CNR.TO",
        effective_as_of=STAMP,
        execution_status=CalculationStatus.INPUT_UNAVAILABLE,
        metrics=None,
        market_data=MarketDataContext(),
        reason_code=ReasonCode.NOT_AVAILABLE_AS_OF,
        reason="No price history is available at or before the requested --as-of boundary.",
    )


def _provider_error_evidence(*, classified: bool = True) -> MomentumRun:
    """A run whose provider failed: no metrics, a fixed reason and, when classified, the failure record."""
    record = ProviderFailureRecord(ProviderFailureKind.UNREACHABLE, "yfinance", "historical_close")
    return MomentumRun(
        ticker="CNR.TO",
        effective_as_of=STAMP,
        execution_status=CalculationStatus.PROVIDER_ERROR,
        metrics=None,
        market_data=MarketDataContext(),
        reason_code=ReasonCode.PROVIDER_ERROR,
        reason="Historical prices could not be retrieved from the market-data provider.",
        provider_failure=record if classified else None,
    )


def _run(evidence: MomentumRun | None = None) -> AnalysisRun:
    return AnalysisRun(
        analysis_run_id=UUID("11111111-1111-4111-8111-111111111111"),
        ticker="CNR.TO",
        analysis_id="momentum",
        method_id="sma_crossover",
        config_schema_version=2,
        requested_config=MomentumSelection(short_window=50, long_window=200, rsi_period=14),
        started_at=STAMP,
        completed_at=STAMP,
        method_version=1,
        result_schema_version=5,
        evidence_codec_version=4,
        status=RunOutcome.COMPLETED,
        result_evidence=encode_native(evidence or _evidence()),
    )


def test_full_typed_round_trip_through_json_envelope() -> None:
    expected = _evidence()
    run = _run(expected)
    restored = decode_evidence(AnalysisRun.model_validate_json(run.model_dump_json()), EVIDENCE_BY_KEY)
    assert restored == expected
    assert restored is not expected
    assert isinstance(restored, MomentumRun)
    assert restored.metrics is not None
    assert isinstance(restored.metrics.status, TrendStatus)
    assert isinstance(restored.price_inputs[1].lineage, ComponentLineage)
    assert isinstance(restored.resolution_trace.events, tuple)
    assert run.result_evidence is not None
    assert json.loads(json.dumps(run.result_evidence, allow_nan=False, ensure_ascii=False)) == run.result_evidence


@pytest.mark.parametrize("retained", [False, True])
def test_optional_metrics_and_missing_profile_remain_explicit(retained: bool) -> None:
    original = _evidence()
    assert original.metrics is not None
    missing = MetricResult.failure(MetricStatus.UNAVAILABLE, ReasonCode.INSUFFICIENT_HISTORY, "Short history.")
    evidence = replace(
        original,
        execution_status=CalculationStatus.INPUT_UNAVAILABLE,
        reason_code=ReasonCode.INSUFFICIENT_HISTORY,
        reason="The long moving average requires 200 observations; 3 were available.",
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
    assert decode_evidence(_run(evidence), EVIDENCE_BY_KEY) == evidence


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
def test_unknown_version_is_classified(field: str) -> None:
    def unexpected_decode(_payload: object, _ticker: str) -> MomentumRun:
        raise AssertionError("Unsupported versions must be rejected before evidence decoding.")

    # Bypass envelope validation deliberately to exercise the decoder's own guard,
    # including version fields normally rejected by the envelope's Literal types.
    run = _run().model_copy(update={field: 99})
    with pytest.raises(UnsupportedRunVersionError, match="Unsupported") as error:
        decode_evidence(run, codecs_with_decode(unexpected_decode))
    assert error.value.reason_code == "unsupported_run_version"


def test_previous_result_schema_version_is_rejected_before_decoding() -> None:
    """A run stored before the profile was embedded in the result is unsupported, not re-read."""

    def unexpected_decode(_payload: object, _ticker: str) -> MomentumRun:
        raise AssertionError("Unsupported versions must be rejected before evidence decoding.")

    for previous in (1, 4):
        with pytest.raises(UnsupportedRunVersionError, match="Unsupported"):
            decode_evidence(
                _run().model_copy(update={"result_schema_version": previous}), codecs_with_decode(unexpected_decode)
            )


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
        decode_evidence(run, EVIDENCE_BY_KEY)
    assert error.value.reason_code == "invalid_stored_run"


@pytest.mark.parametrize("section", ["market_data", "instrument_profile", "data_resolution", "resolution_trace"])
def test_nested_unknown_fields_are_rejected(section: str) -> None:
    run = _run()
    assert run.result_evidence is not None
    run.result_evidence["run"][section]["unexpected"] = "data"
    with pytest.raises(InvalidStoredRunError):
        decode_evidence(run, EVIDENCE_BY_KEY)


def test_mismatched_envelope_and_missing_payload() -> None:
    run = _run()
    with pytest.raises(InvalidStoredRunError):
        decode_evidence(run.model_copy(update={"ticker": "MSFT"}), EVIDENCE_BY_KEY)
    with pytest.raises(UnsupportedRunVersionError):
        decode_evidence(run.model_copy(update={"method_id": "graham_number"}), EVIDENCE_BY_KEY)
    failed = AnalysisRun.model_validate(
        {**run.model_dump(), "status": "failed", "failure_reason_code": "provider_error", "result_evidence": None}
    )
    assert decode_evidence(failed, EVIDENCE_BY_KEY) is None


def test_invalid_native_instance_cannot_bypass_validation() -> None:
    evidence = _evidence()
    assert evidence.metrics is not None
    with pytest.raises(InvalidStoredRunError):
        encode_native(replace(evidence, metrics=replace(evidence.metrics, current_price=float("inf"))))


@pytest.mark.parametrize(
    "evidence",
    [
        pytest.param(_evidence(), id="ok"),
        pytest.param(_unavailable_evidence(), id="input_unavailable-no-metrics"),
        pytest.param(_provider_error_evidence(), id="provider_error-classified"),
        pytest.param(_provider_error_evidence(classified=False), id="provider_error-unclassified"),
    ],
)
def test_every_status_round_trips(evidence: MomentumRun) -> None:
    restored = decode_evidence(_run(evidence), EVIDENCE_BY_KEY)
    assert restored == evidence
    assert isinstance(restored, MomentumRun)
    assert restored.execution_status is evidence.execution_status


def test_unknown_trend_with_metrics_round_trips_as_input_unavailable() -> None:
    original = _evidence()
    assert original.metrics is not None
    evidence = replace(
        original,
        execution_status=CalculationStatus.INPUT_UNAVAILABLE,
        reason_code=ReasonCode.INSUFFICIENT_HISTORY,
        reason="The long moving average requires 200 observations; 3 were available.",
        metrics=replace(original.metrics, status=TrendStatus.UNKNOWN, long_sma_val=None, crossover_signal=None),
    )
    assert decode_evidence(_run(evidence), EVIDENCE_BY_KEY) == evidence


_OK_CHANGES: list[tuple[str, dict[str, object]]] = [
    ("ok without metrics", {"metrics": None}),
    ("ok with a reason", {"reason": "Unexpected."}),
    ("ok with a reason code", {"reason_code": ReasonCode.INSUFFICIENT_HISTORY}),
    ("unavailable without a reason", {"execution_status": CalculationStatus.INPUT_UNAVAILABLE}),
    (
        "unavailable with metrics but a known trend",
        {
            "execution_status": CalculationStatus.INPUT_UNAVAILABLE,
            "reason": "Short.",
            "reason_code": ReasonCode.INSUFFICIENT_HISTORY,
        },
    ),
    ("not_applicable", {"execution_status": CalculationStatus.NOT_APPLICABLE}),
    ("invalid_input", {"execution_status": CalculationStatus.INVALID_INPUT}),
    (
        "provider failure beside ok",
        {"provider_failure": ProviderFailureRecord(ProviderFailureKind.UNREACHABLE, "yfinance")},
    ),
    ("run ticker differing from the metrics", {"ticker": "MSFT"}),
    ("run time differing from the metrics", {"effective_as_of": datetime(2026, 9, 11, tzinfo=UTC)}),
    ("naive time", {"effective_as_of": datetime(2026, 9, 10, 12)}),
]


@pytest.mark.parametrize(("label", "change"), _OK_CHANGES, ids=[label for label, _ in _OK_CHANGES])
def test_inconsistent_status_evidence_is_rejected(label: str, change: dict[str, object]) -> None:
    assert label
    with pytest.raises(InvalidStoredRunError):
        encode_native(replace(_evidence(), **change))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "change",
    [
        {"metrics": _evidence().metrics},
        {"reason_code": ReasonCode.INSUFFICIENT_HISTORY},
        {"reason": ""},
        {"reason": None},
        {"execution_status": CalculationStatus.INPUT_UNAVAILABLE},
    ],
    ids=["with-metrics", "other-code", "empty-reason", "no-reason", "unavailable-with-failure"],
)
def test_inconsistent_failure_evidence_is_rejected(change: dict[str, object]) -> None:
    with pytest.raises(InvalidStoredRunError):
        encode_native(replace(_provider_error_evidence(), **change))  # type: ignore[arg-type]


def test_unavailable_run_without_metrics_accepts_only_the_boundary_code_or_none() -> None:
    with pytest.raises(InvalidStoredRunError):
        encode_native(replace(_unavailable_evidence(), reason_code=ReasonCode.INSUFFICIENT_HISTORY))
    assert encode_native(replace(_unavailable_evidence(), reason_code=None))


def test_a_payload_with_an_unknown_status_is_rejected_on_decode() -> None:
    run = _run()
    assert run.result_evidence is not None
    run.result_evidence["run"]["execution_status"] = "invalid"
    with pytest.raises(InvalidStoredRunError):
        decode_evidence(run, EVIDENCE_BY_KEY)


def test_a_payload_of_the_previous_shape_is_rejected_on_decode() -> None:
    run = _run()
    assert run.result_evidence is not None
    for key in ("ticker", "effective_as_of", "execution_status"):
        del run.result_evidence["run"][key]
    with pytest.raises(InvalidStoredRunError):
        decode_evidence(run, EVIDENCE_BY_KEY)


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
    assert decode_evidence(run, EVIDENCE_BY_KEY) == evidence
    assert run.result_evidence is not None
    document = run.result_evidence["run"]["instrument_profile"]["security_unit_resolution"]["provenance"]["documents"][
        0
    ]
    document["available_at"] = "2026-09-10T12:00:00"
    with pytest.raises(InvalidStoredRunError):
        decode_evidence(run, EVIDENCE_BY_KEY)


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
        decode_evidence(run, EVIDENCE_BY_KEY)
