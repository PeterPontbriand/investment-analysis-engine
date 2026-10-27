"""Free cash flow and the free-cash-flow yield, the cash-flow metrics every consumer shares.

Every function here is pure: it performs no provider, cache, filesystem, clock or language-model access and infers no
periods or accounting bases. Neither function raises for an invalid or nonmeaningful input or returns ``NaN`` or
infinity; each returns a ``MetricResult`` whose reason code and reason explain every non-ok outcome. Data selection and
sign normalization happen outside these functions.

- free cash flow = operating cash flow - positive normalized CapEx;
- FCF yield percent = ``free cash flow / market capitalization * 100``.
"""

from __future__ import annotations

import math

from investment_analysis_engine.core.metric_result import MetricResult, MetricStatus, ReasonCode


def _invalid_request(reason: str) -> MetricResult:
    """Return a not-applicable result for an invalid or overflowing input."""
    return MetricResult.failure(MetricStatus.NOT_APPLICABLE, ReasonCode.INVALID_REQUEST, reason)


def _unavailable(reason_code: ReasonCode, reason: str) -> MetricResult:
    """Return an unavailable result for a failed business-level precondition."""
    return MetricResult.failure(MetricStatus.UNAVAILABLE, reason_code, reason)


def compute_free_cash_flow(operating_cash_flow: float, normalized_capital_expenditures: float) -> MetricResult:
    """Compute free cash flow for one completed fiscal year.

    Free cash flow may be negative; sign normalization is a data-resolution
    concern outside this pure function.

    Args:
        operating_cash_flow: Net cash provided by operating activities (annual).
        normalized_capital_expenditures: Positive normalized CapEx amount (annual).

    Returns:
        ``ok`` with the free cash flow in the inputs' units (may be negative),
        or ``not_applicable`` with ``invalid_request`` when an input is
        non-finite or the subtraction overflows the finite double range.
    """
    if not math.isfinite(operating_cash_flow):
        return _invalid_request(f"operating_cash_flow must be finite (received {operating_cash_flow!r}).")
    if not math.isfinite(normalized_capital_expenditures):
        return _invalid_request(
            f"normalized_capital_expenditures must be finite (received {normalized_capital_expenditures!r})."
        )
    free_cash_flow = operating_cash_flow - normalized_capital_expenditures
    if not math.isfinite(free_cash_flow):
        return _invalid_request("Free cash flow overflows the finite double range for the supplied inputs.")
    return MetricResult.ok(free_cash_flow)


def compute_fcf_yield(free_cash_flow: float, market_capitalization: float) -> MetricResult:
    """Compute the informational free-cash-flow yield as a percentage.

    The numerator is annual and the denominator is current.  The yield is
    supporting context only and must not affect classification under
    ``method_version = 1``.

    Args:
        free_cash_flow: Latest completed fiscal-year free cash flow (annual).
        market_capitalization: Current market capitalization, strictly positive.

    Returns:
        ``ok`` with the yield percent (may be negative), ``unavailable`` with
        ``market_cap_unavailable`` when the market capitalization is not
        strictly positive, or ``not_applicable`` with ``invalid_request``
        when an input is non-finite or the result overflows the finite double
        range.
    """
    if not math.isfinite(free_cash_flow):
        return _invalid_request(f"free_cash_flow must be finite (received {free_cash_flow!r}).")
    if not math.isfinite(market_capitalization):
        return _invalid_request(f"market_capitalization must be finite (received {market_capitalization!r}).")
    if market_capitalization <= 0:
        return _unavailable(
            ReasonCode.MARKET_CAP_UNAVAILABLE,
            f"market_capitalization must be strictly positive (received {market_capitalization}).",
        )
    fcf_yield_percent = free_cash_flow / market_capitalization * 100.0
    if not math.isfinite(fcf_yield_percent):
        return _invalid_request("FCF yield overflows the finite double range for the supplied inputs.")
    return MetricResult.ok(fcf_yield_percent)
