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
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from src.data.financial.provenance import (
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
    if field_name in (
        FinancialField.STOCKHOLDERS_EQUITY,
        FinancialField.OPERATING_CASH_FLOW,
        FinancialField.CAPITAL_EXPENDITURES,
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


class FinancialUnit(StrEnum):
    """Unit of measurement for a financial fact value."""

    CURRENCY_PER_SHARE = "currency_per_share"
    PERCENTAGE_POINTS = "percentage_points"
    CURRENCY = "currency"
    SHARES = "shares"


# These provider-neutral fields support requests for multiple completed annual
# observations. Provider-specific eligibility and identity rules remain in the
# individual adapters rather than becoming properties of ``FinancialField``.
_COMPLETED_ANNUAL_SERIES_FIELDS = frozenset(
    {
        FinancialField.EPS,
        FinancialField.OPERATING_CASH_FLOW,
        FinancialField.CAPITAL_EXPENDITURES,
        FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES,
    }
)


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class FinancialProviderError(Exception):
    """Operational failure of a financial facts provider.

    Represents an *operational* provider failure (e.g. transport or service
    error).  It is NOT used to signal an ordinary missing fact — an empty
    result tuple represents unavailability.
    """


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
# ProviderFact
# ---------------------------------------------------------------------------


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

    def __post_init__(self) -> None:
        """Normalize identifiers and validate all provider-fact invariants."""
        normalized_subject = _normalize_subject_id(self.subject_kind, self.subject_id)
        canonical_provider = _canonicalize_provider_id(self.provider_id)
        normalized_basis = _normalize_optional_basis(self.basis)

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

    def fetch_facts(self, request: FinancialFactRequest) -> tuple[ProviderFact, ...]:
        """Return the provider observations for *request*, or an empty tuple.

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
