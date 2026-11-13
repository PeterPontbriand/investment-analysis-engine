"""Input assembly, result contracts, and deterministic graham_number calculations."""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Final

from investment_analysis_engine.analysis.shared.anchor_filing import AnchorFilingEvidence
from investment_analysis_engine.analysis.shared.financial_resolution import (
    resolve_normalized_eps,
    resolve_optional_quote,
)
from investment_analysis_engine.analysis.shared.metric_evidence import LeftOutYear, left_out_years_of
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureRecord
from investment_analysis_engine.data.financial.facts import FinancialFactRequest, FinancialField
from investment_analysis_engine.data.financial.provenance import FinancialSubjectKind, ResolvedInput, SourceKind
from investment_analysis_engine.data.financial.quote_freshness import QuoteFreshnessEvidence
from investment_analysis_engine.data.financial.resolution_trace import ResolutionTrace
from investment_analysis_engine.data.financial.resolver import InputResolutionResult, InputResolver
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID, AnchorYearEnd
from investment_analysis_engine.data.yfinance.client import YFINANCE_PROVIDER_ID
from investment_analysis_engine.reporting.presentation import format_money
from investment_analysis_engine.strategies._graham.anchor_years import (
    GrahamFilingInput,
    resolve_aligned,
)
from investment_analysis_engine.strategies._graham.outcome import failed_input_outcome
from investment_analysis_engine.strategies.graham_number.vocabulary import METHOD_ID, MethodId

_EPS_BASIS: Final = "three_year_average"
"""The one EPS basis Graham Number resolves: the average of the last three fiscal years."""

_METHOD_NAME: Final = "Graham Number"
"""The method's name as the year messages state it."""


@dataclass(frozen=True)
class GrahamNumberInputAssembly:
    """Assembled method inputs for the Graham Number calculation.

    The assembly layer does **not** perform the calculation.  It only
    resolves and packages the required and optional inputs with full
    provenance.

    Invariants:
        - ``OK``: ``eps``, ``bvps`` present; ``reason`` and ``reason_code`` are ``None``.
        - Non-OK: ``reason`` non-empty and ``reason_code`` present; field slots that were not resolved
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
        quote_provider_failure: The kind and provider of a quote whose provider failed, recorded against
            ``current_price``; it does not change ``status``.
        reason: Explanation when assembly ``status`` is not OK.
        resolution_trace: Ordered resolver events across attempted method inputs.
        method: Always ``"graham_number"``.
        provider_failure: The kind and provider of the input whose provider failed, recorded against that input,
            when ``status`` is ``PROVIDER_ERROR`` and the adapter classified the failure.
        anchor_filing: The anchor annual filing the filing inputs were taken at, with its next due date and whether it
            is stale at the boundary; ``None`` when it was not resolved (an ETF, a failure before it, or every
            filing input overridden).
        left_out_years: The years of EPS left out of the three-year series, with the reason of each; empty unless the
            series came up short because years were left out.
        reason_code: The code of the cause ``reason`` names; present exactly when ``status`` is not ``OK``. The
            presenters show ``reason`` as written.
    """

    status: CalculationStatus
    eps: ResolvedInput | None = None
    bvps: ResolvedInput | None = None
    current_price: ResolvedInput | None = None
    quote_status: CalculationStatus | None = None
    quote_reason: str | None = None
    quote_freshness: QuoteFreshnessEvidence | None = None
    reason: str | None = None
    resolution_trace: ResolutionTrace = field(default_factory=ResolutionTrace, compare=False)
    method: MethodId = field(init=False, default=METHOD_ID)
    provider_failure: ProviderFailureRecord | None = None
    quote_provider_failure: ProviderFailureRecord | None = None
    anchor_filing: AnchorFilingEvidence | None = None
    left_out_years: tuple[LeftOutYear, ...] = ()
    reason_code: ReasonCode | None = None

    def __post_init__(self) -> None:
        """Keep each recorded provider failure tied to the provider-error status it explains."""
        if self.provider_failure is not None and self.status is not CalculationStatus.PROVIDER_ERROR:
            raise ValueError("provider_failure requires a provider_error assembly.")
        if self.quote_provider_failure is not None and self.quote_status is not CalculationStatus.PROVIDER_ERROR:
            raise ValueError("quote_provider_failure requires a provider_error quote status.")
        if (self.reason_code is None) is (self.status is not CalculationStatus.OK):
            raise ValueError("A reason_code is present exactly when the assembly status is not ok.")


@dataclass(frozen=True)
class GrahamNumberResult:
    """Typed result of the Graham Number (sqrt(22.5 * EPS * BVPS)) calculation.

    Attributes:
        status: Calculation outcome.
        maximum_indicated_price: The screening-ceiling price.  ``None`` when
            ``status`` is not ``OK``.
        reason: Human-readable explanation when ``status`` is not ``OK``.
        method: Always ``"graham_number"`` (set automatically, not
            caller-supplied).
        reason_code: The code of the cause ``reason`` names; present exactly when ``status`` is not ``OK``.
    """

    status: CalculationStatus
    maximum_indicated_price: float | None = None
    reason: str | None = None
    method: MethodId = field(init=False, default=METHOD_ID)
    reason_code: ReasonCode | None = None

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
        if (self.reason_code is None) is (self.status is not CalculationStatus.OK):
            raise ValueError("GrahamNumberResult: a reason_code is present exactly when the status is not ok.")


# Classic Graham multiplier: maximum P/E 15 × maximum P/B 1.5 = 22.5
_GRAHAM_MULTIPLIER: Final[float] = 22.5


def compute_graham_number(
    eps: float, bvps: float, *, eps_currency: str | None = None, bvps_currency: str | None = None
) -> GrahamNumberResult:
    """Compute the Graham Number (maximum indicated price).

    Formula: ``sqrt(22.5 * eps * bvps)``.

    Args:
        eps: Earnings per share on the selected basis; finite, as every resolved input is.
        bvps: Book value per common share; finite, as every resolved input is.
        eps_currency: The currency of ``eps``, or ``None`` when it was not recorded.
        bvps_currency: The currency of ``bvps``, or ``None`` when it was not recorded.

    Returns:
        GrahamNumberResult with ``status`` of ``OK``, ``NOT_APPLICABLE`` (an input of zero or less, with the
        ``nonpositive_input`` code) or ``INVALID_INPUT`` (a product too large to compute, with the
        ``invalid_request`` code). When ``status`` is ``OK``, ``maximum_indicated_price`` contains the
        screening-ceiling price; otherwise it is ``None`` and ``reason`` explains the failure.
    """
    if eps <= 0:
        condition = "negative" if eps < 0 else "zero"
        return GrahamNumberResult(
            status=CalculationStatus.NOT_APPLICABLE,
            reason=(
                f"Earnings per share is {condition} ({format_money(eps, eps_currency)}), "
                "so the Graham Number does not apply."
            ),
            reason_code=ReasonCode.NONPOSITIVE_INPUT,
        )
    if bvps <= 0:
        condition = "negative" if bvps < 0 else "zero"
        return GrahamNumberResult(
            status=CalculationStatus.NOT_APPLICABLE,
            reason=(
                f"Book value per common share is {condition} ({format_money(bvps, bvps_currency)}), "
                "so the Graham Number does not apply."
            ),
            reason_code=ReasonCode.NONPOSITIVE_INPUT,
        )

    result_value = math.sqrt(_GRAHAM_MULTIPLIER * eps * bvps)
    if not math.isfinite(result_value):
        return GrahamNumberResult(
            status=CalculationStatus.INVALID_INPUT,
            reason=f"Computed Graham Number is not a valid positive finite value ({result_value!r}).",
            reason_code=ReasonCode.INVALID_REQUEST,
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
        anchor: AnchorYearEnd | None,
        eps_override: float | None = None,
        bvps_override: float | None = None,
        quote_override: float | None = None,
        as_of: datetime | None = None,
        use_cache: bool = True,
    ) -> GrahamNumberInputAssembly:
        """Assemble the inputs required by the Graham Number method.

        Args:
            security_subject_id: The ticker.
            anchor: The anchor annual filing's year-end; each input taken from a filing must end at it. ``None``
                only when both EPS and book value per share are overridden, so no filing input is read.
            eps_override: An explicit EPS, which has no year and is exempt from the year rule.
            bvps_override: An explicit book value per share, exempt in the same way.
            quote_override: An explicit current price.
            as_of: The point-in-time boundary, or ``None`` for now.
            use_cache: Whether the resolved-input cache may be used.

        Raises:
            ValueError: If ``anchor`` is ``None`` while EPS or book value per share is read from a filing.
        """
        if anchor is None and (eps_override is None or bvps_override is None):
            raise ValueError("An input read from a filing is assembled only at the anchor filing.")
        eps_result = resolve_aligned(
            self,
            lambda: resolve_normalized_eps(
                self,
                security_subject_id=security_subject_id,
                security_provider_id=SEC_PROVIDER_ID,
                eps_basis=_EPS_BASIS,
                eps_override=eps_override,
                as_of=as_of,
                use_cache=use_cache,
            ),
            anchor=anchor,
            method_name=_METHOD_NAME,
            which=GrahamFilingInput.EPS,
            overridden=eps_override is not None,
        )
        trace = eps_result.resolution_trace
        if eps_result.status is not CalculationStatus.OK:
            code, message = failed_input_outcome(
                eps_result, security_subject_id=security_subject_id, label="Earnings per share"
            )
            return GrahamNumberInputAssembly(
                status=eps_result.status,
                reason=message,
                resolution_trace=trace,
                provider_failure=_recorded(eps_result, "eps"),
                left_out_years=left_out_years_of("eps", eps_result.left_out),
                reason_code=code,
            )
        eps_input = eps_result.resolved_input

        bvps_request = FinancialFactRequest(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id=security_subject_id,
            field_name=FinancialField.BVPS,
            provider_id=SEC_PROVIDER_ID,
            as_of=as_of,
        )
        bvps_result = resolve_aligned(
            self,
            lambda: self.resolve_bvps(bvps_request, override=bvps_override, use_cache=use_cache),
            anchor=anchor,
            method_name=_METHOD_NAME,
            which=GrahamFilingInput.BVPS,
            overridden=bvps_override is not None,
        )
        trace = trace.extend(bvps_result.resolution_trace)
        if bvps_result.status is not CalculationStatus.OK:
            code, message = failed_input_outcome(
                bvps_result, security_subject_id=security_subject_id, label="Book value per share"
            )
            return GrahamNumberInputAssembly(
                status=bvps_result.status,
                eps=eps_input,
                reason=message,
                resolution_trace=trace,
                provider_failure=_recorded(bvps_result, "bvps"),
                reason_code=code,
            )
        bvps_input = bvps_result.resolved_input
        assert bvps_input is not None
        bvps_input = _with_semantic_bvps_basis(bvps_input)

        quote_result = resolve_optional_quote(
            self,
            security_subject_id=security_subject_id,
            security_provider_id=YFINANCE_PROVIDER_ID,
            quote_override=quote_override,
            as_of=as_of,
            use_cache=use_cache,
        )
        trace = trace.extend(quote_result.resolution_trace)
        if quote_result.status is CalculationStatus.INVALID_INPUT:
            code, message = failed_input_outcome(
                quote_result, security_subject_id=security_subject_id, label="Share price"
            )
            return GrahamNumberInputAssembly(
                status=CalculationStatus.INVALID_INPUT,
                eps=eps_input,
                bvps=bvps_input,
                reason=message,
                resolution_trace=trace,
                reason_code=code,
            )
        if quote_result.status is not CalculationStatus.OK:
            return GrahamNumberInputAssembly(
                status=CalculationStatus.OK,
                eps=eps_input,
                bvps=bvps_input,
                current_price=None,
                quote_status=quote_result.status,
                quote_reason=quote_result.reason,
                quote_provider_failure=_recorded(quote_result, "current_price"),
                quote_freshness=quote_result.quote_freshness,
                resolution_trace=trace,
            )
        return GrahamNumberInputAssembly(
            status=CalculationStatus.OK,
            eps=eps_input,
            bvps=bvps_input,
            current_price=quote_result.resolved_input,
            quote_freshness=quote_result.quote_freshness,
            resolution_trace=trace,
        )


def _recorded(result: InputResolutionResult, input_name: str) -> ProviderFailureRecord | None:
    """Return the failure a resolution recorded, against the strategy input it was resolved for."""
    return None if result.provider_failure is None else result.provider_failure.for_input(input_name)


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
