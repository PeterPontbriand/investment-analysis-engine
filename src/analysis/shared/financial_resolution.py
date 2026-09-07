"""Strategy-neutral financial resolution and security-evidence primitives."""

from __future__ import annotations

import math
from datetime import datetime

from src.data.financial.facts import FinancialFactRequest, FinancialField
from src.data.financial.provenance import FinancialSubjectKind, ResolvedInput, SourceKind
from src.data.financial.resolver import InputResolutionResult, InputResolver
from src.data.instrument_profile import InstrumentKind, InstrumentProfile
from src.data.security_unit import SecurityUnitEvidence, evaluate_security_unit_compatibility


def resolve_normalized_eps(  # noqa: PLR0913
    resolver: InputResolver,
    *,
    security_subject_id: str,
    security_provider_id: str,
    eps_basis: str,
    eps_override: float | None,
    as_of: datetime | None,
    use_cache: bool,
) -> InputResolutionResult:
    """Resolve normalized EPS through the injected financial-fact resolver.

    Delegates to ``resolve_three_year_average_eps`` for the
    ``three_year_average`` basis, or the single-fact ``resolve`` for
    ``ttm`` and any other single-observation basis.  An explicit
    override always bypasses cache/provider.
    """
    if eps_override is not None:
        # Override bypasses cache/provider; retain the selected basis.
        request = FinancialFactRequest(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id=security_subject_id,
            field_name=FinancialField.EPS,
            provider_id=security_provider_id,
            basis=eps_basis,
            as_of=as_of,
        )
        return resolver.resolve(request, override=eps_override, use_cache=use_cache)

    if eps_basis == "three_year_average":
        request = FinancialFactRequest(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id=security_subject_id,
            field_name=FinancialField.EPS,
            provider_id=security_provider_id,
            basis="fiscal_year",
            as_of=as_of,
            observation_count=3,
        )
        return resolver.resolve_three_year_average_eps(request, use_cache=use_cache)

    # Single-observation basis (ttm, etc.)
    request = FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id=security_subject_id,
        field_name=FinancialField.EPS,
        provider_id=security_provider_id,
        basis=eps_basis,
        as_of=as_of,
    )
    return resolver.resolve(request, use_cache=use_cache)


def resolve_optional_quote(  # noqa: PLR0913
    resolver: InputResolver,
    *,
    security_subject_id: str,
    security_provider_id: str,
    quote_override: float | None,
    as_of: datetime | None,
    use_cache: bool,
) -> InputResolutionResult:
    """Resolve a quote without changing the resolver outcome or caller policy."""
    request = FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id=security_subject_id,
        field_name=FinancialField.CURRENT_PRICE,
        provider_id=security_provider_id,
        as_of=as_of,
    )
    return resolver.resolve(request, override=quote_override, use_cache=use_cache)


def validate_profile_ticker(ticker: str, profile: InstrumentProfile | None, *, mismatch_message: str) -> None:
    """Reject accidental reuse of evidence for another requested instrument."""
    if profile is not None and profile.ticker != ticker.strip().upper():
        raise ValueError(mismatch_message)


def is_known_etf(profile: InstrumentProfile | None) -> bool:
    """Return whether affirmative provider evidence classifies the instrument as an ETF."""
    return (
        profile is not None and profile.kind_evidence is not None and profile.kind_evidence.kind is InstrumentKind.ETF
    )


def has_provider_backed_evidence(*inputs: ResolvedInput | None) -> bool:
    """Return whether at least one security fact carries non-override provenance."""
    return any(value is not None and value.source_kind is not SourceKind.OVERRIDE for value in inputs)


def margin_of_safety(
    reference_value: float | None,
    current_price: ResolvedInput | None,
    *,
    valuation_currency: str | None = None,
    security_unit_evidence: SecurityUnitEvidence | None = None,
    require_security_unit_evidence: bool = False,
) -> float | None:
    """Compute comparison only when value, quote, and known currencies are compatible."""
    if reference_value is None or current_price is None or reference_value <= 0:
        return None
    if (
        require_security_unit_evidence
        and not evaluate_security_unit_compatibility(
            security_unit_evidence,
            filing_currency=valuation_currency,
            quote_currency=current_price.currency,
        ).is_compatible
    ):
        return None
    if (
        valuation_currency is not None
        and current_price.currency is not None
        and valuation_currency != current_price.currency
    ):
        return None
    margin = ((reference_value - current_price.value) / reference_value) * 100.0
    return margin if math.isfinite(margin) else None


def common_currency(*inputs: ResolvedInput | None) -> str | None:
    """Return one shared known currency, or None when inputs disagree or omit it."""
    currencies = {item.currency for item in inputs if item is not None and item.currency}
    return next(iter(currencies)) if len(currencies) == 1 else None
