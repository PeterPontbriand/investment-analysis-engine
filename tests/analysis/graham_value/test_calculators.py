"""Deterministic unit tests for the two pure Graham calculators.

Expected values are independently hand-calculated, not derived from the
implementation under test.

Hand calculations:

Graham Number (EPS=4.0, BVPS=12.0):
    sqrt(22.5 * 4.0 * 12.0) = sqrt(1080.0) = 6 * sqrt(30)
    sqrt(30) ≈ 5.477225575...
    6 * 5.477225575 ≈ 32.863353451...

Graham Growth Value (EPS=3.5, g=6.5, currAAA=5.25, basePE=8.5, mult=2.0, baseAAA=4.4):
    pe = 8.5 + 2.0 * 6.5 = 8.5 + 13.0 = 21.5
    value = 3.5 * 21.5 * 4.4 / 5.25
          = 75.25 * 4.4 / 5.25
          = 331.1 / 5.25
          = 63.06666666...
"""

import math
import sys

import pytest

from src.analysis.graham_value.calculators import (
    compute_graham_growth_value,
    compute_graham_number,
)
from src.analysis.graham_value.models import GrahamGrowthValueResult, GrahamMethod, GrahamNumberResult
from src.core.analysis_status import CalculationStatus

# ─────────────────────────────────────────────────────────────────────────────
# Independently hand-calculated expected values
# ─────────────────────────────────────────────────────────────────────────────

# Graham Number: sqrt(22.5 * 4.0 * 12.0) = sqrt(1080) = 6*sqrt(30)
_EXPECTED_GN = 6.0 * math.sqrt(30.0)  # ≈ 32.86335345111903

# Growth: 3.5 * (8.5 + 2*6.5) * 4.4 / 5.25 = 331.1 / 5.25
_EXPECTED_GV = (3.5 * 21.5 * 4.4) / 5.25  # = 331.1 / 5.25 ≈ 63.0666666...


# ─────────────────────────────────────────────────────────────────────────────
# 1. Graham Number against independently hand-calculated value
# ─────────────────────────────────────────────────────────────────────────────


class TestGrahamNumberCalculation:
    def test_hand_calculated_value(self) -> None:
        result = compute_graham_number(eps=4.0, bvps=12.0)
        assert result.status is CalculationStatus.OK
        assert result.maximum_indicated_price is not None
        assert math.isclose(result.maximum_indicated_price, _EXPECTED_GN, rel_tol=1e-12)

    def test_another_valid_input(self) -> None:
        # sqrt(22.5 * 2.0 * 8.0) = sqrt(360) = 6*sqrt(10)
        expected = 6.0 * math.sqrt(10.0)
        result = compute_graham_number(eps=2.0, bvps=8.0)
        assert result.status is CalculationStatus.OK
        assert result.maximum_indicated_price is not None
        assert math.isclose(result.maximum_indicated_price, expected, rel_tol=1e-12)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Growth value against independently hand-calculated value
# ─────────────────────────────────────────────────────────────────────────────


class TestGrowthValueCalculation:
    def test_hand_calculated_value(self) -> None:
        result = compute_graham_growth_value(
            normalized_eps=3.5,
            expected_growth_rate=6.5,
            current_aaa_yield=5.25,
        )
        assert result.status is CalculationStatus.OK
        assert result.growth_value is not None
        assert math.isclose(result.growth_value, _EXPECTED_GV, rel_tol=1e-12)

    def test_another_valid_input(self) -> None:
        # eps=2.0, g=10.0, currAAA=4.0, basePE=8.5, mult=2.0, baseAAA=4.4
        # pe = 8.5 + 2*10 = 28.5
        # value = 2.0 * 28.5 * 4.4 / 4.0 = 250.8 / 4.0 = 62.7
        expected = (2.0 * 28.5 * 4.4) / 4.0
        result = compute_graham_growth_value(
            normalized_eps=2.0,
            expected_growth_rate=10.0,
            current_aaa_yield=4.0,
        )
        assert result.status is CalculationStatus.OK
        assert result.growth_value is not None
        assert math.isclose(result.growth_value, expected, rel_tol=1e-12)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Method discrimination and method-specific result fields
# ─────────────────────────────────────────────────────────────────────────────


class TestMethodDiscrimination:
    def test_graham_number_method_field(self) -> None:
        result = compute_graham_number(eps=1.0, bvps=1.0)
        assert isinstance(result, GrahamNumberResult)
        assert result.method is GrahamMethod.NUMBER

    def test_growth_value_method_field(self) -> None:
        result = compute_graham_growth_value(normalized_eps=1.0, expected_growth_rate=5.0, current_aaa_yield=4.0)
        assert isinstance(result, GrahamGrowthValueResult)
        assert result.method is GrahamMethod.GROWTH_VALUE

    def test_number_result_has_max_price_not_growth_value(self) -> None:
        result = compute_graham_number(eps=2.0, bvps=3.0)
        assert hasattr(result, "maximum_indicated_price")
        assert not hasattr(result, "growth_value")

    def test_growth_result_has_growth_value_not_max_price(self) -> None:
        result = compute_graham_growth_value(normalized_eps=2.0, expected_growth_rate=5.0, current_aaa_yield=4.0)
        assert hasattr(result, "growth_value")
        assert not hasattr(result, "maximum_indicated_price")


# ─────────────────────────────────────────────────────────────────────────────
# 4. Zero and negative EPS/BVPS → not_applicable for Graham Number
# ─────────────────────────────────────────────────────────────────────────────


class TestGrahamNumberApplicability:
    def test_zero_eps(self) -> None:
        result = compute_graham_number(eps=0.0, bvps=10.0)
        assert result.status is CalculationStatus.NOT_APPLICABLE
        assert result.maximum_indicated_price is None
        assert result.reason is not None

    def test_negative_eps(self) -> None:
        result = compute_graham_number(eps=-1.5, bvps=10.0)
        assert result.status is CalculationStatus.NOT_APPLICABLE
        assert result.maximum_indicated_price is None
        assert result.reason is not None

    def test_zero_bvps(self) -> None:
        result = compute_graham_number(eps=5.0, bvps=0.0)
        assert result.status is CalculationStatus.NOT_APPLICABLE
        assert result.maximum_indicated_price is None
        assert result.reason is not None

    def test_negative_bvps(self) -> None:
        result = compute_graham_number(eps=5.0, bvps=-3.0)
        assert result.status is CalculationStatus.NOT_APPLICABLE
        assert result.maximum_indicated_price is None
        assert result.reason is not None


# ─────────────────────────────────────────────────────────────────────────────
# 5. NaN and ±inf never escaping as successful results
# ─────────────────────────────────────────────────────────────────────────────


class TestNonFiniteInputs:
    @pytest.mark.parametrize(
        ("eps", "bvps"),
        [
            (float("nan"), 10.0),
            (10.0, float("nan")),
            (float("inf"), 10.0),
            (10.0, float("inf")),
            (float("-inf"), 10.0),
            (10.0, float("-inf")),
        ],
    )
    def test_graham_number_non_finite(self, eps: float, bvps: float) -> None:
        result = compute_graham_number(eps=eps, bvps=bvps)
        assert result.status is CalculationStatus.INVALID_INPUT
        assert result.maximum_indicated_price is None
        assert result.reason is not None

    @pytest.mark.parametrize(
        ("eps", "g", "curr_aaa"),
        [
            (float("nan"), 5.0, 4.0),
            (1.0, float("nan"), 4.0),
            (1.0, 5.0, float("nan")),
            (1.0, float("inf"), 4.0),
            (1.0, 5.0, float("inf")),
            (float("inf"), 5.0, 4.0),
            (1.0, 5.0, float("-inf")),
        ],
    )
    def test_growth_value_non_finite(self, eps: float, g: float, curr_aaa: float) -> None:
        result = compute_graham_growth_value(normalized_eps=eps, expected_growth_rate=g, current_aaa_yield=curr_aaa)
        assert result.status is CalculationStatus.INVALID_INPUT
        assert result.growth_value is None
        assert result.reason is not None

    def test_non_finite_bvps_graham_number(self) -> None:
        result = compute_graham_number(eps=10.0, bvps=float("nan"))
        assert result.status is CalculationStatus.INVALID_INPUT
        assert result.maximum_indicated_price is None

    def test_non_finite_baseline_aaa(self) -> None:
        result = compute_graham_growth_value(
            normalized_eps=1.0,
            expected_growth_rate=5.0,
            current_aaa_yield=4.0,
            baseline_aaa_yield=float("nan"),
        )
        assert result.status is CalculationStatus.INVALID_INPUT
        assert result.growth_value is None

    def test_non_finite_growth_multiplier(self) -> None:
        result = compute_graham_growth_value(
            normalized_eps=1.0,
            expected_growth_rate=5.0,
            current_aaa_yield=4.0,
            growth_multiplier=float("inf"),
        )
        assert result.status is CalculationStatus.INVALID_INPUT
        assert result.growth_value is None


# ─────────────────────────────────────────────────────────────────────────────
# 6. Zero and negative current AAA yield → invalid_input
# ─────────────────────────────────────────────────────────────────────────────


class TestGrowthValueYieldValidation:
    def test_zero_current_aaa(self) -> None:
        result = compute_graham_growth_value(normalized_eps=3.5, expected_growth_rate=6.5, current_aaa_yield=0.0)
        assert result.status is CalculationStatus.INVALID_INPUT
        assert result.growth_value is None
        assert result.reason is not None

    def test_negative_current_aaa(self) -> None:
        result = compute_graham_growth_value(normalized_eps=3.5, expected_growth_rate=6.5, current_aaa_yield=-2.5)
        assert result.status is CalculationStatus.INVALID_INPUT
        assert result.growth_value is None


# ─────────────────────────────────────────────────────────────────────────────
# 7. Invalid baseline AAA yield → invalid_input
# ─────────────────────────────────────────────────────────────────────────────


class TestGrowthValueBaselineYield:
    def test_zero_baseline_aaa(self) -> None:
        result = compute_graham_growth_value(
            normalized_eps=3.5,
            expected_growth_rate=6.5,
            current_aaa_yield=5.25,
            baseline_aaa_yield=0.0,
        )
        assert result.status is CalculationStatus.INVALID_INPUT
        assert result.growth_value is None

    def test_negative_baseline_aaa(self) -> None:
        result = compute_graham_growth_value(
            normalized_eps=3.5,
            expected_growth_rate=6.5,
            current_aaa_yield=5.25,
            baseline_aaa_yield=-4.4,
        )
        assert result.status is CalculationStatus.INVALID_INPUT
        assert result.growth_value is None


# ─────────────────────────────────────────────────────────────────────────────
# 8. Non-finite calculated output → invalid_input
# ─────────────────────────────────────────────────────────────────────────────


class TestNonFiniteOutput:
    def test_graham_number_overflow_from_finite_inputs(self) -> None:
        # Both inputs are finite, but the intermediate product
        # 22.5 * sys.float_info.max * 1.0 overflows to +inf,
        # which math.sqrt then returns as +inf.  The defensive
        # output guard must catch this.
        eps = sys.float_info.max
        result = compute_graham_number(eps=eps, bvps=1.0)
        assert result.status is CalculationStatus.INVALID_INPUT
        assert result.maximum_indicated_price is None
        assert result.reason is not None
        assert "not finite" in result.reason or "not a valid positive finite" in result.reason

    def test_non_finite_valuation_pe_rejected(self) -> None:
        # growth_multiplier * g overflows to inf:
        # 1e300 * 1e10 → inf  →  valuation P/E guard fires
        result = compute_graham_growth_value(
            normalized_eps=1.0,
            expected_growth_rate=1e10,
            current_aaa_yield=4.0,
            growth_multiplier=1e300,
        )
        assert result.status is CalculationStatus.INVALID_INPUT
        assert result.growth_value is None
        assert result.reason is not None
        assert "valuation P/E is not finite" in result.reason

    def test_non_finite_final_growth_value_rejected(self) -> None:
        # valuation P/E = 8.5 + 2.0 * 0.0 = 8.5 (finite, positive)
        # growth_value = sys.float_info.max * 8.5 * 4.4 / 4.0 → inf
        # →  final growth-value guard fires
        result = compute_graham_growth_value(
            normalized_eps=sys.float_info.max,
            expected_growth_rate=0.0,
            current_aaa_yield=4.0,
        )
        assert result.status is CalculationStatus.INVALID_INPUT
        assert result.growth_value is None
        assert result.reason is not None
        assert "Computed growth value is not finite" in result.reason


# ─────────────────────────────────────────────────────────────────────────────
# 9. Finite negative expected growth not rejected merely for being negative
# ─────────────────────────────────────────────────────────────────────────────


class TestNegativeGrowth:
    def test_negative_growth_producing_negative_pe_rejected(self) -> None:
        # eps=2.0, g=-5.0, currAAA=5.0, basePE=8.5, mult=2.0, baseAAA=4.4
        # pe = 8.5 + 2*(-5.0) = 8.5 - 10.0 = -1.5  → INVALID_INPUT
        result = compute_graham_growth_value(
            normalized_eps=2.0,
            expected_growth_rate=-5.0,
            current_aaa_yield=5.0,
        )
        assert result.status is CalculationStatus.INVALID_INPUT
        assert result.growth_value is None
        assert result.reason is not None

    def test_moderate_negative_growth_accepted(self) -> None:
        # eps=3.0, g=-2.0, currAAA=4.0, basePE=8.5, mult=2.0, baseAAA=4.4
        # pe = 8.5 + 2*(-2.0) = 4.5  → valid
        # value = 3.0 * 4.5 * 4.4 / 4.0 = 59.4 / 4.0 = 14.85
        expected = (3.0 * 4.5 * 4.4) / 4.0
        result = compute_graham_growth_value(
            normalized_eps=3.0,
            expected_growth_rate=-2.0,
            current_aaa_yield=4.0,
        )
        assert result.status is CalculationStatus.OK
        assert result.growth_value is not None
        assert math.isclose(result.growth_value, expected, rel_tol=1e-12)


# ─────────────────────────────────────────────────────────────────────────────
# 10. Growth greater than 100 not rejected merely for being large
# ─────────────────────────────────────────────────────────────────────────────


class TestLargeGrowth:
    def test_growth_150_accepted(self) -> None:
        # eps=1.0, g=150, currAAA=5.0, basePE=8.5, mult=2.0, baseAAA=4.4
        # pe = 8.5 + 2*150 = 308.5
        # value = 1.0 * 308.5 * 4.4 / 5.0 = 1357.4 / 5.0 = 271.48
        expected = (1.0 * 308.5 * 4.4) / 5.0
        result = compute_graham_growth_value(
            normalized_eps=1.0,
            expected_growth_rate=150.0,
            current_aaa_yield=5.0,
        )
        assert result.status is CalculationStatus.OK
        assert result.growth_value is not None
        assert math.isclose(result.growth_value, expected, rel_tol=1e-12)

    def test_growth_500_accepted(self) -> None:
        # eps=2.0, g=500, currAAA=4.0, basePE=8.5, mult=2.0, baseAAA=4.4
        # pe = 8.5 + 1000 = 1008.5
        # value = 2.0 * 1008.5 * 4.4 / 4.0 = 8874.8 / 4.0 = 2218.7
        expected = (2.0 * 1008.5 * 4.4) / 4.0
        result = compute_graham_growth_value(
            normalized_eps=2.0,
            expected_growth_rate=500.0,
            current_aaa_yield=4.0,
        )
        assert result.status is CalculationStatus.OK
        assert result.growth_value is not None
        assert math.isclose(result.growth_value, expected, rel_tol=1e-12)


# ─────────────────────────────────────────────────────────────────────────────
# 11. Growth-calculator parameter validation (base_pe, growth_multiplier)
# ─────────────────────────────────────────────────────────────────────────────


class TestGrowthValueParameterValidation:
    def test_non_finite_base_pe(self) -> None:
        result = compute_graham_growth_value(
            normalized_eps=1.0,
            expected_growth_rate=5.0,
            current_aaa_yield=4.0,
            base_pe=float("nan"),
        )
        assert result.status is CalculationStatus.INVALID_INPUT
        assert result.growth_value is None

    def test_zero_base_pe(self) -> None:
        result = compute_graham_growth_value(
            normalized_eps=1.0,
            expected_growth_rate=5.0,
            current_aaa_yield=4.0,
            base_pe=0.0,
        )
        assert result.status is CalculationStatus.INVALID_INPUT
        assert result.growth_value is None

    def test_negative_base_pe(self) -> None:
        result = compute_graham_growth_value(
            normalized_eps=1.0,
            expected_growth_rate=5.0,
            current_aaa_yield=4.0,
            base_pe=-5.0,
        )
        assert result.status is CalculationStatus.INVALID_INPUT
        assert result.growth_value is None

    def test_negative_growth_multiplier(self) -> None:
        result = compute_graham_growth_value(
            normalized_eps=1.0,
            expected_growth_rate=5.0,
            current_aaa_yield=4.0,
            growth_multiplier=-1.0,
        )
        assert result.status is CalculationStatus.INVALID_INPUT
        assert result.growth_value is None

    def test_zero_growth_multiplier_valid(self) -> None:
        # growth_multiplier=0, g=5.0 → pe = 8.5 + 0 = 8.5 > 0 → valid
        # value = 1.0 * 8.5 * 4.4 / 4.0 = 37.4 / 4.0 = 9.35
        expected = (1.0 * 8.5 * 4.4) / 4.0
        result = compute_graham_growth_value(
            normalized_eps=1.0,
            expected_growth_rate=5.0,
            current_aaa_yield=4.0,
            growth_multiplier=0.0,
        )
        assert result.status is CalculationStatus.OK
        assert result.growth_value is not None
        assert math.isclose(result.growth_value, expected, rel_tol=1e-12)

    def test_zero_valuation_pe_rejected(self) -> None:
        # base_pe=2.0, growth_multiplier=1.0, g=-2.0
        # pe = 2.0 + 1.0*(-2.0) = 0.0 → INVALID_INPUT
        result = compute_graham_growth_value(
            normalized_eps=1.0,
            expected_growth_rate=-2.0,
            current_aaa_yield=4.0,
            base_pe=2.0,
            growth_multiplier=1.0,
        )
        assert result.status is CalculationStatus.INVALID_INPUT
        assert result.growth_value is None

    def test_negative_valuation_pe_rejected(self) -> None:
        # base_pe=2.0, growth_multiplier=1.0, g=-5.0
        # pe = 2.0 + 1.0*(-5.0) = -3.0 → INVALID_INPUT
        result = compute_graham_growth_value(
            normalized_eps=1.0,
            expected_growth_rate=-5.0,
            current_aaa_yield=4.0,
            base_pe=2.0,
            growth_multiplier=1.0,
        )
        assert result.status is CalculationStatus.INVALID_INPUT
        assert result.growth_value is None


# ─────────────────────────────────────────────────────────────────────────────
# 12. Fixed method discriminators (structurally safe)
# ─────────────────────────────────────────────────────────────────────────────


class TestMethodFixedDiscriminators:
    def test_graham_number_result_cannot_set_method(self) -> None:
        """Method is not an init parameter; passing it must fail."""
        with pytest.raises(TypeError, match="method"):
            GrahamNumberResult(  # type: ignore[call-arg]
                status=CalculationStatus.OK,
                maximum_indicated_price=10.0,
                method=GrahamMethod.GROWTH_VALUE,
            )

    def test_graham_growth_value_result_cannot_set_method(self) -> None:
        """Method is not an init parameter; passing it must fail."""
        with pytest.raises(TypeError, match="method"):
            GrahamGrowthValueResult(  # type: ignore[call-arg]
                status=CalculationStatus.OK,
                growth_value=10.0,
                method=GrahamMethod.NUMBER,
            )

    def test_graham_number_ok_result_has_number_method(self) -> None:
        result = compute_graham_number(eps=1.0, bvps=1.0)
        assert result.method is GrahamMethod.NUMBER

    def test_graham_number_error_result_has_number_method(self) -> None:
        result = compute_graham_number(eps=0.0, bvps=1.0)
        assert result.method is GrahamMethod.NUMBER

    def test_growth_value_ok_result_has_growth_method(self) -> None:
        result = compute_graham_growth_value(normalized_eps=1.0, expected_growth_rate=5.0, current_aaa_yield=4.0)
        assert result.method is GrahamMethod.GROWTH_VALUE

    def test_growth_value_error_result_has_growth_method(self) -> None:
        result = compute_graham_growth_value(normalized_eps=1.0, expected_growth_rate=5.0, current_aaa_yield=0.0)
        assert result.method is GrahamMethod.GROWTH_VALUE


# ─────────────────────────────────────────────────────────────────────────────
# 13. Result-state invariants (enforced by __post_init__)
# ─────────────────────────────────────────────────────────────────────────────


class TestResultStateInvariants:
    def test_graham_number_ok_requires_value(self) -> None:
        with pytest.raises(ValueError, match="maximum_indicated_price"):
            GrahamNumberResult(status=CalculationStatus.OK, maximum_indicated_price=None)

    def test_graham_number_ok_rejects_reason(self) -> None:
        with pytest.raises(ValueError, match="reason to be None"):
            GrahamNumberResult(
                status=CalculationStatus.OK,
                maximum_indicated_price=10.0,
                reason="success cannot carry a failure reason",
            )

    def test_graham_number_non_ok_rejects_value(self) -> None:
        with pytest.raises(ValueError, match="maximum_indicated_price"):
            GrahamNumberResult(
                status=CalculationStatus.INVALID_INPUT,
                maximum_indicated_price=5.0,
                reason="should fail",
            )

    def test_graham_number_non_ok_requires_non_empty_reason(self) -> None:
        with pytest.raises(ValueError, match="reason"):
            GrahamNumberResult(status=CalculationStatus.INVALID_INPUT, reason="")

    def test_growth_value_ok_requires_value(self) -> None:
        with pytest.raises(ValueError, match="growth_value"):
            GrahamGrowthValueResult(status=CalculationStatus.OK, growth_value=None)

    def test_growth_value_ok_rejects_reason(self) -> None:
        with pytest.raises(ValueError, match="reason to be None"):
            GrahamGrowthValueResult(
                status=CalculationStatus.OK,
                growth_value=10.0,
                reason="success cannot carry a failure reason",
            )

    def test_growth_value_non_ok_rejects_value(self) -> None:
        with pytest.raises(ValueError, match="growth_value"):
            GrahamGrowthValueResult(
                status=CalculationStatus.NOT_APPLICABLE,
                growth_value=5.0,
                reason="should fail",
            )

    def test_growth_value_non_ok_requires_non_empty_reason(self) -> None:
        with pytest.raises(ValueError, match="reason"):
            GrahamGrowthValueResult(status=CalculationStatus.NOT_APPLICABLE, reason="")
