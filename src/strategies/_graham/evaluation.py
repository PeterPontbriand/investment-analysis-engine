"""Fixture composition the two Graham strategies share, for the evaluation tier.

Both Graham strategies resolve company facts through one provider selection: foreign-private-issuer
evidence when the case selected it, reviewed synthetic facts when it selected those, and explicit absence
otherwise. Each strategy's own ``evaluation`` module builds its resolver and dependency class from these
helpers, so this module imports no strategy.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Final

from src.data.financial.cache import InMemoryResolvedInputCache
from src.data.financial.facts import FinancialFactRequest, FinancialFactsProvider, ProviderFact
from src.data.sec_edgar import SEC_PROVIDER_ID
from src.evaluation.fixture_context import FixtureContext, FixtureRequirement
from src.evaluation.fixture_ids import GRAHAM_FACTS_FIXTURE_ID, GRAHAM_PRECEDENCE_CACHE_FIXTURE_ID
from src.evaluation.fixtures.graham import PROVIDER_ID as GRAHAM_PROVIDER_ID
from src.evaluation.fixtures.graham import FixtureFinancialFactsProvider, precedence_bvps_cache
from src.evaluation.fixtures.sec_edgar_fpi import SEC_FPI_FIXTURE_IDS

REQUIREMENT: Final = FixtureRequirement(
    frozenset({GRAHAM_FACTS_FIXTURE_ID, *SEC_FPI_FIXTURE_IDS}),
    "Graham financial-fact",
    etf_profile_exempt=True,
)
"""Graham needs selected company facts; affirmative ETF profile evidence for the ticker stands in for them."""


class _UnavailableFinancialFactsProvider:
    """Return explicit absence when a case did not select Graham facts."""

    def fetch_facts(
        self,
        request: FinancialFactRequest,
        *,
        effective_as_of: datetime,  # noqa: ARG002
    ) -> tuple[ProviderFact, ...]:
        """Return no facts for every request without consulting another provider."""
        del request
        return ()


def graham_provider(context: FixtureContext) -> FinancialFactsProvider:
    """Return the facts provider the case selected, or one that reports every fact as absent."""
    if context.sec_fpi_provider is not None:
        return context.sec_fpi_provider
    if GRAHAM_FACTS_FIXTURE_ID in context.fixture_ids:
        return FixtureFinancialFactsProvider(quote_retrieved_at=context.clock_at)
    return _UnavailableFinancialFactsProvider()


def graham_cache(context: FixtureContext) -> InMemoryResolvedInputCache | None:
    """Return the reviewed precedence cache when the case selected it."""
    return precedence_bvps_cache() if GRAHAM_PRECEDENCE_CACHE_FIXTURE_ID in context.fixture_ids else None


def graham_provider_id(context: FixtureContext) -> str:
    """Return the provider identity a Graham strategy is configured with."""
    return SEC_PROVIDER_ID if context.sec_fpi_provider is not None else GRAHAM_PROVIDER_ID


def graham_clock(context: FixtureContext) -> Callable[[], datetime]:
    """Return the fixed clock the Graham resolvers read."""
    clock_at = context.clock_at

    def clock() -> datetime:
        return clock_at

    return clock
