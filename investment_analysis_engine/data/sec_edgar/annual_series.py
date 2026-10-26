"""Completed-annual income-statement and cash-flow amounts from SEC Company Facts.

Each field maps to a priority list of concepts per taxonomy. A list holds several concepts only where the evidence shows
that they are the same line item (for example revenue under the concepts that different filers use for their total, or
the three concepts under which cash-flow statements report combined depreciation and amortization). Overlapping revenue
concepts are never summed. A field the evidence could not support for a taxonomy has an empty list and is unavailable;
no neighboring concept stands in for it. One concept is used for every year of a series, so a filer that changed its
tagging has the years its newest concept covers, and the older years are absent rather than read under another concept.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, time
from typing import Final, cast
from zoneinfo import ZoneInfo

from investment_analysis_engine.data.financial.facts import (
    FinancialFactRequest,
    FinancialField,
    FinancialUnit,
    ProviderFact,
)
from investment_analysis_engine.data.financial.provenance import (
    AccountingScope,
    FinancialSubjectKind,
    PeriodKind,
)

SEC_PROVIDER_ID: Final = "sec_edgar"
US_GAAP: Final = "us-gaap"
IFRS_FULL: Final = "ifrs-full"

_ANNUAL_FORMS: Final = frozenset({"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"})
_EASTERN: Final = ZoneInfo("America/New_York")
# The completed-annual duration tolerance, as the other annual series use it: 52/53-week years pass; quarters,
# year-to-date periods and stub years do not.
_MIN_DAYS: Final = 335
_MAX_DAYS: Final = 395

US_GAAP_ANNUAL_CONCEPTS: Final[Mapping[FinancialField, tuple[str, ...]]] = {
    FinancialField.SALES: (
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ),
    FinancialField.COST_OF_REVENUE: ("CostOfRevenue", "CostOfGoodsAndServicesSold"),
    FinancialField.GROSS_PROFIT: ("GrossProfit",),
    FinancialField.OPERATING_INCOME: ("OperatingIncomeLoss",),
    FinancialField.SELLING_GENERAL_ADMINISTRATIVE: ("SellingGeneralAndAdministrativeExpense",),
    FinancialField.DEPRECIATION_AND_AMORTIZATION: (
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
    ),
    FinancialField.DEPRECIATION: ("Depreciation",),
    FinancialField.INTEREST_EXPENSE: ("InterestExpense", "InterestExpenseNonoperating"),
    FinancialField.PRETAX_INCOME: (
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    ),
    FinancialField.INCOME_TAX_EXPENSE: ("IncomeTaxExpenseBenefit",),
    FinancialField.NET_INCOME: ("NetIncomeLoss",),
    FinancialField.INCOME_FROM_CONTINUING_OPERATIONS: ("IncomeLossFromContinuingOperations",),
    FinancialField.DISCONTINUED_OPERATIONS: ("IncomeLossFromDiscontinuedOperationsNetOfTax",),
}
IFRS_ANNUAL_CONCEPTS: Final[Mapping[FinancialField, tuple[str, ...]]] = {
    FinancialField.SALES: ("Revenue", "RevenueFromContractsWithCustomers"),
    FinancialField.COST_OF_REVENUE: ("CostOfSales",),
    FinancialField.GROSS_PROFIT: ("GrossProfit",),
    FinancialField.OPERATING_INCOME: ("ProfitLossFromOperatingActivities",),
    FinancialField.SELLING_GENERAL_ADMINISTRATIVE: (),
    FinancialField.DEPRECIATION_AND_AMORTIZATION: (
        "DepreciationAndAmortisationExpense",
        "AdjustmentsForDepreciationAndAmortisationExpense",
    ),
    FinancialField.DEPRECIATION: (),
    FinancialField.INTEREST_EXPENSE: ("InterestExpense",),
    FinancialField.PRETAX_INCOME: ("ProfitLossBeforeTax",),
    FinancialField.INCOME_TAX_EXPENSE: ("IncomeTaxExpenseContinuingOperations",),
    FinancialField.NET_INCOME: ("ProfitLossAttributableToOwnersOfParent",),
    FinancialField.INCOME_FROM_CONTINUING_OPERATIONS: ("IncomeFromContinuingOperationsAttributableToOwnersOfParent",),
    FinancialField.DISCONTINUED_OPERATIONS: ("ProfitLossFromDiscontinuedOperations",),
}


def annual_concepts(field_name: FinancialField, taxonomy: str) -> tuple[str, ...]:
    """Return the field's priority list under a taxonomy; empty when it is unsupported or not an annual field."""
    table = IFRS_ANNUAL_CONCEPTS if taxonomy == IFRS_FULL else US_GAAP_ANNUAL_CONCEPTS
    return table.get(field_name, ())


@dataclass(frozen=True)
class _Context:
    """What parsing one observation needs beyond the observation itself."""

    request: FinancialFactRequest
    cik: str
    acceptance_by_accession: Mapping[str, datetime]
    retrieved_at: datetime
    taxonomy: str


def select_annual_period_facts(  # noqa: PLR0913
    payload: object,
    *,
    request: FinancialFactRequest,
    cik: str,
    acceptance_by_accession: Mapping[str, datetime],
    retrieved_at: datetime,
    taxonomy: str,
    boundary: datetime,
) -> tuple[ProviderFact, ...]:
    """Return the completed-annual facts of the one concept the series uses, eligible at the boundary, oldest first.

    The concept is the first of the field's list that reports the newest fiscal period end any listed concept reports.
    A fiscal year the concept does not report is absent; no other listed concept fills it. Restatements and equal-rank
    duplicates remain for the series resolver to group, as they do for the other annual fields.
    """
    concepts = annual_concepts(request.field_name, taxonomy)
    if not concepts or not isinstance(payload, Mapping):
        return ()
    context = _Context(request, cik, acceptance_by_accession, retrieved_at, taxonomy)
    by_concept = {concept: _eligible(_facts_of(payload, context, concept), boundary) for concept in concepts}
    ends = [fact.observation_period_end for facts in by_concept.values() for fact in facts]
    newest = max((end for end in ends if end is not None), default=None)
    chosen = next(
        (concept for concept in concepts if any(fact.observation_period_end == newest for fact in by_concept[concept])),
        None,
    )
    return by_concept[chosen] if chosen is not None else ()


def _eligible(facts: tuple[ProviderFact, ...], boundary: datetime) -> tuple[ProviderFact, ...]:
    """Keep the facts whose period had ended and whose filing was available at the boundary, in stable order."""
    kept = [
        fact
        for fact in facts
        if fact.observation_period_end is not None
        and fact.available_at is not None
        and fact.observation_period_end <= boundary
        and fact.available_at <= boundary
    ]
    return tuple(
        sorted(
            kept,
            key=lambda fact: (
                cast(datetime, fact.observation_period_end),
                cast(datetime, fact.observation_period_start),
                cast(datetime, fact.available_at),
                fact.provider_fact_id or "",
            ),
        )
    )


def _facts_of(payload: Mapping[object, object], context: _Context, concept: str) -> tuple[ProviderFact, ...]:
    """Parse every completed-annual observation of one concept."""
    facts = payload.get("facts")
    group = facts.get(context.taxonomy) if isinstance(facts, Mapping) else None
    entry = group.get(concept) if isinstance(group, Mapping) else None
    units = entry.get("units") if isinstance(entry, Mapping) else None
    result: list[ProviderFact] = []
    for unit_name, observations in units.items() if isinstance(units, Mapping) else ():
        currency = str(unit_name).strip().upper()
        if len(currency) != 3 or not currency.isalpha() or not isinstance(observations, Sequence):
            continue
        for observation in observations:
            parsed = _parse(observation, context, concept, currency)
            if parsed is not None:
                result.append(parsed)
    return tuple(result)


def _parse(observation: object, context: _Context, concept: str, currency: str) -> ProviderFact | None:  # noqa: PLR0911
    """Parse one completed-annual observation, or return ``None``."""
    if not isinstance(observation, Mapping):
        return None
    form = observation.get("form")
    if form not in _ANNUAL_FORMS or observation.get("fp") != "FY":
        return None
    value = observation.get("val")
    start, end, accession, filed = (observation.get(key) for key in ("start", "end", "accn", "filed"))
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        return None
    if not all(isinstance(item, str) for item in (start, end, accession, filed)):
        return None
    period_start, period_end = _start_of(cast(str, start)), _end_of(cast(str, end))
    if period_start is None or period_end is None:
        return None
    if not _MIN_DAYS <= (period_end.date() - period_start.date()).days + 1 <= _MAX_DAYS:
        return None
    accession_text = cast(str, accession)
    available_at = context.acceptance_by_accession.get(accession_text)
    if available_at is None:
        available_at = _end_of_filed(cast(str, filed))
        if available_at is None:
            return None
        availability = (
            "availability_source=SEC filed date end in America/New_York, converted to UTC; "
            "acceptanceDateTime unavailable"
        )
    else:
        availability = "availability_source=SEC submissions acceptanceDateTime, normalized to UTC"
    request = context.request
    provider_field = f"{context.taxonomy}:{concept}"
    fiscal_year = observation.get("fy")
    return ProviderFact(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id=request.subject_id,
        field_name=request.field_name,
        value=float(value),
        units=FinancialUnit.CURRENCY,
        provider_id=SEC_PROVIDER_ID,
        provider_field=provider_field,
        retrieved_at=context.retrieved_at,
        basis="fiscal_year",
        currency=currency,
        observation_period_start=period_start,
        observation_period_end=period_end,
        available_at=available_at,
        notes=(
            f"cik={context.cik}",
            f"accession={accession_text}",
            f"form={form}",
            f"provider_fiscal_year={fiscal_year}"
            if isinstance(fiscal_year, (int, str))
            else "provider_fiscal_year=unknown",
            "fiscal_year_source=calendar year containing exact SEC period end",
            f"concept_priority={'>'.join(annual_concepts(request.field_name, context.taxonomy))}",
            availability,
        ),
        fiscal_year=period_end.year,
        period_kind=PeriodKind.COMPLETED_ANNUAL,
        accounting_scope=AccountingScope.CONSOLIDATED,
        provider_fact_id=f"{accession_text}:{provider_field}:{currency}:{start}:{end}",
    )


def _start_of(text: str) -> datetime | None:
    """Return the start of a Company Facts date in UTC, or ``None``."""
    try:
        return datetime.combine(datetime.strptime(text, "%Y-%m-%d").date(), time.min, tzinfo=UTC)
    except ValueError:
        return None


def _end_of(text: str) -> datetime | None:
    """Return the end of a Company Facts date in UTC, or ``None``."""
    try:
        return datetime.combine(datetime.strptime(text, "%Y-%m-%d").date(), time.max, tzinfo=UTC)
    except ValueError:
        return None


def _end_of_filed(text: str) -> datetime | None:
    """Return the end of a filing date in Eastern time, in UTC, or ``None``."""
    try:
        return datetime.combine(datetime.strptime(text, "%Y-%m-%d").date(), time.max, tzinfo=_EASTERN).astimezone(UTC)
    except ValueError:
        return None
