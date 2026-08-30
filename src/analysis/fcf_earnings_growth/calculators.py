"""Pure deterministic calculations for the FCF & earnings-growth strategy (Slice B).

Every function here is pure: it performs no provider/cache/filesystem/clock/
language-model access and infers no periods or accounting bases.  The metric
helpers never raise for invalid or nonmeaningful inputs and never return
``NaN`` or infinity; they return typed ``MetricResult`` objects whose
``reason_code`` and ``reason`` explain every non-ok outcome.
Data selection, sign normalization, and provenance assembly happen outside
these functions (Slice C and later).

Formulas follow ``docs/user/FINANCE_MATH.md`` and the normative contract in
``docs/project/milestones/v0.2/STEP_2_4_FCF_EARNINGS_GROWTH_DESIGN.md``:

- free cash flow = operating cash flow - positive normalized CapEx;
- growth percent = ``(current - prior) / prior * 100`` with a strictly positive prior;
- CAGR percent = ``((ending / beginning) ** (1 / N) - 1) * 100`` with strictly
  positive endpoints and at least one elapsed year;
- FCF yield percent = ``free cash flow / current market capitalization * 100``.
"""

from __future__ import annotations

import math

from src.analysis.fcf_earnings_growth.models import (
    Classification,
    ClassificationDecision,
    FCFClassificationBasis,
    FCFEarningsGrowthPolicy,
    ForwardEvidence,
    ForwardEvidenceStatus,
    ForwardPolicy,
    MetricResult,
    MetricStatus,
    ReasonCode,
    TrendClassification,
)


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


def compute_fcf_per_diluted_share(free_cash_flow: float, diluted_shares: float) -> MetricResult:
    """Compute FCF per diluted share using a strictly positive denominator."""
    if not math.isfinite(free_cash_flow) or not math.isfinite(diluted_shares):
        return _invalid_request("free_cash_flow and diluted_shares must be finite.")
    if diluted_shares <= 0:
        return _unavailable(ReasonCode.NONPOSITIVE_ENDING, "Diluted shares must be strictly positive.")
    result = free_cash_flow / diluted_shares
    if not math.isfinite(result):
        return _invalid_request("FCF per diluted share overflows the finite double range.")
    return MetricResult.ok(result)


def compute_growth_percent(current: float, prior: float) -> MetricResult:
    """Compute one-period growth as a percentage from a strictly positive prior.

    Args:
        current: Most recent value (e.g. FY1 consensus EPS).
        prior: Prior value, which must be strictly positive (e.g. latest actual EPS).

    Returns:
        ``ok`` with the growth percent (zero for no change, negative for a
        decline), ``unavailable`` with ``nonpositive_beginning`` when *prior*
        is not strictly positive, or ``not_applicable`` with
        ``invalid_request`` when an input is non-finite or the result
        overflows the finite double range.
    """
    if not math.isfinite(current):
        return _invalid_request(f"current must be finite (received {current!r}).")
    if not math.isfinite(prior):
        return _invalid_request(f"prior must be finite (received {prior!r}).")
    if prior <= 0:
        return _unavailable(
            ReasonCode.NONPOSITIVE_BEGINNING,
            f"prior must be strictly positive for growth to be meaningful (received {prior}).",
        )
    growth_percent = (current - prior) / prior * 100.0
    if not math.isfinite(growth_percent):
        return _invalid_request("Growth percent overflows the finite double range for the supplied inputs.")
    return MetricResult.ok(growth_percent)


def compute_cagr(beginning: float, ending: float, elapsed_years: int) -> MetricResult:
    """Compute compound annual growth as a percentage over *elapsed_years*.

    Zero or negative endpoints and sign changes make compound annual growth
    nonmeaningful under this policy, so both endpoints must be strictly
    positive and the span must contain at least one elapsed year.

    Args:
        beginning: Strictly positive first observation of the span.
        ending: Strictly positive final observation of the span.
        elapsed_years: Number of elapsed annual intervals between the endpoints.

    Returns:
        ``ok`` with the compound annual growth percent, ``unavailable`` with
        ``nonpositive_beginning``, ``nonpositive_ending``, or ``sign_change``
        for a nonmeaningful endpoint pair, or ``not_applicable`` with
        ``invalid_request`` when an input is non-finite, *elapsed_years* is
        not a positive integer, or the result overflows the finite double
        range.
    """
    for name, value in (("beginning", beginning), ("ending", ending)):
        if not math.isfinite(value):
            return _invalid_request(f"{name} must be finite (received {value!r}).")
    if isinstance(elapsed_years, bool) or not isinstance(elapsed_years, int) or elapsed_years < 1:
        return _invalid_request(f"elapsed_years must be a positive integer (received {elapsed_years!r}).")
    if beginning <= 0:
        return _unavailable(
            ReasonCode.NONPOSITIVE_BEGINNING,
            f"CAGR beginning must be strictly positive (received beginning={beginning}, ending={ending}).",
        )
    if ending <= 0:
        if ending < 0:
            code, detail = ReasonCode.SIGN_CHANGE, "CAGR endpoints changed sign across the span"
        else:
            code, detail = ReasonCode.NONPOSITIVE_ENDING, "CAGR ending must be strictly positive"
        return _unavailable(code, f"{detail} (received beginning={beginning}, ending={ending}).")
    cagr_percent = (math.pow(ending / beginning, 1.0 / elapsed_years) - 1.0) * 100.0
    if not math.isfinite(cagr_percent):
        return _invalid_request("CAGR overflows the finite double range for the supplied inputs.")
    return MetricResult.ok(cagr_percent)


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


def _trend_classification(fcf_cagr: MetricResult, eps_cagr: MetricResult) -> TrendClassification:
    """Map the two historical growth metrics onto the relationship description."""
    if (
        fcf_cagr.status is not MetricStatus.OK
        or eps_cagr.status is not MetricStatus.OK
        or fcf_cagr.value is None
        or eps_cagr.value is None
    ):
        return TrendClassification.INSUFFICIENT_OR_NONMEANINGFUL_GROWTH
    fcf_positive = fcf_cagr.value > 0
    eps_positive = eps_cagr.value > 0
    if fcf_positive and eps_positive:
        return TrendClassification.BOTH_GROWING
    if fcf_positive:
        return TrendClassification.FCF_GROWING_EARNINGS_NOT
    if eps_positive:
        return TrendClassification.EARNINGS_GROWING_FCF_NOT
    return TrendClassification.NEITHER_GROWING


def _failed_gate(fcf_value: float, eps_value: float) -> tuple[ReasonCode, str]:
    """Return the machine code and reason for a failed historical growth gate."""
    if fcf_value > 0:
        return (
            ReasonCode.EPS_NOT_GROWING,
            "Diluted-earnings-per-share compound annual growth is zero or negative.",
        )
    if eps_value > 0:
        return (
            ReasonCode.FCF_NOT_GROWING,
            "Free-cash-flow compound annual growth is zero or negative.",
        )
    return (
        ReasonCode.FCF_AND_EPS_NOT_GROWING,
        "Both free-cash-flow and diluted-earnings-per-share compound annual growth are zero or negative.",
    )


def classify_fcf_earnings_growth(
    *,
    policy: FCFEarningsGrowthPolicy,
    fcf_cagr: MetricResult,
    eps_cagr: MetricResult,
    forward_evidence: ForwardEvidence,
    fcf_per_share_cagr: MetricResult | None = None,
) -> ClassificationDecision:
    """Classify historical growth and apply the selected forward policy.

    The classification is independent of software execution status.  Reason
    precedence follows the strategy contract: nonmeaningful historical growth
    precedes unavailable required consensus, which precedes a failed growth
    gate (historical or forward).

    Args:
        policy: Investor-selected policy controlling the forward evidence gate.
        fcf_cagr: Free-cash-flow CAGR metric for the selected historical span.
        fcf_per_share_cagr: FCF/share CAGR used when selected by policy.
        eps_cagr: Diluted-EPS CAGR metric for the selected historical span.
        forward_evidence: Forward consensus evidence block for FY1/FY2.

    Returns:
        Typed classification decision with the trend description.

    Raises:
        ValueError: If a non-ok ``MetricResult`` used for classification is
            missing a reason code or reason.
    """
    controlling_fcf = (
        fcf_per_share_cagr if policy.classification_basis is FCFClassificationBasis.FCF_PER_SHARE else fcf_cagr
    )
    if controlling_fcf is None:
        controlling_fcf = _unavailable(ReasonCode.MISSING_FACT, "FCF/share evidence is unavailable.")
    trend = _trend_classification(controlling_fcf, eps_cagr)
    if controlling_fcf.status is not MetricStatus.OK or eps_cagr.status is not MetricStatus.OK:
        # Nonmeaningful historical growth: report the first non-ok metric (FCF first).
        failing = controlling_fcf if controlling_fcf.status is not MetricStatus.OK else eps_cagr
        if failing.reason_code is None or failing.reason is None:
            msg = "A non-ok metric used for classification must carry a reason code and reason."
            raise ValueError(msg)
        return ClassificationDecision(
            classification=Classification.INDETERMINATE,
            trend_classification=trend,
            reason_code=failing.reason_code,
            reason=failing.reason,
        )

    fcf_value = controlling_fcf.value
    eps_value = eps_cagr.value
    if fcf_value is None or eps_value is None:
        msg = "An ok metric used for classification must carry a finite value."
        raise ValueError(msg)

    if policy.forward_policy is ForwardPolicy.HARD_GATE:
        if forward_evidence.status is not ForwardEvidenceStatus.COMPLETE:
            return ClassificationDecision(
                classification=Classification.INDETERMINATE,
                trend_classification=trend,
                reason_code=ReasonCode.CONSENSUS_UNAVAILABLE,
                reason=(
                    "The hard gate requires complete consensus evidence, but the "
                    "required forward intervals were not available."
                ),
            )
        actual_to_fy1 = forward_evidence.actual_to_fy1_growth
        fy1_to_fy2 = forward_evidence.fy1_to_fy2_growth
        forward_confirmed = (
            actual_to_fy1.status is MetricStatus.OK
            and fy1_to_fy2.status is MetricStatus.OK
            and actual_to_fy1.value is not None
            and fy1_to_fy2.value is not None
            and actual_to_fy1.value > 0
            and fy1_to_fy2.value > 0
        )
        if not forward_confirmed:
            return ClassificationDecision(
                classification=Classification.FAIL,
                trend_classification=trend,
                reason_code=ReasonCode.FORWARD_GROWTH_NOT_CONFIRMED,
                reason=(
                    "The hard gate failed: forward consensus growth was not positive for both FY1 and FY2 intervals."
                ),
            )

    if fcf_value <= 0 or eps_value <= 0:
        reason_code, reason = _failed_gate(fcf_value, eps_value)
        return ClassificationDecision(
            classification=Classification.FAIL,
            trend_classification=trend,
            reason_code=reason_code,
            reason=reason,
        )

    return ClassificationDecision(
        classification=Classification.PASS,
        trend_classification=trend,
    )
