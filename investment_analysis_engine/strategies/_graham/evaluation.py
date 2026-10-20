"""Fixture composition the two Graham strategies share, for the evaluation tier.

Both Graham strategies resolve company facts through one provider selection: foreign-private-issuer
evidence when the case selected it, reviewed synthetic facts when it selected those, and explicit absence
otherwise. Each strategy's own ``evaluation`` module builds its resolver and dependency class from these
helpers, so this module imports no strategy.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from investment_analysis_engine.data.financial.cache import InMemoryResolvedInputCache
from investment_analysis_engine.data.financial.facts import FinancialFactRequest, FinancialFactsProvider, ProviderFact
from investment_analysis_engine.evaluation.fixture_context import FixtureContext, FixtureRequirement, SharedKey
from investment_analysis_engine.evaluation.fixtures.graham import (
    GRAHAM_FACTS_FIXTURE_ID,
    GRAHAM_PRECEDENCE_CACHE_FIXTURE_ID,
    FixtureFinancialFactsProvider,
    precedence_bvps_cache,
)
from investment_analysis_engine.evaluation.fixtures.sec_edgar_fpi import SEC_FPI_FIXTURE_IDS

FIXTURE_IDS: Final = frozenset({GRAHAM_FACTS_FIXTURE_ID, GRAHAM_PRECEDENCE_CACHE_FIXTURE_ID})
"""The identifiers both Graham compositions understand, apart from the SEC evidence the context consumes."""

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


@dataclass(frozen=True)
class GrahamFixtureInputs:
    """The provider and precedence cache both Graham strategies read within one case.

    Attributes:
        provider: The company-facts provider the case selected, or one that reports every fact as absent.
        cache: The reviewed precedence cache when the case selected it.
    """

    provider: FinancialFactsProvider
    cache: InMemoryResolvedInputCache | None


_INPUTS_KEY: Final = SharedKey("graham_inputs", GrahamFixtureInputs)


def _build_inputs(context: FixtureContext) -> GrahamFixtureInputs:
    """Build the case's Graham inputs from the selected fixtures."""
    provider: FinancialFactsProvider
    if context.sec_fpi_provider is not None:
        provider = context.sec_fpi_provider
    elif GRAHAM_FACTS_FIXTURE_ID in context.fixture_ids:
        provider = FixtureFinancialFactsProvider(quote_retrieved_at=context.clock_at)
    else:
        provider = _UnavailableFinancialFactsProvider()
    return GrahamFixtureInputs(
        provider=provider,
        cache=precedence_bvps_cache() if GRAHAM_PRECEDENCE_CACHE_FIXTURE_ID in context.fixture_ids else None,
    )


def graham_inputs(context: FixtureContext) -> GrahamFixtureInputs:
    """Return the case's Graham inputs, the same instances for both Graham strategies."""
    return context.shared(_INPUTS_KEY, lambda: _build_inputs(context))


def graham_clock(context: FixtureContext) -> Callable[[], datetime]:
    """Return the fixed clock the Graham resolvers read."""
    clock_at = context.clock_at

    def clock() -> datetime:
        return clock_at

    return clock
