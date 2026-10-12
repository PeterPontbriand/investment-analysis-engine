"""The Graham fixture provider labelled the way the production provider router labels its answers.

The direct Graham commands accept only the providers the CLI supports, so a test that drives one through the command
line passes ``--data-provider sec_edgar`` and replaces the resolver builder. The facts the replaced resolver
returns must then carry the provider ids a production composition would give them.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from src.data.financial.facts import FinancialFactRequest, ProviderFact
from src.evaluation.fixtures.graham import NOW, FixtureFinancialFactsProvider
from src.strategies.graham_growth.calculation import GrahamGrowthInputResolver
from src.strategies.graham_number.calculation import GrahamNumberInputResolver


class SecLabeledGrahamProvider:
    """The Graham fixture provider answering the way the production provider router does.

    A saved run's selection admits only the providers the CLI supports, so the resolved facts' provider id has to
    agree with the ``sec_edgar`` value requested on the command line. The production router answers each request
    with facts labelled by that request's provider, so the security facts answer as ``sec_edgar`` and the quote,
    which the resolver requests from ``yfinance``, answers as ``yfinance``. Relabelling every fact as ``sec_edgar``
    instead would make the resolver reject the quote for a provider mismatch, a failure no production composition
    can produce.
    """

    def __init__(self) -> None:
        self._delegate = FixtureFinancialFactsProvider()

    def fetch_facts(self, request: FinancialFactRequest, *, effective_as_of: datetime) -> tuple[ProviderFact, ...]:
        """Return the fixture facts, each labelled with the provider the request names."""
        return tuple(
            replace(fact, provider_id=request.provider_id)
            for fact in self._delegate.fetch_facts(request, effective_as_of=effective_as_of)
        )


def sec_labeled_number_resolver() -> GrahamNumberInputResolver:
    """Return a Graham Number resolver over the relabelled fixture provider."""
    return GrahamNumberInputResolver(SecLabeledGrahamProvider(), clock=lambda: NOW)


def sec_labeled_growth_resolver() -> GrahamGrowthInputResolver:
    """Return a Graham Growth resolver over the relabelled fixture provider."""
    return GrahamGrowthInputResolver(SecLabeledGrahamProvider(), clock=lambda: NOW)
