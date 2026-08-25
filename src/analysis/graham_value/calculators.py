"""Pure calculators for the two Graham valuation methods.

These functions receive already-resolved numeric values, perform validation
and arithmetic, and return typed method-specific results.  They perform no
network, cache, filesystem, settings, or clock I/O.

Formulas (see docs/FINANCE_MATH.md):

    Graham Number:
        maximum_indicated_price = sqrt(22.5 * EPS * BVPS)

    Graham Growth Value:
        growth_value = normalized_eps
            * (base_pe + growth_multiplier * expected_growth_rate)
            * baseline_aaa_yield / current_aaa_yield

All percentage values are expressed in percentage points: 6.5 means 6.5%,
not 0.065.
"""

import math
from typing import Final

from src.analysis.graham_value.models import GrahamGrowthValueResult, GrahamNumberResult
from src.core.analysis_status import CalculationStatus

# Classic Graham multiplier: maximum P/E 15 × maximum P/B 1.5 = 22.5
_GRAHAM_MULTIPLIER: Final[float] = 22.5


def compute_graham_number(eps: float, bvps: float) -> GrahamNumberResult:
    """Compute the Graham Number (maximum indicated price).

    Formula: ``sqrt(22.5 * eps * bvps)``.

    Args:
        eps: Earnings per share on the selected basis.  Must be finite and
            positive for a successful calculation.
        bvps: Book value per common share.  Must be finite and positive for
            a successful calculation.

    Returns:
        GrahamNumberResult with ``status`` of ``OK``, ``NOT_APPLICABLE``, or
        ``INVALID_INPUT``.  When ``status`` is ``OK``,
        ``maximum_indicated_price`` contains the screening-ceiling price;
        otherwise it is ``None`` and ``reason`` explains the failure.
    """
    # --- Finite check (invalid_input) ---
    if not math.isfinite(eps):
        return GrahamNumberResult(
            status=CalculationStatus.INVALID_INPUT,
            reason=f"EPS must be finite (received {eps!r}).",
        )
    if not math.isfinite(bvps):
        return GrahamNumberResult(
            status=CalculationStatus.INVALID_INPUT,
            reason=f"BVPS must be finite (received {bvps!r}).",
        )

    # --- Applicability check (not_applicable) ---
    if eps <= 0:
        return GrahamNumberResult(
            status=CalculationStatus.NOT_APPLICABLE,
            reason=f"EPS must be positive for Graham Number (received {eps}).",
        )
    if bvps <= 0:
        return GrahamNumberResult(
            status=CalculationStatus.NOT_APPLICABLE,
            reason=f"BVPS must be positive for Graham Number (received {bvps}).",
        )

    # --- Calculation ---
    product = _GRAHAM_MULTIPLIER * eps * bvps
    # product is guaranteed > 0 here (all inputs positive and finite,
    # multiplier is positive finite constant)
    result_value = math.sqrt(product)

    if not math.isfinite(result_value) or result_value <= 0:
        return GrahamNumberResult(
            status=CalculationStatus.INVALID_INPUT,
            reason=f"Computed Graham Number is not a valid positive finite value ({result_value!r}).",
        )

    return GrahamNumberResult(
        status=CalculationStatus.OK,
        maximum_indicated_price=result_value,
    )


def compute_graham_growth_value(  # noqa: PLR0913,PLR0917,PLR0911,PLR0912
    normalized_eps: float,
    expected_growth_rate: float,
    current_aaa_yield: float,
    base_pe: float = 8.5,
    growth_multiplier: float = 2.0,
    baseline_aaa_yield: float = 4.4,
) -> GrahamGrowthValueResult:
    """Compute the Graham growth value.

    Formula: ``eps * (base_pe + growth_multiplier * g) * baseline_aaa / current_aaa``.

    All percentage values are in percentage points (e.g. 6.5 means 6.5 %).

    Args:
        normalized_eps: Normalized EPS with an explicit basis.  Must be finite.
            Negative values are permitted (the method does not reject them
            merely for being negative).
        expected_growth_rate: Expected annual growth in percentage points.
            Must be finite.  Negative values are permitted; no clipping,
            capping, or annualization is applied.
        current_aaa_yield: Current AAA corporate-bond yield in percentage
            points.  Must be finite and strictly positive.
        base_pe: Base P/E for a zero-growth company.  Must be finite and
            positive.  Default 8.5.
        growth_multiplier: Multiplier applied to the growth rate.  Must be
            finite and non-negative.  Default 2.0.
        baseline_aaa_yield: Historical benchmark AAA bond yield in percentage
            points.  Must be finite and strictly positive.  Default 4.4.

    Returns:
        GrahamGrowthValueResult with ``status`` of ``OK`` or
        ``INVALID_INPUT``.  When ``status`` is ``OK``, ``growth_value``
        contains the forecast-dependent estimate; otherwise it is ``None``
        and ``reason`` explains the failure.
    """
    # --- Finite checks (invalid_input) ---
    if not math.isfinite(normalized_eps):
        return GrahamGrowthValueResult(
            status=CalculationStatus.INVALID_INPUT,
            reason=f"normalized_eps must be finite (received {normalized_eps!r}).",
        )
    if not math.isfinite(expected_growth_rate):
        return GrahamGrowthValueResult(
            status=CalculationStatus.INVALID_INPUT,
            reason=f"expected_growth_rate must be finite (received {expected_growth_rate!r}).",
        )
    if not math.isfinite(current_aaa_yield):
        return GrahamGrowthValueResult(
            status=CalculationStatus.INVALID_INPUT,
            reason=f"current_aaa_yield must be finite (received {current_aaa_yield!r}).",
        )
    if not math.isfinite(base_pe):
        return GrahamGrowthValueResult(
            status=CalculationStatus.INVALID_INPUT,
            reason=f"base_pe must be finite (received {base_pe!r}).",
        )
    if not math.isfinite(growth_multiplier):
        return GrahamGrowthValueResult(
            status=CalculationStatus.INVALID_INPUT,
            reason=f"growth_multiplier must be finite (received {growth_multiplier!r}).",
        )
    if not math.isfinite(baseline_aaa_yield):
        return GrahamGrowthValueResult(
            status=CalculationStatus.INVALID_INPUT,
            reason=f"baseline_aaa_yield must be finite (received {baseline_aaa_yield!r}).",
        )

    # --- Positivity / non-negativity checks (invalid_input) ---
    if current_aaa_yield <= 0:
        return GrahamGrowthValueResult(
            status=CalculationStatus.INVALID_INPUT,
            reason=f"current_aaa_yield must be strictly positive (received {current_aaa_yield}).",
        )
    if baseline_aaa_yield <= 0:
        return GrahamGrowthValueResult(
            status=CalculationStatus.INVALID_INPUT,
            reason=f"baseline_aaa_yield must be strictly positive (received {baseline_aaa_yield}).",
        )
    if base_pe <= 0:
        return GrahamGrowthValueResult(
            status=CalculationStatus.INVALID_INPUT,
            reason=f"base_pe must be strictly positive (received {base_pe}).",
        )
    if growth_multiplier < 0:
        return GrahamGrowthValueResult(
            status=CalculationStatus.INVALID_INPUT,
            reason=f"growth_multiplier must be non-negative (received {growth_multiplier}).",
        )

    # --- Calculation ---
    valuation_pe = base_pe + growth_multiplier * expected_growth_rate
    if not math.isfinite(valuation_pe):
        return GrahamGrowthValueResult(
            status=CalculationStatus.INVALID_INPUT,
            reason=f"Computed valuation P/E is not finite ({valuation_pe!r}).",
        )
    if valuation_pe <= 0:
        return GrahamGrowthValueResult(
            status=CalculationStatus.INVALID_INPUT,
            reason=f"Computed valuation P/E must be strictly positive (received {valuation_pe}).",
        )

    growth_value = normalized_eps * valuation_pe * baseline_aaa_yield / current_aaa_yield

    # Reject non-finite output
    if not math.isfinite(growth_value):
        return GrahamGrowthValueResult(
            status=CalculationStatus.INVALID_INPUT,
            reason=f"Computed growth value is not finite ({growth_value!r}).",
        )

    return GrahamGrowthValueResult(
        status=CalculationStatus.OK,
        growth_value=growth_value,
    )
