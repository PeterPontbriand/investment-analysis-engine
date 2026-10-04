"""Case-level fixture context and the checks every strategy's fixture composition shares.

The context holds only what is cross-strategy: the selected fixture identifiers, the injected execution
clock and the frozen SEC foreign-private-issuer provider that any strategy reading company facts may use.
Each strategy's own selections and providers are built in its ``evaluation`` module from this context, so no
strategy-specific field lives here. This module also owns the shared error type, the fixture-capability
requirement with its ETF-profile exemption, and the exact-ticker profile resolver.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from src.data.instrument_profile import InstrumentProfile
from src.data.sec_edgar.financial_facts import SecEdgarFinancialFactsAdapter
from src.evaluation.fixture_ids import (
    FCF_GROWTH_NONMEANINGFUL_FIXTURE_ID,
    FCF_GROWTH_PERIOD_AS_OF_FIXTURE_ID,
    FCF_GROWTH_SUCCESS_FIXTURE_ID,
    GRAHAM_FACTS_FIXTURE_ID,
    GRAHAM_PRECEDENCE_CACHE_FIXTURE_ID,
    KNOWN_ETF_PROFILE_FIXTURE_ID,
    MOMENTUM_BOUNDARY_FIXTURE_ID,
    MOMENTUM_SUCCESS_FIXTURE_ID,
)
from src.evaluation.fixtures.instrument_profiles import GOLDEN_ETF_TICKER, fixture_known_etf_profile
from src.evaluation.fixtures.sec_edgar_fpi import (
    SEC_FPI_FIXTURE_IDS,
    SEC_FPI_NVO_FIXTURE_ID,
    fixture_nvo_security_unit_profile,
    fixture_sec_fpi_adapter,
)
from src.evaluation.models import Case

SUPPORTED_FIXTURE_IDS: Final = frozenset(
    {
        MOMENTUM_SUCCESS_FIXTURE_ID,
        MOMENTUM_BOUNDARY_FIXTURE_ID,
        GRAHAM_FACTS_FIXTURE_ID,
        GRAHAM_PRECEDENCE_CACHE_FIXTURE_ID,
        FCF_GROWTH_SUCCESS_FIXTURE_ID,
        FCF_GROWTH_NONMEANINGFUL_FIXTURE_ID,
        FCF_GROWTH_PERIOD_AS_OF_FIXTURE_ID,
        KNOWN_ETF_PROFILE_FIXTURE_ID,
        *SEC_FPI_FIXTURE_IDS,
    }
)


class FixtureCompositionError(ValueError):
    """Raised when a case cannot be composed from approved fixture evidence."""


@dataclass(frozen=True)
class FixtureContext:
    """The case-level selections and providers that more than one strategy can use.

    Attributes:
        fixture_ids: Every fixture identifier the case selected.
        clock_at: Fixed timezone-aware execution time for every clocked resolver.
        sec_fpi_provider: The frozen SEC adapter when the case selected foreign-private-issuer evidence.
    """

    fixture_ids: frozenset[str]
    clock_at: datetime
    sec_fpi_provider: SecEdgarFinancialFactsAdapter | None


@dataclass(frozen=True)
class FixtureRequirement:
    """The fixture capability a strategy's tool needs before it can be dispatched for a case.

    Attributes:
        required_ids: At least one of these identifiers must be selected by the case.
        label: Names the capability in the error raised when none is selected.
        etf_profile_exempt: Whether affirmative ETF profile evidence for the requested ticker satisfies the
            requirement without any of ``required_ids``.
    """

    required_ids: frozenset[str]
    label: str
    etf_profile_exempt: bool


def validate_clock(clock_at: datetime) -> None:
    """Reject an ambiguous deterministic execution clock."""
    if clock_at.tzinfo is None or clock_at.utcoffset() is None:
        raise FixtureCompositionError("Fixture composition clock must be timezone-aware.")


def selected_variant(
    fixture_ids: frozenset[str],
    candidates: frozenset[str],
    *,
    label: str,
) -> str | None:
    """Return the one selected variant of ``candidates``, rejecting ambiguous fixture evidence."""
    selected = fixture_ids & candidates
    if len(selected) > 1:
        joined = ", ".join(sorted(selected))
        raise FixtureCompositionError(f"Conflicting {label} fixture IDs: {joined}.")
    return next(iter(selected), None)


def build_fixture_context(case: Case, *, clock_at: datetime) -> FixtureContext:
    """Validate the clock and the case's fixture identifiers and build the cross-strategy context.

    Args:
        case: Typed case containing only explicitly selected fixture identifiers.
        clock_at: Fixed timezone-aware execution time for every clocked resolver.

    Returns:
        The context every strategy's fixture composition receives.

    Raises:
        FixtureCompositionError: If the clock is naive, an identifier is unsupported, or the case selects
            conflicting foreign-private-issuer evidence.
    """
    validate_clock(clock_at)
    fixture_ids = frozenset(case.fixture_ids)
    unknown_ids = fixture_ids - SUPPORTED_FIXTURE_IDS
    if unknown_ids:
        joined = ", ".join(sorted(unknown_ids))
        raise FixtureCompositionError(f"Unsupported fixture IDs: {joined}.")
    sec_fpi_fixture_id = selected_variant(fixture_ids, SEC_FPI_FIXTURE_IDS, label="SEC FPI evidence")
    sec_fpi_provider = (
        fixture_sec_fpi_adapter(sec_fpi_fixture_id, clock_at=clock_at) if sec_fpi_fixture_id is not None else None
    )
    return FixtureContext(fixture_ids=fixture_ids, clock_at=clock_at, sec_fpi_provider=sec_fpi_provider)


def profile_resolver(context: FixtureContext) -> Callable[[str], InstrumentProfile] | None:
    """Build an exact-ticker profile resolver without any provider fallback."""
    profile = (
        fixture_known_etf_profile()
        if KNOWN_ETF_PROFILE_FIXTURE_ID in context.fixture_ids
        else fixture_nvo_security_unit_profile(resolved_at=context.clock_at)
        if SEC_FPI_NVO_FIXTURE_ID in context.fixture_ids
        else None
    )
    if profile is None:
        return None

    def resolve(ticker: str) -> InstrumentProfile:
        if ticker.strip().upper() != profile.ticker:
            raise FixtureCompositionError(
                f"Profile fixture for {profile.ticker!r} cannot satisfy ticker {ticker.strip().upper()!r}."
            )
        return profile

    return resolve


def require_fixture_evidence(case: Case, requirement: FixtureRequirement, *, ticker: str) -> None:
    """Require the selected tool's fixture capability before registration.

    Args:
        case: Typed case whose selected fixtures are checked.
        requirement: The capability the requested tool needs.
        ticker: The ticker the tool is called with, which an ETF profile exemption must match exactly.

    Raises:
        FixtureCompositionError: If the case selects none of the required identifiers and no exempting ETF
            profile for ``ticker``.
    """
    fixture_ids = frozenset(case.fixture_ids)
    has_matching_etf_profile = (
        KNOWN_ETF_PROFILE_FIXTURE_ID in fixture_ids and ticker.strip().upper() == GOLDEN_ETF_TICKER
    )
    if requirement.etf_profile_exempt and has_matching_etf_profile:
        return
    if not fixture_ids & requirement.required_ids:
        raise FixtureCompositionError(f"Case {case.case_id!r} has no selected {requirement.label} fixture.")
