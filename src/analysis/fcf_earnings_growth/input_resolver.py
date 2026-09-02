"""Deterministic annual-series resolution for FCF and earnings growth."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from src.analysis.fcf_earnings_growth.calculators import (
    compute_cagr,
    compute_fcf_per_diluted_share,
    compute_free_cash_flow,
)
from src.analysis.fcf_earnings_growth.models import (
    AnnualGrowthObservation,
    FCFClassificationBasis,
    FCFEarningsGrowthPolicy,
    HistoricalHorizon,
    MetricResult,
    MetricStatus,
    ReasonCode,
)
from src.core.analysis_status import CalculationStatus
from src.data.financial.cache import (
    ResolvedInputCacheKey,
    ResolvedInputSeriesCacheProtocol,
    ResolvedInputSeriesCacheQuery,
)
from src.data.financial.facts import (
    FinancialFactRequest,
    FinancialFactsProvider,
    FinancialField,
    FinancialProviderError,
    FinancialUnit,
    ProviderFact,
    financial_facts_analysis_scope,
)
from src.data.financial.provenance import (
    AccountingScope,
    CapitalExpenditureSign,
    ComponentLineage,
    FinancialSubjectKind,
    PeriodKind,
    ResolvedInput,
    SourceKind,
)
from src.data.financial.resolution_trace import (
    ResolutionEvent,
    ResolutionOutcome,
    ResolutionStage,
    ResolutionTrace,
)
from src.data.sec_edgar.financial_facts import SEC_PROVIDER_ID

CACHE_SCHEMA_VERSION = 2
_ANNUAL_FIELDS = (
    FinancialField.OPERATING_CASH_FLOW,
    FinancialField.CAPITAL_EXPENDITURES,
    FinancialField.EPS,
    FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES,
)
_REQUIRED_ANNUAL_FIELDS = _ANNUAL_FIELDS[:3]


class ProductionAnnualGrowthSeriesResolver:
    """Resolve annual FCF and EPS history from an approved production provider.

    SEC EDGAR is currently the only provider with evidence-approved mappings
    for all three required annual fields. Keeping that composition here makes
    the supported production path explicit while leaving the C2 resolver
    provider-neutral and independently testable.
    """

    def __init__(
        self,
        provider: FinancialFactsProvider,
        *,
        cache: ResolvedInputSeriesCacheProtocol | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Initialize the resolver with a composed financial-facts provider."""
        self._provider = provider
        self._cache = cache
        self._clock = clock

    def resolve(  # noqa: PLR0913
        self,
        *,
        policy: FCFEarningsGrowthPolicy,
        subject_id: str,
        currency: str,
        as_of: datetime | None,
        provider_id: str = SEC_PROVIDER_ID,
        use_cache: bool = True,
    ) -> AnnualGrowthSeriesAssembly:
        """Resolve the strategy inputs, preserving typed unsupported-provider outcomes."""
        normalized_provider_id = provider_id.strip().lower()
        if normalized_provider_id != SEC_PROVIDER_ID:
            reason = (
                f"Provider {provider_id!r} does not have approved annual operating-cash-flow, "
                "capital-expenditure, and diluted-EPS mappings."
            )
            trace = ResolutionTrace().append(
                _event("annual_series", ResolutionStage.PROVIDER, ResolutionOutcome.REJECTED, reason)
            )
            return _failure_assembly(
                status=CalculationStatus.INPUT_UNAVAILABLE,
                code=ReasonCode.MISSING_FACT,
                reason=reason,
                policy=policy,
                common_count=0,
                longest_count=0,
                trace=trace,
            )

        with financial_facts_analysis_scope(
            self._provider,
            subject_id=subject_id,
            provider_id=normalized_provider_id,
            as_of=as_of,
        ):
            binding = FinancialFieldProvider(normalized_provider_id, self._provider)
            providers = dict.fromkeys(_ANNUAL_FIELDS, binding)
            return resolve_annual_growth_series(
                policy=policy,
                subject_id=subject_id,
                currency=currency,
                as_of=as_of,
                providers=providers,
                cache=self._cache,
                use_cache=use_cache,
                clock=self._clock,
            )


@dataclass(frozen=True)
class FinancialFieldProvider:
    """Bind one semantic financial field to a named provider implementation."""

    provider_id: str
    provider: FinancialFactsProvider

    def __post_init__(self) -> None:
        """Normalize and validate the provider identifier."""
        normalized = self.provider_id.strip().lower()
        if not normalized:
            raise ValueError("FinancialFieldProvider.provider_id must be non-empty.")
        object.__setattr__(self, "provider_id", normalized)


@dataclass(frozen=True)
class SeriesSelection:
    """Deterministic record of annual-history horizon selection."""

    requested: HistoricalHorizon
    candidate_elapsed_years: tuple[int, ...]
    selected_elapsed_years: int | None
    fallback_applied: bool
    common_period_count: int
    longest_contiguous_observation_count: int

    def __post_init__(self) -> None:
        """Validate selection coherence."""
        if self.selected_elapsed_years is not None and self.selected_elapsed_years not in (3, 4, 5):
            raise ValueError("selected_elapsed_years must be 3, 4, 5, or None.")
        if self.common_period_count < 0 or self.longest_contiguous_observation_count < 0:
            raise ValueError("Series-selection counts must be non-negative.")
        expected_fallback = (
            self.requested is HistoricalHorizon.LONGEST_AVAILABLE
            and self.selected_elapsed_years is not None
            and self.selected_elapsed_years < 5
        )
        if self.fallback_applied is not expected_fallback:
            raise ValueError("fallback_applied is inconsistent with the requested and selected horizons.")


@dataclass(frozen=True)
class AnnualGrowthSeriesAssembly:
    """Typed result of annual financial-fact resolution and horizon selection."""

    status: CalculationStatus
    reason_code: ReasonCode | None
    reason: str | None
    observations: tuple[AnnualGrowthObservation, ...]
    requested_horizon: HistoricalHorizon
    selected_horizon_years: int | None
    selected_observation_count: int
    used_horizon_fallback: bool
    fcf_cagr: MetricResult
    fcf_per_share_cagr: MetricResult
    eps_cagr: MetricResult
    span_sign_change_fcf: bool
    span_sign_change_eps: bool
    selection: SeriesSelection
    resolution_trace: ResolutionTrace

    def __post_init__(self) -> None:
        """Enforce success/failure and selected-span invariants."""
        if self.selected_observation_count != len(self.observations):
            raise ValueError("selected_observation_count must equal len(observations).")
        if self.selected_horizon_years is not None and len(self.observations) != self.selected_horizon_years + 1:
            raise ValueError("A selected horizon requires exactly N + 1 observations.")
        if self.status is CalculationStatus.OK:
            if self.reason_code is not None or self.reason is not None or self.selected_horizon_years is None:
                raise ValueError("A successful annual-series assembly requires a selected horizon and no reason.")
        elif self.reason_code is None or self.reason is None or not self.reason.strip():
            raise ValueError("A failed annual-series assembly requires a reason code and reason.")
        if self.selection.selected_elapsed_years != self.selected_horizon_years:
            raise ValueError("selection.selected_elapsed_years must match selected_horizon_years.")
        if self.selection.fallback_applied is not self.used_horizon_fallback:
            raise ValueError("Selection and assembly fallback flags must match.")


@dataclass(frozen=True)
class _FieldResolution:
    inputs: tuple[ResolvedInput, ...] = ()
    reason_code: ReasonCode | None = None
    reason: str | None = None
    provider_error: bool = False


def _event(field: str, stage: ResolutionStage, outcome: ResolutionOutcome, message: str) -> ResolutionEvent:
    return ResolutionEvent(field_name=field, stage=stage, outcome=outcome, message=message)


def _candidate_horizons(horizon: HistoricalHorizon) -> tuple[int, ...]:
    if horizon is HistoricalHorizon.LONGEST_AVAILABLE:
        return (5, 4, 3)
    return (int(horizon.value),)


def _failure_metric(code: ReasonCode, reason: str) -> MetricResult:
    return MetricResult.failure(MetricStatus.UNAVAILABLE, code, reason)


def _failure_assembly(  # noqa: PLR0913
    *,
    status: CalculationStatus,
    code: ReasonCode,
    reason: str,
    policy: FCFEarningsGrowthPolicy,
    common_count: int,
    longest_count: int,
    trace: ResolutionTrace,
) -> AnnualGrowthSeriesAssembly:
    selection = SeriesSelection(
        requested=policy.historical_horizon,
        candidate_elapsed_years=_candidate_horizons(policy.historical_horizon),
        selected_elapsed_years=None,
        fallback_applied=False,
        common_period_count=common_count,
        longest_contiguous_observation_count=longest_count,
    )
    metric = _failure_metric(code, reason)
    return AnnualGrowthSeriesAssembly(
        status=status,
        reason_code=code,
        reason=reason,
        observations=(),
        requested_horizon=policy.historical_horizon,
        selected_horizon_years=None,
        selected_observation_count=0,
        used_horizon_fallback=False,
        fcf_cagr=metric,
        fcf_per_share_cagr=metric,
        eps_cagr=metric,
        span_sign_change_fcf=False,
        span_sign_change_eps=False,
        selection=selection,
        resolution_trace=trace,
    )


def _fact_rejection(  # noqa: PLR0911
    fact: ProviderFact, field: FinancialField, subject_id: str, currency: str, as_of: datetime
) -> tuple[ReasonCode, str] | None:
    if fact.subject_kind is not FinancialSubjectKind.SECURITY or fact.subject_id != subject_id:
        return ReasonCode.MISSING_FACT, "The provider fact does not belong to the requested security."
    if fact.field_name is not field:
        return ReasonCode.MISSING_FACT, "The provider fact has the wrong semantic field."
    if fact.basis != "fiscal_year" or fact.period_kind is not PeriodKind.COMPLETED_ANNUAL:
        return ReasonCode.INCOMPATIBLE_PERIOD, "The fact is not a completed fiscal-year observation."
    if fact.fiscal_year is None or fact.observation_period_start is None or fact.observation_period_end is None:
        return ReasonCode.INCOMPATIBLE_PERIOD, "The annual fact is missing its fiscal-year label or period bounds."
    if fact.observation_period_start >= fact.observation_period_end:
        return ReasonCode.INCOMPATIBLE_PERIOD, "The annual fact has a non-positive reporting period."
    if fact.accounting_scope is not AccountingScope.CONSOLIDATED:
        return ReasonCode.INCOMPATIBLE_SCOPE, "The annual fact does not prove consolidated accounting scope."
    if fact.provider_fact_id is None:
        return ReasonCode.AMBIGUOUS_FACT, "The annual fact lacks a stable provider_fact_id."
    if fact.available_at is None or fact.available_at > as_of:
        return ReasonCode.NOT_AVAILABLE_AS_OF, "The annual fact was not publicly available at the analysis boundary."
    expected_units = (
        FinancialUnit.CURRENCY_PER_SHARE
        if field is FinancialField.EPS
        else FinancialUnit.SHARES
        if field is FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES
        else FinancialUnit.CURRENCY
    )
    if fact.units is not expected_units:
        return ReasonCode.INCOMPATIBLE_UNITS, "The annual fact has incompatible units."
    if field is not FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES and fact.currency != currency:
        return ReasonCode.INCOMPATIBLE_CURRENCY, "The annual fact has an incompatible or unknown currency."
    if field is FinancialField.CAPITAL_EXPENDITURES and fact.capital_expenditure_sign is None:
        return ReasonCode.AMBIGUOUS_FACT, "The capital-expenditure sign convention is missing."
    return None


def _normalized_value(fact: ProviderFact) -> tuple[float | None, str | None]:
    if fact.field_name is not FinancialField.CAPITAL_EXPENDITURES:
        return fact.value, None
    if fact.capital_expenditure_sign is CapitalExpenditureSign.POSITIVE_EXPENDITURE:
        if fact.value < 0:
            return None, "A positive-expenditure CapEx fact carried a negative value."
        return fact.value, f"Capital expenditure normalized from raw value {fact.value}."
    if fact.capital_expenditure_sign is CapitalExpenditureSign.NEGATIVE_CASH_OUTFLOW:
        if fact.value > 0:
            return None, "A negative-cash-outflow CapEx fact carried a positive value."
        return -fact.value, f"Capital expenditure normalized from raw value {fact.value}."
    return None, "The capital-expenditure sign convention is missing."


def _fact_identity(fact: ProviderFact) -> tuple[object, ...]:
    return (
        fact.field_name,
        fact.value,
        fact.units,
        fact.currency,
        fact.basis,
        fact.fiscal_year,
        fact.observation_period_start,
        fact.observation_period_end,
        fact.available_at,
        fact.accounting_scope,
        fact.capital_expenditure_sign,
    )


def _to_provider_input(
    fact: ProviderFact, value: float, resolved_at: datetime, as_of: datetime | None, note: str | None
) -> ResolvedInput:
    notes = fact.notes if note is None else (*fact.notes, note)
    return ResolvedInput(
        field_name=fact.field_name.value,
        value=value,
        source_kind=SourceKind.PROVIDER,
        resolved_at=resolved_at,
        basis=fact.basis,
        units=fact.units.value,
        currency=fact.currency,
        provider_id=fact.provider_id,
        provider_field=fact.provider_field,
        observation_period_start=fact.observation_period_start,
        observation_period_end=fact.observation_period_end,
        observed_at=fact.observed_at,
        available_at=fact.available_at,
        as_of=as_of,
        retrieved_at=fact.retrieved_at,
        notes=notes,
        fiscal_year=fact.fiscal_year,
        period_kind=fact.period_kind,
        accounting_scope=fact.accounting_scope,
        capital_expenditure_sign=fact.capital_expenditure_sign,
        provider_fact_id=fact.provider_fact_id,
    )


def _to_cache_input(stored: ResolvedInput, resolved_at: datetime) -> ResolvedInput:
    return ResolvedInput(
        field_name=stored.field_name,
        value=stored.value,
        source_kind=SourceKind.CACHE,
        resolved_at=resolved_at,
        origin_source_kind=stored.source_kind,
        basis=stored.basis,
        units=stored.units,
        currency=stored.currency,
        provider_id=stored.provider_id,
        provider_field=stored.provider_field,
        observation_period_start=stored.observation_period_start,
        observation_period_end=stored.observation_period_end,
        observed_at=stored.observed_at,
        available_at=stored.available_at,
        as_of=stored.as_of,
        retrieved_at=stored.retrieved_at,
        cache_schema_version=CACHE_SCHEMA_VERSION,
        lineage=stored.lineage,
        notes=stored.notes,
        fiscal_year=stored.fiscal_year,
        period_kind=stored.period_kind,
        accounting_scope=stored.accounting_scope,
        capital_expenditure_sign=stored.capital_expenditure_sign,
        provider_fact_id=stored.provider_fact_id,
    )


def _select_provider_facts(  # noqa: PLR0913, PLR0917
    facts: Sequence[ProviderFact],
    field: FinancialField,
    subject_id: str,
    currency: str,
    effective_as_of: datetime,
    requested_as_of: datetime | None,
    resolved_at: datetime,
) -> _FieldResolution:
    eligible: list[ProviderFact] = []
    rejections: list[tuple[ReasonCode, str]] = []
    identities: dict[str, tuple[object, ...]] = {}
    for fact in facts:
        rejection = _fact_rejection(fact, field, subject_id, currency, effective_as_of)
        if rejection is not None:
            rejections.append(rejection)
            continue
        assert fact.provider_fact_id is not None
        identity = _fact_identity(fact)
        previous = identities.get(fact.provider_fact_id)
        if previous is not None and previous != identity:
            return _FieldResolution(
                reason_code=ReasonCode.AMBIGUOUS_FACT,
                reason=f"provider_fact_id {fact.provider_fact_id!r} identifies contradictory facts.",
            )
        identities[fact.provider_fact_id] = identity
        eligible.append(fact)
    by_period: dict[tuple[datetime, datetime], list[ProviderFact]] = {}
    for fact in eligible:
        assert fact.observation_period_start is not None
        assert fact.observation_period_end is not None
        by_period.setdefault((fact.observation_period_start, fact.observation_period_end), []).append(fact)
    selected: list[ResolvedInput] = []
    for period in sorted(by_period, key=lambda item: (item[1], item[0])):
        candidates = by_period[period]
        fiscal_years = {fact.fiscal_year for fact in candidates}
        if len(fiscal_years) != 1:
            return _FieldResolution(
                reason_code=ReasonCode.AMBIGUOUS_FACT, reason="Facts for one period disagree on the fiscal-year label."
            )
        latest_time = max(fact.available_at for fact in candidates if fact.available_at is not None)
        latest = [fact for fact in candidates if fact.available_at == latest_time]
        normalized: list[tuple[ProviderFact, float, str | None]] = []
        for fact in latest:
            value, note = _normalized_value(fact)
            if value is None:
                return _FieldResolution(reason_code=ReasonCode.AMBIGUOUS_FACT, reason=note)
            normalized.append((fact, value, note))
        if len({item[1] for item in normalized}) != 1:
            return _FieldResolution(
                reason_code=ReasonCode.AMBIGUOUS_FACT,
                reason="Latest provider facts for one period have conflicting normalized values.",
            )
        chosen = min(
            normalized, key=lambda item: (item[0].provider_fact_id or "", item[0].provider_id, item[0].provider_field)
        )
        selected.append(_to_provider_input(chosen[0], chosen[1], resolved_at, requested_as_of, chosen[2]))
    if not selected:
        code, reason = (
            rejections[0] if rejections else (ReasonCode.MISSING_FACT, f"No usable {field.value} facts were returned.")
        )
        return _FieldResolution(reason_code=code, reason=reason)
    return _FieldResolution(inputs=tuple(selected))


def _longest_contiguous_count(inputs: Sequence[ResolvedInput]) -> int:
    if not inputs:
        return 0
    longest = current = 1
    for previous, following in zip(inputs, inputs[1:], strict=False):
        current = (
            current + 1
            if _periods_are_contiguous(previous.observation_period_end, following.observation_period_start)
            else 1
        )
        longest = max(longest, current)
    return longest


def _periods_are_contiguous(previous_end: datetime | None, following_start: datetime | None) -> bool:
    """Accept boundary-style intervals and SEC inclusive consecutive dates."""
    if previous_end is None or following_start is None:
        return False
    return previous_end == following_start or previous_end.date() + timedelta(days=1) == following_start.date()


def _resolve_field(  # noqa: PLR0913
    *,
    field: FinancialField,
    binding: FinancialFieldProvider,
    subject_id: str,
    currency: str,
    effective_as_of: datetime,
    requested_as_of: datetime | None,
    required_count: int,
    cache: ResolvedInputSeriesCacheProtocol | None,
    use_cache: bool,
    resolved_at: datetime,
) -> tuple[_FieldResolution, ResolutionTrace]:
    trace = ResolutionTrace()
    if use_cache and cache is not None:
        query = ResolvedInputSeriesCacheQuery(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id=subject_id,
            field_name=field.value,
            basis="fiscal_year",
            provider_id=binding.provider_id,
            analysis_as_of=requested_as_of,
            schema_version=CACHE_SCHEMA_VERSION,
        )
        entries = cache.get_series(query)
        cached = tuple(_to_cache_input(entry.resolved_input, resolved_at) for entry in entries)
        if len(cached) >= required_count and _longest_contiguous_count(cached) >= required_count:
            return _FieldResolution(inputs=cached), trace.append(
                _event(
                    field.value,
                    ResolutionStage.CACHE,
                    ResolutionOutcome.HIT,
                    "Complete annual field series resolved from cache.",
                )
            )
        trace = trace.append(
            _event(
                field.value,
                ResolutionStage.CACHE,
                ResolutionOutcome.MISS,
                "Annual field cache was absent, stale, or incomplete; refreshing the complete field.",
            )
        )
    request = FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id=subject_id,
        field_name=field,
        provider_id=binding.provider_id,
        basis="fiscal_year",
        as_of=requested_as_of,
        observation_count=required_count,
    )
    try:
        facts = binding.provider.fetch_facts(request)
    except FinancialProviderError as exc:
        reason = f"{field.value} provider failed: {exc}"
        return _FieldResolution(
            reason_code=ReasonCode.PROVIDER_ERROR, reason=reason, provider_error=True
        ), trace.append(_event(field.value, ResolutionStage.PROVIDER, ResolutionOutcome.ERROR, reason))
    resolution = _select_provider_facts(
        facts, field, subject_id, currency, effective_as_of, requested_as_of, resolved_at
    )
    if resolution.reason_code is not None:
        return resolution, trace.append(
            _event(
                field.value,
                ResolutionStage.PROVIDER,
                ResolutionOutcome.REJECTED,
                resolution.reason or "Provider facts were rejected.",
            )
        )
    if use_cache and cache is not None:
        for resolved in resolution.inputs:
            assert resolved.observation_period_start is not None
            assert resolved.observation_period_end is not None
            cache.put(
                ResolvedInputCacheKey(
                    subject_kind=FinancialSubjectKind.SECURITY,
                    subject_id=subject_id,
                    field_name=field.value,
                    basis="fiscal_year",
                    provider_id=binding.provider_id,
                    analysis_as_of=requested_as_of,
                    schema_version=CACHE_SCHEMA_VERSION,
                    observation_period_start=resolved.observation_period_start,
                    observation_period_end=resolved.observation_period_end,
                ),
                resolved,
            )
    return resolution, trace.append(
        _event(
            field.value,
            ResolutionStage.PROVIDER,
            ResolutionOutcome.SUCCESS,
            "Annual field series resolved from provider.",
        )
    )


def _assemble_common(
    field_inputs: Mapping[FinancialField, tuple[ResolvedInput, ...]],
    resolved_at: datetime,
    requested_as_of: datetime | None,
) -> tuple[tuple[AnnualGrowthObservation, ...], ReasonCode | None, str | None]:
    indexed = {
        field: {(item.observation_period_start, item.observation_period_end): item for item in inputs}
        for field, inputs in field_inputs.items()
    }
    periods = set.intersection(*(set(indexed[field]) for field in _REQUIRED_ANNUAL_FIELDS))
    observations: list[AnnualGrowthObservation] = []
    for period in sorted(periods, key=lambda item: (item[1], item[0])):
        ocf = indexed[FinancialField.OPERATING_CASH_FLOW][period]
        capex = indexed[FinancialField.CAPITAL_EXPENDITURES][period]
        eps = indexed[FinancialField.EPS][period]
        diluted_shares = indexed.get(FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES, {}).get(period)
        if (
            diluted_shares is not None
            and diluted_shares.provider_id == SEC_PROVIDER_ID
            and eps.provider_id == SEC_PROVIDER_ID
            and diluted_shares.provider_fact_id is not None
            and eps.provider_fact_id is not None
            and diluted_shares.provider_fact_id.split(":", maxsplit=1)[0]
            != eps.provider_fact_id.split(":", maxsplit=1)[0]
        ):
            diluted_shares = None
        period_start, period_end = period
        assert period_start is not None
        assert period_end is not None
        if len({ocf.fiscal_year, capex.fiscal_year, eps.fiscal_year}) != 1 or ocf.fiscal_year is None:
            return (), ReasonCode.AMBIGUOUS_FACT, "Aligned facts disagree on their fiscal-year label."
        if ocf.currency != capex.currency:
            return (), ReasonCode.INCOMPATIBLE_CURRENCY, "Aligned cash-flow facts have incompatible currencies."
        metric = compute_free_cash_flow(ocf.value, capex.value)
        if metric.status is not MetricStatus.OK or metric.value is None:
            return (
                (),
                metric.reason_code or ReasonCode.INVALID_REQUEST,
                metric.reason or "Free cash flow could not be derived.",
            )
        available = max(item.available_at for item in (ocf, capex) if item.available_at is not None)
        retrieved = max(item.retrieved_at for item in (ocf, capex) if item.retrieved_at is not None)
        fcf = ResolvedInput(
            field_name="free_cash_flow",
            value=metric.value,
            source_kind=SourceKind.DERIVED,
            resolved_at=resolved_at,
            basis="fiscal_year",
            units=FinancialUnit.CURRENCY.value,
            currency=ocf.currency,
            observation_period_start=period[0],
            observation_period_end=period[1],
            available_at=available,
            as_of=requested_as_of,
            retrieved_at=retrieved,
            lineage=ComponentLineage(
                transformation="operating_cash_flow - normalized_capital_expenditures",
                components=(ocf, capex),
            ),
            fiscal_year=ocf.fiscal_year,
            period_kind=PeriodKind.COMPLETED_ANNUAL,
            accounting_scope=AccountingScope.CONSOLIDATED,
        )
        fcf_per_share: ResolvedInput | None = None
        if diluted_shares is not None:
            per_share_metric = compute_fcf_per_diluted_share(fcf.value, diluted_shares.value)
            if per_share_metric.status is MetricStatus.OK and per_share_metric.value is not None:
                share_available = diluted_shares.available_at
                share_retrieved = diluted_shares.retrieved_at
                fcf_per_share = ResolvedInput(
                    field_name="free_cash_flow_per_diluted_share",
                    value=per_share_metric.value,
                    source_kind=SourceKind.DERIVED,
                    resolved_at=resolved_at,
                    basis="fiscal_year",
                    units=FinancialUnit.CURRENCY_PER_SHARE.value,
                    currency=ocf.currency,
                    observation_period_start=period[0],
                    observation_period_end=period[1],
                    available_at=max(available, share_available) if share_available is not None else available,
                    as_of=requested_as_of,
                    retrieved_at=max(retrieved, share_retrieved) if share_retrieved is not None else retrieved,
                    lineage=ComponentLineage(
                        transformation="free_cash_flow / weighted_average_diluted_shares",
                        components=(fcf, diluted_shares),
                    ),
                    fiscal_year=ocf.fiscal_year,
                    period_kind=PeriodKind.COMPLETED_ANNUAL,
                    accounting_scope=AccountingScope.CONSOLIDATED,
                )
        observations.append(
            AnnualGrowthObservation(
                fiscal_year=ocf.fiscal_year,
                period_start=period_start,
                period_end=period_end,
                operating_cash_flow=ocf,
                normalized_capital_expenditures=capex,
                free_cash_flow=fcf,
                diluted_eps=eps,
                weighted_average_diluted_shares=diluted_shares if fcf_per_share is not None else None,
                free_cash_flow_per_diluted_share=fcf_per_share,
            )
        )
    return tuple(observations), None, None


def _has_span_sign_change(values: Sequence[float]) -> bool:
    return any(value == 0 for value in values) or any(
        left * right < 0 for left, right in zip(values, values[1:], strict=False)
    )


def resolve_annual_growth_series(  # noqa: PLR0911, PLR0912, PLR0913, PLR0915, PLR0917
    *,
    policy: FCFEarningsGrowthPolicy,
    subject_id: str,
    currency: str,
    as_of: datetime | None,
    providers: Mapping[FinancialField, FinancialFieldProvider],
    cache: ResolvedInputSeriesCacheProtocol | None = None,
    use_cache: bool = True,
    clock: Callable[[], datetime] | None = None,
) -> AnnualGrowthSeriesAssembly:
    """Resolve, align, derive, and select annual FCF/EPS history."""
    now = (clock or (lambda: datetime.now(UTC)))()
    if now.tzinfo is None or now.utcoffset() is None:
        return _failure_assembly(
            status=CalculationStatus.INVALID_INPUT,
            code=ReasonCode.INVALID_REQUEST,
            reason="clock must return a timezone-aware datetime.",
            policy=policy,
            common_count=0,
            longest_count=0,
            trace=ResolutionTrace(),
        )
    if as_of is not None and (as_of.tzinfo is None or as_of.utcoffset() is None):
        return _failure_assembly(
            status=CalculationStatus.INVALID_INPUT,
            code=ReasonCode.INVALID_REQUEST,
            reason="as_of must be timezone-aware.",
            policy=policy,
            common_count=0,
            longest_count=0,
            trace=ResolutionTrace(),
        )
    normalized_subject = subject_id.strip().upper()
    normalized_currency = currency.strip().upper()
    missing_required_provider = any(field not in providers for field in _REQUIRED_ANNUAL_FIELDS)
    missing_selected_share_provider = (
        policy.classification_basis is FCFClassificationBasis.FCF_PER_SHARE
        and FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES not in providers
    )
    if (
        not normalized_subject
        or not normalized_currency
        or missing_required_provider
        or missing_selected_share_provider
    ):
        return _failure_assembly(
            status=CalculationStatus.INVALID_INPUT,
            code=ReasonCode.INVALID_REQUEST,
            reason="subject_id, currency, and providers for OCF, CapEx, and EPS are required.",
            policy=policy,
            common_count=0,
            longest_count=0,
            trace=ResolutionTrace(),
        )
    effective_as_of = as_of or now
    candidates = _candidate_horizons(policy.historical_horizon)
    required_count = max(candidates) + 1
    trace = ResolutionTrace()
    resolved_fields: dict[FinancialField, tuple[ResolvedInput, ...]] = {}
    for field in _ANNUAL_FIELDS:
        if field not in providers:
            resolved_fields[field] = ()
            continue
        resolution, field_trace = _resolve_field(
            field=field,
            binding=providers[field],
            subject_id=normalized_subject,
            currency=normalized_currency,
            effective_as_of=effective_as_of,
            requested_as_of=as_of,
            required_count=required_count,
            cache=cache,
            use_cache=use_cache,
            resolved_at=now,
        )
        trace = trace.extend(field_trace)
        if resolution.reason_code is not None:
            if (
                field is FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES
                and policy.classification_basis is FCFClassificationBasis.TOTAL_FCF
            ):
                resolved_fields[field] = ()
                continue
            status = (
                CalculationStatus.PROVIDER_ERROR if resolution.provider_error else CalculationStatus.INPUT_UNAVAILABLE
            )
            return _failure_assembly(
                status=status,
                code=resolution.reason_code,
                reason=resolution.reason or "Annual field resolution failed.",
                policy=policy,
                common_count=0,
                longest_count=0,
                trace=trace,
            )
        resolved_fields[field] = resolution.inputs
    common, code, reason = _assemble_common(resolved_fields, now, as_of)
    if code is not None:
        return _failure_assembly(
            status=CalculationStatus.INPUT_UNAVAILABLE,
            code=code,
            reason=reason or "Annual observations could not be assembled.",
            policy=policy,
            common_count=0,
            longest_count=0,
            trace=trace,
        )
    if policy.classification_basis is FCFClassificationBasis.FCF_PER_SHARE and any(
        item.free_cash_flow_per_diluted_share is None for item in common
    ):
        return _failure_assembly(
            status=CalculationStatus.INPUT_UNAVAILABLE,
            code=ReasonCode.INCOMPATIBLE_SCOPE,
            reason="Compatible same-accession diluted-share evidence is unavailable for every annual period.",
            policy=policy,
            common_count=len(common),
            longest_count=_longest_contiguous_count(tuple(item.free_cash_flow for item in common)),
            trace=trace,
        )
    longest_count = _longest_contiguous_count(tuple(item.free_cash_flow for item in common))
    selected: tuple[AnnualGrowthObservation, ...] = ()
    selected_years: int | None = None
    for elapsed in candidates:
        if len(common) < elapsed + 1:
            continue
        candidate = common[-(elapsed + 1) :]
        if all(
            _periods_are_contiguous(left.period_end, right.period_start)
            for left, right in zip(candidate, candidate[1:], strict=False)
        ):
            selected = candidate
            selected_years = elapsed
            break
    if selected_years is None:
        too_few_contiguous_observations = len(common) < min(candidates) + 1 and longest_count == len(common)
        code = ReasonCode.INSUFFICIENT_HISTORY if too_few_contiguous_observations else ReasonCode.NON_CONTIGUOUS_HISTORY
        reason = (
            "Insufficient common annual history."
            if code is ReasonCode.INSUFFICIENT_HISTORY
            else "The most recent common annual history is not contiguous."
        )
        return _failure_assembly(
            status=CalculationStatus.INPUT_UNAVAILABLE,
            code=code,
            reason=reason,
            policy=policy,
            common_count=len(common),
            longest_count=longest_count,
            trace=trace,
        )
    fcf_values = [item.free_cash_flow.value for item in selected]
    eps_values = [item.diluted_eps.value for item in selected]
    fcf_per_share_values = [
        item.free_cash_flow_per_diluted_share.value
        for item in selected
        if item.free_cash_flow_per_diluted_share is not None
    ]
    fcf_sign = _has_span_sign_change(fcf_values)
    eps_sign = _has_span_sign_change(eps_values)
    fcf_cagr = (
        _failure_metric(ReasonCode.SIGN_CHANGE, "Free cash flow changes sign or reaches zero within the selected span.")
        if fcf_sign
        else compute_cagr(fcf_values[0], fcf_values[-1], selected_years)
    )
    eps_cagr = (
        _failure_metric(ReasonCode.SIGN_CHANGE, "Diluted EPS changes sign or reaches zero within the selected span.")
        if eps_sign
        else compute_cagr(eps_values[0], eps_values[-1], selected_years)
    )
    if len(fcf_per_share_values) != len(selected):
        fcf_per_share_cagr = _failure_metric(ReasonCode.MISSING_FACT, "FCF/share evidence is unavailable.")
    elif _has_span_sign_change(fcf_per_share_values):
        fcf_per_share_cagr = _failure_metric(
            ReasonCode.SIGN_CHANGE, "FCF/share changes sign or reaches zero within the selected span."
        )
    else:
        fcf_per_share_cagr = compute_cagr(fcf_per_share_values[0], fcf_per_share_values[-1], selected_years)
    fallback = policy.historical_horizon is HistoricalHorizon.LONGEST_AVAILABLE and selected_years < 5
    selection = SeriesSelection(
        requested=policy.historical_horizon,
        candidate_elapsed_years=candidates,
        selected_elapsed_years=selected_years,
        fallback_applied=fallback,
        common_period_count=len(common),
        longest_contiguous_observation_count=longest_count,
    )
    return AnnualGrowthSeriesAssembly(
        status=CalculationStatus.OK,
        reason_code=None,
        reason=None,
        observations=selected,
        requested_horizon=policy.historical_horizon,
        selected_horizon_years=selected_years,
        selected_observation_count=len(selected),
        used_horizon_fallback=fallback,
        fcf_cagr=fcf_cagr,
        fcf_per_share_cagr=fcf_per_share_cagr,
        eps_cagr=eps_cagr,
        span_sign_change_fcf=fcf_sign,
        span_sign_change_eps=eps_sign,
        selection=selection,
        resolution_trace=trace.append(
            _event(
                "annual_growth_series",
                ResolutionStage.DERIVATION,
                ResolutionOutcome.SUCCESS,
                "Aligned annual observations and calculated the selected-span growth metrics.",
            )
        ),
    )
