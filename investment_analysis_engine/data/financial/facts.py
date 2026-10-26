"""Provider-neutral financial-fact contracts for deterministic analysis.

Defines the closed semantic field/unit enumerations, the request and
provider-fact payloads, the operational provider-failure exception, and the
structural ``FinancialFactsProvider`` protocol for field-level resolution.

These contracts are *provider-neutral*: they name semantic fields
(``current_price``, ``eps``, ``bvps``, ``current_aaa_yield``) plus the narrow
accounting/share-count components required for a transparent BVPS derivation.
They name semantic units rather than any specific vendor's field identifiers.
No resolver, cache, fallback, or provider adapter is implemented here—only
the shared provider-boundary contracts.

All ``datetime`` fields, when present, must be timezone-aware; naive datetimes
raise ``ValueError`` at construction.  Subject-ID and provider-ID
normalization is identical to the C1 cache-key conventions.
"""

from __future__ import annotations

import math
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from investment_analysis_engine.core.failure_codes import FailureReasonCode, provider_reason_code
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind, require_provider_identity
from investment_analysis_engine.data.financial.provenance import (
    AccountingScope,
    CapitalExpenditureSign,
    FinancialSubjectKind,
    PeriodKind,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _require_timezone_aware(dt: datetime, *, field_name: str) -> None:
    """Raise ``ValueError`` if *dt* is not timezone-aware."""
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        msg = f"{field_name} must be timezone-aware (received {dt!r})."
        raise ValueError(msg)


def _require_finite(value: float, *, field_name: str) -> None:
    """Raise ``ValueError`` if *value* is not finite."""
    if not math.isfinite(value):
        msg = f"{field_name} must be finite (received {value!r})."
        raise ValueError(msg)


def _require_non_empty(text: str, *, field_name: str) -> None:
    """Raise ``ValueError`` if *text* is empty or whitespace-only."""
    if not text.strip():
        msg = f"{field_name} must be a non-empty string."
        raise ValueError(msg)


def _normalize_subject_id(subject_kind: FinancialSubjectKind, subject_id: str) -> str:
    """Normalize *subject_id* per C1 cache-key conventions.

    SECURITY uses ``strip().upper()``; MACRO uses ``strip()`` (case preserved).
    The result must remain non-empty.
    """
    normalized = subject_id.strip().upper() if subject_kind is FinancialSubjectKind.SECURITY else subject_id.strip()
    if not normalized:
        msg = "subject_id must be non-empty after normalization."
        raise ValueError(msg)
    return normalized


def _canonicalize_provider_id(provider_id: str) -> str:
    """Canonicalize a provider ID with ``strip().lower()`` (must stay non-empty)."""
    canonical = provider_id.strip().lower()
    if not canonical:
        msg = "provider_id must be non-empty after canonicalization."
        raise ValueError(msg)
    return canonical


def _validate_field_subject(field_name: FinancialField, subject_kind: FinancialSubjectKind) -> None:
    """Enforce the semantic field/subject pairing rule."""
    if field_name is FinancialField.CURRENT_AAA_YIELD:
        if subject_kind is not FinancialSubjectKind.MACRO:
            msg = "CURRENT_AAA_YIELD requires a MACRO subject."
            raise ValueError(msg)
    elif subject_kind is not FinancialSubjectKind.SECURITY:
        msg = f"{field_name.name} requires a SECURITY subject."
        raise ValueError(msg)


def _expected_unit(field_name: FinancialField) -> FinancialUnit:
    """Return the unit a given field must carry."""
    if field_name is FinancialField.CURRENT_AAA_YIELD:
        return FinancialUnit.PERCENTAGE_POINTS
    if (
        field_name
        in (
            FinancialField.STOCKHOLDERS_EQUITY,
            FinancialField.OPERATING_CASH_FLOW,
            FinancialField.CAPITAL_EXPENDITURES,
        )
        or field_name in INSTANT_SERIES_FIELDS
        or field_name in ANNUAL_PERIOD_FIELDS
    ):
        return FinancialUnit.CURRENCY
    if field_name in (
        FinancialField.COMMON_SHARES_OUTSTANDING,
        FinancialField.PREFERRED_SHARES_OUTSTANDING,
        FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES,
    ):
        return FinancialUnit.SHARES
    return FinancialUnit.CURRENCY_PER_SHARE


def _normalize_optional_basis(basis: str | None) -> str | None:
    """Return a stripped basis, or ``None``; a supplied empty basis is rejected."""
    if basis is None:
        return None
    stripped = basis.strip()
    if not stripped:
        msg = "basis must be non-empty when provided."
        raise ValueError(msg)
    return stripped


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FinancialField(StrEnum):
    """Provider-neutral semantic field names for a financial fact."""

    CURRENT_PRICE = "current_price"
    EPS = "eps"
    BVPS = "bvps"
    CURRENT_AAA_YIELD = "current_aaa_yield"
    STOCKHOLDERS_EQUITY = "stockholders_equity"
    COMMON_SHARES_OUTSTANDING = "common_shares_outstanding"
    PREFERRED_SHARES_OUTSTANDING = "preferred_shares_outstanding"
    OPERATING_CASH_FLOW = "operating_cash_flow"
    CAPITAL_EXPENDITURES = "capital_expenditures"
    WEIGHTED_AVERAGE_DILUTED_SHARES = "weighted_average_diluted_shares"
    TOTAL_ASSETS = "total_assets"
    TOTAL_LIABILITIES = "total_liabilities"
    CURRENT_ASSETS = "current_assets"
    CURRENT_LIABILITIES = "current_liabilities"
    CASH_AND_EQUIVALENTS = "cash_and_equivalents"
    SHORT_TERM_INVESTMENTS = "short_term_investments"
    LONG_TERM_INVESTMENTS = "long_term_investments"
    NET_PPE = "net_ppe"
    RECEIVABLES = "receivables"
    RETAINED_EARNINGS = "retained_earnings"
    SHORT_TERM_BORROWINGS = "short_term_borrowings"
    CURRENT_PORTION_OF_LONG_TERM_DEBT = "current_portion_of_long_term_debt"
    NONCURRENT_LONG_TERM_DEBT = "noncurrent_long_term_debt"
    LONG_TERM_DEBT_TOTAL = "long_term_debt_total"
    LEASE_LIABILITIES_AS_DEBT = "lease_liabilities_as_debt"
    PREFERRED_STOCK = "preferred_stock"
    NONCONTROLLING_INTEREST = "noncontrolling_interest"
    SALES = "sales"
    COST_OF_REVENUE = "cost_of_revenue"
    GROSS_PROFIT = "gross_profit"
    OPERATING_INCOME = "operating_income"
    SELLING_GENERAL_ADMINISTRATIVE = "selling_general_administrative"
    DEPRECIATION_AND_AMORTIZATION = "depreciation_and_amortization"
    DEPRECIATION = "depreciation"
    INTEREST_EXPENSE = "interest_expense"
    PRETAX_INCOME = "pretax_income"
    INCOME_TAX_EXPENSE = "income_tax_expense"
    NET_INCOME = "net_income"
    INCOME_FROM_CONTINUING_OPERATIONS = "income_from_continuing_operations"
    DISCONTINUED_OPERATIONS = "discontinued_operations"


class FinancialUnit(StrEnum):
    """Unit of measurement for a financial fact value."""

    CURRENCY_PER_SHARE = "currency_per_share"
    PERCENTAGE_POINTS = "percentage_points"
    CURRENCY = "currency"
    SHARES = "shares"


# Balance-sheet amounts at a date. They are served only by an ``InstantSeriesRequest``; the
# latest-only ``FinancialFactRequest`` path does not offer them.
INSTANT_SERIES_FIELDS = frozenset(
    {
        FinancialField.TOTAL_ASSETS,
        FinancialField.TOTAL_LIABILITIES,
        FinancialField.CURRENT_ASSETS,
        FinancialField.CURRENT_LIABILITIES,
        FinancialField.CASH_AND_EQUIVALENTS,
        FinancialField.SHORT_TERM_INVESTMENTS,
        FinancialField.LONG_TERM_INVESTMENTS,
        FinancialField.NET_PPE,
        FinancialField.RECEIVABLES,
        FinancialField.RETAINED_EARNINGS,
        FinancialField.SHORT_TERM_BORROWINGS,
        FinancialField.CURRENT_PORTION_OF_LONG_TERM_DEBT,
        FinancialField.NONCURRENT_LONG_TERM_DEBT,
        FinancialField.LONG_TERM_DEBT_TOTAL,
        FinancialField.LEASE_LIABILITIES_AS_DEBT,
        FinancialField.PREFERRED_STOCK,
        FinancialField.NONCONTROLLING_INTEREST,
    }
)

# Income-statement and cash-flow amounts of a completed fiscal year, served by the completed-annual series request.
ANNUAL_PERIOD_FIELDS = frozenset(
    {
        FinancialField.SALES,
        FinancialField.COST_OF_REVENUE,
        FinancialField.GROSS_PROFIT,
        FinancialField.OPERATING_INCOME,
        FinancialField.SELLING_GENERAL_ADMINISTRATIVE,
        FinancialField.DEPRECIATION_AND_AMORTIZATION,
        FinancialField.DEPRECIATION,
        FinancialField.INTEREST_EXPENSE,
        FinancialField.PRETAX_INCOME,
        FinancialField.INCOME_TAX_EXPENSE,
        FinancialField.NET_INCOME,
        FinancialField.INCOME_FROM_CONTINUING_OPERATIONS,
        FinancialField.DISCONTINUED_OPERATIONS,
    }
)

# The basis of a common-share count taken from the cover page of an annual filing, as against the balance-sheet
# count at a fiscal year-end that the basis "fiscal_year_end" asks for.
COVER_PAGE_BASIS = "cover_page"

# Consecutive fiscal year-ends are a year apart, give or take the 52/53-week variation of a fiscal calendar. The
# bounds are those of the completed-annual duration tolerance, so a quarter-end or a stub date is never a neighbor.
_MIN_YEAR_END_GAP_DAYS = 335
_MAX_YEAR_END_GAP_DAYS = 395

# These provider-neutral fields support requests for multiple completed annual
# observations. Provider-specific eligibility and identity rules remain in the
# individual adapters rather than becoming properties of ``FinancialField``.
_COMPLETED_ANNUAL_SERIES_FIELDS = (
    frozenset(
        {
            FinancialField.EPS,
            FinancialField.OPERATING_CASH_FLOW,
            FinancialField.CAPITAL_EXPENDITURES,
            FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES,
        }
    )
    | ANNUAL_PERIOD_FIELDS
)


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class FinancialProviderError(Exception):
    """Operational failure of a financial facts provider.

    Represents an *operational* provider failure (e.g. transport or service
    error).  It is NOT used to signal an ordinary missing fact — an empty
    result tuple represents unavailability.

    ``kind`` and ``provider_id`` say what the adapter observed and which provider it was; both are
    ``None`` for a failure the adapter did not classify.
    """

    def __init__(self, *args: object, kind: ProviderFailureKind | None = None, provider_id: str | None = None) -> None:
        """Carry the failure kind and the provider that failed beside the message."""
        require_provider_identity(kind, provider_id)
        super().__init__(*args)
        self.kind = kind
        self.provider_id = provider_id

    @property
    def reason_code(self) -> FailureReasonCode:
        """Return the stable code of the recorded kind, or ``provider_error`` when the adapter did not classify it."""
        return provider_reason_code(self.kind)


# ---------------------------------------------------------------------------
# FinancialFactRequest
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FinancialFactRequest:
    """A provider-neutral request for one semantic financial field.

    ``as_of`` is ``None`` for a current request; it is never replaced with the
    wall-clock time. ``observation_count`` greater than one requires
    ``basis="fiscal_year"`` and is supported for EPS, operating cash flow, and
    capital expenditures.

    Normalization (applied in ``__post_init__``):
        - SECURITY ``subject_id``: ``strip().upper()``
        - MACRO ``subject_id``: ``strip()`` (case preserved)
        - ``provider_id``: ``strip().lower()``
        - ``basis``: ``strip()`` if present; empty/whitespace-only rejected

    Attributes:
        subject_kind: SECURITY or MACRO.
        subject_id: Security symbol (normalized) or macro identifier.
        field_name: One of the supported semantic ``FinancialField`` values.
        provider_id: Non-empty provider identifier (normalized lowercase).
        basis: Basis/variant label, or None.
        as_of: None = current; timezone-aware = historical boundary.
        observation_count: Number of observations requested (>= 1; fiscal-year
            series are supported for EPS, operating cash flow, and CapEx).
    """

    subject_kind: FinancialSubjectKind
    subject_id: str
    field_name: FinancialField
    provider_id: str
    basis: str | None = None
    as_of: datetime | None = None
    observation_count: int = 1

    def __post_init__(self) -> None:
        """Normalize identifiers and validate all request invariants."""
        normalized_subject = _normalize_subject_id(self.subject_kind, self.subject_id)
        canonical_provider = _canonicalize_provider_id(self.provider_id)
        normalized_basis = _normalize_optional_basis(self.basis)

        if self.as_of is not None:
            _require_timezone_aware(self.as_of, field_name="as_of")

        if self.observation_count < 1:
            msg = f"observation_count must be >= 1 (received {self.observation_count})."
            raise ValueError(msg)

        _validate_field_subject(self.field_name, self.subject_kind)

        if self.observation_count > 1 and (
            self.field_name not in _COMPLETED_ANNUAL_SERIES_FIELDS or self.basis != "fiscal_year"
        ):
            msg = (
                "observation_count > 1 requires basis='fiscal_year' and field eps, "
                f"operating_cash_flow, or capital_expenditures (field {self.field_name.name} requested)."
            )
            raise ValueError(msg)

        object.__setattr__(self, "subject_id", normalized_subject)
        object.__setattr__(self, "provider_id", canonical_provider)
        object.__setattr__(self, "basis", normalized_basis)


# ---------------------------------------------------------------------------
# InstantSeriesRequest
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InstantSeriesRequest:
    """A request for one balance-sheet field at named fiscal year-ends.

    The latest-only ``FinancialFactRequest`` is left as it is. This request names the dates, and a provider returns
    what its filings report for exactly those dates, never the newest balance sheet in place of an earlier one.

    Normalization (applied in ``__post_init__``): ``subject_id`` is ``strip().upper()``, ``provider_id`` is
    ``strip().lower()``, and ``period_ends`` is sorted ascending.

    Attributes:
        subject_id: Security symbol (normalized).
        field_name: One of ``INSTANT_SERIES_FIELDS``.
        provider_id: Non-empty provider identifier (normalized lowercase).
        period_ends: At least one fiscal year-end; consecutive year-ends are a year apart within the annual-duration
            tolerance, so a quarter-end, a year-to-date date or a stub date is refused.
        as_of: None = current; timezone-aware = historical boundary.
    """

    subject_id: str
    field_name: FinancialField
    provider_id: str
    period_ends: tuple[date, ...]
    as_of: datetime | None = None

    def __post_init__(self) -> None:
        """Normalize identifiers and validate the field, the boundary and the dates."""
        if self.field_name not in INSTANT_SERIES_FIELDS:
            msg = f"{self.field_name.name} is not a balance-sheet field served by an instant series."
            raise ValueError(msg)
        if self.as_of is not None:
            _require_timezone_aware(self.as_of, field_name="as_of")
        ordered = tuple(sorted(self.period_ends))
        if not ordered:
            raise ValueError("period_ends must name at least one fiscal year-end.")
        for earlier, later in zip(ordered, ordered[1:], strict=False):
            gap = (later - earlier).days
            if not _MIN_YEAR_END_GAP_DAYS <= gap <= _MAX_YEAR_END_GAP_DAYS:
                msg = f"period_ends must be consecutive fiscal year-ends ({earlier} and {later} are {gap} days apart)."
                raise ValueError(msg)
        object.__setattr__(self, "subject_id", _normalize_subject_id(FinancialSubjectKind.SECURITY, self.subject_id))
        object.__setattr__(self, "provider_id", _canonicalize_provider_id(self.provider_id))
        object.__setattr__(self, "period_ends", ordered)


class InstantAbsenceReason(StrEnum):
    """Why an instant series has no value at a requested date."""

    NOT_TAGGED = "not_tagged"
    OTHER_CONCEPT = "other_concept"
    CONFLICT = "conflict"
    UNSUPPORTED = "unsupported"
    BASIS_MISMATCH = "basis_mismatch"
    AFTER_BOUNDARY = "after_boundary"
    NO_ANCHOR_FILING = "no_anchor_filing"


@dataclass(frozen=True)
class InstantAbsence:
    """A requested date with no value, and the reason.

    Attributes:
        period_end: The requested year-end.
        reason: Why there is no value. ``NOT_TAGGED`` says that none of the field's listed concepts is tagged for the
            date in any eligible filing; ``OTHER_CONCEPT`` says that the concept chosen for the run is not tagged for
            it while another listed concept is, and nothing is substituted.
        detail: A non-empty explanation.
        related_concept: For ``NOT_TAGGED`` and ``OTHER_CONCEPT``, the first concept the evidence records as related to
            the field (one that may hold part of the same quantity, such as Deere's ``DebtCurrent`` for the current
            portion of long-term debt) that is tagged at the date, as ``<taxonomy>:<concept>``; otherwise ``None``.
            It is never used as a value.
    """

    period_end: date
    reason: InstantAbsenceReason
    detail: str
    related_concept: str | None = None

    def __post_init__(self) -> None:
        """Require an explanation."""
        _require_non_empty(self.detail, field_name="detail")


@dataclass(frozen=True)
class InstantSeriesFacts:
    """What a provider reports for the requested dates: one fact per date present and the dates absent."""

    facts: tuple[ProviderFact, ...] = ()
    absences: tuple[InstantAbsence, ...] = ()

    def __post_init__(self) -> None:
        """Require instants, and each date either present or absent, once."""
        present = []
        for fact in self.facts:
            if fact.period_kind is not PeriodKind.INSTANT or fact.observation_period_end is None:
                raise ValueError("An instant series carries instant facts only.")
            present.append(fact.observation_period_end.date())
        dates = present + [item.period_end for item in self.absences]
        if len(set(dates)) != len(dates):
            raise ValueError("A requested date is either present or absent, once.")


# ---------------------------------------------------------------------------
# ProviderFact
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProviderShareSource:
    """Raw share-count evidence, distinct from positive shares outstanding."""

    subject_id: str
    provider_id: str
    provider_field: str
    value: float
    retrieved_at: datetime
    observation_period_end: datetime
    available_at: datetime
    provider_fact_id: str

    def __post_init__(self) -> None:
        """Allow zero raw shares while retaining finite, dated source evidence."""
        for value in (self.subject_id, self.provider_id, self.provider_field, self.provider_fact_id):
            _require_non_empty(value, field_name="share source identifier")
        _require_finite(self.value, field_name="share source value")
        if self.value < 0:
            raise ValueError("Raw share counts must be nonnegative.")
        for timestamp in (self.retrieved_at, self.observation_period_end, self.available_at):
            _require_timezone_aware(timestamp, field_name="share source timestamp")


@dataclass(frozen=True)
class ProviderAmountSource:
    """One term of an adapter derivation of a currency amount, which may be negative."""

    subject_id: str
    provider_id: str
    provider_field: str
    value: float
    currency: str
    retrieved_at: datetime
    observation_period_end: datetime
    available_at: datetime
    provider_fact_id: str

    def __post_init__(self) -> None:
        """Retain finite, dated, currency-denominated source evidence."""
        for value in (self.subject_id, self.provider_id, self.provider_field, self.currency, self.provider_fact_id):
            _require_non_empty(value, field_name="amount source identifier")
        _require_finite(self.value, field_name="amount source value")
        for timestamp in (self.retrieved_at, self.observation_period_end, self.available_at):
            _require_timezone_aware(timestamp, field_name="amount source timestamp")


@dataclass(frozen=True)
class ProviderFact:
    """A frozen provider-origin financial fact payload.

    This is NOT a ``ResolvedInput``: it carries no ``source_kind``, no
    resolver/cache state, no ``resolved_at``/``cache_schema_version``/
    ``origin_source_kind``.  Method applicability (e.g. whether a non-positive
    EPS/BVPS is usable) is decided by the calculator, not here — finite zero or
    negative EPS/BVPS remain representable.

    Normalization (applied in ``__post_init__``):
        - SECURITY ``subject_id``: ``strip().upper()``
        - MACRO ``subject_id``: ``strip()`` (case preserved)
        - ``provider_id``: ``strip().lower()``
        - ``currency``: ``strip().upper()`` for per-share facts

    Attributes:
        subject_kind: SECURITY or MACRO.
        subject_id: Security symbol (normalized) or macro identifier.
        field_name: One of the supported semantic ``FinancialField`` values.
        value: Finite numeric value.
        units: Unit of measurement; must match the field.
        provider_id: Non-empty provider identifier (normalized lowercase).
        provider_field: Non-empty exact upstream field/series identifier.
        retrieved_at: Timezone-aware time this fact was fetched.
        basis: Basis/variant label, or None.
        currency: ISO 4217 code (uppercase) for per-share facts; must be absent
            for percentage-point facts.
        observation_period_start: Timezone-aware start of a reporting period.
        observation_period_end: Timezone-aware end of a reporting period.
        observed_at: Timezone-aware point-observation timestamp.
        available_at: Timezone-aware time when fact became publicly knowable.
        notes: Immutable additional provenance annotations. Narrow BVPS derivation
            components use monetary or share-count units rather than per-share units.
        fiscal_year: Optional provider-supplied fiscal-year label for an annual
            observation; ``None`` when the period is not annual.
        period_kind: Optional classification of the reporting period.
        accounting_scope: Optional accounting scope of the source line item.
        capital_expenditure_sign: Optional sign convention for capital-expenditure amounts.
        provider_fact_id: Optional provider-specific fact identifier.
    """

    subject_kind: FinancialSubjectKind
    subject_id: str
    field_name: FinancialField
    value: float
    units: FinancialUnit
    provider_id: str
    provider_field: str
    retrieved_at: datetime
    basis: str | None = None
    currency: str | None = None
    observation_period_start: datetime | None = None
    observation_period_end: datetime | None = None
    observed_at: datetime | None = None
    available_at: datetime | None = None
    notes: tuple[str, ...] = field(default=())
    fiscal_year: int | None = None
    period_kind: PeriodKind | None = None
    accounting_scope: AccountingScope | None = None
    capital_expenditure_sign: CapitalExpenditureSign | None = None
    provider_fact_id: str | None = None
    source_facts: tuple[ProviderFact | ProviderShareSource | ProviderAmountSource, ...] = ()
    source_transformation: str | None = None

    def __post_init__(self) -> None:
        """Normalize identifiers and validate all provider-fact invariants."""
        normalized_subject = _normalize_subject_id(self.subject_kind, self.subject_id)
        canonical_provider = _canonicalize_provider_id(self.provider_id)
        normalized_basis = _normalize_optional_basis(self.basis)

        _validate_provider_sources(self, normalized_subject, canonical_provider)

        _require_non_empty(self.provider_field, field_name="provider_field")
        _require_finite(self.value, field_name="value")

        _require_timezone_aware(self.retrieved_at, field_name="retrieved_at")
        _validate_optional_datetime(self.observation_period_start, "observation_period_start")
        _validate_optional_datetime(self.observation_period_end, "observation_period_end")
        _validate_optional_datetime(self.observed_at, "observed_at")
        _validate_optional_datetime(self.available_at, "available_at")

        if (
            self.observation_period_start is not None
            and self.observation_period_end is not None
            and self.observation_period_start > self.observation_period_end
        ):
            msg = "observation_period_start must not be later than observation_period_end."
            raise ValueError(msg)

        _validate_provider_fact_metadata(self)

        _validate_field_subject(self.field_name, self.subject_kind)

        expected_unit = _expected_unit(self.field_name)
        if self.units is not expected_unit:
            msg = f"{self.field_name.name} requires units {expected_unit.name} (received {self.units.name})."
            raise ValueError(msg)

        # Currency rules depend on unit.
        if self.units in (FinancialUnit.CURRENCY_PER_SHARE, FinancialUnit.CURRENCY):
            if self.currency is None:
                msg = f"{self.field_name.name} ({self.units.value}) requires a currency."
                raise ValueError(msg)
            normalized_currency = self.currency.strip().upper()
            if not normalized_currency:
                msg = f"currency must be non-empty for {self.units.value} facts."
                raise ValueError(msg)
        else:
            if self.currency is not None:
                msg = f"{self.field_name.name} ({self.units.value}) must not carry a currency."
                raise ValueError(msg)
            normalized_currency = None

        # Strict positivity for current market price and AAA yield.
        if self.field_name is FinancialField.CURRENT_PRICE and self.value <= 0:
            msg = f"current_price must be strictly positive (received {self.value})."
            raise ValueError(msg)
        if self.field_name is FinancialField.CURRENT_AAA_YIELD and self.value <= 0:
            msg = f"current_aaa_yield must be strictly positive (received {self.value})."
            raise ValueError(msg)
        if self.field_name is FinancialField.COMMON_SHARES_OUTSTANDING and self.value <= 0:
            msg = f"common_shares_outstanding must be strictly positive (received {self.value})."
            raise ValueError(msg)
        if self.field_name is FinancialField.PREFERRED_SHARES_OUTSTANDING and self.value < 0:
            msg = f"preferred_shares_outstanding must be non-negative (received {self.value})."
            raise ValueError(msg)

        object.__setattr__(self, "subject_id", normalized_subject)
        object.__setattr__(self, "provider_id", canonical_provider)
        object.__setattr__(self, "basis", normalized_basis)
        object.__setattr__(self, "currency", normalized_currency)


def _validate_provider_fact_metadata(fact: ProviderFact) -> None:
    """Validate metadata field consistency invariants for a provider fact."""
    if fact.provider_fact_id is not None:
        _require_non_empty(fact.provider_fact_id, field_name="provider_fact_id")
    if fact.fiscal_year is not None and fact.fiscal_year < 1:
        msg = f"fiscal_year must be a positive year label (received {fact.fiscal_year})."
        raise ValueError(msg)
    if fact.fiscal_year is not None and fact.period_kind is not PeriodKind.COMPLETED_ANNUAL:
        msg = "fiscal_year requires period_kind=completed_annual."
        raise ValueError(msg)
    if fact.period_kind is PeriodKind.INSTANT and (
        fact.observation_period_start is not None or fact.observation_period_end is None
    ):
        msg = "period_kind=instant requires an observation_period_end and no observation_period_start."
        raise ValueError(msg)
    if fact.capital_expenditure_sign is not None and fact.field_name is not FinancialField.CAPITAL_EXPENDITURES:
        msg = "capital_expenditure_sign is only applicable to capital_expenditures facts."
        raise ValueError(msg)
    if fact.provider_fact_id is not None:
        object.__setattr__(fact, "provider_fact_id", fact.provider_fact_id.strip())


def _validate_optional_datetime(dt: datetime | None, field_name: str) -> None:
    """Validate an optional datetime field is timezone-aware if present."""
    if dt is not None:
        _require_timezone_aware(dt, field_name=field_name)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class FinancialFactsProvider(Protocol):
    """Structural protocol for financial facts providers.

    Contract semantics:
        - an empty tuple means the requested fact is unavailable;
        - one or more ``ProviderFact`` objects represent provider observations;
        - an operational provider failure is reported by raising
          ``FinancialProviderError`` (an ordinary missing fact is not).

    This protocol performs no cache or resolution behavior.
    """

    def fetch_facts(self, request: FinancialFactRequest, *, effective_as_of: datetime) -> tuple[ProviderFact, ...]:
        """Return the provider observations for *request*, or an empty tuple.

        Args:
            request: The provider-neutral fact request.
            effective_as_of: The resolved point-in-time cutoff (``request.as_of`` when
                given, otherwise the run's own execution clock) for any provider-side
                availability/eligibility decision. Never a substitute for the
                provider's own retrieval clock, and never itself a clock read.

        Raises:
            FinancialProviderError: On an operational provider failure.
        """
        ...


@runtime_checkable
class InstantSeriesProvider(Protocol):
    """Optional provider capability: balance-sheet fields at named fiscal year-ends."""

    def fetch_instant_series(self, request: InstantSeriesRequest, *, effective_as_of: datetime) -> InstantSeriesFacts:
        """Return the value at each requested date that the provider's filings report, and the dates they do not.

        Args:
            request: The exact-date series request.
            effective_as_of: The resolved point-in-time cutoff (``request.as_of`` when given, otherwise the run's own
                execution clock).

        Raises:
            FinancialProviderError: On an operational provider failure.
        """
        ...


@runtime_checkable
class AnalysisScopedFinancialFactsProvider(Protocol):
    """Optional provider capability for one immutable analysis data view."""

    def analysis_scope(
        self,
        *,
        subject_id: str,
        provider_id: str,
        as_of: datetime | None,
    ) -> AbstractContextManager[None]:
        """Return a context that reuses one provider snapshot for the analysis."""
        ...


def financial_facts_analysis_scope(
    provider: FinancialFactsProvider,
    *,
    subject_id: str,
    provider_id: str,
    as_of: datetime | None,
) -> AbstractContextManager[None]:
    """Use an analysis scope when supported, otherwise preserve legacy behavior."""
    if isinstance(provider, AnalysisScopedFinancialFactsProvider):
        return provider.analysis_scope(subject_id=subject_id, provider_id=provider_id, as_of=as_of)
    return nullcontext()


def _validate_provider_sources(fact: ProviderFact, subject: str, provider: str) -> None:
    """Reject incomplete or cross-subject adapter derivation provenance."""
    if bool(fact.source_facts) != bool(fact.source_transformation):
        raise ValueError("Provider source facts require a named transformation.")
    if fact.source_transformation is not None and not fact.source_transformation.strip():
        raise ValueError("Provider transformation must be non-empty.")
    if any(source.subject_id != subject or source.provider_id != provider for source in fact.source_facts):
        raise ValueError("Provider lineage must retain the same subject and provider.")
