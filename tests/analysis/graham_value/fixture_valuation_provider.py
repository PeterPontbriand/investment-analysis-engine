"""Deterministic fixture-backed ValuationFactsProvider for Step 2.3 Slice D.

Provides a small, internally coherent synthetic dataset sufficient to exercise
both Graham methods and the resolver/assembly contracts without network access.

All field identifiers, provider IDs, and series names are **synthetic fixture
identifiers** and do NOT represent verified production-provider capabilities.
Production-provider evidence belongs to Slice E1.

The provider satisfies the ``ValuationFactsProvider`` protocol:
    - ``fetch_facts(request) -> tuple[ProviderFact, ...]``
    - Empty tuple = fact unavailable.
    - ``ValuationProviderError`` = operational provider failure.
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.analysis.graham_value.facts import (
    ProviderFact,
    ValuationFactRequest,
    ValuationField,
    ValuationProviderError,
    ValuationUnit,
)
from src.analysis.graham_value.provenance import ValuationSubjectKind

# ---------------------------------------------------------------------------
# Synthetic identity constants (NOT production mappings)
# ---------------------------------------------------------------------------

PROVIDER_ID: str = "fixture-synth"
SECURITY_ID: str = "SYNTH"
MACRO_ID: str = "fixture-aaa"
CURRENCY: str = "USD"

# Synthetic field identifiers
FIELD_ANNUAL_EPS: str = "fx_annual_eps"
FIELD_TTM_EPS: str = "fx_ttm_eps"
FIELD_BVPS: str = "fx_bvps"
FIELD_QUOTE: str = "fx_quote"
FIELD_AAA_YIELD: str = "fx_aaa_yield"

# ---------------------------------------------------------------------------
# Fixed UTC timestamps
# ---------------------------------------------------------------------------

NOW = datetime(2025, 7, 1, 12, 0, tzinfo=UTC)
"""The fixed "current time" injected into the resolver clock."""

# Fiscal-year EPS periods
FY2022_START = datetime(2021, 7, 1, tzinfo=UTC)
FY2022_END = datetime(2022, 6, 30, tzinfo=UTC)
FY2022_AVAIL = datetime(2022, 9, 15, tzinfo=UTC)

FY2023_START = datetime(2022, 7, 1, tzinfo=UTC)
FY2023_END = datetime(2023, 6, 30, tzinfo=UTC)
FY2023_AVAIL = datetime(2023, 9, 14, tzinfo=UTC)

FY2024_START = datetime(2023, 7, 1, tzinfo=UTC)
FY2024_END = datetime(2024, 6, 30, tzinfo=UTC)
FY2024_AVAIL = datetime(2024, 9, 13, tzinfo=UTC)

# TTM EPS (genuine continuous twelve-month interval)
TTM_PERIOD_START = datetime(2024, 7, 1, tzinfo=UTC)
TTM_PERIOD_END = datetime(2025, 6, 30, tzinfo=UTC)
TTM_AVAIL = datetime(2025, 6, 30, 12, 0, tzinfo=UTC)  # available_at > period_end, <= NOW

# BVPS
BVPS_PERIOD_END = datetime(2024, 12, 31, tzinfo=UTC)
BVPS_AVAIL = datetime(2025, 2, 10, tzinfo=UTC)

# Quote
QUOTE_OBSERVED = datetime(2025, 6, 30, 16, 0, tzinfo=UTC)
QUOTE_AVAIL = datetime(2025, 6, 30, 16, 0, tzinfo=UTC)

# AAA yield
AAA_OBSERVED = datetime(2025, 6, 27, tzinfo=UTC)
AAA_AVAIL = datetime(2025, 6, 27, tzinfo=UTC)

# All happy-path retrieved_at (>= available_at per correction #1)
RETRIEVED_AT = datetime(2025, 6, 30, 17, 0, tzinfo=UTC)

# Adverse: future-published (available_at > NOW)
FUTURE_AVAIL = datetime(2025, 8, 1, tzinfo=UTC)
# retrieved_at >= available_at (temporal coherence)
FUTURE_RETRIEVED_AT = datetime(2025, 8, 1, 12, 0, tzinfo=UTC)

# ---------------------------------------------------------------------------
# Synthetic values (realistic, internally coherent)
# ---------------------------------------------------------------------------

EPS_FY2022: float = 2.10
EPS_FY2023: float = 3.40
EPS_FY2024: float = 4.20
EPS_TTM: float = 4.80
BVPS_VALUE: float = 18.50
QUOTE_VALUE: float = 52.30
AAA_YIELD_VALUE: float = 4.15

# ---------------------------------------------------------------------------
# Adverse-case subject IDs
# ---------------------------------------------------------------------------

SUBJECT_MISSING: str = "MISSING"
SUBJECT_ERROR: str = "ERROR"
SUBJECT_FUTURE: str = "FUTURE"
SUBJECT_INCOMPATIBLE: str = "INCOMPATIBLE"


# ---------------------------------------------------------------------------
# FixtureValuationProvider
# ---------------------------------------------------------------------------


class FixtureValuationProvider:
    """Deterministic fixture-backed ``ValuationFactsProvider``.

    Dispatches on ``request.subject_id`` to select scenario behavior:

    - ``SYNTH``: Happy-path synthetic data.
    - ``MISSING``: Returns empty tuple (fact unavailable).
    - ``ERROR``: Raises ``ValuationProviderError``.
    - ``FUTURE``: Returns a fact whose ``available_at`` is after ``NOW``.
    - ``INCOMPATIBLE``: Returns a fact with a mismatched basis (coherence failure).

    All data is synthetic and deterministic. No network, filesystem, or
    wall-clock dependency.
    """

    def fetch_facts(self, request: ValuationFactRequest) -> tuple[ProviderFact, ...]:
        """Return provider observations for *request*.

        Dispatches based on subject_id to select the scenario.

        Raises:
            ValuationProviderError: If subject_id is ``ERROR``.
        """
        subject = request.subject_id

        if subject == SUBJECT_MISSING:
            return ()

        if subject == SUBJECT_ERROR:
            raise ValuationProviderError("Simulated fixture provider operational failure.")

        if subject == SUBJECT_FUTURE:
            return self._future_fact(request)

        if subject == SUBJECT_INCOMPATIBLE:
            return self._incompatible_fact(request)

        # Happy path
        return self._happy_path(request)

    # ------------------------------------------------------------------
    # Happy-path data
    # ------------------------------------------------------------------

    def _happy_path(self, request: ValuationFactRequest) -> tuple[ProviderFact, ...]:
        """Return the synthetic happy-path facts for the request."""
        if request.subject_kind is ValuationSubjectKind.MACRO:
            return self._macro_facts(request)
        return self._security_facts(request)

    def _security_facts(self, request: ValuationFactRequest) -> tuple[ProviderFact, ...]:
        """Return security-subject facts."""
        if request.field_name is ValuationField.EPS:
            if request.observation_count == 3:
                return self._annual_eps_facts()
            if request.basis == "ttm":
                return (self._ttm_eps_fact(),)
            # Unsupported EPS basis: unavailable.
            return ()

        if request.field_name is ValuationField.BVPS:
            return (self._bvps_fact(),)

        if request.field_name is ValuationField.CURRENT_PRICE:
            return (self._quote_fact(),)

        # Unknown field for security subject
        return ()

    def _macro_facts(self, request: ValuationFactRequest) -> tuple[ProviderFact, ...]:
        """Return macro-subject facts."""
        if request.field_name is ValuationField.CURRENT_AAA_YIELD:
            return (self._aaa_yield_fact(),)
        return ()

    # ------------------------------------------------------------------
    # Individual fact constructors
    # ------------------------------------------------------------------

    def _annual_eps_facts(self) -> tuple[ProviderFact, ...]:
        """Three completed fiscal-year EPS observations."""
        return (
            ProviderFact(
                subject_kind=ValuationSubjectKind.SECURITY,
                subject_id=SECURITY_ID,
                field_name=ValuationField.EPS,
                value=EPS_FY2022,
                units=ValuationUnit.CURRENCY_PER_SHARE,
                provider_id=PROVIDER_ID,
                provider_field=FIELD_ANNUAL_EPS,
                retrieved_at=RETRIEVED_AT,
                basis="fiscal_year",
                currency=CURRENCY,
                observation_period_start=FY2022_START,
                observation_period_end=FY2022_END,
                available_at=FY2022_AVAIL,
                notes=("fixture: FY2022 annual EPS",),
            ),
            ProviderFact(
                subject_kind=ValuationSubjectKind.SECURITY,
                subject_id=SECURITY_ID,
                field_name=ValuationField.EPS,
                value=EPS_FY2023,
                units=ValuationUnit.CURRENCY_PER_SHARE,
                provider_id=PROVIDER_ID,
                provider_field=FIELD_ANNUAL_EPS,
                retrieved_at=RETRIEVED_AT,
                basis="fiscal_year",
                currency=CURRENCY,
                observation_period_start=FY2023_START,
                observation_period_end=FY2023_END,
                available_at=FY2023_AVAIL,
                notes=("fixture: FY2023 annual EPS",),
            ),
            ProviderFact(
                subject_kind=ValuationSubjectKind.SECURITY,
                subject_id=SECURITY_ID,
                field_name=ValuationField.EPS,
                value=EPS_FY2024,
                units=ValuationUnit.CURRENCY_PER_SHARE,
                provider_id=PROVIDER_ID,
                provider_field=FIELD_ANNUAL_EPS,
                retrieved_at=RETRIEVED_AT,
                basis="fiscal_year",
                currency=CURRENCY,
                observation_period_start=FY2024_START,
                observation_period_end=FY2024_END,
                available_at=FY2024_AVAIL,
                notes=("fixture: FY2024 annual EPS",),
            ),
        )

    def _ttm_eps_fact(self) -> ProviderFact:
        """Explicit TTM EPS observation."""
        return ProviderFact(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=SECURITY_ID,
            field_name=ValuationField.EPS,
            value=EPS_TTM,
            units=ValuationUnit.CURRENCY_PER_SHARE,
            provider_id=PROVIDER_ID,
            provider_field=FIELD_TTM_EPS,
            retrieved_at=RETRIEVED_AT,
            basis="ttm",
            currency=CURRENCY,
            observation_period_start=TTM_PERIOD_START,
            observation_period_end=TTM_PERIOD_END,
            available_at=TTM_AVAIL,
            notes=("fixture: TTM EPS",),
        )

    def _bvps_fact(self) -> ProviderFact:
        """Provider-reported BVPS."""
        return ProviderFact(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=SECURITY_ID,
            field_name=ValuationField.BVPS,
            value=BVPS_VALUE,
            units=ValuationUnit.CURRENCY_PER_SHARE,
            provider_id=PROVIDER_ID,
            provider_field=FIELD_BVPS,
            retrieved_at=RETRIEVED_AT,
            currency=CURRENCY,
            observation_period_end=BVPS_PERIOD_END,
            available_at=BVPS_AVAIL,
            notes=("fixture: book value per share",),
        )

    def _quote_fact(self) -> ProviderFact:
        """Point-in-time quote observation."""
        return ProviderFact(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=SECURITY_ID,
            field_name=ValuationField.CURRENT_PRICE,
            value=QUOTE_VALUE,
            units=ValuationUnit.CURRENCY_PER_SHARE,
            provider_id=PROVIDER_ID,
            provider_field=FIELD_QUOTE,
            retrieved_at=RETRIEVED_AT,
            currency=CURRENCY,
            observed_at=QUOTE_OBSERVED,
            available_at=QUOTE_AVAIL,
            notes=("fixture: point-in-time quote",),
        )

    def _aaa_yield_fact(self) -> ProviderFact:
        """Identified AAA corporate-yield fixture observation."""
        return ProviderFact(
            subject_kind=ValuationSubjectKind.MACRO,
            subject_id=MACRO_ID,
            field_name=ValuationField.CURRENT_AAA_YIELD,
            value=AAA_YIELD_VALUE,
            units=ValuationUnit.PERCENTAGE_POINTS,
            provider_id=PROVIDER_ID,
            provider_field=FIELD_AAA_YIELD,
            retrieved_at=RETRIEVED_AT,
            observed_at=AAA_OBSERVED,
            available_at=AAA_AVAIL,
            notes=("fixture: synthetic AAA yield series",),
        )

    # ------------------------------------------------------------------
    # Adverse-case facts
    # ------------------------------------------------------------------

    def _future_fact(self, request: ValuationFactRequest) -> tuple[ProviderFact, ...]:
        """Return a fact with available_at after NOW (temporally ineligible).

        All FUTURE facts use ``FUTURE_RETRIEVED_AT`` to ensure
        ``retrieved_at >= available_at`` (temporal coherence), even though
        the data is in the future relative to the resolver clock.
        """
        if request.subject_kind is ValuationSubjectKind.MACRO:
            return (
                ProviderFact(
                    subject_kind=ValuationSubjectKind.MACRO,
                    subject_id=SUBJECT_FUTURE,
                    field_name=ValuationField.CURRENT_AAA_YIELD,
                    value=AAA_YIELD_VALUE,
                    units=ValuationUnit.PERCENTAGE_POINTS,
                    provider_id=PROVIDER_ID,
                    provider_field=FIELD_AAA_YIELD,
                    retrieved_at=FUTURE_RETRIEVED_AT,
                    observed_at=AAA_OBSERVED,
                    available_at=FUTURE_AVAIL,
                    notes=("fixture: future-published adverse case",),
                ),
            )
        if request.field_name is ValuationField.EPS:
            return (
                ProviderFact(
                    subject_kind=ValuationSubjectKind.SECURITY,
                    subject_id=SUBJECT_FUTURE,
                    field_name=ValuationField.EPS,
                    value=EPS_TTM,
                    units=ValuationUnit.CURRENCY_PER_SHARE,
                    provider_id=PROVIDER_ID,
                    provider_field=FIELD_TTM_EPS,
                    retrieved_at=FUTURE_RETRIEVED_AT,
                    basis=request.basis if request.basis is not None else "ttm",
                    currency=CURRENCY,
                    observation_period_start=TTM_PERIOD_START,
                    observation_period_end=TTM_PERIOD_END,
                    available_at=FUTURE_AVAIL,
                    notes=("fixture: future-published adverse case",),
                ),
            )
        if request.field_name is ValuationField.BVPS:
            return (
                ProviderFact(
                    subject_kind=ValuationSubjectKind.SECURITY,
                    subject_id=SUBJECT_FUTURE,
                    field_name=ValuationField.BVPS,
                    value=BVPS_VALUE,
                    units=ValuationUnit.CURRENCY_PER_SHARE,
                    provider_id=PROVIDER_ID,
                    provider_field=FIELD_BVPS,
                    retrieved_at=FUTURE_RETRIEVED_AT,
                    currency=CURRENCY,
                    observation_period_end=BVPS_PERIOD_END,
                    available_at=FUTURE_AVAIL,
                    notes=("fixture: future-published adverse case",),
                ),
            )
        # CURRENT_PRICE and other fields
        return (
            ProviderFact(
                subject_kind=ValuationSubjectKind.SECURITY,
                subject_id=SUBJECT_FUTURE,
                field_name=request.field_name,
                value=QUOTE_VALUE,
                units=ValuationUnit.CURRENCY_PER_SHARE,
                provider_id=PROVIDER_ID,
                provider_field=FIELD_QUOTE,
                retrieved_at=FUTURE_RETRIEVED_AT,
                currency=CURRENCY,
                observed_at=QUOTE_OBSERVED,
                available_at=FUTURE_AVAIL,
                notes=("fixture: future-published adverse case",),
            ),
        )

    def _incompatible_fact(self, request: ValuationFactRequest) -> tuple[ProviderFact, ...]:
        """Return a fact with a mismatched basis (coherence failure)."""
        # Return a fact whose basis is "mismatched_basis" while the request
        # asks for a different basis (or None). This triggers the resolver's
        # coherence check to reject it as PROVIDER_ERROR.
        requested_basis = request.basis
        if requested_basis is None:
            # If no basis requested, use a non-None basis to trigger mismatch
            mismatched = "mismatched_basis"
        else:
            # If a basis was requested, ensure we return something different
            mismatched = "mismatched_basis" if requested_basis != "mismatched_basis" else "other"
        return (
            ProviderFact(
                subject_kind=ValuationSubjectKind.SECURITY,
                subject_id=SUBJECT_INCOMPATIBLE,
                field_name=ValuationField.EPS,
                value=EPS_TTM,
                units=ValuationUnit.CURRENCY_PER_SHARE,
                provider_id=PROVIDER_ID,
                provider_field=FIELD_TTM_EPS,
                retrieved_at=RETRIEVED_AT,
                basis=mismatched,
                currency=CURRENCY,
                observation_period_start=TTM_PERIOD_START,
                observation_period_end=TTM_PERIOD_END,
                available_at=TTM_AVAIL,
                notes=("fixture: semantically incompatible basis",),
            ),
        )
