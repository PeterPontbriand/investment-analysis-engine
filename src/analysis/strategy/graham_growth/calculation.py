"""Input assembly, result contracts, and deterministic graham_growth calculations."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

from src.analysis.shared.financial_resolution import resolve_normalized_eps, resolve_optional_quote
from src.analysis.shared.graham_contracts import GrahamMethod, _trace_event
from src.core.analysis_status import CalculationStatus
from src.data.financial.facts import FinancialFactRequest, FinancialField
from src.data.financial.provenance import FinancialSubjectKind, ResolvedInput, SourceKind
from src.data.financial.quote_freshness import QuoteFreshnessEvidence
from src.data.financial.resolution_trace import ResolutionOutcome, ResolutionStage, ResolutionTrace
from src.data.financial.resolver import InputResolutionResult, InputResolver


@dataclass(frozen=True)
class GrowthValueInputAssembly:
    """Assembled method inputs for the Graham Growth Value calculation.

    Invariants:
        - ``OK``: ``eps``, ``expected_growth``, ``current_aaa_yield``
          present; ``reason`` is ``None``.
        - Non-OK: ``reason`` non-empty.
        - ``current_price`` is ``None`` when the quote was unavailable or
          the assembly failed before reaching quote resolution.
        - ``quote_status`` / ``quote_reason`` carry the diagnostic when the
          quote was attempted and degraded non-fatally.

    Attributes:
        status: Assembly outcome.
        eps: Resolved EPS input with an explicit basis (present when OK).
        expected_growth: Resolved expected growth rate in percentage points
            (present when OK).
        current_aaa_yield: Resolved current AAA yield in percentage points
            (present when OK).
        current_price: Resolved current price (optional; ``None`` when
            absent or unavailable).
        quote_status: Status of the quote resolution attempt (set when a
            quote was requested and did not return OK).
        quote_reason: Human-readable reason for a non-OK quote.
        reason: Explanation when assembly ``status`` is not OK.
        resolution_trace: Ordered resolver events across attempted method inputs.
        method: Always ``GrahamMethod.GROWTH_VALUE``.
    """

    status: CalculationStatus
    eps: ResolvedInput | None = None
    expected_growth: ResolvedInput | None = None
    current_aaa_yield: ResolvedInput | None = None
    current_price: ResolvedInput | None = None
    quote_status: CalculationStatus | None = None
    quote_reason: str | None = None
    quote_freshness: QuoteFreshnessEvidence | None = None
    reason: str | None = None
    resolution_trace: ResolutionTrace = field(default_factory=ResolutionTrace, compare=False)
    method: GrahamMethod = field(init=False, default=GrahamMethod.GROWTH_VALUE)


@dataclass(frozen=True)
class GrahamGrowthValueResult:
    """Typed result of the Graham growth-value calculation.

    Attributes:
        status: Calculation outcome.
        growth_value: The forecast-dependent growth estimate.  ``None`` when
            ``status`` is not ``OK``.
        reason: Human-readable explanation when ``status`` is not ``OK``.
        method: Always ``GrahamMethod.GROWTH_VALUE`` (set automatically, not
            caller-supplied).
    """

    status: CalculationStatus
    growth_value: float | None = None
    reason: str | None = None
    method: GrahamMethod = field(init=False, default=GrahamMethod.GROWTH_VALUE)

    def __post_init__(self) -> None:
        """Enforce result-state invariants."""
        if self.status is CalculationStatus.OK:
            if self.growth_value is None:
                raise ValueError("GrahamGrowthValueResult: status OK requires growth_value to be present.")
            if self.reason is not None:
                raise ValueError("GrahamGrowthValueResult: status OK requires reason to be None.")
        else:
            if self.growth_value is not None:
                raise ValueError(f"GrahamGrowthValueResult: status {self.status} requires growth_value to be None.")
            if not self.reason:
                raise ValueError(f"GrahamGrowthValueResult: status {self.status} requires a non-empty reason.")


@dataclass(frozen=True)
class GrahamGrowthCalculationPolicy:
    """Configured constants used by the Graham growth-value calculation."""

    base_pe: float
    growth_multiplier: float
    baseline_aaa_yield: float

    def __post_init__(self) -> None:
        """Reject non-finite or financially invalid calculation constants."""
        values = (self.base_pe, self.growth_multiplier, self.baseline_aaa_yield)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Graham growth calculation constants must be finite.")
        if self.base_pe <= 0:
            raise ValueError("Graham growth base_pe must be positive.")
        if self.growth_multiplier < 0:
            raise ValueError("Graham growth growth_multiplier must be non-negative.")
        if self.baseline_aaa_yield <= 0:
            raise ValueError("Graham growth baseline_aaa_yield must be positive.")


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


class GrahamGrowthInputResolver(InputResolver):
    """Assemble method inputs using borrowed provider, cache, and clock dependencies."""

    def assemble_growth_value(  # noqa: PLR0911, PLR0913
        self,
        *,
        security_subject_id: str,
        security_provider_id: str,
        eps_basis: str,
        eps_override: float | None = None,
        expected_growth: float | None = None,
        aaa_subject_id: str,
        aaa_provider_id: str,
        aaa_yield_override: float | None = None,
        quote_override: float | None = None,
        quote_provider_id: str | None = None,
        as_of: datetime | None = None,
        use_cache: bool = True,
    ) -> GrowthValueInputAssembly:
        """Assemble the inputs required by the Graham Growth Value method."""
        if not eps_basis.strip():
            reason = "eps_basis must be a non-empty string."
            return GrowthValueInputAssembly(
                status=CalculationStatus.INVALID_INPUT,
                reason=reason,
                resolution_trace=_trace_event(
                    "eps",
                    ResolutionStage.VALIDATION,
                    ResolutionOutcome.INVALID,
                    reason,
                ),
            )

        eps_result = resolve_normalized_eps(
            self,
            security_subject_id=security_subject_id,
            security_provider_id=security_provider_id,
            eps_basis=eps_basis,
            eps_override=eps_override,
            as_of=as_of,
            use_cache=use_cache,
        )
        trace = eps_result.resolution_trace
        if eps_result.status is not CalculationStatus.OK:
            return GrowthValueInputAssembly(
                status=eps_result.status,
                reason=f"eps: {eps_result.reason}",
                resolution_trace=trace,
            )
        eps_input = eps_result.resolved_input

        growth_result = self._resolve_expected_growth(expected_growth, as_of=as_of)
        trace = trace.extend(growth_result.resolution_trace)
        if growth_result.status is not CalculationStatus.OK:
            return GrowthValueInputAssembly(
                status=growth_result.status,
                eps=eps_input,
                reason=f"expected_growth: {growth_result.reason}",
                resolution_trace=trace,
            )
        growth_input = growth_result.resolved_input

        aaa_request = FinancialFactRequest(
            subject_kind=FinancialSubjectKind.MACRO,
            subject_id=aaa_subject_id,
            field_name=FinancialField.CURRENT_AAA_YIELD,
            provider_id=aaa_provider_id,
            as_of=as_of,
        )
        aaa_result = self.resolve(aaa_request, override=aaa_yield_override, use_cache=use_cache)
        trace = trace.extend(aaa_result.resolution_trace)
        if aaa_result.status is not CalculationStatus.OK:
            return GrowthValueInputAssembly(
                status=aaa_result.status,
                eps=eps_input,
                expected_growth=growth_input,
                reason=f"current_aaa_yield: {aaa_result.reason}",
                resolution_trace=trace,
            )
        aaa_input = aaa_result.resolved_input

        quote_result = resolve_optional_quote(
            self,
            security_subject_id=security_subject_id,
            security_provider_id=quote_provider_id or security_provider_id,
            quote_override=quote_override,
            as_of=as_of,
            use_cache=use_cache,
        )
        trace = trace.extend(quote_result.resolution_trace)
        if quote_result.status is CalculationStatus.INVALID_INPUT:
            return GrowthValueInputAssembly(
                status=CalculationStatus.INVALID_INPUT,
                eps=eps_input,
                expected_growth=growth_input,
                current_aaa_yield=aaa_input,
                reason=f"current_price: {quote_result.reason}",
                resolution_trace=trace,
            )
        if quote_result.status is not CalculationStatus.OK:
            return GrowthValueInputAssembly(
                status=CalculationStatus.OK,
                eps=eps_input,
                expected_growth=growth_input,
                current_aaa_yield=aaa_input,
                current_price=None,
                quote_status=quote_result.status,
                quote_reason=quote_result.reason,
                quote_freshness=quote_result.quote_freshness,
                resolution_trace=trace,
            )
        return GrowthValueInputAssembly(
            status=CalculationStatus.OK,
            eps=eps_input,
            expected_growth=growth_input,
            current_aaa_yield=aaa_input,
            current_price=quote_result.resolved_input,
            quote_freshness=quote_result.quote_freshness,
            resolution_trace=trace,
        )

    def _resolve_expected_growth(self, value: float | None, *, as_of: datetime | None = None) -> InputResolutionResult:
        """Validate and construct an OVERRIDE ResolvedInput for expected growth."""
        field_name = "expected_growth"
        if value is None:
            reason = "expected_growth is required but was not provided."
            return InputResolutionResult(
                status=CalculationStatus.INPUT_UNAVAILABLE,
                reason=reason,
                resolution_trace=_trace_event(
                    field_name,
                    ResolutionStage.OVERRIDE,
                    ResolutionOutcome.UNAVAILABLE,
                    reason,
                ),
            )
        if not math.isfinite(value):
            reason = f"expected_growth must be finite (received {value!r})."
            return InputResolutionResult(
                status=CalculationStatus.INVALID_INPUT,
                reason=reason,
                resolution_trace=_trace_event(
                    field_name,
                    ResolutionStage.OVERRIDE,
                    ResolutionOutcome.INVALID,
                    reason,
                ),
            )
        ri = ResolvedInput(
            field_name=field_name,
            value=value,
            source_kind=SourceKind.OVERRIDE,
            resolved_at=self._clock(),
            units="percentage_points",
            as_of=as_of,
        )
        return InputResolutionResult(
            status=CalculationStatus.OK,
            resolved_input=ri,
            resolution_trace=_trace_event(
                field_name,
                ResolutionStage.OVERRIDE,
                ResolutionOutcome.SUCCESS,
                "Explicit expected-growth assumption was accepted.",
            ),
        )
