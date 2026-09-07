"""Input assembly, result contracts, and deterministic graham_number calculations."""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Final

from src.analysis.shared.financial_resolution import resolve_normalized_eps, resolve_optional_quote
from src.analysis.shared.graham_contracts import GrahamMethod, _trace_event
from src.core.analysis_status import CalculationStatus
from src.data.financial.facts import FinancialFactRequest, FinancialField
from src.data.financial.provenance import FinancialSubjectKind, ResolvedInput, SourceKind
from src.data.financial.resolution_trace import ResolutionOutcome, ResolutionStage, ResolutionTrace
from src.data.financial.resolver import InputResolver


@dataclass(frozen=True)
class GrahamNumberInputAssembly:
    """Assembled method inputs for the Graham Number calculation.

    The assembly layer does **not** perform the calculation.  It only
    resolves and packages the required and optional inputs with full
    provenance.

    Invariants:
        - ``OK``: ``eps``, ``bvps`` present; ``reason`` is ``None``.
        - Non-OK: ``reason`` non-empty; field slots that were not resolved
          are ``None``.
        - ``current_price`` is ``None`` when the quote was unavailable or
          the assembly failed before reaching quote resolution.
        - ``quote_status`` / ``quote_reason`` carry the diagnostic when the
          quote was attempted and degraded non-fatally.

    Attributes:
        status: Assembly outcome.
        eps: Resolved EPS input (present when OK).
        bvps: Resolved BVPS input (present when OK).
        current_price: Resolved current price (optional; ``None`` when
            absent or unavailable).
        quote_status: Status of the quote resolution attempt (set when a
            quote was requested and did not return OK).
        quote_reason: Human-readable reason for a non-OK quote.
        reason: Explanation when assembly ``status`` is not OK.
        resolution_trace: Ordered resolver events across attempted method inputs.
        method: Always ``GrahamMethod.NUMBER``.
    """

    status: CalculationStatus
    eps: ResolvedInput | None = None
    bvps: ResolvedInput | None = None
    current_price: ResolvedInput | None = None
    quote_status: CalculationStatus | None = None
    quote_reason: str | None = None
    reason: str | None = None
    resolution_trace: ResolutionTrace = field(default_factory=ResolutionTrace, compare=False)
    method: GrahamMethod = field(init=False, default=GrahamMethod.NUMBER)


@dataclass(frozen=True)
class GrahamNumberResult:
    """Typed result of the Graham Number (sqrt(22.5 * EPS * BVPS)) calculation.

    Attributes:
        status: Calculation outcome.
        maximum_indicated_price: The screening-ceiling price.  ``None`` when
            ``status`` is not ``OK``.
        reason: Human-readable explanation when ``status`` is not ``OK``.
        method: Always ``GrahamMethod.NUMBER`` (set automatically, not
            caller-supplied).
    """

    status: CalculationStatus
    maximum_indicated_price: float | None = None
    reason: str | None = None
    method: GrahamMethod = field(init=False, default=GrahamMethod.NUMBER)

    def __post_init__(self) -> None:
        """Enforce result-state invariants."""
        if self.status is CalculationStatus.OK:
            if self.maximum_indicated_price is None:
                raise ValueError("GrahamNumberResult: status OK requires maximum_indicated_price to be present.")
            if self.reason is not None:
                raise ValueError("GrahamNumberResult: status OK requires reason to be None.")
        else:
            if self.maximum_indicated_price is not None:
                raise ValueError(
                    f"GrahamNumberResult: status {self.status} requires maximum_indicated_price to be None."
                )
            if not self.reason:
                raise ValueError(f"GrahamNumberResult: status {self.status} requires a non-empty reason.")


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


class GrahamNumberInputResolver(InputResolver):
    """Assemble method inputs using borrowed provider, cache, and clock dependencies."""

    def assemble_graham_number(  # noqa: PLR0913
        self,
        *,
        security_subject_id: str,
        security_provider_id: str,
        eps_basis: str = "three_year_average",
        eps_override: float | None = None,
        bvps_override: float | None = None,
        quote_override: float | None = None,
        quote_provider_id: str | None = None,
        as_of: datetime | None = None,
        use_cache: bool = True,
    ) -> GrahamNumberInputAssembly:
        """Assemble the inputs required by the Graham Number method."""
        if eps_basis not in ("three_year_average", "ttm"):
            reason = f"eps_basis must be 'three_year_average' or 'ttm' (received {eps_basis!r})."
            return GrahamNumberInputAssembly(
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
            return GrahamNumberInputAssembly(
                status=eps_result.status,
                reason=f"eps: {eps_result.reason}",
                resolution_trace=trace,
            )
        eps_input = eps_result.resolved_input

        bvps_request = FinancialFactRequest(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id=security_subject_id,
            field_name=FinancialField.BVPS,
            provider_id=security_provider_id,
            as_of=as_of,
        )
        bvps_result = self.resolve_bvps(bvps_request, override=bvps_override, use_cache=use_cache)
        trace = trace.extend(bvps_result.resolution_trace)
        if bvps_result.status is not CalculationStatus.OK:
            return GrahamNumberInputAssembly(
                status=bvps_result.status,
                eps=eps_input,
                reason=f"bvps: {bvps_result.reason}",
                resolution_trace=trace,
            )
        bvps_input = bvps_result.resolved_input
        assert bvps_input is not None
        bvps_input = _with_semantic_bvps_basis(bvps_input)

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
            return GrahamNumberInputAssembly(
                status=CalculationStatus.INVALID_INPUT,
                eps=eps_input,
                bvps=bvps_input,
                reason=f"current_price: {quote_result.reason}",
                resolution_trace=trace,
            )
        if quote_result.status is not CalculationStatus.OK:
            return GrahamNumberInputAssembly(
                status=CalculationStatus.OK,
                eps=eps_input,
                bvps=bvps_input,
                current_price=None,
                quote_status=quote_result.status,
                quote_reason=quote_result.reason,
                resolution_trace=trace,
            )
        return GrahamNumberInputAssembly(
            status=CalculationStatus.OK,
            eps=eps_input,
            bvps=bvps_input,
            current_price=quote_result.resolved_input,
            resolution_trace=trace,
        )


def _with_semantic_bvps_basis(value: ResolvedInput) -> ResolvedInput:
    """Annotate derived period-end BVPS at the Graham method-input boundary."""
    if value.basis is not None or value.source_kind is not SourceKind.DERIVED:
        return value
    if value.lineage is None or not value.lineage.components:
        return value
    component_bases = {component.basis for component in value.lineage.components}
    if component_bases != {"fiscal_year_end"}:
        return value
    return replace(value, basis="fiscal_year_end")
