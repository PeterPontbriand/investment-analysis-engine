"""Input assembly, result contracts, and deterministic graham_growth calculations."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
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
from investment_analysis_engine.data.financial.resolution_trace import (
    ResolutionOutcome,
    ResolutionStage,
    ResolutionTrace,
    single_event_trace,
)
from investment_analysis_engine.data.financial.resolver import InputResolutionResult, InputResolver
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID, AnchorYearEnd
from investment_analysis_engine.data.yfinance.client import YFINANCE_PROVIDER_ID
from investment_analysis_engine.strategies._graham.anchor_years import (
    GrahamFilingInput,
    resolve_aligned,
)
from investment_analysis_engine.strategies._graham.outcome import failed_input_outcome
from investment_analysis_engine.strategies.graham_growth.vocabulary import METHOD_ID, MethodId

_METHOD_NAME: Final = "Graham Growth Value"
"""The method's name as the year messages state it."""


@dataclass(frozen=True)
class GrowthValueInputAssembly:
    """Assembled method inputs for the Graham Growth Value calculation.

    Invariants:
        - ``OK``: ``eps``, ``expected_growth``, ``current_aaa_yield``
          present; ``reason`` and ``reason_code`` are ``None``.
        - Non-OK: ``reason`` non-empty and ``reason_code`` present.
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
        quote_provider_failure: The kind and provider of a quote whose provider failed, recorded against
            ``current_price``; it does not change ``status``.
        reason: Explanation when assembly ``status`` is not OK.
        resolution_trace: Ordered resolver events across attempted method inputs.
        method: Always ``"graham_growth_value"``.
        provider_failure: The kind and provider of the input whose provider failed, recorded against that input,
            when ``status`` is ``PROVIDER_ERROR`` and the adapter classified the failure.
        anchor_filing: The anchor annual filing EPS was taken at, with its next due date and whether it is stale at
            the boundary; ``None`` when it was not resolved (an ETF, a failure before it, or EPS overridden).
        left_out_years: The years of EPS left out of the three-year series, with the reason of each; empty unless the
            series came up short because years were left out.
        reason_code: The code of the cause ``reason`` names; present exactly when ``status`` is not ``OK``. The
            presenters show ``reason`` as written.
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
class GrahamGrowthValueResult:
    """Typed result of the Graham growth-value calculation.

    Attributes:
        status: Calculation outcome.
        growth_value: The forecast-dependent growth estimate.  ``None`` when
            ``status`` is not ``OK``.
        reason: Human-readable explanation when ``status`` is not ``OK``.
        method: Always ``"graham_growth_value"`` (set automatically, not
            caller-supplied).
        reason_code: The code of the cause ``reason`` names; present exactly when ``status`` is not ``OK``.
    """

    status: CalculationStatus
    growth_value: float | None = None
    reason: str | None = None
    method: MethodId = field(init=False, default=METHOD_ID)
    reason_code: ReasonCode | None = None

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
        if (self.reason_code is None) is (self.status is not CalculationStatus.OK):
            raise ValueError("GrahamGrowthValueResult: a reason_code is present exactly when the status is not ok.")


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


def compute_graham_growth_value(  # noqa: PLR0913,PLR0917
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
        normalized_eps: Normalized EPS with an explicit basis.  Finite, as every resolved input is.
            Negative values are permitted (the method does not reject them
            merely for being negative).
        expected_growth_rate: Expected annual growth in percentage points.
            Finite.  Negative values are permitted; no clipping,
            capping, or annualization is applied.
        current_aaa_yield: Current AAA corporate-bond yield in percentage
            points.  Finite and strictly positive, as the selection requires.
        base_pe: Base P/E for a zero-growth company.  Must be finite and
            positive.  Default 8.5.
        growth_multiplier: Multiplier applied to the growth rate.  Must be
            finite and non-negative.  Default 2.0.
        baseline_aaa_yield: Historical benchmark AAA bond yield in percentage
            points.  Must be finite and strictly positive.  Default 4.4.

    Returns:
        GrahamGrowthValueResult with ``status`` of ``OK`` or ``INVALID_INPUT``. ``INVALID_INPUT`` carries the
        ``invalid_request`` code and is a valuation P/E of zero or less, or a value too large to compute. When
        ``status`` is ``OK``, ``growth_value`` contains the forecast-dependent estimate; otherwise it is ``None``
        and ``reason`` explains the failure.

    Raises:
        ValueError: If a calculation constant is not finite, or ``base_pe`` or ``baseline_aaa_yield`` is not
            positive, or ``growth_multiplier`` is negative; ``GrahamGrowthCalculationPolicy`` rules these out.
    """
    constants = (base_pe, growth_multiplier, baseline_aaa_yield)
    if not all(math.isfinite(value) for value in constants):
        raise ValueError("Graham growth calculation constants must be finite.")
    if base_pe <= 0 or baseline_aaa_yield <= 0 or growth_multiplier < 0:
        raise ValueError("Graham growth calculation constants are out of range.")

    valuation_pe = base_pe + growth_multiplier * expected_growth_rate
    if not math.isfinite(valuation_pe):
        return GrahamGrowthValueResult(
            status=CalculationStatus.INVALID_INPUT,
            reason=f"Computed valuation P/E is not finite ({valuation_pe!r}).",
            reason_code=ReasonCode.INVALID_REQUEST,
        )
    if valuation_pe <= 0:
        return GrahamGrowthValueResult(
            status=CalculationStatus.INVALID_INPUT,
            reason=f"The computed valuation P/E is zero or negative ({valuation_pe}), so the value cannot be computed.",
            reason_code=ReasonCode.INVALID_REQUEST,
        )

    growth_value = normalized_eps * valuation_pe * baseline_aaa_yield / current_aaa_yield

    if not math.isfinite(growth_value):
        return GrahamGrowthValueResult(
            status=CalculationStatus.INVALID_INPUT,
            reason=f"Computed growth value is not finite ({growth_value!r}).",
            reason_code=ReasonCode.INVALID_REQUEST,
        )

    return GrahamGrowthValueResult(
        status=CalculationStatus.OK,
        growth_value=growth_value,
    )


def _recorded(result: InputResolutionResult, input_name: str) -> ProviderFailureRecord | None:
    """Return the failure a resolution recorded, against the strategy input it was resolved for."""
    return None if result.provider_failure is None else result.provider_failure.for_input(input_name)


AAA_SUBJECT_ID: Final = "AAA"
"""The subject of the AAA corporate-yield input."""
AAA_PROVIDER_ID: Final = "user_override"
"""The source identity of the AAA yield: the user supplies it, and no provider does."""


class GrahamGrowthInputResolver(InputResolver):
    """Assemble method inputs using borrowed provider, cache, and clock dependencies."""

    def assemble_growth_value(  # noqa: PLR0911, PLR0913
        self,
        *,
        security_subject_id: str,
        anchor: AnchorYearEnd | None,
        eps_basis: str,
        eps_override: float | None = None,
        expected_growth: float,
        aaa_yield_override: float,
        quote_override: float | None = None,
        as_of: datetime | None = None,
        use_cache: bool = True,
    ) -> GrowthValueInputAssembly:
        """Assemble the inputs required by the Graham Growth Value method.

        Args:
            security_subject_id: The ticker.
            anchor: The anchor annual filing's year-end; EPS read from a filing must end at it. ``None`` only when
                EPS is overridden, so no filing input is read.
            eps_basis: ``three_year_average`` or ``fiscal_year``.
            eps_override: An explicit EPS, which has no year and is exempt from the year rule.
            expected_growth: The expected growth rate in percentage points.
            aaa_yield_override: The current AAA yield in percentage points.
            quote_override: An explicit current price.
            as_of: The point-in-time boundary, or ``None`` for now.
            use_cache: Whether the resolved-input cache may be used.

        Raises:
            ValueError: If ``anchor`` is ``None`` while EPS is read from a filing.
        """
        if anchor is None and eps_override is None:
            raise ValueError("An input read from a filing is assembled only at the anchor filing.")

        eps_result = resolve_aligned(
            self,
            lambda: resolve_normalized_eps(
                self,
                security_subject_id=security_subject_id,
                security_provider_id=SEC_PROVIDER_ID,
                eps_basis=eps_basis,
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
            return GrowthValueInputAssembly(
                status=eps_result.status,
                reason=message,
                resolution_trace=trace,
                provider_failure=_recorded(eps_result, "eps"),
                left_out_years=left_out_years_of("eps", eps_result.left_out),
                reason_code=code,
            )
        eps_input = eps_result.resolved_input

        growth_result = self._resolve_expected_growth(expected_growth, as_of=as_of)
        trace = trace.extend(growth_result.resolution_trace)
        growth_input = growth_result.resolved_input
        assert growth_input is not None

        aaa_request = FinancialFactRequest(
            subject_kind=FinancialSubjectKind.MACRO,
            subject_id=AAA_SUBJECT_ID,
            field_name=FinancialField.CURRENT_AAA_YIELD,
            provider_id=AAA_PROVIDER_ID,
            as_of=as_of,
        )
        aaa_result = self.resolve(aaa_request, override=aaa_yield_override, use_cache=use_cache)
        trace = trace.extend(aaa_result.resolution_trace)
        if aaa_result.status is not CalculationStatus.OK:
            code, message = failed_input_outcome(aaa_result, security_subject_id=security_subject_id, label="AAA yield")
            return GrowthValueInputAssembly(
                status=aaa_result.status,
                eps=eps_input,
                expected_growth=growth_input,
                reason=message,
                resolution_trace=trace,
                provider_failure=_recorded(aaa_result, "current_aaa_yield"),
                reason_code=code,
            )
        aaa_input = aaa_result.resolved_input

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
            return GrowthValueInputAssembly(
                status=CalculationStatus.INVALID_INPUT,
                eps=eps_input,
                expected_growth=growth_input,
                current_aaa_yield=aaa_input,
                reason=message,
                resolution_trace=trace,
                reason_code=code,
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
                quote_provider_failure=_recorded(quote_result, "current_price"),
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

    def _resolve_expected_growth(self, value: float, *, as_of: datetime | None = None) -> InputResolutionResult:
        """Construct the OVERRIDE ResolvedInput for the expected growth, a finite number the selection guarantees."""
        field_name = "expected_growth"
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
            resolution_trace=single_event_trace(
                field_name,
                ResolutionStage.OVERRIDE,
                ResolutionOutcome.SUCCESS,
                "Explicit expected-growth assumption was accepted.",
            ),
        )
