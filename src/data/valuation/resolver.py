"""Provider-neutral valuation input resolution with provenance and temporal integrity."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.core.analysis_status import CalculationStatus
from src.data.valuation.cache import ValuationCacheKey, ValuationCacheProtocol
from src.data.valuation.facts import (
    ProviderFact,
    ValuationFactRequest,
    ValuationFactsProvider,
    ValuationField,
    ValuationProviderError,
    ValuationUnit,
)
from src.data.valuation.provenance import (
    ComponentLineage,
    ResolvedInput,
    SourceKind,
)
from src.data.valuation.resolution_trace import (
    ResolutionEvent,
    ResolutionOutcome,
    ResolutionStage,
    ResolutionTrace,
)

# ---------------------------------------------------------------------------
# InputResolutionResult
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InputResolutionResult:
    """Outcome of a single-fact input resolution.

    Invariants:
        - ``OK`` requires ``resolved_input`` present and ``reason`` is ``None``.
        - ``INVALID_INPUT``, ``INPUT_UNAVAILABLE``, ``PROVIDER_ERROR`` require
          ``resolved_input`` is ``None`` and a non-empty ``reason``.
        - ``NOT_APPLICABLE`` is calculator-level semantics and is rejected here.

    Attributes:
        status: The resolution outcome.
        resolved_input: Present only when status is ``OK``.
        reason: Non-empty explanation when status is not ``OK``.
        resolution_trace: Ordered resolver events actually observed for this resolution.
    """

    status: CalculationStatus
    resolved_input: ResolvedInput | None = None
    reason: str | None = None
    resolution_trace: ResolutionTrace = field(default_factory=ResolutionTrace, compare=False)

    def __post_init__(self) -> None:
        """Enforce status/value invariants."""
        if self.status is CalculationStatus.NOT_APPLICABLE:
            msg = "InputResolutionResult does not permit CalculationStatus.NOT_APPLICABLE."
            raise ValueError(msg)
        if self.status is CalculationStatus.OK:
            if self.resolved_input is None:
                msg = "InputResolutionResult: status OK requires resolved_input to be present."
                raise ValueError(msg)
            if self.reason is not None:
                msg = "InputResolutionResult: status OK requires reason to be None."
                raise ValueError(msg)
        else:
            if self.resolved_input is not None:
                msg = f"InputResolutionResult: status {self.status} requires resolved_input to be None."
                raise ValueError(msg)
            if not self.reason:
                msg = f"InputResolutionResult: status {self.status} requires a non-empty reason."
                raise ValueError(msg)


# ---------------------------------------------------------------------------
# InputResolver
# ---------------------------------------------------------------------------


class InputResolver:
    """Resolves a single valuation fact through override, cache, or provider.

    Precedence for one field:
        1. Explicit override (short-circuits cache and provider).
        2. Valid cache entry (relabelled as CACHE source).
        3. Configured provider (validated, then optionally cached).
        4. Explicit unavailable / provider-error outcome.

    Args:
        provider: The configured ``ValuationFactsProvider``.
        cache: Optional valuation cache implementation.
        clock: Zero-argument callable returning a timezone-aware datetime.
            Defaults to ``datetime.now(UTC)``.
        cache_schema_version: Positive integer schema version for cache keys.
    """

    _DEFAULT_CLOCK: Callable[[], datetime] = staticmethod(lambda: datetime.now(UTC))

    def __init__(
        self,
        provider: ValuationFactsProvider,
        cache: ValuationCacheProtocol | None = None,
        clock: Callable[[], datetime] | None = None,
        cache_schema_version: int = 1,
    ) -> None:
        """Create an ``InputResolver``.

        Args:
            provider: The configured ``ValuationFactsProvider``.
            cache: Optional valuation cache.
            clock: Clock callable returning a timezone-aware datetime.
            cache_schema_version: Positive integer schema version for cache keys.

        Raises:
            ValueError: If ``cache_schema_version`` is less than 1.
        """
        if cache_schema_version < 1:
            msg = f"cache_schema_version must be >= 1 (received {cache_schema_version})."
            raise ValueError(msg)
        self._provider = provider
        self._cache = cache
        self._clock: Callable[[], datetime] = clock if clock is not None else self._DEFAULT_CLOCK
        self._schema_version = cache_schema_version

    def resolve(
        self,
        request: ValuationFactRequest,
        *,
        override: float | None = None,
        use_cache: bool = True,
    ) -> InputResolutionResult:
        """Resolve a single valuation fact and retain the path actually taken."""
        field_name = request.field_name.value

        # 0. Single-observation contract.
        if request.observation_count != 1:
            reason = f"This single-fact resolver requires observation_count=1 (received {request.observation_count})."
            return InputResolutionResult(
                status=CalculationStatus.INVALID_INPUT,
                reason=reason,
                resolution_trace=_trace_event(
                    field_name,
                    ResolutionStage.VALIDATION,
                    ResolutionOutcome.INVALID,
                    reason,
                ),
            )

        # 1. Explicit override — no cache, no provider.
        if override is not None:
            return self._resolve_override(request, override)

        trace = _trace_event(
            field_name,
            ResolutionStage.OVERRIDE,
            ResolutionOutcome.NOT_USED,
            "No explicit override was supplied.",
        )

        # 2. Cache lookup.
        if not use_cache:
            trace = trace.append(
                _event(
                    field_name,
                    ResolutionStage.CACHE,
                    ResolutionOutcome.NOT_USED,
                    "Cache use was disabled for this resolution.",
                )
            )
        elif self._cache is None:
            trace = trace.append(
                _event(
                    field_name,
                    ResolutionStage.CACHE,
                    ResolutionOutcome.NOT_USED,
                    "No valuation cache is configured.",
                )
            )
        else:
            key = self._build_cache_key(request)
            entry = self._cache.get(key)
            if entry is None:
                trace = trace.append(
                    _event(
                        field_name,
                        ResolutionStage.CACHE,
                        ResolutionOutcome.MISS,
                        (
                            "Cache returned no usable entry; its get() contract does not "
                            "distinguish absent, stale, or temporally ineligible entries."
                        ),
                    )
                )
            else:
                ri = self._try_cache_hit(request, entry.resolved_input, key)
                if ri is not None:
                    return InputResolutionResult(
                        status=CalculationStatus.OK,
                        resolved_input=ri,
                        resolution_trace=trace.append(
                            _event(
                                field_name,
                                ResolutionStage.CACHE,
                                ResolutionOutcome.HIT,
                                "Cache entry passed resolver temporal checks and was accepted.",
                            )
                        ),
                    )
                trace = trace.append(
                    _event(
                        field_name,
                        ResolutionStage.CACHE,
                        ResolutionOutcome.REJECTED,
                        "Cache returned an entry that failed resolver temporal eligibility.",
                    )
                )

        # 3. Provider fallback.
        return _prepend_trace(self._resolve_provider(request, use_cache), trace)

    def resolve_bvps(
        self,
        request: ValuationFactRequest,
        *,
        override: float | None = None,
        use_cache: bool = True,
    ) -> InputResolutionResult:
        """Resolve direct BVPS first, then conservatively derive it from SEC-style components.

        The derived path requires parent stockholders' equity, period-end common
        shares outstanding, and same-period zero preferred-share evidence. The
        resolver itself never interprets missing preferred-share data as zero.
        """
        if request.field_name is not ValuationField.BVPS:
            reason = f"resolve_bvps requires a BVPS request (received {request.field_name.value})."
            return InputResolutionResult(
                status=CalculationStatus.INVALID_INPUT,
                reason=reason,
                resolution_trace=_trace_event(
                    request.field_name.value,
                    ResolutionStage.VALIDATION,
                    ResolutionOutcome.INVALID,
                    reason,
                ),
            )

        direct = self.resolve(request, override=override, use_cache=use_cache)
        if direct.status is not CalculationStatus.INPUT_UNAVAILABLE or override is not None:
            return direct
        if request.basis is not None:
            return direct

        derived = self._derive_bvps_from_components(request, use_cache=use_cache)
        return _prepend_trace(derived, direct.resolution_trace)

    def resolve_three_year_average_eps(  # noqa: PLR0911, PLR0912, PLR0915
        self,
        request: ValuationFactRequest,
        *,
        use_cache: bool = True,
    ) -> InputResolutionResult:
        """Resolve the three-year average EPS.

        The financial selection/composition behavior is unchanged; this method
        additionally retains the cache/provider/derivation path actually taken.
        """
        field_name = ValuationField.EPS.value

        # --- 1. Request validation (before any cache/provider work) ---
        if request.field_name is not ValuationField.EPS:
            reason = f"resolve_three_year_average_eps requires field_name=EPS (received {request.field_name.name})."
            return InputResolutionResult(
                status=CalculationStatus.INVALID_INPUT,
                reason=reason,
                resolution_trace=_trace_event(
                    field_name,
                    ResolutionStage.VALIDATION,
                    ResolutionOutcome.INVALID,
                    reason,
                ),
            )
        if request.observation_count != 3:
            reason = (
                f"resolve_three_year_average_eps requires observation_count=3 (received {request.observation_count})."
            )
            return InputResolutionResult(
                status=CalculationStatus.INVALID_INPUT,
                reason=reason,
                resolution_trace=_trace_event(
                    field_name,
                    ResolutionStage.VALIDATION,
                    ResolutionOutcome.INVALID,
                    reason,
                ),
            )
        if request.basis != "fiscal_year":
            reason = f'resolve_three_year_average_eps requires basis="fiscal_year" (received {request.basis!r}).'
            return InputResolutionResult(
                status=CalculationStatus.INVALID_INPUT,
                reason=reason,
                resolution_trace=_trace_event(
                    field_name,
                    ResolutionStage.VALIDATION,
                    ResolutionOutcome.INVALID,
                    reason,
                ),
            )

        trace = _trace_event(
            field_name,
            ResolutionStage.OVERRIDE,
            ResolutionOutcome.NOT_USED,
            "No explicit EPS override was supplied.",
        )

        # --- 2. Derived cache lookup ---
        if not use_cache:
            trace = trace.append(
                _event(
                    field_name,
                    ResolutionStage.CACHE,
                    ResolutionOutcome.NOT_USED,
                    "Cache use was disabled for the derived EPS resolution.",
                )
            )
        elif self._cache is None:
            trace = trace.append(
                _event(
                    field_name,
                    ResolutionStage.CACHE,
                    ResolutionOutcome.NOT_USED,
                    "No valuation cache is configured.",
                )
            )
        else:
            key = self._build_derived_cache_key(request)
            entry = self._cache.get(key)
            if entry is None:
                trace = trace.append(
                    _event(
                        field_name,
                        ResolutionStage.CACHE,
                        ResolutionOutcome.MISS,
                        (
                            "Cache returned no usable derived EPS entry; its get() "
                            "contract does not distinguish absent, stale, or "
                            "temporally ineligible entries."
                        ),
                    )
                )
            else:
                ri = self._try_derived_cache_hit(entry.resolved_input, key)
                if ri is not None:
                    return InputResolutionResult(
                        status=CalculationStatus.OK,
                        resolved_input=ri,
                        resolution_trace=trace.append(
                            _event(
                                field_name,
                                ResolutionStage.CACHE,
                                ResolutionOutcome.HIT,
                                "Derived EPS cache entry passed eligibility checks and was accepted.",
                            )
                        ),
                    )
                trace = trace.append(
                    _event(
                        field_name,
                        ResolutionStage.CACHE,
                        ResolutionOutcome.REJECTED,
                        "Derived EPS cache entry failed resolver eligibility checks.",
                    )
                )

        # --- 3. Provider call (exactly once) ---
        trace = trace.append(
            _event(
                field_name,
                ResolutionStage.PROVIDER,
                ResolutionOutcome.ATTEMPTED,
                "Requested completed fiscal-year EPS observations from the configured provider.",
            )
        )
        try:
            facts = self._provider.fetch_facts(request)
        except ValuationProviderError as exc:
            reason = f"Provider error: {exc}"
            return InputResolutionResult(
                status=CalculationStatus.PROVIDER_ERROR,
                reason=reason,
                resolution_trace=trace.append(
                    _event(
                        field_name,
                        ResolutionStage.PROVIDER,
                        ResolutionOutcome.ERROR,
                        reason,
                    )
                ),
            )

        trace = trace.append(
            _event(
                field_name,
                ResolutionStage.PROVIDER,
                ResolutionOutcome.SUCCESS,
                f"Provider returned {len(facts)} fiscal-year EPS candidate(s).",
            )
        )

        # --- 4. Validate every candidate ---
        for fact in facts:
            err = self._validate_candidate(fact, request)
            if err is not None:
                return InputResolutionResult(
                    status=CalculationStatus.PROVIDER_ERROR,
                    reason=err,
                    resolution_trace=trace.append(
                        _event(
                            field_name,
                            ResolutionStage.PROVIDER,
                            ResolutionOutcome.REJECTED,
                            f"Rejected provider candidate before composition: {err}",
                        )
                    ),
                )

        # --- 5. Temporal eligibility (capture one clock value) ---
        resolver_now = self._clock()
        eligible: list[ProviderFact] = []
        for fact in facts:
            if self._is_temporally_eligible(fact, request, resolver_now):
                eligible.append(fact)

        trace = trace.append(
            _event(
                field_name,
                ResolutionStage.DERIVATION,
                ResolutionOutcome.ATTEMPTED,
                "Selecting three compatible, temporally eligible fiscal-year EPS observations.",
            )
        )

        # --- 6. Selection ---
        by_period_end: dict[datetime, list[ProviderFact]] = {}
        for fact in eligible:
            assert fact.observation_period_end is not None
            by_period_end.setdefault(fact.observation_period_end, []).append(fact)

        sorted_ends = sorted(by_period_end.keys(), reverse=True)

        if len(sorted_ends) < 3:
            reason = (
                "Insufficient eligible fiscal-year EPS observations: "
                f"found {len(sorted_ends)} distinct period(s), need 3."
            )
            return InputResolutionResult(
                status=CalculationStatus.INPUT_UNAVAILABLE,
                reason=reason,
                resolution_trace=trace.append(
                    _event(
                        field_name,
                        ResolutionStage.DERIVATION,
                        ResolutionOutcome.UNAVAILABLE,
                        reason,
                    )
                ),
            )

        selected_ends = sorted_ends[:3]

        for end in selected_ends:
            if len(by_period_end[end]) > 1:
                reason = (
                    f"Ambiguous: {len(by_period_end[end])} candidates share "
                    f"observation_period_end={end.isoformat()} in a selected period."
                )
                return InputResolutionResult(
                    status=CalculationStatus.PROVIDER_ERROR,
                    reason=reason,
                    resolution_trace=trace.append(
                        _event(
                            field_name,
                            ResolutionStage.DERIVATION,
                            ResolutionOutcome.ERROR,
                            reason,
                        )
                    ),
                )

        selected_facts = [by_period_end[end][0] for end in selected_ends]

        # --- 7. Selected-series compatibility ---
        common_provider_field = selected_facts[0].provider_field
        common_units = selected_facts[0].units
        common_currency = selected_facts[0].currency
        common_basis = selected_facts[0].basis
        for fact in selected_facts[1:]:
            if fact.provider_field != common_provider_field:
                reason = f"Incompatible provider_field: {fact.provider_field!r} != {common_provider_field!r}."
                return InputResolutionResult(
                    status=CalculationStatus.PROVIDER_ERROR,
                    reason=reason,
                    resolution_trace=_derivation_error_trace(trace, field_name, reason),
                )
            if fact.units is not common_units:
                reason = f"Incompatible units: {fact.units.name} != {common_units.name}."
                return InputResolutionResult(
                    status=CalculationStatus.PROVIDER_ERROR,
                    reason=reason,
                    resolution_trace=_derivation_error_trace(trace, field_name, reason),
                )
            if fact.currency != common_currency:
                reason = f"Incompatible currency: {fact.currency!r} != {common_currency!r}."
                return InputResolutionResult(
                    status=CalculationStatus.PROVIDER_ERROR,
                    reason=reason,
                    resolution_trace=_derivation_error_trace(trace, field_name, reason),
                )
            if fact.basis != common_basis:
                reason = f"Incompatible basis: {fact.basis!r} != {common_basis!r}."
                return InputResolutionResult(
                    status=CalculationStatus.PROVIDER_ERROR,
                    reason=reason,
                    resolution_trace=_derivation_error_trace(trace, field_name, reason),
                )

        # --- 8. Composition ---
        def _end_key(f: ProviderFact) -> datetime:
            assert f.observation_period_end is not None
            return f.observation_period_end

        selected_facts_sorted = sorted(selected_facts, key=_end_key)

        resolved_at = resolver_now
        components: list[ResolvedInput] = []
        for fact in selected_facts_sorted:
            comp = ResolvedInput(
                field_name="eps",
                value=fact.value,
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
                as_of=request.as_of,
                retrieved_at=fact.retrieved_at,
                notes=fact.notes,
            )
            components.append(comp)

        values = [f.value for f in selected_facts_sorted]
        mean_value = sum(values) / 3.0

        oldest = components[0]
        newest = components[-1]
        available_ats = [c.available_at for c in components if c.available_at is not None]
        derived_available_at = max(available_ats) if len(available_ats) == len(components) else None
        retrieved_ats = [c.retrieved_at for c in components if c.retrieved_at is not None]
        derived_retrieved_at = max(retrieved_ats) if retrieved_ats else resolver_now

        lineage = ComponentLineage(
            transformation="arithmetic_mean",
            components=tuple(components),
        )

        derived_ri = ResolvedInput(
            field_name="eps",
            value=mean_value,
            source_kind=SourceKind.DERIVED,
            resolved_at=resolved_at,
            basis="three_year_average",
            units=common_units.value,
            currency=common_currency,
            provider_id=request.provider_id,
            observation_period_start=oldest.observation_period_start,
            observation_period_end=newest.observation_period_end,
            observed_at=None,
            available_at=derived_available_at,
            as_of=request.as_of,
            retrieved_at=derived_retrieved_at,
            lineage=lineage,
        )

        # --- 9. Cache the DERIVED result ---
        if use_cache and self._cache is not None:
            key = self._build_derived_cache_key(request)
            self._cache.put(key, derived_ri)

        return InputResolutionResult(
            status=CalculationStatus.OK,
            resolved_input=derived_ri,
            resolution_trace=trace.append(
                _event(
                    field_name,
                    ResolutionStage.DERIVATION,
                    ResolutionOutcome.SUCCESS,
                    "Derived three-year-average EPS from three compatible fiscal-year observations.",
                )
            ),
        )

    def _derive_bvps_from_components(  # noqa: PLR0911
        self,
        request: ValuationFactRequest,
        *,
        use_cache: bool,
    ) -> InputResolutionResult:
        trace = _trace_event(
            ValuationField.BVPS.value,
            ResolutionStage.DERIVATION,
            ResolutionOutcome.ATTEMPTED,
            "Direct BVPS was unavailable; attempting conservative component derivation.",
        )

        equity_result = self.resolve(
            _bvps_component_request(request, ValuationField.STOCKHOLDERS_EQUITY),
            use_cache=use_cache,
        )
        trace = trace.extend(equity_result.resolution_trace)
        if equity_result.status is not CalculationStatus.OK:
            return _bvps_component_failure("stockholders_equity", equity_result, trace)
        equity = equity_result.resolved_input
        assert equity is not None

        shares_result = self.resolve(
            _bvps_component_request(request, ValuationField.COMMON_SHARES_OUTSTANDING),
            use_cache=use_cache,
        )
        trace = trace.extend(shares_result.resolution_trace)
        if shares_result.status is not CalculationStatus.OK:
            return _bvps_component_failure("common_shares_outstanding", shares_result, trace)
        shares = shares_result.resolved_input
        assert shares is not None

        preferred_result = self.resolve(
            _bvps_component_request(request, ValuationField.PREFERRED_SHARES_OUTSTANDING),
            use_cache=use_cache,
        )
        trace = trace.extend(preferred_result.resolution_trace)
        if preferred_result.status is not CalculationStatus.OK:
            return _bvps_component_failure("preferred_shares_outstanding", preferred_result, trace)
        preferred = preferred_result.resolved_input
        assert preferred is not None

        alignment_error = _bvps_component_alignment_error(equity, preferred, shares)
        if alignment_error is not None:
            return InputResolutionResult(
                status=CalculationStatus.INPUT_UNAVAILABLE,
                reason=alignment_error,
                resolution_trace=_derivation_outcome_trace(
                    trace,
                    ValuationField.BVPS.value,
                    ResolutionOutcome.UNAVAILABLE,
                    alignment_error,
                ),
            )
        if preferred.value > 0:
            reason = (
                "BVPS unavailable: stockholders_equity cannot be treated as common shareholders' equity "
                "because same-period preferred_shares_outstanding is non-zero."
            )
            return InputResolutionResult(
                status=CalculationStatus.INPUT_UNAVAILABLE,
                reason=reason,
                resolution_trace=_derivation_outcome_trace(
                    trace,
                    ValuationField.BVPS.value,
                    ResolutionOutcome.UNAVAILABLE,
                    reason,
                ),
            )

        value = equity.value / shares.value
        if not math.isfinite(value):
            reason = "BVPS derivation produced a non-finite value."
            return InputResolutionResult(
                status=CalculationStatus.PROVIDER_ERROR,
                reason=reason,
                resolution_trace=_derivation_outcome_trace(
                    trace,
                    ValuationField.BVPS.value,
                    ResolutionOutcome.ERROR,
                    reason,
                ),
            )

        components = (equity, preferred, shares)
        available_ats = [component.available_at for component in components if component.available_at is not None]
        available_at = max(available_ats) if len(available_ats) == len(components) else None
        retrieved_ats = [component.retrieved_at for component in components if component.retrieved_at is not None]
        retrieved_at = max(retrieved_ats) if retrieved_ats else None
        resolved_at = self._clock()
        lineage = ComponentLineage(
            transformation=("stockholders_equity / common_shares_outstanding; zero preferred-share evidence guard"),
            components=components,
        )
        derived = ResolvedInput(
            field_name=ValuationField.BVPS.value,
            value=value,
            source_kind=SourceKind.DERIVED,
            resolved_at=resolved_at,
            basis=request.basis,
            units=ValuationUnit.CURRENCY_PER_SHARE.value,
            currency=equity.currency,
            provider_id=request.provider_id,
            observation_period_end=equity.observation_period_end,
            available_at=available_at,
            as_of=request.as_of,
            retrieved_at=retrieved_at,
            lineage=lineage,
            notes=(
                "measurement_basis=common equity per period-end common share",
                "stockholders_equity accepted as common equity only because same-period "
                "preferred-share evidence resolved to zero",
                "no independent split normalization applied; source filing share/EPS "
                "restatement semantics are retained",
            ),
        )

        if use_cache and self._cache is not None:
            self._cache.put(self._build_cache_key(request), derived)
        return InputResolutionResult(
            status=CalculationStatus.OK,
            resolved_input=derived,
            resolution_trace=_derivation_outcome_trace(
                trace,
                ValuationField.BVPS.value,
                ResolutionOutcome.SUCCESS,
                "Derived BVPS from compatible same-period components with a zero preferred-share evidence guard.",
            ),
        )

    def _build_derived_cache_key(self, request: ValuationFactRequest) -> ValuationCacheKey:
        """Build the cache key for a derived three-year-average EPS result."""
        return ValuationCacheKey(
            subject_kind=request.subject_kind,
            subject_id=request.subject_id,
            field_name="eps",
            basis="three_year_average",
            provider_id=request.provider_id,
            analysis_as_of=request.as_of,
            schema_version=self._schema_version,
        )

    def _try_derived_cache_hit(
        self,
        stored: ResolvedInput,
        key: ValuationCacheKey,
    ) -> ResolvedInput | None:
        """Relabel a cached DERIVED entry as a CACHE-sourced ResolvedInput.

        Returns None if the entry is not a valid DERIVED source or is temporally unusable.
        """
        if stored.source_kind is not SourceKind.DERIVED:
            return None
        if stored.available_at is not None and stored.available_at > self._clock():
            return None

        return ResolvedInput(
            field_name=stored.field_name,
            value=stored.value,
            source_kind=SourceKind.CACHE,
            resolved_at=self._clock(),
            origin_source_kind=SourceKind.DERIVED,
            basis=stored.basis,
            units=stored.units,
            currency=stored.currency,
            provider_id=stored.provider_id,
            provider_field=stored.provider_field,
            observation_period_start=stored.observation_period_start,
            observation_period_end=stored.observation_period_end,
            observed_at=stored.observed_at,
            available_at=stored.available_at,
            as_of=key.analysis_as_of,
            retrieved_at=stored.retrieved_at,
            cache_schema_version=key.schema_version,
            lineage=stored.lineage,
            notes=stored.notes,
        )

    @staticmethod
    def _validate_candidate(  # noqa: PLR0911
        fact: ProviderFact, request: ValuationFactRequest
    ) -> str | None:
        """Validate a single provider fact candidate. Returns error string or None."""
        if fact.subject_kind is not request.subject_kind:
            return f"Provider fact subject_kind ({fact.subject_kind}) does not match request ({request.subject_kind})."
        if fact.subject_id != request.subject_id:
            return f"Provider fact subject_id ({fact.subject_id!r}) does not match request ({request.subject_id!r})."
        if fact.field_name is not ValuationField.EPS:
            return f"Provider fact field_name ({fact.field_name.name}) is not EPS."
        if fact.provider_id != request.provider_id:
            return f"Provider fact provider_id ({fact.provider_id!r}) does not match request ({request.provider_id!r})."
        if fact.basis != "fiscal_year":
            return f"Provider fact basis ({fact.basis!r}) is not 'fiscal_year'."
        if fact.observation_period_start is None:
            return "Provider fact is missing observation_period_start."
        if fact.observation_period_end is None:
            return "Provider fact is missing observation_period_end."
        return None

    @staticmethod
    def _is_temporally_eligible(  # noqa: PLR0911
        fact: ProviderFact,
        request: ValuationFactRequest,
        resolver_now: datetime,
    ) -> bool:
        """Check temporal eligibility of a single candidate."""
        period_end = fact.observation_period_end
        assert period_end is not None  # guaranteed by prior validation

        if request.as_of is not None:
            # Historical: period_end <= as_of, available_at present and <= as_of
            if period_end > request.as_of:
                return False
            if fact.available_at is None:
                return False
            return not fact.available_at > request.as_of
        else:
            # Current: period_end <= resolver_now, available_at is None or <= resolver_now
            if period_end > resolver_now:
                return False
            return fact.available_at is None or fact.available_at <= resolver_now

    def _resolve_override(
        self,
        request: ValuationFactRequest,
        override: float,
    ) -> InputResolutionResult:
        """Validate and construct an OVERRIDE resolution."""
        field_name = request.field_name.value
        if not math.isfinite(override):
            reason = f"Override value must be finite (received {override!r})."
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

        if request.field_name is ValuationField.CURRENT_PRICE and override <= 0:
            reason = f"current_price override must be strictly positive (received {override})."
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
        if request.field_name is ValuationField.CURRENT_AAA_YIELD and override <= 0:
            reason = f"current_aaa_yield override must be strictly positive (received {override})."
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

        resolved_at = self._clock()
        ri = ResolvedInput(
            field_name=field_name,
            value=override,
            source_kind=SourceKind.OVERRIDE,
            resolved_at=resolved_at,
            basis=request.basis,
            units=_field_unit(request.field_name).value,
            as_of=request.as_of,
        )
        return InputResolutionResult(
            status=CalculationStatus.OK,
            resolved_input=ri,
            resolution_trace=_trace_event(
                field_name,
                ResolutionStage.OVERRIDE,
                ResolutionOutcome.SUCCESS,
                "Explicit override was accepted; cache and provider were bypassed.",
            ),
        )

    def _build_cache_key(self, request: ValuationFactRequest) -> ValuationCacheKey:
        """Construct the cache key from the request and configured schema version."""
        return ValuationCacheKey(
            subject_kind=request.subject_kind,
            subject_id=request.subject_id,
            field_name=request.field_name.value,
            basis=request.basis,
            provider_id=request.provider_id,
            analysis_as_of=request.as_of,
            schema_version=self._schema_version,
        )

    def _try_cache_hit(
        self,
        request: ValuationFactRequest,
        stored: ResolvedInput,
        key: ValuationCacheKey,
    ) -> ResolvedInput | None:
        """Relabel a valid cached entry as a new CACHE-sourced ``ResolvedInput``.

        Returns ``None`` if the entry is temporally unusable for the request.
        """
        # Current-request temporal check: available_at must not be in the future.
        if request.as_of is None and stored.available_at is not None and stored.available_at > self._clock():
            return None

        return ResolvedInput(
            field_name=stored.field_name,
            value=stored.value,
            source_kind=SourceKind.CACHE,
            resolved_at=self._clock(),
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
            as_of=request.as_of,
            retrieved_at=stored.retrieved_at,
            cache_schema_version=key.schema_version,
            lineage=stored.lineage,
            notes=stored.notes,
        )

    def _resolve_provider(
        self,
        request: ValuationFactRequest,
        use_cache: bool,
    ) -> InputResolutionResult:
        """Call the provider, validate the response, and optionally cache it."""
        field_name = request.field_name.value
        trace = _trace_event(
            field_name,
            ResolutionStage.PROVIDER,
            ResolutionOutcome.ATTEMPTED,
            f"Requested {field_name} from provider {request.provider_id!r}.",
        )
        try:
            facts = self._provider.fetch_facts(request)
        except ValuationProviderError as exc:
            reason = f"Provider error: {exc}"
            return InputResolutionResult(
                status=CalculationStatus.PROVIDER_ERROR,
                reason=reason,
                resolution_trace=trace.append(
                    _event(
                        field_name,
                        ResolutionStage.PROVIDER,
                        ResolutionOutcome.ERROR,
                        reason,
                    )
                ),
            )

        if len(facts) == 0:
            reason = "Provider returned no data for the requested field."
            return InputResolutionResult(
                status=CalculationStatus.INPUT_UNAVAILABLE,
                reason=reason,
                resolution_trace=trace.append(
                    _event(
                        field_name,
                        ResolutionStage.PROVIDER,
                        ResolutionOutcome.UNAVAILABLE,
                        reason,
                    )
                ),
            )

        if len(facts) > 1:
            reason = f"Provider returned {len(facts)} facts for a single-observation request; expected exactly 1."
            return InputResolutionResult(
                status=CalculationStatus.PROVIDER_ERROR,
                reason=reason,
                resolution_trace=trace.append(
                    _event(
                        field_name,
                        ResolutionStage.PROVIDER,
                        ResolutionOutcome.ERROR,
                        reason,
                    )
                ),
            )

        fact = facts[0]

        validation = _validate_provider_response(request, fact, self._clock())
        if validation is not None:
            status, reason = validation
            outcome = (
                ResolutionOutcome.UNAVAILABLE
                if status is CalculationStatus.INPUT_UNAVAILABLE
                else ResolutionOutcome.REJECTED
            )
            return InputResolutionResult(
                status=status,
                reason=reason,
                resolution_trace=trace.append(
                    _event(
                        field_name,
                        ResolutionStage.PROVIDER,
                        outcome,
                        reason,
                    )
                ),
            )

        ri = ResolvedInput(
            field_name=field_name,
            value=fact.value,
            source_kind=SourceKind.PROVIDER,
            resolved_at=self._clock(),
            basis=fact.basis,
            units=fact.units.value,
            currency=fact.currency,
            provider_id=fact.provider_id,
            provider_field=fact.provider_field,
            observation_period_start=fact.observation_period_start,
            observation_period_end=fact.observation_period_end,
            observed_at=fact.observed_at,
            available_at=fact.available_at,
            as_of=request.as_of,
            retrieved_at=fact.retrieved_at,
            notes=fact.notes,
        )

        if use_cache and self._cache is not None:
            key = self._build_cache_key(request)
            self._cache.put(key, ri)

        return InputResolutionResult(
            status=CalculationStatus.OK,
            resolved_input=ri,
            resolution_trace=trace.append(
                _event(
                    field_name,
                    ResolutionStage.PROVIDER,
                    ResolutionOutcome.SUCCESS,
                    "Provider fact passed resolver validation and was accepted.",
                )
            ),
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _event(
    field_name: str,
    stage: ResolutionStage,
    outcome: ResolutionOutcome,
    message: str,
) -> ResolutionEvent:
    """Construct one resolver trace event."""
    return ResolutionEvent(
        field_name=field_name,
        stage=stage,
        outcome=outcome,
        message=message,
    )


def _trace_event(
    field_name: str,
    stage: ResolutionStage,
    outcome: ResolutionOutcome,
    message: str,
) -> ResolutionTrace:
    """Construct a one-event resolver trace."""
    return ResolutionTrace(events=(_event(field_name, stage, outcome, message),))


def _prepend_trace(
    result: InputResolutionResult,
    prefix: ResolutionTrace,
) -> InputResolutionResult:
    """Return a result with earlier trace events prepended in execution order."""
    if not prefix:
        return result
    return InputResolutionResult(
        status=result.status,
        resolved_input=result.resolved_input,
        reason=result.reason,
        resolution_trace=prefix.extend(result.resolution_trace),
    )


def _derivation_outcome_trace(
    trace: ResolutionTrace,
    field_name: str,
    outcome: ResolutionOutcome,
    message: str,
) -> ResolutionTrace:
    """Append one derivation outcome event."""
    return trace.append(
        _event(
            field_name,
            ResolutionStage.DERIVATION,
            outcome,
            message,
        )
    )


def _derivation_error_trace(
    trace: ResolutionTrace,
    field_name: str,
    message: str,
) -> ResolutionTrace:
    """Append one derivation error event."""
    return _derivation_outcome_trace(
        trace,
        field_name,
        ResolutionOutcome.ERROR,
        message,
    )


def _field_unit(field_name: ValuationField) -> ValuationUnit:
    """Map a semantic field to its required unit."""
    if field_name is ValuationField.CURRENT_AAA_YIELD:
        return ValuationUnit.PERCENTAGE_POINTS
    if field_name is ValuationField.STOCKHOLDERS_EQUITY:
        return ValuationUnit.CURRENCY
    if field_name in (ValuationField.COMMON_SHARES_OUTSTANDING, ValuationField.PREFERRED_SHARES_OUTSTANDING):
        return ValuationUnit.SHARES
    return ValuationUnit.CURRENCY_PER_SHARE


def _bvps_component_request(request: ValuationFactRequest, field_name: ValuationField) -> ValuationFactRequest:
    """Build a fiscal-year-end component request inheriting the BVPS analysis boundary."""
    return ValuationFactRequest(
        subject_kind=request.subject_kind,
        subject_id=request.subject_id,
        field_name=field_name,
        provider_id=request.provider_id,
        basis="fiscal_year_end",
        as_of=request.as_of,
    )


def _bvps_component_failure(
    name: str,
    result: InputResolutionResult,
    trace: ResolutionTrace,
) -> InputResolutionResult:
    """Wrap a component-resolution failure with BVPS derivation context."""
    reason = f"BVPS unavailable: required {name} component could not be resolved: {result.reason}"
    outcome = {
        CalculationStatus.PROVIDER_ERROR: ResolutionOutcome.ERROR,
        CalculationStatus.INVALID_INPUT: ResolutionOutcome.INVALID,
    }.get(result.status, ResolutionOutcome.UNAVAILABLE)
    return InputResolutionResult(
        status=result.status,
        reason=reason,
        resolution_trace=_derivation_outcome_trace(
            trace,
            ValuationField.BVPS.value,
            outcome,
            reason,
        ),
    )


def _bvps_component_alignment_error(
    equity: ResolvedInput,
    preferred: ResolvedInput,
    shares: ResolvedInput,
) -> str | None:
    """Return a reason when BVPS derivation components are not safely compatible."""
    components = (equity, preferred, shares)
    period_ends = {component.observation_period_end for component in components}
    if None in period_ends or len(period_ends) != 1:
        return "BVPS unavailable: equity and share-count components do not share one reporting-period end."
    if equity.currency is None:
        return "BVPS unavailable: stockholders_equity component has no currency."
    if equity.units != ValuationUnit.CURRENCY.value:
        return "BVPS unavailable: stockholders_equity component is not a currency amount."
    if preferred.units != ValuationUnit.SHARES.value or shares.units != ValuationUnit.SHARES.value:
        return "BVPS unavailable: share-count components are not expressed in shares."

    error = None
    if preferred.value < 0:
        error = "BVPS unavailable: preferred_shares_outstanding is negative."
    elif shares.value <= 0:
        error = "BVPS unavailable: common_shares_outstanding must be strictly positive."
    return error


def _validate_provider_response(
    request: ValuationFactRequest,
    fact: ProviderFact,
    now: datetime,
) -> tuple[CalculationStatus, str] | None:
    """Validate that the fact coherently answers the request and is temporally eligible.

    Returns a ``(status, reason)`` tuple when validation fails, or ``None`` on success.
    """
    # Coherence: the fact must answer the request.
    coherence_checks: tuple[tuple[bool, str], ...] = (
        (
            fact.subject_kind is request.subject_kind,
            f"Provider fact subject_kind ({fact.subject_kind}) does not match request ({request.subject_kind}).",
        ),
        (
            fact.subject_id == request.subject_id,
            f"Provider fact subject_id ({fact.subject_id!r}) does not match request ({request.subject_id!r}).",
        ),
        (
            fact.field_name is request.field_name,
            f"Provider fact field_name ({fact.field_name.name}) does not match request ({request.field_name.name}).",
        ),
        (
            fact.provider_id == request.provider_id,
            f"Provider fact provider_id ({fact.provider_id!r}) does not match request ({request.provider_id!r}).",
        ),
        (
            fact.basis == request.basis,
            f"Provider fact basis ({fact.basis!r}) does not match request ({request.basis!r}).",
        ),
    )
    for passed, message in coherence_checks:
        if not passed:
            return (CalculationStatus.PROVIDER_ERROR, message)

    # Temporal eligibility.
    if request.as_of is not None:
        # Historical: available_at is required and must be <= as_of.
        if fact.available_at is None:
            return (
                CalculationStatus.INPUT_UNAVAILABLE,
                "Historical request requires available_at; fact has no available_at.",
            )
        if fact.available_at > request.as_of:
            return (
                CalculationStatus.INPUT_UNAVAILABLE,
                f"Fact available_at ({fact.available_at.isoformat()}) is later than "
                f"request as_of ({request.as_of.isoformat()}).",
            )
    elif fact.available_at is not None and fact.available_at > now:
        return (
            CalculationStatus.INPUT_UNAVAILABLE,
            f"Fact available_at ({fact.available_at.isoformat()}) is later than current time ({now.isoformat()}).",
        )
    return None
