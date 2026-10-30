"""Balance-sheet values at named fiscal year-ends, read from SEC Company Facts.

A request names the year-ends it wants and the result holds what the issuer's eligible annual filings report for
exactly those dates, never the newest balance sheet in place of an earlier one. A year-end the newest filing does not
report may come from an earlier eligible filing, on the same taxonomy and in the same currency, under the same
boundary. Every mapping below was approved from captured filings (see the Step 3.5 mapping evidence); a field the
evidence could not support for a taxonomy has an empty concept list and is reported unsupported.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time
from typing import Final

from investment_analysis_engine.data.financial.facts import (
    SHARE_COUNT_SERIES_FIELD,
    FinancialField,
    FinancialUnit,
    InstantAbsence,
    InstantAbsenceReason,
    InstantSeriesFacts,
    InstantSeriesRequest,
    ProviderAmountSource,
    ProviderFact,
    ProviderShareSource,
    instant_series_unit,
)
from investment_analysis_engine.data.financial.provenance import FinancialSubjectKind, PeriodKind

SEC_PROVIDER_ID: Final = "sec_edgar"
US_GAAP: Final = "us-gaap"
IFRS_FULL: Final = "ifrs-full"

# One list per field and taxonomy, in priority order. A list holds several concepts only where the evidence shows
# that they are the same line item (receivables, short-term investments, and net PP&E under IFRS). An empty list is a
# field the evidence did not support for the taxonomy: it is unavailable, and no neighboring concept stands in.
US_GAAP_CONCEPTS: Final[Mapping[FinancialField, tuple[str, ...]]] = {
    FinancialField.TOTAL_ASSETS: ("Assets",),
    FinancialField.TOTAL_LIABILITIES: ("Liabilities",),
    FinancialField.CURRENT_ASSETS: ("AssetsCurrent",),
    FinancialField.CURRENT_LIABILITIES: ("LiabilitiesCurrent",),
    FinancialField.CASH_AND_EQUIVALENTS: ("CashAndCashEquivalentsAtCarryingValue",),
    FinancialField.SHORT_TERM_INVESTMENTS: (
        "ShortTermInvestments",
        "MarketableSecuritiesCurrent",
        "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
    ),
    FinancialField.LONG_TERM_INVESTMENTS: ("LongTermInvestments",),
    FinancialField.NET_PPE: (
        "PropertyPlantAndEquipmentNet",
        "PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization",
    ),
    FinancialField.RECEIVABLES: ("AccountsReceivableNetCurrent", "ReceivablesNetCurrent"),
    FinancialField.RETAINED_EARNINGS: ("RetainedEarningsAccumulatedDeficit",),
    FinancialField.SHORT_TERM_BORROWINGS: ("ShortTermBorrowings", "CommercialPaper"),
    FinancialField.CURRENT_PORTION_OF_LONG_TERM_DEBT: ("LongTermDebtCurrent",),
    FinancialField.NONCURRENT_LONG_TERM_DEBT: ("LongTermDebtNoncurrent",),
    FinancialField.LONG_TERM_DEBT_TOTAL: ("LongTermDebt",),
    FinancialField.LEASE_LIABILITIES_AS_DEBT: ("FinanceLeaseLiability",),
    FinancialField.PREFERRED_STOCK: ("PreferredStockValue",),
    FinancialField.NONCONTROLLING_INTEREST: ("MinorityInterest",),
}
IFRS_CONCEPTS: Final[Mapping[FinancialField, tuple[str, ...]]] = {
    FinancialField.TOTAL_ASSETS: ("Assets",),
    FinancialField.TOTAL_LIABILITIES: ("Liabilities",),
    FinancialField.CURRENT_ASSETS: ("CurrentAssets",),
    FinancialField.CURRENT_LIABILITIES: ("CurrentLiabilities",),
    FinancialField.CASH_AND_EQUIVALENTS: ("CashAndCashEquivalents",),
    FinancialField.SHORT_TERM_INVESTMENTS: (),
    FinancialField.LONG_TERM_INVESTMENTS: (),
    FinancialField.NET_PPE: ("PropertyPlantAndEquipment", "PropertyPlantAndEquipmentIncludingRightofuseAssets"),
    FinancialField.RECEIVABLES: ("CurrentTradeReceivables",),
    FinancialField.RETAINED_EARNINGS: ("RetainedEarnings",),
    FinancialField.SHORT_TERM_BORROWINGS: ("ShorttermBorrowings",),
    FinancialField.CURRENT_PORTION_OF_LONG_TERM_DEBT: ("CurrentPortionOfLongtermBorrowings",),
    FinancialField.NONCURRENT_LONG_TERM_DEBT: (),
    FinancialField.LONG_TERM_DEBT_TOTAL: (),
    FinancialField.LEASE_LIABILITIES_AS_DEBT: ("LeaseLiabilities",),
    FinancialField.PREFERRED_STOCK: (),
    FinancialField.NONCONTROLLING_INTEREST: ("NoncontrollingInterests",),
}

# Concepts the evidence records as related to a field without being the same line item. A related concept is never a
# value: where the field is absent at a date and a related concept is tagged, the absence says so, and the metric
# that reads the field decides what that means (an absent debt component is zero only when no related concept is
# tagged). The lists hold what the regression set showed and nothing speculative.
US_GAAP_RELATED: Final[Mapping[FinancialField, tuple[str, ...]]] = {
    FinancialField.RECEIVABLES: ("AccountsAndOtherReceivablesNetCurrent",),
    FinancialField.SHORT_TERM_BORROWINGS: ("DebtCurrent",),
    FinancialField.CURRENT_PORTION_OF_LONG_TERM_DEBT: ("DebtCurrent", "LongTermDebtAndCapitalLeaseObligationsCurrent"),
    FinancialField.NONCURRENT_LONG_TERM_DEBT: ("LongTermDebtAndCapitalLeaseObligations",),
    FinancialField.LEASE_LIABILITIES_AS_DEBT: ("FinanceLeaseLiabilityCurrent", "FinanceLeaseLiabilityNoncurrent"),
}
IFRS_RELATED: Final[Mapping[FinancialField, tuple[str, ...]]] = {
    FinancialField.SHORT_TERM_BORROWINGS: (
        "CommercialPapersIssued",
        "CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings",
    ),
    FinancialField.CURRENT_PORTION_OF_LONG_TERM_DEBT: ("CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings",),
}

# Total liabilities is derived, for US GAAP only, where a date has no tagged ``Liabilities``: total liabilities and
# equity, minus total equity including noncontrolling interest, minus the temporary equity tagged at the same date
# (the first of the two concepts that is tagged; they are never added). Under IFRS the identity does not hold to the
# unit in a filing whose lines are each rounded, so the derivation is not offered.
_LIABILITIES_AND_EQUITY: Final = "LiabilitiesAndStockholdersEquity"
_EQUITY_WITH_NONCONTROLLING: Final = "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"
_TEMPORARY_EQUITY: Final = (
    "TemporaryEquityCarryingAmountIncludingPortionAttributableToNoncontrollingInterests",
    "RedeemableNoncontrollingInterestEquityCarryingAmount",
)
_DERIVATION_TRANSFORMATION: Final = (
    "total liabilities and equity - equity including noncontrolling interest - temporary equity"
)


@dataclass(frozen=True)
class InstantSource:
    """The frozen evidence one selection reads.

    Attributes:
        company_facts: The Company Facts payload of the issuer (empty when the document was not an object).
        cik_matches: Whether the payload declares the resolved CIK.
        taxonomy: The single taxonomy of the anchor filing, or ``None`` when it has none or several.
        acceptance_by_accession: Eligible annual filings (accepted at or before the boundary) and their acceptance
            times. Empty when the issuer has no eligible annual filing.
        accession_taxonomies: The taxonomies each accession tags.
        retrieved_at: When the evidence was retrieved.
        boundary: The point-in-time cutoff.
    """

    company_facts: Mapping[object, object]
    cik_matches: bool
    taxonomy: str | None
    acceptance_by_accession: Mapping[str, datetime]
    accession_taxonomies: Mapping[str, frozenset[str]]
    retrieved_at: datetime
    boundary: datetime


@dataclass(frozen=True)
class _Observation:
    """One non-dimensional balance-sheet value of an eligible annual filing."""

    value: float
    currency: str
    end: date
    accession: str
    available_at: datetime
    form: str


def select_instant_series(request: InstantSeriesRequest, source: InstantSource) -> InstantSeriesFacts:
    """Return the value at each requested year-end, and the year-ends with none.

    The common share count is selected by ``_select_share_counts`` and is a count of shares, not an amount; every other
    field is a currency amount.

    A year-end after the boundary is absent. The concept is chosen once for the run, as the first listed concept with a
    value at any requested year-end; a year-end that concept does not cover is absent even where another listed
    concept covers it. Where two eligible filings report a year-end, the newest filing's value is used, and two
    values of equal priority that disagree make the year-end absent as a conflict. A value on another taxonomy than the
    anchor filing's, or in another currency than the newest year-end's, is not used.
    """
    absences: dict[date, InstantAbsence] = {}
    pending = _date_checks(request, source, absences)
    if not pending:
        return InstantSeriesFacts(absences=_ordered(absences))
    namespace = source.taxonomy
    assert namespace is not None
    if request.field_name is SHARE_COUNT_SERIES_FIELD:
        return _select_share_counts(request, source, namespace, pending, absences)
    concepts = (US_GAAP_CONCEPTS if namespace == US_GAAP else IFRS_CONCEPTS)[request.field_name]
    derivable = namespace == US_GAAP and request.field_name is FinancialField.TOTAL_LIABILITIES
    if not concepts:
        for day in pending:
            absences[day] = _absence(day, InstantAbsenceReason.UNSUPPORTED, _unsupported_detail(request, namespace))
        return InstantSeriesFacts(absences=_ordered(absences))

    by_concept = {concept: _observations(source, namespace, concept) for concept in concepts}
    wanted = set(pending)
    chosen = next(
        (concept for concept in concepts if any(item.end in wanted for item in by_concept[concept].usable)),
        None,
    )
    facts: dict[date, ProviderFact] = {}
    for day in pending:
        if chosen is not None:
            result = _select_at(by_concept[chosen].usable, day)
            if isinstance(result, _Observation):
                facts[day] = _fact_of(request, source, namespace, chosen, result)
                continue
            if result is _CONFLICT:
                absences[day] = _absence(
                    day, InstantAbsenceReason.CONFLICT, f"Eligible filings disagree on {namespace}:{chosen} at {day}."
                )
                continue
        derived = _derive_total_liabilities(request, source, day) if derivable else None
        if isinstance(derived, ProviderFact):
            facts[day] = derived
            continue
        absences[day] = (
            derived if isinstance(derived, InstantAbsence) else _missing(day, concepts, chosen, by_concept, namespace)
        )
    _note_related_concepts(request, source, namespace, facts, absences)
    return _one_currency(request, InstantSeriesFacts(facts=tuple(facts.values()), absences=_ordered(absences)))


# The common share count's two paths, for the series and for the latest-only path alike. The direct concept is read per
# taxonomy; the derived path (issued less treasury shares) is offered for US GAAP only. The provider fields are what a
# count is labelled with, and the only ones a consumer may recognise as a share count.
US_GAAP_SHARES_OUTSTANDING_CONCEPT: Final = "CommonStockSharesOutstanding"
IFRS_SHARES_OUTSTANDING_CONCEPT: Final = "NumberOfSharesOutstanding"
SHARES_ISSUED_CONCEPT: Final = "CommonStockSharesIssued"
TREASURY_SHARES_CONCEPT: Final = "TreasuryStockCommonShares"
SEC_DIRECT_COMMON_SHARES_FIELDS: Final[Mapping[str, str]] = {
    US_GAAP: f"{US_GAAP}:{US_GAAP_SHARES_OUTSTANDING_CONCEPT}",
    IFRS_FULL: f"{IFRS_FULL}:{IFRS_SHARES_OUTSTANDING_CONCEPT}",
}
"""The provider field of a directly reported common share count, by taxonomy."""
SEC_DERIVED_COMMON_SHARES_FIELD: Final = (
    f"derived:{US_GAAP}:{SHARES_ISSUED_CONCEPT}-{US_GAAP}:{TREASURY_SHARES_CONCEPT}"
)
"""The provider field of a common share count derived as issued less treasury shares."""
_DIRECT_SHARE_CONCEPT: Final[Mapping[str, str]] = {
    US_GAAP: US_GAAP_SHARES_OUTSTANDING_CONCEPT,
    IFRS_FULL: IFRS_SHARES_OUTSTANDING_CONCEPT,
}
_SHARES_UNIT: Final = "shares"
_SHARES_DERIVATION: Final = "common shares issued - treasury common shares"


def _share_observations(source: InstantSource, namespace: str, concept_name: str) -> _Concept:
    """Read the share instants of one concept from the eligible annual filings.

    ``_Observation.currency`` holds the unit name (``shares``) for these.
    """
    observations = _concept_units(source.company_facts, namespace, concept_name).get(_SHARES_UNIT)
    usable: list[_Observation] = []
    other: list[_Observation] = []
    if isinstance(observations, Sequence) and not isinstance(observations, (str, bytes)):
        for raw in observations:
            parsed = _parse(raw, _SHARES_UNIT, source)
            if parsed is None:
                continue
            same = source.accession_taxonomies.get(parsed.accession, frozenset()) == frozenset({namespace})
            (usable if same else other).append(parsed)
    return _Concept(usable=tuple(usable), other_taxonomy=tuple(other))


def _select_share_counts(
    request: InstantSeriesRequest,
    source: InstantSource,
    namespace: str,
    pending: Sequence[date],
    absences: dict[date, InstantAbsence],
) -> InstantSeriesFacts:
    """Return the common share count at each pending year-end, by the direct path else issued less treasury.

    At a date the direct count is the newest filing's value, and two values of equal priority that disagree (the
    classes of a multi-class issuer) make the date absent as a conflict, with no fallback to the derived path. Only
    where no direct count is tagged is issued less treasury taken, from the newest single filing that tags both at the
    date; terms of different filings are never mixed. A count is never taken from another date.
    """
    direct = _share_observations(source, namespace, _DIRECT_SHARE_CONCEPT[namespace])
    derivable = namespace == US_GAAP
    issued = _share_observations(source, US_GAAP, SHARES_ISSUED_CONCEPT) if derivable else None
    treasury = _share_observations(source, US_GAAP, TREASURY_SHARES_CONCEPT) if derivable else None
    facts: dict[date, ProviderFact] = {}
    for day in pending:
        result = _select_at(direct.usable, day)
        if isinstance(result, _Observation) and result.value <= 0:
            absences[day] = _absence(
                day,
                InstantAbsenceReason.CONFLICT,
                f"The reported count {SEC_DIRECT_COMMON_SHARES_FIELDS[namespace]} at {day} is not positive.",
            )
            continue
        if isinstance(result, _Observation):
            facts[day] = _direct_share_fact(request, source, namespace, result)
            continue
        if result is _CONFLICT:
            absences[day] = _absence(
                day,
                InstantAbsenceReason.CONFLICT,
                f"Eligible filings disagree on {SEC_DIRECT_COMMON_SHARES_FIELDS[namespace]} at {day}.",
            )
            continue
        derived = (
            _derive_share_count(request, source, issued.usable, treasury.usable, day)
            if issued is not None and treasury is not None
            else None
        )
        if isinstance(derived, ProviderFact):
            facts[day] = derived
        elif isinstance(derived, InstantAbsence):
            absences[day] = derived
        else:
            absences[day] = _missing_share_count(day, namespace, direct, issued, treasury)
    return InstantSeriesFacts(facts=tuple(facts.values()), absences=_ordered(absences))


def _share_fact(  # noqa: PLR0913
    request: InstantSeriesRequest,
    source: InstantSource,
    *,
    value: float,
    provider_field: str,
    day: date,
    accession: str,
    available_at: datetime,
    notes: tuple[str, ...],
    sources: tuple[ProviderShareSource, ...] = (),
) -> ProviderFact:
    """Build a share-count fact: units ``shares``, no currency, the filing it came from in its notes."""
    return ProviderFact(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id=request.subject_id,
        field_name=request.field_name,
        value=value,
        units=instant_series_unit(request.field_name),
        provider_id=SEC_PROVIDER_ID,
        provider_field=provider_field,
        retrieved_at=source.retrieved_at,
        basis="fiscal_year_end",
        observation_period_end=_end_of(day),
        available_at=available_at,
        period_kind=PeriodKind.INSTANT,
        source_facts=sources,
        source_transformation=_SHARES_DERIVATION if sources else None,
        notes=(f"accession={accession}", *notes, "available_at uses EDGAR acceptanceDateTime"),
        provider_fact_id=f"{accession}:{provider_field}:{_SHARES_UNIT}:{day.isoformat()}",
    )


def _direct_share_fact(
    request: InstantSeriesRequest, source: InstantSource, namespace: str, item: _Observation
) -> ProviderFact:
    """Build the fact of a directly reported count."""
    return _share_fact(
        request,
        source,
        value=item.value,
        provider_field=SEC_DIRECT_COMMON_SHARES_FIELDS[namespace],
        day=item.end,
        accession=item.accession,
        available_at=item.available_at,
        notes=(f"form={item.form}", "definition=period-end common stock shares outstanding; reported directly"),
    )


def _derive_share_count(
    request: InstantSeriesRequest,
    source: InstantSource,
    issued: Sequence[_Observation],
    treasury: Sequence[_Observation],
    day: date,
) -> ProviderFact | InstantAbsence | None:
    """Derive issued less treasury shares at ``day`` from one filing, or return ``None`` when no filing tags both."""
    accessions = sorted(
        {item.accession for item in issued if item.end == day}
        & {item.accession for item in treasury if item.end == day},
        key=lambda accession: source.acceptance_by_accession[accession],
        reverse=True,
    )
    if not accessions:
        return None
    accession = accessions[0]
    first, second = _one_value(issued, accession, day), _one_value(treasury, accession, day)
    if not isinstance(first, _Observation) or not isinstance(second, _Observation):
        return _absence(day, InstantAbsenceReason.CONFLICT, f"The terms of the share count disagree at {day}.")
    value = first.value - second.value
    if first.value <= 0 or second.value < 0 or value <= 0:
        return _absence(day, InstantAbsenceReason.CONFLICT, f"The derived share count at {day} is not positive.")
    sources = tuple(
        ProviderShareSource(
            subject_id=request.subject_id,
            provider_id=SEC_PROVIDER_ID,
            provider_field=f"{US_GAAP}:{name}",
            value=term.value,
            retrieved_at=source.retrieved_at,
            observation_period_end=_end_of(day),
            available_at=term.available_at,
            provider_fact_id=f"{accession}:{US_GAAP}:{name}:{_SHARES_UNIT}:{day.isoformat()}",
        )
        for name, term in ((SHARES_ISSUED_CONCEPT, first), (TREASURY_SHARES_CONCEPT, second))
    )
    return _share_fact(
        request,
        source,
        value=value,
        provider_field=SEC_DERIVED_COMMON_SHARES_FIELD,
        day=day,
        accession=accession,
        available_at=first.available_at,
        notes=(f"derivation={_SHARES_DERIVATION}", "every term tagged at the same date in the same filing"),
        sources=sources,
    )


def _missing_share_count(
    day: date, namespace: str, direct: _Concept, issued: _Concept | None, treasury: _Concept | None
) -> InstantAbsence:
    """Say why a date has no share count."""
    concepts = [direct, *(item for item in (issued, treasury) if item is not None)]
    if any(item.end == day for concept in concepts for item in concept.other_taxonomy):
        return _absence(
            day,
            InstantAbsenceReason.BASIS_MISMATCH,
            f"Only a filing on another taxonomy than {namespace} reports a share count at {day}.",
        )
    return _absence(
        day, InstantAbsenceReason.NOT_TAGGED, f"No {namespace} share count, direct or issued less treasury, at {day}."
    )


def _note_related_concepts(
    request: InstantSeriesRequest,
    source: InstantSource,
    namespace: str,
    facts: dict[date, ProviderFact],
    absences: dict[date, InstantAbsence],
) -> None:
    """Record, on each absence and fact, the related concept the evidence lists for the field that is tagged there."""
    related = IFRS_RELATED if namespace == IFRS_FULL else US_GAAP_RELATED
    for day, absence in list(absences.items()):
        if absence.reason in {InstantAbsenceReason.NOT_TAGGED, InstantAbsenceReason.OTHER_CONCEPT}:
            absences[day] = replace(
                absence, related_concept=_related_tagged(source, namespace, related.get(request.field_name, ()), day)
            )
    for day, fact in list(facts.items()):
        found = _related_tagged(source, namespace, related.get(request.field_name, ()), day)
        if found is not None:
            facts[day] = replace(fact, notes=(*fact.notes, f"related_concept_tagged={found}"))


def _related_tagged(source: InstantSource, namespace: str, concepts: tuple[str, ...], day: date) -> str | None:
    """Return the first related concept tagged at ``day`` in an eligible filing on the anchor taxonomy."""
    return next(
        (
            f"{namespace}:{name}"
            for name in concepts
            if any(item.end == day for item in _observations(source, namespace, name).usable)
        ),
        None,
    )


def _date_checks(
    request: InstantSeriesRequest, source: InstantSource, absences: dict[date, InstantAbsence]
) -> list[date]:
    """Record the dates no filing can answer and return the dates still to read."""
    pending: list[date] = []
    for day in request.period_ends:
        if not source.cik_matches:
            absences[day] = _absence(
                day, InstantAbsenceReason.UNSUPPORTED, "Company Facts do not declare the resolved CIK."
            )
        elif not source.acceptance_by_accession:
            absences[day] = _absence(
                day, InstantAbsenceReason.NO_ANCHOR_FILING, "No annual filing was accepted at or before the boundary."
            )
        elif source.taxonomy not in {US_GAAP, IFRS_FULL}:
            absences[day] = _absence(
                day,
                InstantAbsenceReason.UNSUPPORTED,
                "The anchor filing does not tag exactly one of us-gaap and ifrs-full.",
            )
        elif day > source.boundary.date():
            absences[day] = _absence(day, InstantAbsenceReason.AFTER_BOUNDARY, f"{day} is after the boundary.")
        else:
            pending.append(day)
    return pending


@dataclass(frozen=True)
class _Concept:
    """The values of one concept: those usable on the anchor taxonomy, and how many were set aside."""

    usable: tuple[_Observation, ...]
    other_taxonomy: tuple[_Observation, ...]


def _observations(source: InstantSource, namespace: str, concept_name: str) -> _Concept:
    """Read the non-dimensional instants of one concept from the eligible annual filings."""
    units = _concept_units(source.company_facts, namespace, concept_name)
    usable: list[_Observation] = []
    other: list[_Observation] = []
    for unit_name, observations in units.items():
        currency = _currency(unit_name)
        if currency is None or not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
            continue
        for raw in observations:
            parsed = _parse(raw, currency, source)
            if parsed is None:
                continue
            same = source.accession_taxonomies.get(parsed.accession, frozenset()) == frozenset({namespace})
            (usable if same else other).append(parsed)
    return _Concept(usable=tuple(usable), other_taxonomy=tuple(other))


def _concept_units(payload: Mapping[object, object], namespace: str, concept_name: str) -> Mapping[object, object]:
    """Return the units mapping of one concept, or an empty mapping."""
    facts = payload.get("facts")
    group = facts.get(namespace) if isinstance(facts, Mapping) else None
    concept = group.get(concept_name) if isinstance(group, Mapping) else None
    units = concept.get("units") if isinstance(concept, Mapping) else None
    return units if isinstance(units, Mapping) else {}


def _parse(raw: object, currency: str, source: InstantSource) -> _Observation | None:
    """Parse one instant of an eligible annual filing, or return ``None``."""
    if not isinstance(raw, Mapping) or "start" in raw:
        return None
    value, end, accession = raw.get("val"), raw.get("end"), raw.get("accn")
    form = raw.get("form")
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        return None
    if not isinstance(end, str) or not isinstance(accession, str) or not isinstance(form, str):
        return None
    available_at = source.acceptance_by_accession.get(accession)
    try:
        day = date.fromisoformat(end)
    except ValueError:
        return None
    if available_at is None or available_at > source.boundary or day > source.boundary.date():
        return None
    return _Observation(float(value), currency, day, accession, available_at, form)


class _Conflict:
    """Marker: eligible filings of equal priority disagree."""


_CONFLICT: Final = _Conflict()


def _select_at(observations: Sequence[_Observation], day: date) -> _Observation | _Conflict | None:
    """Return the newest filing's value at ``day``, a conflict, or ``None`` when there is none."""
    at_day = [item for item in observations if item.end == day]
    if not at_day:
        return None
    newest = max(item.available_at for item in at_day)
    latest = [item for item in at_day if item.available_at == newest]
    if len({(item.value, item.currency) for item in latest}) != 1:
        return _CONFLICT
    return latest[0]


def _fact_of(
    request: InstantSeriesRequest, source: InstantSource, namespace: str, concept: str, item: _Observation
) -> ProviderFact:
    """Build the provider fact for one selected observation."""
    provider_field = f"{namespace}:{concept}"
    return ProviderFact(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id=request.subject_id,
        field_name=request.field_name,
        value=item.value,
        units=FinancialUnit.CURRENCY,
        provider_id=SEC_PROVIDER_ID,
        provider_field=provider_field,
        retrieved_at=source.retrieved_at,
        basis="fiscal_year_end",
        currency=item.currency,
        observation_period_end=_end_of(item.end),
        available_at=item.available_at,
        period_kind=PeriodKind.INSTANT,
        notes=(
            f"accession={item.accession}",
            f"form={item.form}",
            f"concept_priority={'>'.join(_priority(request, namespace))}",
            "available_at uses EDGAR acceptanceDateTime",
        ),
        provider_fact_id=f"{item.accession}:{provider_field}:{item.currency}:{item.end.isoformat()}",
    )


def _priority(request: InstantSeriesRequest, namespace: str) -> tuple[str, ...]:
    """Return the field's listed concepts for the taxonomy."""
    return (US_GAAP_CONCEPTS if namespace == US_GAAP else IFRS_CONCEPTS)[request.field_name]


def _derive_total_liabilities(
    request: InstantSeriesRequest, source: InstantSource, day: date
) -> ProviderFact | InstantAbsence | None:
    """Derive total liabilities at ``day`` from the terms of one filing, or return ``None`` when a term is missing.

    The newest eligible filing that tags both required terms at ``day`` supplies every term. Terms from different
    filings are never mixed. A filing whose terms disagree, or whose result is negative, is a conflict.
    """
    equity_total = _observations(source, US_GAAP, _LIABILITIES_AND_EQUITY).usable
    equity = _observations(source, US_GAAP, _EQUITY_WITH_NONCONTROLLING).usable
    temporary = [_observations(source, US_GAAP, name).usable for name in _TEMPORARY_EQUITY]
    accessions = sorted(
        {item.accession for item in equity_total if item.end == day}
        & {item.accession for item in equity if item.end == day},
        key=lambda accession: source.acceptance_by_accession[accession],
        reverse=True,
    )
    if not accessions:
        return None
    accession = accessions[0]
    terms = [
        _one_value(equity_total, accession, day),
        _one_value(equity, accession, day),
    ]
    temporary_name, temporary_term = next(
        (
            (name, term)
            for name, items in zip(_TEMPORARY_EQUITY, temporary, strict=True)
            if (term := _one_value(items, accession, day)) is not None
        ),
        (None, None),
    )
    if any(term is _CONFLICT for term in terms) or temporary_term is _CONFLICT:
        return _absence(day, InstantAbsenceReason.CONFLICT, f"The terms of total liabilities disagree at {day}.")
    total, equity_term = terms
    assert isinstance(total, _Observation)
    assert isinstance(equity_term, _Observation)
    extra = temporary_term if isinstance(temporary_term, _Observation) else None
    if total.currency != equity_term.currency or (extra is not None and extra.currency != total.currency):
        return _absence(
            day, InstantAbsenceReason.BASIS_MISMATCH, f"The terms of total liabilities at {day} differ in currency."
        )
    value = total.value - equity_term.value - (extra.value if extra is not None else 0.0)
    if value < 0:
        return _absence(day, InstantAbsenceReason.CONFLICT, f"The derived total liabilities at {day} is negative.")
    names = [_LIABILITIES_AND_EQUITY, _EQUITY_WITH_NONCONTROLLING]
    used = [total, equity_term]
    if extra is not None and temporary_name is not None:
        names.append(temporary_name)
        used.append(extra)
    provider_field = "derived:" + "-".join(f"{US_GAAP}:{name}" for name in names)
    sources = tuple(
        ProviderAmountSource(
            subject_id=request.subject_id,
            provider_id=SEC_PROVIDER_ID,
            provider_field=f"{US_GAAP}:{name}",
            value=term.value,
            currency=term.currency,
            retrieved_at=source.retrieved_at,
            observation_period_end=_end_of(term.end),
            available_at=term.available_at,
            provider_fact_id=f"{term.accession}:{US_GAAP}:{name}:{term.currency}:{term.end.isoformat()}",
        )
        for name, term in zip(names, used, strict=True)
    )
    return ProviderFact(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id=request.subject_id,
        field_name=request.field_name,
        value=value,
        units=FinancialUnit.CURRENCY,
        provider_id=SEC_PROVIDER_ID,
        provider_field=provider_field,
        retrieved_at=source.retrieved_at,
        basis="fiscal_year_end",
        currency=total.currency,
        observation_period_end=_end_of(day),
        available_at=total.available_at,
        period_kind=PeriodKind.INSTANT,
        source_facts=sources,
        source_transformation=_DERIVATION_TRANSFORMATION,
        notes=(
            f"accession={accession}",
            f"derivation={_DERIVATION_TRANSFORMATION}",
            "every term tagged at the same date in the same filing",
        ),
        provider_fact_id=f"{accession}:{provider_field}:{total.currency}:{day.isoformat()}",
    )


def _one_value(observations: Sequence[_Observation], accession: str, day: date) -> _Observation | _Conflict | None:
    """Return the single value one filing reports at ``day``, a conflict, or ``None``."""
    at_day = [item for item in observations if item.accession == accession and item.end == day]
    if not at_day:
        return None
    if len({(item.value, item.currency) for item in at_day}) != 1:
        return _CONFLICT
    return at_day[0]


def _missing(
    day: date,
    concepts: tuple[str, ...],
    chosen: str | None,
    by_concept: Mapping[str, _Concept],
    namespace: str,
) -> InstantAbsence:
    """Say why a date has no value for the run's concept."""
    if any(item.end == day for concept in concepts for item in by_concept[concept].other_taxonomy):
        return _absence(
            day,
            InstantAbsenceReason.BASIS_MISMATCH,
            f"Only a filing on another taxonomy than {namespace} reports {day}.",
        )
    if any(item.end == day for concept in concepts if concept != chosen for item in by_concept[concept].usable):
        return _absence(
            day,
            InstantAbsenceReason.OTHER_CONCEPT,
            f"{namespace}:{chosen} is not tagged at {day}; another listed concept is, and none is substituted.",
        )
    return _absence(day, InstantAbsenceReason.NOT_TAGGED, f"None of {', '.join(concepts)} is tagged at {day}.")


def _one_currency(request: InstantSeriesRequest, series: InstantSeriesFacts) -> InstantSeriesFacts:
    """Keep the values in the currency of the newest year-end and report the rest as a basis mismatch."""
    if len({fact.currency for fact in series.facts}) <= 1:
        return series
    newest = max(series.facts, key=lambda fact: fact.observation_period_end or datetime.min.replace(tzinfo=UTC))
    kept = tuple(fact for fact in series.facts if fact.currency == newest.currency)
    dropped = tuple(
        _absence(
            (fact.observation_period_end or _end_of(request.period_ends[0])).date(),
            InstantAbsenceReason.BASIS_MISMATCH,
            f"The value is in {fact.currency}; the run's currency is {newest.currency}.",
        )
        for fact in series.facts
        if fact.currency != newest.currency
    )
    return InstantSeriesFacts(facts=kept, absences=tuple(sorted(series.absences + dropped, key=lambda a: a.period_end)))


def _unsupported_detail(request: InstantSeriesRequest, namespace: str) -> str:
    """Explain an unsupported mapping."""
    return f"{request.field_name.value} has no approved {namespace} mapping; it is unavailable, not zero."


def _absence(day: date, reason: InstantAbsenceReason, detail: str) -> InstantAbsence:
    """Build one absence."""
    return InstantAbsence(period_end=day, reason=reason, detail=detail)


def _ordered(absences: Mapping[date, InstantAbsence]) -> tuple[InstantAbsence, ...]:
    """Return the absences in date order."""
    return tuple(absences[day] for day in sorted(absences))


def _currency(unit_name: object) -> str | None:
    """Return the three-letter currency code of a monetary unit, or ``None``."""
    code = str(unit_name).strip()
    return code.upper() if len(code) == 3 and code.isalpha() else None


def _end_of(day: date) -> datetime:
    """Return the end of the day in UTC, as the other balance-sheet facts date their period end."""
    return datetime.combine(day, time.max, tzinfo=UTC)
