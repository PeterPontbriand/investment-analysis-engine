"""Arithmetic tests for the shared free-cash-flow and FCF-yield functions."""

from __future__ import annotations

import math

import pytest

from investment_analysis_engine.analysis.shared.cash_flow import compute_fcf_yield, compute_free_cash_flow
from investment_analysis_engine.core.metric_result import MetricResult, MetricStatus, ReasonCode


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


def test_cash_flow_functions_return_finite_values_on_ok() -> None:
    """Returned metric values are always finite floats, never NaN/Inf."""
    for result in (compute_free_cash_flow(1.0, 2.0), compute_fcf_yield(1.0, 2.0)):
        assert result.status is MetricStatus.OK
        assert result.value is not None
        assert math.isfinite(result.value)
