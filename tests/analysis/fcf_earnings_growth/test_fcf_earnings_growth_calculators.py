"""Arithmetic tests for the pure FCF & earnings-growth calculators."""

from __future__ import annotations

import math

import pytest

from src.analysis.fcf_earnings_growth.calculators import (
    compute_cagr,
    compute_fcf_per_diluted_share,
    compute_fcf_yield,
    compute_free_cash_flow,
    compute_growth_percent,
)
from src.analysis.fcf_earnings_growth.models import MetricResult, MetricStatus, ReasonCode


def _assert_ok(result: MetricResult, expected: float, *, abs_tol: float | None = None) -> None:
    """Assert a successful metric result with a finite value and no reasons."""
    value = result.value
    assert result.status is MetricStatus.OK
    assert value is not None
    assert math.isfinite(value)
    assert value == pytest.approx(expected, abs=abs_tol)
    assert result.reason_code is None
    assert result.reason is None


def _assert_failure(result: MetricResult, status: MetricStatus, reason_code: ReasonCode) -> None:
    """Assert a non-ok metric result carrying the expected machine code."""
    assert result.status is status
    assert result.value is None
    assert result.reason_code is reason_code
    assert result.reason is not None
    assert result.reason.strip()


class TestComputeFreeCashFlow:
    """Free cash flow = operating cash flow - positive normalized CapEx."""

    def test_positive_fcf(self) -> None:
        _assert_ok(compute_free_cash_flow(300.0, 100.0), 200.0)

    def test_negative_fcf_is_explicit(self) -> None:
        _assert_ok(compute_free_cash_flow(50.0, 120.0), -70.0)

    def test_zero_capex(self) -> None:
        _assert_ok(compute_free_cash_flow(75.5, 0.0), 75.5)

    def test_operating_loss(self) -> None:
        _assert_ok(compute_free_cash_flow(-25.0, 10.0), -35.0)

    @pytest.mark.parametrize(
        ("ocf", "capex"),
        [(float("nan"), 10.0), (10.0, float("nan")), (float("inf"), 10.0), (10.0, float("-inf"))],
    )
    def test_non_finite_inputs(self, ocf: float, capex: float) -> None:
        result = compute_free_cash_flow(ocf, capex)
        _assert_failure(result, MetricStatus.NOT_APPLICABLE, ReasonCode.INVALID_REQUEST)

    def test_subtraction_overflow(self) -> None:
        result = compute_free_cash_flow(float("1.7976931348623157e308"), -1.0e308)
        _assert_failure(result, MetricStatus.NOT_APPLICABLE, ReasonCode.INVALID_REQUEST)


class TestComputeFcfPerDilutedShare:
    """FCF/share uses the compatible positive diluted-share denominator."""

    def test_derives_per_share_value(self) -> None:
        _assert_ok(compute_fcf_per_diluted_share(250.0, 100.0), 2.5)

    @pytest.mark.parametrize("shares", [0.0, -1.0])
    def test_rejects_nonpositive_denominator(self, shares: float) -> None:
        _assert_failure(
            compute_fcf_per_diluted_share(250.0, shares),
            MetricStatus.UNAVAILABLE,
            ReasonCode.NONPOSITIVE_ENDING,
        )


class TestComputeGrowthPercent:
    """One-period growth from a strictly positive prior value."""

    def test_positive_growth(self) -> None:
        _assert_ok(compute_growth_percent(6.0, 5.0), 20.0)

    def test_decline(self) -> None:
        _assert_ok(compute_growth_percent(4.0, 5.0), -20.0)

    def test_no_change(self) -> None:
        _assert_ok(compute_growth_percent(5.0, 5.0), 0.0)

    def test_positive_estimate_from_prior_can_still_grow(self) -> None:
        # A positive estimate is not necessarily positive growth.
        _assert_ok(compute_growth_percent(1.0, 2.0), -50.0)

    @pytest.mark.parametrize("prior", [0.0, -1.5])
    def test_nonpositive_prior(self, prior: float) -> None:
        result = compute_growth_percent(3.0, prior)
        _assert_failure(result, MetricStatus.UNAVAILABLE, ReasonCode.NONPOSITIVE_BEGINNING)

    @pytest.mark.parametrize(
        ("current", "prior"),
        [(float("nan"), 1.0), (1.0, float("nan")), (float("inf"), 1.0)],
    )
    def test_non_finite_inputs(self, current: float, prior: float) -> None:
        result = compute_growth_percent(current, prior)
        _assert_failure(result, MetricStatus.NOT_APPLICABLE, ReasonCode.INVALID_REQUEST)

    def test_division_overflow(self) -> None:
        result = compute_growth_percent(1.0e308, 1.0e-308)
        _assert_failure(result, MetricStatus.NOT_APPLICABLE, ReasonCode.INVALID_REQUEST)


class TestComputeCagr:
    """CAGR percent = ((ending / beginning) ** (1 / N) - 1) * 100."""

    def test_one_year_double(self) -> None:
        _assert_ok(compute_cagr(100.0, 200.0, 1), 100.0)

    def test_five_year_example(self) -> None:
        # Six observations FY2020..FY2025 hold five elapsed annual intervals.
        expected = ((320.0 / 100.0) ** (1 / 5) - 1.0) * 100.0
        _assert_ok(compute_cagr(100.0, 320.0, 5), expected)
        _assert_ok(compute_cagr(100.0, 320.0, 5), 26.19, abs_tol=0.01)  # documented example magnitude

    def test_three_year_decline(self) -> None:
        expected = ((100.0 / 200.0) ** (1 / 3) - 1.0) * 100.0
        result = compute_cagr(200.0, 100.0, 3)
        _assert_ok(result, expected)
        assert result.value is not None
        assert result.value < 0

    def test_flat_series(self) -> None:
        _assert_ok(compute_cagr(50.0, 50.0, 4), 0.0)

    @pytest.mark.parametrize(
        ("beginning", "ending", "reason_code"),
        [
            (0.0, 100.0, ReasonCode.NONPOSITIVE_BEGINNING),
            (-50.0, 100.0, ReasonCode.NONPOSITIVE_BEGINNING),
            (-50.0, -100.0, ReasonCode.NONPOSITIVE_BEGINNING),
            (100.0, 0.0, ReasonCode.NONPOSITIVE_ENDING),
            (100.0, -50.0, ReasonCode.SIGN_CHANGE),
        ],
    )
    def test_nonmeaningful_endpoints(self, beginning: float, ending: float, reason_code: ReasonCode) -> None:
        result = compute_cagr(beginning, ending, 3)
        _assert_failure(result, MetricStatus.UNAVAILABLE, reason_code)

    @pytest.mark.parametrize("elapsed_years", [0, -1, 2.5, "3", None, True])
    def test_invalid_elapsed_years(self, elapsed_years: object) -> None:
        result = compute_cagr(100.0, 200.0, elapsed_years)  # type: ignore[arg-type]
        _assert_failure(result, MetricStatus.NOT_APPLICABLE, ReasonCode.INVALID_REQUEST)

    @pytest.mark.parametrize(
        ("beginning", "ending"),
        [(float("nan"), 100.0), (100.0, float("inf"))],
    )
    def test_non_finite_inputs(self, beginning: float, ending: float) -> None:
        result = compute_cagr(beginning, ending, 3)
        _assert_failure(result, MetricStatus.NOT_APPLICABLE, ReasonCode.INVALID_REQUEST)

    def test_ratio_overflow(self) -> None:
        result = compute_cagr(1.0e-308, 1.0e308, 1)
        _assert_failure(result, MetricStatus.NOT_APPLICABLE, ReasonCode.INVALID_REQUEST)


class TestComputeFcfYield:
    """FCF yield percent = annual FCF / current market capitalization * 100."""

    def test_yield(self) -> None:
        _assert_ok(compute_fcf_yield(25.0, 500.0), 5.0)

    def test_negative_yield_is_explicit(self) -> None:
        _assert_ok(compute_fcf_yield(-10.0, 200.0), -5.0)

    @pytest.mark.parametrize("market_cap", [0.0, -1.0])
    def test_nonpositive_market_cap(self, market_cap: float) -> None:
        result = compute_fcf_yield(10.0, market_cap)
        _assert_failure(result, MetricStatus.UNAVAILABLE, ReasonCode.MARKET_CAP_UNAVAILABLE)

    @pytest.mark.parametrize(
        ("fcf", "market_cap"),
        [(float("nan"), 100.0), (100.0, float("inf"))],
    )
    def test_non_finite_inputs(self, fcf: float, market_cap: float) -> None:
        result = compute_fcf_yield(fcf, market_cap)
        _assert_failure(result, MetricStatus.NOT_APPLICABLE, ReasonCode.INVALID_REQUEST)

    def test_division_overflow(self) -> None:
        result = compute_fcf_yield(1.0e308, 1.0e-308)
        _assert_failure(result, MetricStatus.NOT_APPLICABLE, ReasonCode.INVALID_REQUEST)


def test_calculators_return_finite_values_on_ok() -> None:
    """Returned metric values are always finite floats, never NaN/Inf."""
    for result in (
        compute_free_cash_flow(1.0, 2.0),
        compute_growth_percent(1.0, 2.0),
        compute_cagr(1.0, 2.0, 3),
        compute_fcf_yield(1.0, 2.0),
    ):
        assert result.status is MetricStatus.OK
        assert result.value is not None
        assert math.isfinite(result.value)
