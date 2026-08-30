"""Construction-invariant tests for the FCF & earnings-growth Slice B models."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from src.analysis.fcf_earnings_growth import models as models_module
from src.analysis.fcf_earnings_growth.models import (
    AnnualGrowthObservation,
    Classification,
    ClassificationDecision,
    FCFEarningsGrowthPolicy,
    FCFEarningsGrowthResult,
    ForwardEvidence,
    ForwardEvidenceStatus,
    HistoricalHorizon,
    MetricResult,
    MetricStatus,
    ReasonCode,
    TrendClassification,
)
from src.core.analysis_status import CalculationStatus
from src.data.financial.provenance import ResolvedInput, SourceKind

RESOLVED_AT = datetime(2025, 12, 31, tzinfo=UTC)
PERIOD_START = datetime(2020, 1, 1, tzinfo=UTC)
PERIOD_END = datetime(2025, 12, 31, tzinfo=UTC)


def _forward_unavailable() -> ForwardEvidence:
    """Build a valid no-estimate forward evidence block."""
    return ForwardEvidence(
        status=ForwardEvidenceStatus.UNAVAILABLE,
        latest_actual_eps=None,
        fy1_consensus_eps=None,
        fy2_consensus_eps=None,
        actual_to_fy1_growth=MetricResult.failure(
            MetricStatus.UNAVAILABLE, ReasonCode.MISSING_FACT, "No FY1 consensus estimate was available."
        ),
        fy1_to_fy2_growth=MetricResult.failure(
            MetricStatus.UNAVAILABLE, ReasonCode.MISSING_FACT, "No FY2 consensus estimate was available."
        ),
        confirms_positive_growth=None,
    )


def _make_result(**overrides: object) -> FCFEarningsGrowthResult:
    """Build a valid FAIL result and apply *overrides* before construction."""
    base: dict[str, object] = {
        "ticker": "TEST",
        "effective_as_of": RESOLVED_AT,
        "policy": FCFEarningsGrowthPolicy(),
        "execution_status": CalculationStatus.OK,
        "classification": Classification.FAIL,
        "classification_reason_code": ReasonCode.EPS_NOT_GROWING,
        "classification_reason": "Diluted-earnings-per-share compound annual growth is zero or negative.",
        "fcf_cagr": MetricResult.ok(10.0),
        "fcf_per_share_cagr": MetricResult.failure(
            MetricStatus.UNAVAILABLE, ReasonCode.MISSING_FACT, "FCF/share evidence is unavailable."
        ),
        "eps_cagr": MetricResult.ok(-2.0),
        "trend_classification": TrendClassification.FCF_GROWING_EARNINGS_NOT,
        "fcf_yield": MetricResult.ok(5.0),
        "forward_evidence": _forward_unavailable(),
        "period_start": PERIOD_START,
        "period_end": PERIOD_END,
    }
    base.update(overrides)
    return FCFEarningsGrowthResult(**base)  # type: ignore[arg-type]


def _make_pass_result(**overrides: object) -> FCFEarningsGrowthResult:
    """Build a valid PASS result; *overrides* win over the PASS defaults."""
    values: dict[str, object] = {
        "classification": Classification.PASS,
        "classification_reason_code": None,
        "classification_reason": None,
        "fcf_cagr": MetricResult.ok(12.0),
        "eps_cagr": MetricResult.ok(6.0),
        "trend_classification": TrendClassification.BOTH_GROWING,
        "period_start": PERIOD_START,
        "period_end": PERIOD_END,
    }
    values.update(overrides)
    return _make_result(**values)


def _make_indeterminate_result(**overrides: object) -> FCFEarningsGrowthResult:
    """Build a valid INDETERMINATE result; *overrides* win over the defaults."""
    values: dict[str, object] = {
        "classification": Classification.INDETERMINATE,
        "classification_reason_code": ReasonCode.INSUFFICIENT_HISTORY,
        "classification_reason": "Only two completed fiscal years were available.",
        "fcf_cagr": MetricResult.failure(
            MetricStatus.UNAVAILABLE, ReasonCode.INSUFFICIENT_HISTORY, "Insufficient annual history."
        ),
        "eps_cagr": MetricResult.failure(
            MetricStatus.UNAVAILABLE, ReasonCode.INSUFFICIENT_HISTORY, "Insufficient annual history."
        ),
        "trend_classification": TrendClassification.INSUFFICIENT_OR_NONMEANINGFUL_GROWTH,
    }
    values.update(overrides)
    return _make_result(**values)


class TestMetricResult:
    """ok/failure field invariants for the typed metric outcome."""

    def test_ok_result(self) -> None:
        result = MetricResult.ok(25.5)
        assert result.status is MetricStatus.OK
        assert result.value == 25.5
        assert result.reason_code is None
        assert result.reason is None

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
    def test_ok_rejects_non_finite_value(self, value: float) -> None:
        with pytest.raises(ValueError, match="finite"):
            MetricResult.ok(value)

    def test_ok_rejects_reason_fields(self) -> None:
        with pytest.raises(ValueError, match="reason fields to be None"):
            MetricResult(
                status=MetricStatus.OK,
                value=1.0,
                reason_code=ReasonCode.MISSING_FACT,
                reason="should not be present",
            )

    def test_failure_factory(self) -> None:
        result = MetricResult.failure(MetricStatus.UNAVAILABLE, ReasonCode.INSUFFICIENT_HISTORY, "Not enough history.")
        assert result.status is MetricStatus.UNAVAILABLE
        assert result.value is None
        assert result.reason_code is ReasonCode.INSUFFICIENT_HISTORY
        assert result.reason == "Not enough history."

    def test_failure_factory_rejects_ok_status(self) -> None:
        with pytest.raises(ValueError, match="non-ok status"):
            MetricResult.failure(MetricStatus.OK, ReasonCode.MISSING_FACT, "invalid")

    @pytest.mark.parametrize("status", [MetricStatus.UNAVAILABLE, MetricStatus.NOT_APPLICABLE])
    def test_non_ok_rejects_numeric_value(self, status: MetricStatus) -> None:
        with pytest.raises(ValueError, match="value to be None"):
            MetricResult(status=status, value=1.0, reason_code=ReasonCode.MISSING_FACT, reason="r")

    def test_non_ok_requires_reason_code(self) -> None:
        with pytest.raises(ValueError, match="reason_code"):
            MetricResult(status=MetricStatus.UNAVAILABLE, reason="r")

    @pytest.mark.parametrize("reason", [None, "", "   "])
    def test_non_ok_requires_non_empty_reason(self, reason: str | None) -> None:
        with pytest.raises(ValueError, match="non-empty reason"):
            MetricResult(status=MetricStatus.NOT_APPLICABLE, reason_code=ReasonCode.NOT_REQUESTED, reason=reason)


class TestForwardEvidence:
    """Status completeness and confirms_positive_growth invariants."""

    def _eps(self, name: str, value: float) -> ResolvedInput:
        return ResolvedInput(
            field_name=name,
            value=value,
            source_kind=SourceKind.PROVIDER,
            resolved_at=RESOLVED_AT,
            provider_id="fixture",
        )

    def test_complete_valid(self) -> None:
        evidence = ForwardEvidence(
            status=ForwardEvidenceStatus.COMPLETE,
            latest_actual_eps=self._eps("latest_actual_eps", 5.0),
            fy1_consensus_eps=self._eps("fy1_consensus_eps", 6.0),
            fy2_consensus_eps=self._eps("fy2_consensus_eps", 7.0),
            actual_to_fy1_growth=MetricResult.ok(20.0),
            fy1_to_fy2_growth=MetricResult.ok(16.67),
            confirms_positive_growth=True,
        )
        assert evidence.confirms_positive_growth is True

    def test_complete_requires_all_three_values(self) -> None:
        with pytest.raises(ValueError, match="all three EPS values"):
            ForwardEvidence(
                status=ForwardEvidenceStatus.COMPLETE,
                latest_actual_eps=self._eps("latest_actual_eps", 5.0),
                fy1_consensus_eps=self._eps("fy1_consensus_eps", 6.0),
                fy2_consensus_eps=None,
                actual_to_fy1_growth=MetricResult.ok(20.0),
                fy1_to_fy2_growth=MetricResult.ok(16.67),
                confirms_positive_growth=True,
            )

    def test_partial_requires_at_least_one_estimate(self) -> None:
        with pytest.raises(ValueError, match="at least one consensus estimate"):
            ForwardEvidence(
                status=ForwardEvidenceStatus.PARTIAL,
                latest_actual_eps=self._eps("latest_actual_eps", 5.0),
                fy1_consensus_eps=None,
                fy2_consensus_eps=None,
                actual_to_fy1_growth=MetricResult.failure(MetricStatus.UNAVAILABLE, ReasonCode.MISSING_FACT, "No FY1."),
                fy1_to_fy2_growth=MetricResult.failure(MetricStatus.UNAVAILABLE, ReasonCode.MISSING_FACT, "No FY2."),
                confirms_positive_growth=None,
            )

    def test_partial_valid_with_single_interval(self) -> None:
        evidence = ForwardEvidence(
            status=ForwardEvidenceStatus.PARTIAL,
            latest_actual_eps=self._eps("latest_actual_eps", 5.0),
            fy1_consensus_eps=self._eps("fy1_consensus_eps", 4.0),
            fy2_consensus_eps=None,
            actual_to_fy1_growth=MetricResult.ok(-20.0),
            fy1_to_fy2_growth=MetricResult.failure(MetricStatus.UNAVAILABLE, ReasonCode.MISSING_FACT, "No FY2."),
            confirms_positive_growth=None,
        )
        assert evidence.confirms_positive_growth is None

    def test_partial_with_complete_intervals_rejected(self) -> None:
        with pytest.raises(ValueError, match="must have status=complete"):
            ForwardEvidence(
                status=ForwardEvidenceStatus.PARTIAL,
                latest_actual_eps=self._eps("latest_actual_eps", 5.0),
                fy1_consensus_eps=self._eps("fy1_consensus_eps", 6.0),
                fy2_consensus_eps=self._eps("fy2_consensus_eps", 7.0),
                actual_to_fy1_growth=MetricResult.ok(20.0),
                fy1_to_fy2_growth=MetricResult.ok(16.67),
                confirms_positive_growth=True,
            )

    def test_unavailable_requires_no_estimates(self) -> None:
        with pytest.raises(ValueError, match="no usable consensus estimate"):
            ForwardEvidence(
                status=ForwardEvidenceStatus.UNAVAILABLE,
                latest_actual_eps=None,
                fy1_consensus_eps=self._eps("fy1_consensus_eps", 6.0),
                fy2_consensus_eps=None,
                actual_to_fy1_growth=MetricResult.failure(MetricStatus.UNAVAILABLE, ReasonCode.MISSING_FACT, "No FY1."),
                fy1_to_fy2_growth=MetricResult.failure(MetricStatus.UNAVAILABLE, ReasonCode.MISSING_FACT, "No FY2."),
                confirms_positive_growth=None,
            )

    def test_confirms_true_required_when_both_positive(self) -> None:
        with pytest.raises(ValueError, match="confirms_positive_growth must be True"):
            ForwardEvidence(
                status=ForwardEvidenceStatus.COMPLETE,
                latest_actual_eps=self._eps("latest_actual_eps", 5.0),
                fy1_consensus_eps=self._eps("fy1_consensus_eps", 6.0),
                fy2_consensus_eps=self._eps("fy2_consensus_eps", 7.0),
                actual_to_fy1_growth=MetricResult.ok(20.0),
                fy1_to_fy2_growth=MetricResult.ok(16.67),
                confirms_positive_growth=False,
            )

    def test_confirms_false_when_one_interval_nonpositive(self) -> None:
        evidence = ForwardEvidence(
            status=ForwardEvidenceStatus.COMPLETE,
            latest_actual_eps=self._eps("latest_actual_eps", 5.0),
            fy1_consensus_eps=self._eps("fy1_consensus_eps", 4.0),
            fy2_consensus_eps=self._eps("fy2_consensus_eps", 4.2),
            actual_to_fy1_growth=MetricResult.ok(-20.0),
            fy1_to_fy2_growth=MetricResult.ok(5.0),
            confirms_positive_growth=False,
        )
        assert evidence.confirms_positive_growth is False

    def test_confirms_none_required_when_incomplete(self) -> None:
        with pytest.raises(ValueError, match="confirms_positive_growth must be None"):
            ForwardEvidence(
                status=ForwardEvidenceStatus.PARTIAL,
                latest_actual_eps=self._eps("latest_actual_eps", 5.0),
                fy1_consensus_eps=self._eps("fy1_consensus_eps", 6.0),
                fy2_consensus_eps=None,
                actual_to_fy1_growth=MetricResult.ok(20.0),
                fy1_to_fy2_growth=MetricResult.failure(MetricStatus.UNAVAILABLE, ReasonCode.MISSING_FACT, "No FY2."),
                confirms_positive_growth=True,
            )


class TestAnnualGrowthObservation:
    """Fiscal-year span and derived FCF identity invariants."""

    def _components(
        self, resolved_input: Callable[..., ResolvedInput], *, ocf: float, capex: float, fcf: float, eps: float
    ) -> dict[str, object]:
        make = resolved_input
        return {
            "period_start": datetime(2023, 12, 31, tzinfo=UTC),
            "period_end": datetime(2024, 12, 31, tzinfo=UTC),
            "operating_cash_flow": make("operating_cash_flow", ocf),
            "normalized_capital_expenditures": make("normalized_capital_expenditures", capex),
            "free_cash_flow": make("free_cash_flow", fcf),
            "diluted_eps": make("diluted_eps", eps),
        }

    def test_valid_observation(self, resolved_input: Callable[..., ResolvedInput]) -> None:
        observation = AnnualGrowthObservation(
            fiscal_year=2024,
            **self._components(resolved_input, ocf=300.0, capex=100.0, fcf=200.0, eps=5.0),  # type: ignore[arg-type]
        )
        assert observation.free_cash_flow.value == 200.0

    def test_negative_fcf_observation_is_explicit(self, resolved_input: Callable[..., ResolvedInput]) -> None:
        observation = AnnualGrowthObservation(
            fiscal_year=2024,
            **self._components(resolved_input, ocf=50.0, capex=120.0, fcf=-70.0, eps=1.0),  # type: ignore[arg-type]
        )
        assert observation.free_cash_flow.value == -70.0

    def test_fiscal_year_must_be_positive(self, resolved_input: Callable[..., ResolvedInput]) -> None:
        with pytest.raises(ValueError, match="positive year label"):
            AnnualGrowthObservation(
                fiscal_year=0,
                **self._components(resolved_input, ocf=300.0, capex=100.0, fcf=200.0, eps=5.0),  # type: ignore[arg-type]
            )

    def test_period_start_must_not_be_after_end(self, resolved_input: Callable[..., ResolvedInput]) -> None:
        make = resolved_input
        with pytest.raises(ValueError, match="period_start"):
            AnnualGrowthObservation(
                fiscal_year=2024,
                period_start=datetime(2024, 12, 31, tzinfo=UTC),
                period_end=datetime(2023, 12, 31, tzinfo=UTC),
                operating_cash_flow=make("operating_cash_flow", 300.0),
                normalized_capital_expenditures=make("normalized_capital_expenditures", 100.0),
                free_cash_flow=make("free_cash_flow", 200.0),
                diluted_eps=make("diluted_eps", 5.0),
            )

    def test_fcf_identity_enforced(self, resolved_input: Callable[..., ResolvedInput]) -> None:
        with pytest.raises(ValueError, match="free_cash_flow must equal"):
            AnnualGrowthObservation(
                fiscal_year=2024,
                **self._components(resolved_input, ocf=300.0, capex=100.0, fcf=150.0, eps=5.0),  # type: ignore[arg-type]
            )


class TestClassificationDecision:
    """Reason-presence invariants on the classification decision."""

    def test_pass_requires_no_reason(self) -> None:
        with pytest.raises(ValueError, match="must not carry a classification reason"):
            ClassificationDecision(
                classification=Classification.PASS,
                trend_classification=TrendClassification.BOTH_GROWING,
                reason_code=ReasonCode.FCF_NOT_GROWING,
                reason="should not be present",
            )

    def test_pass_valid(self) -> None:
        decision = ClassificationDecision(
            classification=Classification.PASS,
            trend_classification=TrendClassification.BOTH_GROWING,
        )
        assert decision.reason_code is None
        assert decision.reason is None

    def test_fail_requires_reason(self) -> None:
        with pytest.raises(ValueError, match="reason_code and a non-empty reason"):
            ClassificationDecision(
                classification=Classification.FAIL,
                trend_classification=TrendClassification.NEITHER_GROWING,
            )

    def test_indeterminate_requires_reason(self) -> None:
        with pytest.raises(ValueError, match="reason_code and a non-empty reason"):
            ClassificationDecision(
                classification=Classification.INDETERMINATE,
                trend_classification=TrendClassification.INSUFFICIENT_OR_NONMEANINGFUL_GROWTH,
            )

    def test_blank_reason_rejected(self) -> None:
        with pytest.raises(ValueError, match="reason_code and a non-empty reason"):
            ClassificationDecision(
                classification=Classification.FAIL,
                trend_classification=TrendClassification.NEITHER_GROWING,
                reason_code=ReasonCode.FCF_AND_EPS_NOT_GROWING,
                reason="   ",
            )

    def test_fail_valid(self) -> None:
        decision = ClassificationDecision(
            classification=Classification.FAIL,
            trend_classification=TrendClassification.NEITHER_GROWING,
            reason_code=ReasonCode.FCF_AND_EPS_NOT_GROWING,
            reason="Both series declined.",
        )
        assert decision.reason_code is ReasonCode.FCF_AND_EPS_NOT_GROWING


class TestFCFEarningsGrowthResult:
    """Result-level invariants from the strategy contract."""

    def test_fixed_identifiers(self) -> None:
        result = _make_result()
        assert result.schema_version == 2
        assert result.strategy_id == "fcf_earnings_growth"
        assert result.method_id == "reported_fcf_eps_cagr"
        assert result.method_version == 2
        assert models_module.SCHEMA_VERSION == 2
        assert models_module.STRATEGY_ID == "fcf_earnings_growth"
        assert models_module.METHOD_ID == "reported_fcf_eps_cagr"
        assert models_module.METHOD_VERSION == 2

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("schema_version", 2),
            ("strategy_id", "other_strategy"),
            ("method_id", "other_method"),
            ("method_version", 2),
        ],
    )
    def test_fixed_identifiers_cannot_be_supplied(self, field: str, value: int | str) -> None:
        with pytest.raises(TypeError, match=field):
            _make_result(**{field: value})

    def test_valid_fail_result(self) -> None:
        result = _make_result()
        assert result.classification is Classification.FAIL
        assert result.classification_reason_code is ReasonCode.EPS_NOT_GROWING

    def test_valid_pass_result(self) -> None:
        result = _make_pass_result()
        assert result.classification is Classification.PASS
        assert result.classification_reason_code is None
        assert result.period_start is not None
        assert result.period_end is not None

    def test_valid_indeterminate_result(self) -> None:
        result = _make_indeterminate_result()
        assert result.classification is Classification.INDETERMINATE
        assert result.classification_reason_code is ReasonCode.INSUFFICIENT_HISTORY

    def test_empty_ticker_rejected(self) -> None:
        with pytest.raises(ValueError, match="ticker must be non-empty"):
            _make_result(ticker="")

    def test_selected_horizon_must_be_3_4_5(self) -> None:
        with pytest.raises(ValueError, match="must be 3, 4, or 5"):
            _make_result(selected_horizon_years=7)

    def test_observation_count_must_match(self) -> None:
        with pytest.raises(ValueError, match="selected_observation_count must equal"):
            _make_result(selected_observation_count=5)

    def test_horizon_requires_n_plus_1_observations(self, resolved_input: Callable[..., ResolvedInput]) -> None:
        make = resolved_input

        def _observation(year: int) -> AnnualGrowthObservation:
            return AnnualGrowthObservation(
                fiscal_year=year,
                period_start=datetime(year - 1, 12, 31, tzinfo=UTC),
                period_end=datetime(year, 12, 31, tzinfo=UTC),
                operating_cash_flow=make("operating_cash_flow", 300.0),
                normalized_capital_expenditures=make("normalized_capital_expenditures", 100.0),
                free_cash_flow=make("free_cash_flow", 200.0),
                diluted_eps=make("diluted_eps", 5.0),
            )

        five_observations = tuple(_observation(year) for year in range(2021, 2026))
        with pytest.raises(ValueError, match="requires exactly N \\+ 1 observations"):
            _make_result(
                selected_horizon_years=3,
                selected_observation_count=5,
                annual_observations=five_observations,
            )
        valid = _make_result(
            selected_horizon_years=3,
            selected_observation_count=4,
            annual_observations=five_observations[:4],
        )
        assert valid.selected_observation_count == 4

    def test_used_horizon_fallback_requires_longest_available(self) -> None:
        with pytest.raises(ValueError, match="only valid under the longest_available horizon"):
            _make_result(
                policy=FCFEarningsGrowthPolicy(historical_horizon=HistoricalHorizon.THREE_YEARS),
                used_horizon_fallback=True,
            )

    def _observations(self, make: Callable[..., ResolvedInput], count: int) -> tuple[AnnualGrowthObservation, ...]:
        """Build *count* valid annual observations for FY2021 onward."""
        return tuple(
            AnnualGrowthObservation(
                fiscal_year=2021 + index,
                period_start=datetime(2020 + index, 12, 31, tzinfo=UTC),
                period_end=datetime(2021 + index, 12, 31, tzinfo=UTC),
                operating_cash_flow=make("operating_cash_flow", 300.0),
                normalized_capital_expenditures=make("normalized_capital_expenditures", 100.0),
                free_cash_flow=make("free_cash_flow", 200.0),
                diluted_eps=make("diluted_eps", 5.0),
            )
            for index in range(count)
        )

    def test_used_horizon_fallback_forbidden_at_five_years(self, resolved_input: Callable[..., ResolvedInput]) -> None:
        six = self._observations(resolved_input, 6)
        with pytest.raises(ValueError, match="exactly 3 or 4 years"):
            _make_result(
                policy=FCFEarningsGrowthPolicy(historical_horizon=HistoricalHorizon.LONGEST_AVAILABLE),
                selected_horizon_years=5,
                selected_observation_count=6,
                annual_observations=six,
                used_horizon_fallback=True,
            )

    def test_used_horizon_fallback_requires_explicit_3_or_4_years(self) -> None:
        with pytest.raises(ValueError, match="exactly 3 or 4 years"):
            _make_result(
                policy=FCFEarningsGrowthPolicy(historical_horizon=HistoricalHorizon.LONGEST_AVAILABLE),
                used_horizon_fallback=True,
            )

    def test_used_horizon_fallback_allowed_below_five_years(self, resolved_input: Callable[..., ResolvedInput]) -> None:
        four = self._observations(resolved_input, 4)
        result = _make_result(
            policy=FCFEarningsGrowthPolicy(historical_horizon=HistoricalHorizon.LONGEST_AVAILABLE),
            selected_horizon_years=3,
            selected_observation_count=4,
            annual_observations=four,
            used_horizon_fallback=True,
        )
        assert result.used_horizon_fallback is True

    def test_include_fcf_yield_false_requires_not_applicable(self) -> None:
        with pytest.raises(ValueError, match="include_fcf_yield=false requires"):
            _make_result(
                policy=FCFEarningsGrowthPolicy(include_fcf_yield=False),
                fcf_yield=MetricResult.ok(5.0),
            )

    def test_include_fcf_yield_false_valid_with_not_requested(self) -> None:
        result = _make_result(
            policy=FCFEarningsGrowthPolicy(include_fcf_yield=False),
            fcf_yield=MetricResult.failure(
                MetricStatus.NOT_APPLICABLE, ReasonCode.NOT_REQUESTED, "FCF yield was not requested."
            ),
        )
        assert result.fcf_yield.status is MetricStatus.NOT_APPLICABLE
        assert result.fcf_yield.reason_code is ReasonCode.NOT_REQUESTED

    def test_pass_requires_ok_execution_status(self) -> None:
        with pytest.raises(ValueError, match="requires execution_status=ok"):
            _make_pass_result(execution_status=CalculationStatus.PROVIDER_ERROR)

    def test_pass_requires_non_null_periods(self) -> None:
        with pytest.raises(ValueError, match="requires execution_status=ok"):
            _make_pass_result(period_start=None, period_end=PERIOD_END)

    def test_pass_requires_both_historical_metrics_ok(self) -> None:
        with pytest.raises(ValueError, match="requires execution_status=ok"):
            _make_pass_result(
                eps_cagr=MetricResult.failure(
                    MetricStatus.UNAVAILABLE, ReasonCode.INSUFFICIENT_HISTORY, "Not enough history."
                )
            )

    def test_pass_rejects_classification_reason(self) -> None:
        with pytest.raises(ValueError, match="must not carry a classification reason"):
            _make_pass_result(
                classification_reason_code=ReasonCode.FCF_NOT_GROWING,
                classification_reason="should not be present",
            )

    def test_fail_requires_ok_execution_status(self) -> None:
        with pytest.raises(ValueError, match="requires execution_status=ok"):
            _make_result(execution_status=CalculationStatus.PROVIDER_ERROR)

    def test_fail_requires_fcf_cagr_ok(self) -> None:
        with pytest.raises(ValueError, match="requires execution_status=ok"):
            _make_result(
                fcf_cagr=MetricResult.failure(
                    MetricStatus.UNAVAILABLE, ReasonCode.INSUFFICIENT_HISTORY, "Not enough history."
                )
            )

    def test_fail_requires_eps_cagr_ok(self) -> None:
        with pytest.raises(ValueError, match="requires execution_status=ok"):
            _make_result(
                eps_cagr=MetricResult.failure(
                    MetricStatus.UNAVAILABLE, ReasonCode.INSUFFICIENT_HISTORY, "Not enough history."
                )
            )

    def test_fail_requires_non_null_period_start(self) -> None:
        with pytest.raises(ValueError, match="requires execution_status=ok"):
            _make_result(period_start=None)

    def test_fail_requires_non_null_period_end(self) -> None:
        with pytest.raises(ValueError, match="requires execution_status=ok"):
            _make_result(period_end=None)

    def test_fail_requires_reason_fields(self) -> None:
        with pytest.raises(ValueError, match="requires classification_reason_code"):
            _make_result(classification_reason_code=None, classification_reason=None)

    def test_fail_rejects_blank_reason(self) -> None:
        with pytest.raises(ValueError, match="requires classification_reason_code"):
            _make_result(classification_reason="   ")

    def test_result_is_frozen(self) -> None:
        result = _make_result()
        with pytest.raises(FrozenInstanceError):
            result.ticker = "OTHER"  # type: ignore[misc]
