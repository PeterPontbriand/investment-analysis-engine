"""Deterministic preservation and corruption checks for FCF workspace evidence."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest

from src.analysis.strategy.fcf_earnings_growth.models import (
    AnnualGrowthObservation,
    Classification,
    FCFClassificationBasis,
    FCFEarningsGrowthPolicy,
    FCFEarningsGrowthResult,
    ForwardEvidence,
    ForwardEvidenceStatus,
    ForwardPolicy,
    MetricResult,
    MetricStatus,
    ReasonCode,
    TrendClassification,
)
from src.core.analysis_status import CalculationStatus
from src.data.financial.provenance import ComponentLineage, ResolvedInput, SourceKind
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
from src.workspace.requests import FCFGrowthSelection
from src.workspace.runs import AnalysisRun

STAMP = datetime(2026, 9, 10, 12, tzinfo=UTC)


def _input(name: str, value: float, *, units: str = "currency") -> ResolvedInput:
    return ResolvedInput(
        name,
        value,
        SourceKind.PROVIDER,
        STAMP,
        provider_id="sec_edgar",
        units=units,
        currency="USD",
        available_at=STAMP,
        retrieved_at=STAMP,
        notes=("First", "Second"),
    )


def _unavailable() -> MetricResult:
    return MetricResult.failure(MetricStatus.UNAVAILABLE, ReasonCode.CONSENSUS_UNAVAILABLE, "No consensus")


def _result() -> FCFEarningsGrowthResult:
    observations: list[AnnualGrowthObservation] = []
    for year in range(2022, 2026):
        start, end = datetime(year, 1, 1, tzinfo=UTC), datetime(year, 12, 31, tzinfo=UTC)
        ocf, capex = _input("operating_cash_flow", 100.0), _input("capital_expenditures", 20.0)
        fcf = ResolvedInput(
            "free_cash_flow",
            80.0,
            SourceKind.DERIVED,
            STAMP,
            units="currency",
            currency="USD",
            lineage=ComponentLineage("OCF minus normalized CapEx", (ocf, capex)),
        )
        shares = _input("weighted_average_diluted_shares", 10.0, units="shares")
        per_share = ResolvedInput(
            "free_cash_flow_per_diluted_share",
            8.0,
            SourceKind.DERIVED,
            STAMP,
            units="currency_per_share",
            currency="USD",
            lineage=ComponentLineage("FCF divided by shares", (fcf, shares)),
        )
        observations.append(
            AnnualGrowthObservation(
                year,
                start,
                end,
                ocf,
                capex,
                fcf,
                _input("diluted_eps", 4.0, units="currency_per_share"),
                shares,
                per_share,
            )
        )
    unit = SecurityUnitEvidence(
        "KO",
        SecurityUnitKind.ORDINARY_SHARE,
        SecurityUnitKind.ORDINARY_SHARE,
        1.0,
        "sec_edgar",
        "Annual filing",
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
    return FCFEarningsGrowthResult(
        ticker="KO",
        requested_as_of=STAMP,
        effective_as_of=STAMP,
        policy=FCFEarningsGrowthPolicy(),
        instrument_profile=profile,
        execution_status=CalculationStatus.OK,
        classification=Classification.FAIL,
        classification_reason_code=ReasonCode.FCF_AND_EPS_NOT_GROWING,
        classification_reason="Zero historical growth",
        selected_horizon_years=3,
        selected_observation_count=4,
        used_horizon_fallback=True,
        period_start=observations[0].period_end,
        period_end=observations[-1].period_end,
        annual_observations=tuple(observations),
        fcf_cagr=MetricResult.ok(0.0),
        fcf_per_share_cagr=MetricResult.ok(0.0),
        eps_cagr=MetricResult.ok(0.0),
        trend_classification=TrendClassification.NEITHER_GROWING,
        market_capitalization=_input("market_capitalization", 1600.0),
        fcf_yield=MetricResult.ok(5.0),
        forward_evidence=ForwardEvidence(
            status=ForwardEvidenceStatus.UNAVAILABLE,
            latest_actual_eps=observations[-1].diluted_eps,
            fy1_consensus_eps=None,
            fy2_consensus_eps=None,
            actual_to_fy1_growth=_unavailable(),
            fy1_to_fy2_growth=_unavailable(),
            confirms_positive_growth=None,
        ),
        warnings=("Horizon fallback", "Consensus unavailable"),
        diagnostics=ResolutionTrace(
            (
                ResolutionEvent("fcf", ResolutionStage.PROVIDER, ResolutionOutcome.SUCCESS, "Resolved history"),
                ResolutionEvent("consensus", ResolutionStage.PROVIDER, ResolutionOutcome.UNAVAILABLE, "No estimates"),
            )
        ),
    )


def _run(result: FCFEarningsGrowthResult | None = None) -> AnalysisRun:
    return AnalysisRun(
        analysis_run_id=UUID("11111111-1111-4111-8111-111111111111"),
        ticker="KO",
        analysis_id="fcf_earnings_growth",
        method_id="reported_fcf_eps_cagr",
        config_schema_version=1,
        requested_config=FCFGrowthSelection(),
        started_at=STAMP,
        completed_at=STAMP,
        method_version=2,
        result_schema_version=3,
        evidence_codec_version=1,
        status=RunOutcome.COMPLETED,
        result_evidence=encode_evidence(result or _result()),
    )


def test_full_native_result_round_trip() -> None:
    original = _result()
    run = _run(original)
    restored = decode_evidence(AnalysisRun.model_validate_json(run.model_dump_json()))
    assert isinstance(restored, FCFEarningsGrowthResult)
    assert restored == original
    assert restored.diagnostics == original.diagnostics
    assert restored.annual_observations[0].free_cash_flow is not original.annual_observations[0].free_cash_flow
    assert (restored.method_version, restored.schema_version) == (2, 3)
    assert encode_evidence(restored) == run.result_evidence


def test_per_share_policy_and_missing_optional_metrics_round_trip() -> None:
    original = _result()
    result = replace(
        original,
        policy=FCFEarningsGrowthPolicy(
            classification_basis=FCFClassificationBasis.FCF_PER_SHARE,
            forward_policy=ForwardPolicy.CONFIRMATION,
            include_fcf_yield=False,
        ),
        instrument_profile=None,
        market_capitalization=None,
        fcf_cagr=MetricResult.failure(
            MetricStatus.UNAVAILABLE, ReasonCode.MISSING_FACT, "Total FCF growth unavailable"
        ),
        fcf_yield=MetricResult.failure(MetricStatus.NOT_APPLICABLE, ReasonCode.NOT_REQUESTED, "Not requested"),
    )
    assert decode_evidence(_run(result)) == result


@pytest.mark.parametrize(
    "status",
    [
        CalculationStatus.INPUT_UNAVAILABLE,
        CalculationStatus.PROVIDER_ERROR,
        CalculationStatus.INVALID_INPUT,
        CalculationStatus.NOT_APPLICABLE,
    ],
)
def test_non_success_preserves_explicit_reasons_and_profile(status: CalculationStatus) -> None:
    original = _result()
    metric_status = (
        MetricStatus.NOT_APPLICABLE if status is CalculationStatus.NOT_APPLICABLE else MetricStatus.UNAVAILABLE
    )
    reason = (
        ReasonCode.INSTRUMENT_KIND_NOT_APPLICABLE
        if status is CalculationStatus.NOT_APPLICABLE
        else ReasonCode.MISSING_FACT
    )
    metric = MetricResult.failure(metric_status, reason, "No company history")
    result = replace(
        original,
        execution_status=status,
        classification=Classification.INDETERMINATE,
        classification_reason_code=reason,
        classification_reason="No company history",
        selected_horizon_years=None,
        selected_observation_count=0,
        used_horizon_fallback=False,
        annual_observations=(),
        period_start=None,
        period_end=None,
        fcf_cagr=metric,
        fcf_per_share_cagr=metric,
        eps_cagr=metric,
        instrument_profile=InstrumentProfile(
            "KO", None, InstrumentKindEvidence("KO", InstrumentKind.ETF, "ETF", "yfinance", STAMP), ()
        ),
    )
    assert decode_evidence(_run(result)) == result


@pytest.mark.parametrize("status", [ForwardEvidenceStatus.PARTIAL, ForwardEvidenceStatus.COMPLETE])
def test_forward_evidence_round_trip(status: ForwardEvidenceStatus) -> None:
    original = _result()
    complete = status is ForwardEvidenceStatus.COMPLETE
    forward = ForwardEvidence(
        status=status,
        latest_actual_eps=_input("eps", 4.0),
        fy1_consensus_eps=_input("fy1", 5.0),
        fy2_consensus_eps=_input("fy2", 6.0) if complete else None,
        actual_to_fy1_growth=MetricResult.ok(25.0),
        fy1_to_fy2_growth=MetricResult.ok(20.0) if complete else _unavailable(),
        confirms_positive_growth=True if complete else None,
    )
    result = replace(original, forward_evidence=forward)
    assert decode_evidence(_run(result)) == result


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
def test_versions_rejected_before_decoding(field: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected(_payload: object) -> FCFEarningsGrowthResult:
        raise AssertionError("Unsupported versions must fail before decoding")

    monkeypatch.setattr("src.workspace.codecs.decode_fcf_growth", unexpected)
    with pytest.raises(UnsupportedRunVersionError):
        decode_evidence(_run().model_copy(update={field: 99}))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("strategy_id", "graham"),
        ("method_id", "sma_crossover"),
        ("method_version", 1),
        ("schema_version", 1),
        ("method_version", True),
        ("schema_version", 3.0),
        ("selected_observation_count", 1),
        ("ticker", "MSFT"),
        ("extra", 1),
        ("effective_as_of", "2026-09-10T12:00:00"),
        ("classification", "unknown"),
    ],
)
def test_corrupt_result_is_classified(field: str, value: object) -> None:
    run = _run()
    assert run.result_evidence is not None
    run.result_evidence["result"][field] = value
    with pytest.raises(InvalidStoredRunError):
        decode_evidence(run)


@pytest.mark.parametrize(
    "location",
    [
        "metric_inf",
        "metric_string",
        "metric_bool",
        "annual_time",
        "annual_fcf",
        "per_share",
        "lineage",
        "profile_ticker",
        "document_time",
        "forward",
        "policy",
    ],
)
def test_corrupt_nested_evidence(location: str) -> None:
    run = _run()
    assert run.result_evidence is not None
    result = run.result_evidence["result"]
    observation = result["annual_observations"][0]
    if location.startswith("metric_"):
        result["fcf_cagr"]["value"] = {"metric_inf": float("inf"), "metric_string": "0", "metric_bool": True}[location]
    elif location == "annual_time":
        observation["period_end"] = "2022-12-31T00:00:00"
    elif location == "annual_fcf":
        observation["free_cash_flow"]["value"] = 81.0
    elif location == "per_share":
        observation["free_cash_flow_per_diluted_share"] = None
    elif location == "lineage":
        observation["free_cash_flow"]["lineage"]["components"] = []
    elif location == "profile_ticker":
        result["instrument_profile"]["ticker"] = "MSFT"
    elif location == "document_time":
        result["instrument_profile"]["security_unit_resolution"]["provenance"]["documents"][0]["available_at"] = (
            "2026-09-10T12:00:00"
        )
    elif location == "forward":
        result["forward_evidence"]["confirms_positive_growth"] = True
    else:
        result["policy"]["classification_basis"] = "unknown"
    with pytest.raises(InvalidStoredRunError):
        decode_evidence(run)


def test_pairing_missing_metadata_and_absent_evidence() -> None:
    run = _run()
    with pytest.raises(UnsupportedRunVersionError):
        decode_evidence(run.model_copy(update={"analysis_id": "momentum"}))
    with pytest.raises(InvalidStoredRunError):
        decode_evidence(run.model_copy(update={"result_evidence": {"result": {}}}))
    with pytest.raises(InvalidStoredRunError):
        decode_evidence(run.model_copy(update={"ticker": "MSFT"}))
    assert (
        decode_evidence(
            run.model_copy(
                update={"status": RunOutcome.FAILED, "failure_reason_code": "provider_error", "result_evidence": None}
            )
        )
        is None
    )


def test_decoding_is_pure_and_does_not_mutate_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    run = _run()
    before = run.model_dump_json()

    def unexpected(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Replay must not execute analysis")

    monkeypatch.setattr(
        "src.analysis.strategy.fcf_earnings_growth.analyzer.FCFEarningsGrowthAnalyzer.run_analysis", unexpected
    )
    for name in (
        "compute_free_cash_flow",
        "compute_fcf_per_diluted_share",
        "compute_growth_percent",
        "compute_cagr",
        "compute_fcf_yield",
        "classify_fcf_earnings_growth",
    ):
        monkeypatch.setattr(f"src.analysis.strategy.fcf_earnings_growth.calculators.{name}", unexpected)
    restored = decode_evidence(run)
    assert isinstance(restored, FCFEarningsGrowthResult)
    assert restored.fcf_cagr.value == 0.0
    assert run.model_dump_json() == before


def test_invalid_native_evidence_is_revalidated() -> None:
    original = _result()
    # A frozen native instance can still be corrupted by explicit low-level mutation.
    object.__setattr__(original, "effective_as_of", STAMP.replace(tzinfo=None))
    with pytest.raises(InvalidStoredRunError):
        encode_evidence(original)


@pytest.mark.parametrize("field", ["strategy_id", "method_id", "method_version", "schema_version"])
def test_missing_native_metadata_rejected(field: str) -> None:
    run = _run()
    assert run.result_evidence is not None
    del run.result_evidence["result"][field]
    with pytest.raises(InvalidStoredRunError):
        decode_evidence(run)


@pytest.mark.parametrize(
    ("field", "value"),
    [("method_version", 1), ("result_schema_version", 1), ("method_version", True), ("result_schema_version", 3.0)],
)
def test_fcf_envelope_requires_native_version_types(field: str, value: object) -> None:
    with pytest.raises(UnsupportedRunVersionError):
        decode_evidence(_run().model_copy(update={field: value}))


def test_cached_history_and_absent_per_share_evidence_round_trip() -> None:
    original = _result()
    annual = original.annual_observations[0]
    cached = replace(
        annual.operating_cash_flow,
        source_kind=SourceKind.CACHE,
        origin_source_kind=SourceKind.PROVIDER,
        cache_schema_version=1,
    )
    result = replace(
        original,
        annual_observations=(
            replace(
                annual,
                operating_cash_flow=cached,
                weighted_average_diluted_shares=None,
                free_cash_flow_per_diluted_share=None,
            ),
            *original.annual_observations[1:],
        ),
        fcf_per_share_cagr=MetricResult.failure(
            MetricStatus.UNAVAILABLE, ReasonCode.MISSING_FACT, "Shares unavailable"
        ),
    )
    assert decode_evidence(_run(result)) == result
