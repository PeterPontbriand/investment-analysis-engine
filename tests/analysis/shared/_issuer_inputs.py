"""The inputs of the Step 3.5 regression issuers, read through the SEC adapter that serves the captured fixtures.

No number is retyped from the evidence record: every value comes from the adapter, the resolver and the fixture files.
"""

from datetime import UTC, date, datetime

from investment_analysis_engine.data.financial.facts import (
    FinancialFactRequest,
    FinancialField,
    InstantAbsence,
    InstantAbsenceReason,
    InstantSeriesRequest,
    ProviderFact,
)
from investment_analysis_engine.data.financial.provenance import FinancialSubjectKind, ResolvedInput, SourceKind
from investment_analysis_engine.data.financial.resolver import InputResolver
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from tests._sec_instants import NOW, REGRESSION_SET, adapter_for, annual_series, year_ends


def to_resolved(fact: ProviderFact) -> ResolvedInput:
    """Return the resolved input of a provider fact, as the resolver builds one."""
    return ResolvedInput(
        field_name=fact.field_name.value,
        value=fact.value,
        source_kind=SourceKind.PROVIDER,
        resolved_at=NOW,
        basis=fact.basis,
        units=fact.units.value,
        currency=fact.currency,
        provider_id=fact.provider_id,
        provider_field=fact.provider_field,
        observation_period_start=fact.observation_period_start,
        observation_period_end=fact.observation_period_end,
        available_at=fact.available_at,
        retrieved_at=fact.retrieved_at,
        notes=fact.notes,
        fiscal_year=fact.fiscal_year,
        period_kind=fact.period_kind,
        provider_fact_id=fact.provider_fact_id,
    )


def balance(ticker: str, field: FinancialField) -> ResolvedInput | InstantAbsence:
    """Return the balance-sheet field at the issuer's latest year-end, as the resolver reports it."""
    request = InstantSeriesRequest(ticker, field, SEC_PROVIDER_ID, year_ends(REGRESSION_SET[ticker], 1))
    resolution = InputResolver(adapter_for(ticker), clock=lambda: NOW).resolve_instant_series(request)
    if resolution.inputs:
        return resolution.inputs[0]
    return resolution.absences[0]


def annual(ticker: str, field: FinancialField) -> ResolvedInput | None:
    """Return the annual field of the issuer's latest fiscal year, or ``None`` when its filings report none."""
    facts = annual_series(ticker, field, count=1)
    if not facts:
        return None
    latest = max(facts, key=lambda fact: fact.observation_period_end or NOW)
    return to_resolved(latest)


def share_count(ticker: str, basis: str) -> ResolvedInput | None:
    """Return the issuer's share count on ``basis`` (``fiscal_year_end`` or ``cover_page``), or ``None``."""
    request = FinancialFactRequest(
        FinancialSubjectKind.SECURITY, ticker, FinancialField.COMMON_SHARES_OUTSTANDING, SEC_PROVIDER_ID, basis=basis
    )
    facts = adapter_for(ticker).fetch_facts(request, effective_as_of=NOW)
    return to_resolved(facts[0]) if facts else None


def year_end(ticker: str) -> date:
    """Return the issuer's latest fiscal year-end."""
    return REGRESSION_SET[ticker]


def synthetic(name: str, value: float, *, day: date = date(2025, 12, 31)) -> ResolvedInput:
    """Return a synthetic resolved input of ``name`` observed at ``day``, for the edge rows of a rule."""
    return ResolvedInput(
        field_name=name,
        value=value,
        source_kind=SourceKind.PROVIDER,
        resolved_at=NOW,
        currency="USD",
        provider_id=SEC_PROVIDER_ID,
        provider_field=f"synthetic:{name}",
        observation_period_end=datetime.combine(day, datetime.max.time(), tzinfo=UTC),
        available_at=NOW,
        retrieved_at=NOW,
    )


def absent(
    reason: InstantAbsenceReason = InstantAbsenceReason.NOT_TAGGED,
    *,
    related: str | None = None,
    day: date = date(2025, 12, 31),
) -> InstantAbsence:
    """Return a synthetic absence of ``reason`` at ``day``."""
    return InstantAbsence(period_end=day, reason=reason, detail=f"synthetic {reason.value}", related_concept=related)
