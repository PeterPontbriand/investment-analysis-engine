"""Graham-specific assembly of reusable resolved valuation inputs."""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from datetime import datetime

from src.analysis.graham_value.models import GrahamMethod
from src.core.analysis_status import CalculationStatus
from src.data.valuation.facts import ValuationFactRequest, ValuationField
from src.data.valuation.provenance import ResolvedInput, SourceKind, ValuationSubjectKind
from src.data.valuation.resolution_trace import (
    ResolutionEvent,
    ResolutionOutcome,
    ResolutionStage,
    ResolutionTrace,
)
from src.data.valuation.resolver import InputResolutionResult, InputResolver


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
    reason: str | None = None
    resolution_trace: ResolutionTrace = field(default_factory=ResolutionTrace, compare=False)
    method: GrahamMethod = field(init=False, default=GrahamMethod.GROWTH_VALUE)


class GrahamInputResolver(InputResolver):
    """Add Graham method-input assembly to the reusable valuation resolver."""

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

        eps_result = self._resolve_eps(
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

        bvps_request = ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=security_subject_id,
            field_name=ValuationField.BVPS,
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

        quote_result = self._resolve_optional_quote(
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

        eps_result = self._resolve_eps(
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

        aaa_request = ValuationFactRequest(
            subject_kind=ValuationSubjectKind.MACRO,
            subject_id=aaa_subject_id,
            field_name=ValuationField.CURRENT_AAA_YIELD,
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

        quote_result = self._resolve_optional_quote(
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
                resolution_trace=trace,
            )
        return GrowthValueInputAssembly(
            status=CalculationStatus.OK,
            eps=eps_input,
            expected_growth=growth_input,
            current_aaa_yield=aaa_input,
            current_price=quote_result.resolved_input,
            resolution_trace=trace,
        )

    def _resolve_eps(  # noqa: PLR0913
        self,
        *,
        security_subject_id: str,
        security_provider_id: str,
        eps_basis: str,
        eps_override: float | None,
        as_of: datetime | None,
        use_cache: bool,
    ) -> InputResolutionResult:
        """Resolve EPS using the appropriate C2C entry point.

        Delegates to ``resolve_three_year_average_eps`` for the
        ``three_year_average`` basis, or the single-fact ``resolve`` for
        ``ttm`` and any other single-observation basis.  An explicit
        override always bypasses cache/provider.
        """
        if eps_override is not None:
            # Override bypasses cache/provider; retain the selected basis.
            request = ValuationFactRequest(
                subject_kind=ValuationSubjectKind.SECURITY,
                subject_id=security_subject_id,
                field_name=ValuationField.EPS,
                provider_id=security_provider_id,
                basis=eps_basis,
                as_of=as_of,
            )
            return self.resolve(request, override=eps_override, use_cache=use_cache)

        if eps_basis == "three_year_average":
            request = ValuationFactRequest(
                subject_kind=ValuationSubjectKind.SECURITY,
                subject_id=security_subject_id,
                field_name=ValuationField.EPS,
                provider_id=security_provider_id,
                basis="fiscal_year",
                as_of=as_of,
                observation_count=3,
            )
            return self.resolve_three_year_average_eps(request, use_cache=use_cache)

        # Single-observation basis (ttm, etc.)
        request = ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=security_subject_id,
            field_name=ValuationField.EPS,
            provider_id=security_provider_id,
            basis=eps_basis,
            as_of=as_of,
        )
        return self.resolve(request, use_cache=use_cache)

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

    def _resolve_optional_quote(
        self,
        *,
        security_subject_id: str,
        security_provider_id: str,
        quote_override: float | None,
        as_of: datetime | None,
        use_cache: bool,
    ) -> InputResolutionResult:
        """Resolve the optional current price.

        This method is only called after all required inputs succeed.
        Returns an ``InputResolutionResult`` whose status determines the
        caller's behavior:
            - OK: include the resolved input.
            - INPUT_UNAVAILABLE / PROVIDER_ERROR: non-fatal degradation.
            - INVALID_INPUT: fatal — fail the assembly.

        Note: this method is only called after all required inputs succeed.
        """
        request = ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=security_subject_id,
            field_name=ValuationField.CURRENT_PRICE,
            provider_id=security_provider_id,
            as_of=as_of,
        )
        return self.resolve(request, override=quote_override, use_cache=use_cache)


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


def _event(
    field_name: str,
    stage: ResolutionStage,
    outcome: ResolutionOutcome,
    message: str,
) -> ResolutionEvent:
    """Construct one Graham assembly trace event."""
    return ResolutionEvent(field_name=field_name, stage=stage, outcome=outcome, message=message)


def _trace_event(
    field_name: str,
    stage: ResolutionStage,
    outcome: ResolutionOutcome,
    message: str,
) -> ResolutionTrace:
    """Construct a one-event Graham assembly trace."""
    return ResolutionTrace(events=(_event(field_name, stage, outcome, message),))
